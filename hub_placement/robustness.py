import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from time import perf_counter

import math
import numpy as np
from scipy.sparse.csgraph import dijkstra

from .metro import K, METHODS, REPEATS, RESOLUTIONS, compare_gate, evaluate, method_buckets, summarize, travel_times
from .metro_inputs import ROAD_SPEEDS, checked_sources, load_metro
from .solver import SOLVER_OPTIONS, exhaustive, solve_p_median, weighted_p95

SCENARIOS = {
    "original": {},
    "shifted": {"shift": (1, -1)},
    "slower_highways": {"speeds": ROAD_SPEEDS | {"S1100": 67.5, "S1200": 45}},
    "denser": {"grid_size": 9},
}


def independent_triples(costs, weights):
    """Check the small reference with pairwise minima and vectorized third-site scores."""
    best = (np.inf, ())
    for first in range(costs.shape[1] - 2):
        for second in range(first + 1, costs.shape[1] - 1):
            pair = np.minimum(costs[:, first], costs[:, second])
            totals = (np.minimum(pair[:, None], costs[:, second + 1:]) * weights[:, None]).sum(axis=0)
            index = int(totals.argmin())
            best = min(best, (float(totals[index]), (first, second, second + 1 + index)))
    return best


def scenario_run(path, name, options):
    metro = load_metro(path, **options)
    budgets = {res: len(method_buckets(metro, res, 0, "fixed").weights) for res in RESOLUTIONS}
    plans = defaultdict(list)
    routing_times = []
    exact_runs = []
    tasks = [(r, m) for r in RESOLUTIONS for m in METHODS]
    print(f"{name}: {len(metro.names)} candidates, {math.comb(len(metro.names), K):,} triples", flush=True)
    for repeat in range(REPEATS):
        begin = perf_counter()
        network = dijkstra(metro.graph, directed=False, indices=metro.candidates)
        original = travel_times(metro, network, metro.demand)
        routing = perf_counter() - begin
        routing_times.append(routing)
        for res, method in tasks[repeat:] + tasks[:repeat]:
            plans[res, method].append(evaluate(metro, network, original, routing, res, budgets[res], method))
        begin = perf_counter()
        cost, hubs = exhaustive(original, metro.weights, K)
        enumeration = perf_counter() - begin
        exact_runs.append({
            "cost_resident_minutes": cost, "model_dual_bound": cost,
            "hubs": [metro.names[i] for i in hubs],
            "p95_minutes": weighted_p95(original[:, hubs].min(axis=1), metro.weights),
            "enumeration_seconds": enumeration, "routing_inclusive_seconds": routing + enumeration,
        })
        print(f"  repeat {repeat + 1}: exact {routing + enumeration:.3f} s", flush=True)
    reference = exact_runs[0] | {
        "routing_inclusive_seconds_median": median(row["routing_inclusive_seconds"] for row in exact_runs),
        "enumeration_seconds_median": median(row["enumeration_seconds"] for row in exact_runs),
    }
    independent_check = None
    if name == "original":
        second_cost, second_hubs = independent_triples(original, metro.weights)
        if hubs != second_hubs or not math.isclose(cost, second_cost, rel_tol=1e-12):
            raise ValueError("Independent vectorized exact check disagrees")
        independent_check = {"hubs": reference["hubs"], "cost_resident_minutes": second_cost}
    rows = []
    for res in RESOLUTIONS:
        methods = {method: summarize(plans[res, method], reference) for method in METHODS}
        if any(method["cost_excess_pct"] < -1e-7 for method in methods.values()):
            raise ValueError("An approximate plan supposedly beat the exact optimum")
        rows.append({"resolution": res, "bucket_count": budgets[res], "methods": methods,
                     "decision": compare_gate(methods, reference)})
    return {"scenario": name, "settings": options, "candidates": len(metro.names),
            "triples": math.comb(len(metro.names), K), "block_count": len(metro.demand),
            "routing_seconds": routing_times, "exact": reference, "exact_runs": exact_runs,
            "independent_check": independent_check, "budgets": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/metro"))
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("outputs/robustness.json"))
    args = parser.parse_args()
    sources = checked_sources(args.data, args.fetch)
    solve_p_median(np.array([[1., 2.], [2., 1.]]), np.array([1, 2]), 1)
    results = [scenario_run(args.data, name, options) for name, options in SCENARIOS.items()]
    recorded = json.loads(Path("outputs/metro.json").read_bytes())["exhaustive"]
    reference = results[0]["exact"]
    if reference["hubs"] != recorded["hubs"] or not math.isclose(reference["cost_resident_minutes"],
                                                                  recorded["cost_resident_minutes"], rel_tol=1e-12):
        raise ValueError("Original scenario no longer reproduces the recorded Madison result")
    data = {"schema_version": 1, "sources": sources, "solver_options": SOLVER_OPTIONS,
            "repeats": REPEATS, "k": K, "scenarios": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
