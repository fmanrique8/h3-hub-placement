import argparse
import json
import platform
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import numpy as np

from .aggregation import Buckets, adaptive_h3, fixed_h3, weighted_kmeans
from .fixtures import COARSE_RESOLUTION, FAMILY_SEEDS, FINE_RESOLUTION, FIXED_RESOLUTION, FIXTURE_VERSION, all_instances
from .solver import SOLVER_OPTIONS, distances, exhaustive, score_plan, solve_p_median

METHODS = ("raw", "fixed", "adaptive_spread", "kmeans", "adaptive_volume")
OUTPUT = Path("outputs/benchmark.json")
EPSILON = 1e-7


def aggregate(case, method, budget):
    points, weights = case.demand, case.weights
    if method == "raw":
        return Buckets(points, weights)
    if method == "fixed":
        return fixed_h3(points, weights)
    if method == "kmeans":
        return weighted_kmeans(points, weights, budget)
    return adaptive_h3(points, weights, budget, method.removeprefix("adaptive_"))


def evaluate_case(case, methods=METHODS):
    # The common target is part of instance preparation. Each timed method builds its own inputs.
    budget = len(fixed_h3(case.demand, case.weights).weights)
    plans = {}
    for method in methods:
        started = perf_counter()
        buckets = aggregate(case, method, budget)
        aggregated = perf_counter()
        solution = solve_p_median(distances(buckets.points, case.candidates), buckets.weights, case.k)
        solved = perf_counter()
        cost, p95 = score_plan(case.demand, case.weights, case.candidates, solution.hubs)
        finished = perf_counter()
        if buckets.weights.sum() != case.weights.sum() or (method != "raw" and len(buckets.weights) != budget):
            raise AssertionError(f"{method} did not preserve demand or bucket budget")
        plans[method] = {
            "bucket_count": len(buckets.weights),
            "bucket_spread_weight_km": buckets.spread,
            "representatives": buckets.points.tolist(),
            "weights": buckets.weights.tolist(),
            "cells": list(buckets.cells),
            "hubs": [case.names[i] for i in solution.hubs],
            "cost_weight_km": cost,
            "weighted_p95_km": p95,
            "model_cost_weight_km": solution.objective,
            "solver_status": solution.status,
            "solver_gap": solution.gap,
            "solver_dual_bound_weight_km": solution.dual_bound,
            "runtime_seconds": finished - started,
            "aggregation_seconds": aggregated - started,
            "model_and_solve_seconds": solved - aggregated,
            "scoring_seconds": finished - solved,
        }
    raw_cost = plans["raw"]["cost_weight_km"]
    raw_hubs = set(plans["raw"]["hubs"])
    for plan in plans.values():
        selected = set(plan["hubs"])
        plan["cost_delta_pct"] = 100 * (plan["cost_weight_km"] - raw_cost) / raw_cost
        plan["added_hubs"] = sorted(selected - raw_hubs)
        plan["removed_hubs"] = sorted(raw_hubs - selected)
    return {
        "family": case.family, "seed": case.seed, "k": case.k, "budget": budget,
        "candidate_names": list(case.names), "candidates": case.candidates.tolist(),
        "plans": plans,
    }


def small_verification():
    demand = np.array([[0.0, 0.0], [1.0, 0.0], [4.0, 0.0], [8.0, 0.0], [9.0, 0.0]])
    candidates = np.array([[0.0, 0.0], [2.0, 0.0], [6.0, 0.0], [9.0, 0.0]])
    weights = np.array([3, 6, 4, 2, 5])
    costs = distances(demand, candidates)
    exact_cost, exact_hubs = exhaustive(costs, weights, 2)
    fitted = solve_p_median(costs, weights, 2)
    if fitted.hubs != exact_hubs or not np.isclose(fitted.objective, exact_cost):
        raise AssertionError("Small-instance exhaustive optimum disagrees with MILP")
    return {"candidate_subsets": 6, "k": 2, "hubs_zero_based": list(exact_hubs), "objective": exact_cost, "mip_gap": fitted.gap}


def summarize(cases):
    methods = {}
    for method in METHODS:
        rows = [case["plans"][method] for case in cases]
        methods[method] = {
            "median_runtime_seconds": float(np.median([row["runtime_seconds"] for row in rows])),
            "median_cost_delta_pct": float(np.median([row["cost_delta_pct"] for row in rows])),
            "max_cost_delta_pct": max(row["cost_delta_pct"] for row in rows),
            "hubs_changed_cases": sum(bool(row["added_hubs"]) for row in rows),
            "max_solver_gap": max(row["solver_gap"] for row in rows),
        }
    paired = [case["plans"]["adaptive_spread"]["cost_weight_km"] - case["plans"]["adaptive_volume"]["cost_weight_km"] for case in cases]
    return {
        "methods": methods,
        "spread_vs_volume": {
            "wins": sum(value < -EPSILON for value in paired),
            "ties": sum(abs(value) <= EPSILON for value in paired),
            "losses": sum(value > EPSILON for value in paired),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    cases = []
    verified = small_verification()
    for i, instance in enumerate(all_instances()):
        # Rotate the method order without changing inputs or solver budgets.
        order = METHODS[i % len(METHODS):] + METHODS[:i % len(METHODS)]
        case = evaluate_case(instance, order)
        cases.append(case)
        print(f"{case['family']} seed {case['seed']}: " + ", ".join(
            f"{method} {case['plans'][method]['cost_delta_pct']:+.3f}% ({case['plans'][method]['runtime_seconds']:.3f}s)"
            for method in METHODS
        ), flush=True)
    payload = {
        "schema_version": 1, "fixture_version": FIXTURE_VERSION, "seeds": FAMILY_SEEDS,
        "environment": {"python": platform.python_version(), "os": platform.platform(), "machine": platform.machine(),
                        **{module: version(module) for module in ("h3", "numpy", "scipy", "scikit-learn", "matplotlib", "threadpoolctl")}},
        "solver_options": SOLVER_OPTIONS,
        "h3_resolutions": {"adaptive_start": COARSE_RESOLUTION, "fixed": FIXED_RESOLUTION, "max": FINE_RESOLUTION},
        "small_exhaustive_verification": verified,
        "summary": summarize(cases), "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
