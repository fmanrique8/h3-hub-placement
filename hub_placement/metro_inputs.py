import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

import numpy as np
import shapefile
from scipy.sparse import coo_array
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from .fixtures import KM_PER_DEGREE

ORIGIN_LAT, ORIGIN_LNG = 43.08, -89.41
LNG_SCALE = KM_PER_DEGREE * np.cos(np.radians(ORIGIN_LAT))
WEST, SOUTH, EAST, NORTH = -89.54, 43.00, -89.28, 43.16
ROAD_SPEEDS = {"S1100": 90, "S1200": 60, "S1400": 35, "S1630": 40, "S1640": 25}
CONNECTOR_KPH = 20
SOURCES = {
    "dane-edges.zip": (
        "https://www2.census.gov/geo/tiger/TIGER2024/EDGES/tl_2024_55025_edges.zip",
        "aff85a68f02a16867519a1af8e7311383e20c8c5449d2e391241178240afdf9f",
    ),
    "dane-blocks.json": (
        "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10/query?"
        "f=json&where=STATE%3D%2755%27%20AND%20COUNTY%3D%27025%27%20AND%20POP100%3E0&"
        "geometry=-89.54%2C43.00%2C-89.28%2C43.16&geometryType=esriGeometryEnvelope&inSR=4326&"
        "outFields=GEOID%2CINTPTLAT%2CINTPTLON%2CPOP100&returnGeometry=false&orderByFields=GEOID",
        "3ed3ed3d70e5673a351e40807726a37a0ebbb480bb4a3a639b55993e79f6219a",
    ),
}


@dataclass(frozen=True)
class Metro:
    demand: np.ndarray
    weights: np.ndarray
    block_ids: tuple[str, ...]
    graph: object
    nodes: np.ndarray
    candidates: np.ndarray
    names: tuple[str, ...]
    node_index: cKDTree
    edges: np.ndarray
    edge_count: int


def to_xy(lng, lat):
    return (lng - ORIGIN_LNG) * LNG_SCALE, (lat - ORIGIN_LAT) * KM_PER_DEGREE


def to_geographic(x, y):
    return ORIGIN_LAT + y / KM_PER_DEGREE, ORIGIN_LNG + x / LNG_SCALE


def checked_sources(path: Path, fetch: bool) -> dict:
    inputs = {}
    for name, (url, digest) in SOURCES.items():
        file = path / name
        if fetch and not file.exists():
            request = Request(url, headers={"User-Agent": "h3-hub-placement-research/0.1"})
            with urlopen(request, timeout=40) as content:
                data = content.read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"Unexpected SHA-256 for {name}. Inspect the source vintage before using it.")
            path.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        if not file.exists():
            raise FileNotFoundError(f"Missing {file}. Add --fetch to download the pinned public sources.")
        if hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Unexpected SHA-256 for {file}")
        inputs[name] = {"url": url, "sha256": digest, "bytes": file.stat().st_size}
    return inputs


def load_blocks(path: Path):
    source = json.loads(path.read_bytes())
    if source.get("exceededTransferLimit") or source.get("error"):
        raise ValueError("TIGERweb block extract is incomplete")
    blocks = []
    for feature in source["features"]:
        attributes = feature["attributes"]
        lng, lat = (float(attributes[key]) for key in ("INTPTLON", "INTPTLAT"))
        if WEST <= lng <= EAST and SOUTH <= lat <= NORTH:
            blocks.append((attributes["GEOID"], to_xy(lng, lat), int(attributes["POP100"])))
    keys, coords, weights = zip(*sorted(blocks))
    if len(set(keys)) != len(keys) or min(weights) <= 0:
        raise ValueError("Block keys must be unique with strictly positive populations")
    return tuple(keys), np.asarray(coords), np.asarray(weights)


def load_roads(path: Path, speeds=ROAD_SPEEDS):
    positions = {}
    links = {}
    with ZipFile(path) as archive:
        prefix = "tl_2024_55025_edges"
        with shapefile.Reader(shp=io.BytesIO(archive.read(f"{prefix}.shp")),
                              dbf=io.BytesIO(archive.read(f"{prefix}.dbf"))) as entries:
            for item in entries.iterShapeRecords(fields=["MTFCC", "TNIDF", "TNIDT"]):
                road = item.record
                if road.MTFCC not in speeds:
                    continue
                if len(item.shape.parts) != 1:
                    raise ValueError("A selected TIGER edge has multiple geometry parts")
                graph_ids = road.TNIDF, road.TNIDT
                if not all(graph_ids) or graph_ids[0] == graph_ids[1]:
                    continue
                lng, lat = np.array(item.shape.points).T
                xy = np.column_stack(to_xy(lng, lat))
                distance = np.linalg.norm(np.diff(xy, axis=0), axis=1).sum()
                if distance <= 0:
                    continue
                for node, position in zip(graph_ids, (xy[0], xy[-1]), strict=True):
                    old = positions.setdefault(node, position)
                    if not np.allclose(old, position, rtol=0, atol=0.0003):
                        raise ValueError(f"Inconsistent TIGER node geometry for {node}")
                pair = tuple(sorted(graph_ids))
                minutes = float(distance * 60 / speeds[road.MTFCC])
                links[pair] = min(links.get(pair, np.inf), minutes)
    order = sorted(positions)
    indices = {key: i for i, key in enumerate(order)}
    edges = np.array([(indices[a], indices[b]) for a, b in links], dtype=np.int32)
    times = np.array(list(links.values()))
    graph = coo_array((np.r_[times, times], (np.r_[edges[:, 0], edges[:, 1]], np.r_[edges[:, 1], edges[:, 0]])),
                      shape=(len(order), len(order))).tocsr()
    _, groups = connected_components(graph, directed=False)
    keep = groups == np.bincount(groups).argmax()
    idx = np.flatnonzero(keep)
    connected = graph[idx][:, idx]
    return connected, np.array([positions[key] for key in order])[keep]


def load_metro(path: Path, *, grid_size=5, shift=(0, 0), speeds=ROAD_SPEEDS) -> Metro:
    keys, points, weights = load_blocks(path / "dane-blocks.json")
    graph, nodes = load_roads(path / "dane-edges.zip", speeds)
    node_index = cKDTree(nodes)
    anchors = np.array([to_xy(lng, lat) for lat in np.linspace(SOUTH + 0.016, NORTH - 0.016, grid_size)
                        for lng in np.linspace(WEST + 0.026, EAST - 0.026, grid_size)]) + shift
    offsets, nearest = node_index.query(anchors)
    candidates = {}
    for i, (index, offset) in enumerate(zip(nearest, offsets, strict=True), start=1):
        if offset <= 0.9:
            candidates.setdefault(int(index), f"M{i:02}")
    if len(candidates) < 3:
        raise ValueError("Fewer than three eligible candidate nodes")
    road_edges = np.column_stack(graph.nonzero())
    road_edges = road_edges[road_edges[:, 0] < road_edges[:, 1]]
    return Metro(points, weights, keys, graph, nodes, np.array(list(candidates)), tuple(candidates.values()),
                 node_index, road_edges, len(road_edges))
