"""Time two exact implementations and fixed H3 on the pinned dense road case."""

import argparse
import json
import math
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from statistics import median
from time import perf_counter

import h3
import numpy as np
from scipy.sparse.csgraph import dijkstra
from threadpoolctl import threadpool_info, threadpool_limits

from .metro import K, evaluate, method_buckets, travel_times
from .metro_inputs import CONNECTOR_KPH, ROAD_SPEEDS, checked_sources, load_metro
from .robustness import SCENARIOS, independent_triples
from .solver import SOLVER_OPTIONS, exhaustive, solve_p_median, weighted_p95

RESOLUTION = 7
METHODS = ("fixed_h3", "simple_exact", "vectorized_exact")


def benchmark(data, fetch, cpu):
    sources = checked_sources(data, fetch)
    start = perf_counter()
    metro = load_metro(data, **SCENARIOS["denser"])
    ingestion = perf_counter() - start
    budget = len(method_buckets(metro, RESOLUTION, 0, "fixed").weights)
    solve_p_median(np.array([[1., 2.], [2., 1.]]), np.array([1, 2]), 1)
    trials = []
    for rotation in range(len(METHODS)):
        start = perf_counter()
        network = dijkstra(metro.graph, directed=False, indices=metro.candidates)
        graph_routing = perf_counter() - start
        start = perf_counter()
        original = travel_times(metro, network, metro.demand)
        point_lookup = perf_counter() - start
        routing = graph_routing + point_lookup
        order = METHODS[rotation:] + METHODS[:rotation]
        runs = {}
        for method in order:
            if method == "fixed_h3":
                row = evaluate(metro, network, original, routing, RESOLUTION, budget, "fixed")
            else:
                start = perf_counter()
                if method == "simple_exact":
                    search_cost, hubs = exhaustive(original, metro.weights, K)
                else:
                    search_cost, hubs = independent_triples(original, metro.weights)
                service = original[:, hubs].min(axis=1)
                cost = float(metro.weights @ service)
                p95 = weighted_p95(service, metro.weights)
                seconds = perf_counter() - start
                if not math.isclose(search_cost, cost, rel_tol=1e-12):
                    raise ValueError(f"{method} search and point-level rescore disagree")
                row = {
                    "hubs": [metro.names[i] for i in hubs],
                    "cost_resident_minutes": cost, "p95_minutes": p95,
                    "solver_gap": 0.0, "method_seconds": seconds,
                    "routing_inclusive_seconds": routing + seconds,
                }
            runs[method] = row
        ref = runs["simple_exact"]
        for method, row in runs.items():
            difference = row["cost_resident_minutes"] - ref["cost_resident_minutes"]
            equivalent = math.isclose(row["cost_resident_minutes"], ref["cost_resident_minutes"], rel_tol=1e-12)
            if (method.endswith("_exact") and not equivalent) or (difference < 0 and not equivalent):
                raise ValueError(f"{method} disagrees with the exact objective")
            row["cost_excess_pct"] = 100 * difference / ref["cost_resident_minutes"]
            row["same_objective_as_exact"] = equivalent
            row["same_hubs_as_exact"] = row["hubs"] == ref["hubs"]
        trials.append({"order": order, "graph_routing_seconds": graph_routing,
                       "original_point_lookup_seconds": point_lookup, "methods": runs})
        print(f"Repeat {rotation + 1} " + " | ".join(
            f"{name} {runs[name]['routing_inclusive_seconds']:.3f}s" for name in order
        ), flush=True)

    return {
        "study": "madison-denser-exact-baselines-v1", "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "platform": platform.platform(), "machine": platform.machine(), "cpu": cpu,
            "python": platform.python_version(), "h3_core": h3.versions()["c"],
            "packages": {package: version(package) for package in ("h3", "numpy", "scipy", "pyshp", "threadpoolctl")},
            "threadpools": [{key: pool[key] for key in ("internal_api", "version", "num_threads")}
                            for pool in threadpool_info()],
        },
        "sources": sources, "grid_size": SCENARIOS["denser"]["grid_size"], "k": K,
        "candidates": len(metro.names), "blocks": len(metro.demand), "population": metro.weights.sum().item(),
        "candidate_triples": math.comb(len(metro.names), K),
        "road_speeds_kph": ROAD_SPEEDS, "connector_speed_kph": CONNECTOR_KPH,
        "fixed_h3_resolution": RESOLUTION, "fixed_h3_buckets": budget, "solver_options": SOLVER_OPTIONS,
        "ingestion_seconds_excluded": ingestion, "repeats": trials,
        "medians": {
            method: {metric: median(trial["methods"][method][metric] for trial in trials)
                     for metric in ("method_seconds", "routing_inclusive_seconds")}
            for method in METHODS
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/metro"))
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--cpu", default=platform.processor() or platform.machine(), help="CPU model for the run record")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with threadpool_limits(limits=1, user_api="blas"):
        result = benchmark(args.data, args.fetch, args.cpu)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
