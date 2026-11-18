import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from time import perf_counter

import numpy as np
from scipy.sparse.csgraph import dijkstra

from .aggregation import Buckets, adaptive_h3, fixed_h3, weighted_kmeans
from .metro_inputs import CONNECTOR_KPH, ROAD_SPEEDS, checked_sources, load_metro, to_geographic
from .solver import SOLVER_OPTIONS, exhaustive, solve_p_median, weighted_p95

RESOLUTIONS = (6, 7)
METHODS = ("fixed", "adaptive_spread", "kmeans", "adaptive_volume")
REPEATS = 3
K = 3


def method_buckets(metro, resolution, budget, method):
    points, weights = metro.demand, metro.weights
    if method == "raw":
        return Buckets(points, weights)
    if method == "fixed":
        return fixed_h3(points, weights, resolution=resolution, to_geographic=to_geographic)
    if method == "kmeans":
        return weighted_kmeans(points, weights, budget)
    return adaptive_h3(points, weights, budget, method.removeprefix("adaptive_"), to_geographic=to_geographic)


def travel_times(metro, network_minutes, coordinates):
    offset, nearest = metro.node_index.query(coordinates)
    return network_minutes[:, nearest].T + (offset * 60 / CONNECTOR_KPH)[:, None]


def evaluate(metro, network_minutes, original, routing_seconds, resolution, budget, method):
    start = perf_counter()
    bucket = method_buckets(metro, resolution, budget, method)
    if (not np.isclose(bucket.weights.sum(), metro.weights.sum(), rtol=1e-12, atol=0)
            or len(bucket.weights) != budget):
        raise ValueError("Demand or bucket budget changed")
    model = original if method == "raw" else travel_times(metro, network_minutes, bucket.points)
    plan = solve_p_median(model, bucket.weights, K)
    service = original[:, plan.hubs].min(axis=1)
    cost = float(metro.weights @ service)
    tail = weighted_p95(service, metro.weights)
    seconds = perf_counter() - start
    return {
        "hubs": [metro.names[i] for i in plan.hubs], "cost_resident_minutes": cost,
        "mean_minutes": cost / float(metro.weights.sum()), "p95_minutes": tail,
        "solver_gap": plan.gap, "solver_status": plan.status, "model_dual_bound": plan.dual_bound,
        "method_seconds": seconds, "routing_inclusive_seconds": routing_seconds + seconds,
    }


def summarize(rows, reference, *, allow_unstable=False):
    best = min(rows, key=lambda row: (row["cost_resident_minutes"], row["solver_gap"], row["hubs"]))
    selection = best["hubs"]
    stable = all(selection == row["hubs"] for row in rows)
    if not stable and not allow_unstable:
        raise RuntimeError("Solver did not repeat the same plan; inspect the time-capped runs")
    cost = best["cost_resident_minutes"]
    tail = best["p95_minutes"]
    raw_cost_bound = max(reference["model_dual_bound"], 0.0)
    return {
        "hubs": selection, "hubs_stable": stable, "added": sorted(set(selection) - set(reference["hubs"])),
        "removed": sorted(set(reference["hubs"]) - set(selection)),
        "cost_resident_minutes": cost, "mean_minutes": best["mean_minutes"], "p95_minutes": tail,
        "cost_excess_pct": 100 * (cost / reference["cost_resident_minutes"] - 1),
        "cost_bound_excess_pct": 100 * (cost / raw_cost_bound - 1) if raw_cost_bound else None,
        "p95_delta_pct": 100 * (tail / reference["p95_minutes"] - 1),
        "max_solver_gap": max(row["solver_gap"] for row in rows),
        "method_seconds_median": median(row["method_seconds"] for row in rows),
        "routing_inclusive_seconds_median": median(row["routing_inclusive_seconds"] for row in rows),
        "runs": rows,
    }


def compare_gate(methods, raw):
    adaptive = methods["adaptive_spread"]
    checks = {
        "twice_as_fast_as_raw": adaptive["routing_inclusive_seconds_median"] <= raw["routing_inclusive_seconds_median"] / 2,
        "within_one_percent_of_raw_cost": adaptive["cost_bound_excess_pct"] is not None and adaptive["cost_bound_excess_pct"] <= 1.0,
        "within_five_percent_of_raw_p95": adaptive["p95_delta_pct"] <= 5.0,
    }
    for simpler in ("fixed", "kmeans"):
        baseline = methods[simpler]
        cost_gain = baseline["cost_excess_pct"] - adaptive["cost_excess_pct"]
        faster = adaptive["routing_inclusive_seconds_median"] <= 0.9 * baseline["routing_inclusive_seconds_median"]
        acceptable = (adaptive["cost_resident_minutes"] <= 1.01 * baseline["cost_resident_minutes"] and
                      adaptive["p95_minutes"] <= 1.05 * baseline["p95_minutes"])
        checks[f"advantage_over_{simpler}"] = cost_gain >= 0.5 or (faster and acceptable)
    return checks | {"continue": all(checks.values())}


