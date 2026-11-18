from dataclasses import dataclass
from functools import lru_cache

import h3
import numpy as np
from numpy.typing import NDArray
from sklearn.cluster import KMeans
from threadpoolctl import threadpool_limits

from .fixtures import COARSE_RESOLUTION, FINE_RESOLUTION, FIXED_RESOLUTION, to_lat_lng


@dataclass(frozen=True)
class Buckets:
    points: NDArray
    weights: NDArray
    cells: tuple[str, ...] = ()
    spread: float = 0.0


def index_leaves(points: NDArray, to_geographic=to_lat_lng) -> list[str]:
    return [h3.latlng_to_cell(*to_geographic(x, y), FINE_RESOLUTION) for x, y in points]


def group_cells(leaves: list[str], resolution: int) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for i, leaf in enumerate(leaves):
        cell = h3.cell_to_parent(leaf, resolution)
        groups.setdefault(cell, []).append(i)
    return groups


def summarize_group(points, weights, members):
    coordinates = points[members]
    weighted = weights[members]
    center = np.average(coordinates, weights=weighted, axis=0)
    spread = weighted @ np.linalg.norm(coordinates - center, axis=1)
    return center, weighted.sum().item(), float(spread)


def summarize(points, weights, labels, groups) -> Buckets:
    centroids, volumes, spreads = zip(*(summarize_group(points, weights, members) for members in groups))
    return Buckets(np.array(centroids), np.array(volumes), tuple(labels), sum(spreads))


def fixed_h3(points: NDArray, weights: NDArray, *, resolution=FIXED_RESOLUTION, to_geographic=to_lat_lng) -> Buckets:
    groups = group_cells(index_leaves(points, to_geographic), resolution)
    cells = sorted(groups)
    return summarize(points, weights, cells, [groups[cell] for cell in cells])


def adaptive_h3(points: NDArray, weights: NDArray, budget: int, priority: str, *, to_geographic=to_lat_lng) -> Buckets:
    if priority not in {"spread", "volume"}:
        raise ValueError("priority must be spread or volume")
    leaves = index_leaves(points, to_geographic)
    levels = {
        level: group_cells(leaves, level)
        for level in range(COARSE_RESOLUTION, FINE_RESOLUTION + 1)
    }
    members = {cell: group for cells in levels.values() for cell, group in cells.items()}
    children: dict[str, list[str]] = {}
    for level in range(COARSE_RESOLUTION + 1, FINE_RESOLUTION + 1):
        for cell in sorted(levels[level]):
            children.setdefault(h3.cell_to_parent(cell, level - 1), []).append(cell)

    def expand_unary(cell):
        while len(children.get(cell, ())) == 1:
            cell = children[cell][0]
        return cell

    def options(cell):
        return tuple(expand_unary(child) for child in children.get(cell, ()))

    def counts_for(frontier):
        counts = {0}
        for cell in frontier:
            counts = {x + y for x in counts for y in achievable(cell) if x + y <= budget}
        return counts

    @lru_cache(maxsize=None)
    def achievable(cell):
        branches = options(cell)
        return {1} | counts_for(branches) if branches else {1}

    @lru_cache(maxsize=None)
    def score(cell):
        _, volume, spread = summarize_group(points, weights, members[cell])
        return spread if priority == "spread" else volume

    frontier = sorted(expand_unary(cell) for cell in levels[COARSE_RESOLUTION])
    if budget not in counts_for(frontier):
        raise ValueError(f"No occupied H3 partition with exactly {budget} cells")
    while len(frontier) < budget:
        for cell in sorted(frontier, key=lambda leaf: (-score(leaf), leaf)):
            branches = options(cell)
            if branches and len(frontier) - 1 + len(branches) <= budget:
                proposed = [leaf for leaf in frontier if leaf != cell] + list(branches)
                if budget in counts_for(proposed):
                    frontier = proposed
                    break
        else:
            raise RuntimeError("Refinement could not reach its verified bucket budget")

    cells = sorted(frontier)
    return summarize(points, weights, cells, [members[cell] for cell in cells])


def weighted_kmeans(points: NDArray, weights: NDArray, budget: int) -> Buckets:
    with threadpool_limits(limits=1):
        model = KMeans(n_clusters=budget, n_init=10, random_state=0, algorithm="lloyd")
        labels = model.fit_predict(points, sample_weight=weights.astype(float))
    groups = [np.flatnonzero(labels == i) for i in range(budget)]
    if any(len(group) == 0 for group in groups):
        raise RuntimeError("K-means did not fill the bucket budget")
    return summarize(points, weights, (), groups)
