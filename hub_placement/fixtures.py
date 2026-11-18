from dataclasses import dataclass

import h3
import numpy as np
from numpy.typing import NDArray
from scipy.spatial.distance import cdist

ORIGIN_LAT, ORIGIN_LNG = 4.65, -74.08
KM_PER_DEGREE = np.pi * 6371.0088 / 180
LNG_SCALE = KM_PER_DEGREE * np.cos(np.radians(ORIGIN_LAT))
FAMILY_SEEDS = {"regional": (271, 379, 487, 659), "split-cell": (271, 379, 487)}
COARSE_RESOLUTION, FIXED_RESOLUTION, FINE_RESOLUTION = 5, 6, 8
FIXTURE_VERSION = "synthetic-v1"


@dataclass(frozen=True)
class Instance:
    family: str
    seed: int
    demand: NDArray
    weights: NDArray
    candidates: NDArray
    names: tuple[str, ...]
    k: int


def to_lat_lng(x, y):
    return ORIGIN_LAT + y / KM_PER_DEGREE, ORIGIN_LNG + x / LNG_SCALE


def to_xy(lat, lng):
    return ((lng - ORIGIN_LNG) * LNG_SCALE, (lat - ORIGIN_LAT) * KM_PER_DEGREE)


def regional(seed: int) -> Instance:
    rng = np.random.default_rng(seed)
    centers = np.array([[-13, -9], [-9, 8], [3, 4], [10, -10], [14, 10]])
    centers = centers + rng.normal(0, 1.5, centers.shape)
    clusters = [rng.normal(center, [2.6, 2.0], (42, 2)) for center in centers]
    weights = [rng.integers(1, 9 + index * 3, 42) for index in range(len(centers))]
    background = rng.uniform([-20, -16], [20, 16], (32, 2))
    candidates = np.array([(x, y) for y in (-13, -6, 1, 8, 15) for x in (-17, -9, -1, 7, 15)])
    return Instance(
        "regional", seed, np.vstack([*clusters, background]),
        np.concatenate([*weights, rng.integers(1, 5, 32)]),
        candidates, tuple(f"H{i + 1:02}" for i in range(len(candidates))), 3,
    )


def split_cell(seed: int) -> Instance:
    """Place two unequal lobes inside one fixed bucket and offer a midpoint site."""
    rng = np.random.default_rng(seed)
    anchor = h3.cell_to_parent(h3.latlng_to_cell(ORIGIN_LAT, ORIGIN_LNG, FINE_RESOLUTION), FIXED_RESOLUTION)
    children = sorted(h3.cell_to_children(anchor, FINE_RESOLUTION))
    centers = np.array([to_xy(*h3.cell_to_latlng(child)) for child in children])
    distances = cdist(centers, centers)
    # Pick the widest pair; the sign of the x coordinates fixes the displayed labels.
    first, second = np.unravel_index(np.argmax(distances), distances.shape)
    west, east = sorted((centers[first], centers[second]), key=lambda point: point[0])
    lobe_weights = [rng.integers(6, 10, 42), rng.integers(2, 5, 42)]
    lobe_centers = (west, east)
    lobes = [rng.normal(point, 0.075, (42, 2)) for point in lobe_centers]
    # Keep the intentional fixture within the chosen logical H3 cell.
    for points, center in zip(lobes, lobe_centers, strict=True):
        for i, point in enumerate(points):
            finest = h3.latlng_to_cell(*to_lat_lng(*point), FINE_RESOLUTION)
            if h3.cell_to_parent(finest, FIXED_RESOLUTION) != anchor:
                points[i] = center
    midpoint = 0.71 * west + 0.29 * east
    north = np.array([-12.5, 11.0])
    south = np.array([13.0, -11.5])
    outer = [rng.normal(center, [0.8, 0.52], (45, 2)) for center in (north, south)]
    weights = [rng.integers(10, 17, len(points)) for points in outer]
    background = rng.uniform([-17, -15], [17, 15], (29, 2))
    # Low-volume isolated demand sets the fixed-budget occupied-cell count.
    candidates = np.array([west, midpoint, east, north, south, [-12, -11], [12, 10], [-5, -3], [6, 6], [0, 10]])
    return Instance(
        "split-cell", seed, np.vstack([*lobes, *outer, background]),
        np.concatenate([*lobe_weights, *weights, rng.integers(1, 3, len(background))]),
        candidates, ("West", "Middle", "East", "North", "South", "H06", "H07", "H08", "H09", "H10"), 3,
    )


def all_instances():
    generators = {"regional": regional, "split-cell": split_cell}
    for family, seeds in FAMILY_SEEDS.items():
        for seed in seeds:
            yield generators[family](seed)