def main():
    parser = argparse.ArgumentParser(description="Compare matched aggregation methods on a pinned Madison road model.")
    parser.add_argument("--data", type=Path, default=Path("data/metro"))
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("outputs/metro.json"))
    args = parser.parse_args()
    sources = checked_sources(args.data, args.fetch)
    start = perf_counter()
    metro = load_metro(args.data)
    ingestion = perf_counter() - start
    budgets = {res: len(fixed_h3(metro.demand, metro.weights, resolution=res,
                                 to_geographic=to_geographic).weights) for res in RESOLUTIONS}
    print(f"{len(metro.demand)} blocks; population {metro.weights.sum()}; {len(metro.names)} candidates; budgets {budgets}", flush=True)
    measurements = defaultdict(list)
    durations = []
    tasks = [(None, "raw")] + [(res, method) for res in RESOLUTIONS for method in METHODS]
    # Warm the common solver with the tiny independent problem before measuring it.
    solve_p_median(np.array([[1.0, 2.0], [2.0, 1.0]]), np.array([1, 2]), 1)
    for repeat in range(REPEATS):
        begin = perf_counter()
        network = dijkstra(metro.graph, directed=False, indices=metro.candidates)
        original = travel_times(metro, network, metro.demand)
        routing_seconds = perf_counter() - begin
        durations.append(routing_seconds)
        for res, method in tasks[repeat:] + tasks[:repeat]:
            plan = evaluate(metro, network, original, routing_seconds, res,
                            budgets[res] if res else len(metro.demand), method)
            measurements[res, method].append(plan)
            print(f"repeat {repeat + 1} {str(res):>4} {method:<16} {','.join(plan['hubs'])} "
                  f"cost {plan['mean_minutes']:.5f} min, gap {plan['solver_gap']:.6g}, "
                  f"{plan['method_seconds']:.3f} s", flush=True)
    begin = perf_counter()
    exact_cost, exact_hubs = exhaustive(original, metro.weights, K)
    enum_seconds = perf_counter() - begin
    raw_rows = measurements[None, "raw"]
    for row in raw_rows:
        if row["model_dual_bound"] > exact_cost + 1e-5 or (row["solver_gap"] == 0 and
                not math.isclose(exact_cost, row["cost_resident_minutes"], abs_tol=1e-6)):
            raise ValueError("Exhaustive raw optimum disagrees with the MILP report")
    reference = {
        "triples": math.comb(len(metro.names), K), "cost_resident_minutes": exact_cost,
        "model_dual_bound": exact_cost, "hubs": [metro.names[i] for i in exact_hubs],
        "p95_minutes": weighted_p95(original[:, exact_hubs].min(axis=1), metro.weights),
        "mean_minutes": exact_cost / float(metro.weights.sum()), "enumeration_seconds": enum_seconds,
        "routing_inclusive_seconds": enum_seconds + median(durations),
    }
    raw = summarize(raw_rows, reference, allow_unstable=True)
    results = []
    for res in RESOLUTIONS:
        plans = {method: summarize(measurements[res, method], reference) for method in METHODS}
        results.append({"resolution": res, "bucket_count": budgets[res], "methods": plans,
                        "decision": compare_gate(plans, raw), "decision_vs_exact_raw": compare_gate(
                            plans, {"routing_inclusive_seconds_median": reference["routing_inclusive_seconds"]})})
    payload = {
        "schema_version": 1, "study": "madison-dane-v1", "k": K, "sources": sources,
        "solver_options": SOLVER_OPTIONS, "repeat_count": REPEATS,
        "block_count": len(metro.demand), "population": int(metro.weights.sum()),
        "node_count": len(metro.nodes), "edge_count": metro.edge_count,
        "road_speeds_kph": ROAD_SPEEDS, "connector_speed_kph": CONNECTOR_KPH,
        "ingestion_seconds": ingestion, "candidate_routing_seconds": durations,
        "candidates": {name: metro.nodes[i].tolist() for name, i in zip(metro.names, metro.candidates, strict=True)},
        "raw": raw, "exhaustive": reference,
        "budgets": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
