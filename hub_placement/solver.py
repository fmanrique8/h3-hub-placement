import warnings
from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array
from scipy.spatial.distance import cdist

SOLVER_OPTIONS = {"time_limit": 20.0, "mip_rel_gap": 1e-6, "threads": 1, "random_seed": 0, "presolve": True}


@dataclass(frozen=True)
class Solution:
    hubs: tuple[int, ...]
    objective: float
    status: int
    gap: float
    dual_bound: float


def distances(points, candidates):
    return cdist(points, candidates, metric="euclidean")


def solve_p_median(costs, weights, k: int) -> Solution:
    """Binary open-site variables and continuous assignments to open sites."""
    n, m = costs.shape
    if not 1 <= k <= m or n == 0:
        raise ValueError("choose k in [1, number of candidates] and supply demand")
    assignment = np.arange(m, m + n * m)
    site = np.arange(m)
    link_rows = np.arange(n + 1, n + 1 + n * m)
    rows = np.r_[np.zeros(m, dtype=int), np.repeat(np.arange(1, n + 1), m), link_rows, link_rows]
    cols = np.r_[site, assignment, assignment, np.tile(site, n)]
    coefficients = np.r_[np.ones(m + 2 * n * m), -np.ones(n * m)]
    matrix = coo_array((coefficients, (rows, cols)), shape=(1 + n + n * m, m + n * m)).tocsc()
    lower = np.r_[k, np.ones(n), np.full(n * m, -np.inf)]
    upper = np.r_[k, np.ones(n), np.zeros(n * m)]
    objective = np.r_[np.zeros(m), (costs * weights[:, None]).ravel()]
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Unrecognized options detected:.*passed to HiGHS", category=RuntimeWarning)
        result = milp(
            objective, integrality=np.r_[np.ones(m), np.zeros(n * m)],
            bounds=Bounds(0.0, 1.0), constraints=LinearConstraint(matrix, lower, upper),
            options=SOLVER_OPTIONS.copy(),
        )
    if result.x is None or result.status not in {0, 1}:
        raise RuntimeError(f"No usable p-median solution ({result.status}): {result.message}")
    hubs = tuple(np.flatnonzero(result.x[:m] > 0.5).tolist())
    if len(hubs) != k or not np.isclose(result.fun, weights @ costs[:, hubs].min(axis=1)):
        raise RuntimeError("Solver incumbent failed the open-site or objective check")
    return Solution(hubs, float(result.fun), int(result.status), float(result.mip_gap), float(result.mip_dual_bound))


def exhaustive(costs, weights, k):
    return min((float(weights @ costs[:, hubs].min(axis=1)), hubs) for hubs in combinations(range(costs.shape[1]), k))


def weighted_p95(values, weights):
    order = np.argsort(values, kind="stable")
    index = np.searchsorted(np.cumsum(weights[order]), 0.95 * weights.sum(), side="left")
    return float(values[order[index]])


def score_plan(demand, weights, candidates, hubs):
    service = distances(demand, candidates[list(hubs)]).min(axis=1)
    return float(weights @ service), weighted_p95(service, weights)
