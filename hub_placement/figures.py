import argparse
import csv
import hashlib
import json
from pathlib import Path
from shutil import copyfile

import h3
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from .benchmark import METHODS, OUTPUT
from .fixtures import to_xy

METHOD_STYLE = {
    "raw": ("Raw demand", "#20242b", "o"),
    "fixed": ("Fixed H3", "#a24f36", "s"),
    "adaptive_spread": ("Adaptive H3 · spread", "#17695f", "D"),
    "kmeans": ("Weighted k-means", "#684a86", "^"),
    "adaptive_volume": ("Adaptive H3 · volume", "#5b6d83", "x"),
}
PAPER = "#fbfaf7"
INK = "#20242b"
LINE = "#deddd8"


def chart(cases, highlighted, path):
    fig, ax = plt.subplots(figsize=(7.0, 4.8), layout="constrained")
    for method in METHODS:
        label, color, shape = METHOD_STYLE[method]
        values = [case["plans"][method] for case in cases]
        ax.scatter([plan["runtime_seconds"] for plan in values], [plan["cost_delta_pct"] for plan in values],
                   s=53, marker=shape, color=color, alpha=0.73, label=label, zorder=3)
    selected = highlighted["plans"]["fixed"]
    ax.scatter(selected["runtime_seconds"], selected["cost_delta_pct"], s=145, marker="o",
               edgecolors=METHOD_STYLE["fixed"][1], facecolors="none", linewidth=1.5, zorder=4)
    ax.set_xscale("log")
    ax.set_xlabel("Total runtime (seconds, log scale)")
    ax.set_ylabel("Extra cost vs. raw-demand plan (%)")
    ax.set_title("Runtime and placement cost", loc="left", fontsize=16, pad=12)
    ax.grid(axis="y", color=LINE, zorder=0)
    ax.axhline(0, color="#6c737d", lw=0.9)
    ax.spines[["top", "right"]].set_visible(False)
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", frameon=False, ncols=3, fontsize=8)
    fig.savefig(path, dpi=180, facecolor=PAPER)
    plt.close(fig)


def failure_map(case, path):
    raw, fixed = case["plans"]["raw"], case["plans"]["fixed"]
    demand = np.asarray(raw["representatives"])
    weights = np.asarray(raw["weights"])
    sites = dict(zip(case["candidate_names"], np.array(case["candidates"]), strict=True))
    west, middle, east = (sites[name] for name in ("West", "Middle", "East"))
    centers = np.asarray(fixed["representatives"])
    bucket = np.linalg.norm(centers - middle, axis=1).argmin()
    polygon = np.array([to_xy(*vertex) for vertex in h3.cell_to_boundary(fixed["cells"][bucket])])

    fig, ax = plt.subplots(figsize=(7.0, 5.4), layout="constrained")
    ax.fill(*polygon.T, color="#eae4de", alpha=0.7, edgecolor="#96735f", linestyle="--", linewidth=1.2)
    ax.scatter(*demand.T, s=weights * 2.5, color="#386d62", alpha=0.42, zorder=2)
    ax.scatter(*east, marker="s", s=105, facecolors=PAPER, edgecolors=INK, linewidth=1.5, zorder=3)
    ax.scatter(*centers[bucket], marker="o", s=120, facecolors="none", edgecolors="#7c4f36", linewidth=1.3, zorder=3)
    ax.scatter(*west, marker="D", s=130, color=METHOD_STYLE["raw"][1], edgecolors=PAPER, linewidth=1.3, zorder=4)
    ax.scatter(*middle, marker="D", s=130, color=METHOD_STYLE["fixed"][1], edgecolors=PAPER, linewidth=1.3, zorder=4)
    ax.annotate("Raw plan\ncloser to the heavier edge", xy=west, xytext=(0.02, 0.94), textcoords="axes fraction",
                va="top", arrowprops={"arrowstyle": "->", "color": INK}, bbox={"facecolor": PAPER, "edgecolor": "none", "pad": 5})
    ax.annotate("Fixed H3 plan\nnear the bucket centroid", xy=middle, xytext=(0.98, 0.05), textcoords="axes fraction",
                ha="right", va="bottom", color=METHOD_STYLE["fixed"][1],
                arrowprops={"arrowstyle": "->", "color": METHOD_STYLE["fixed"][1]},
                bbox={"facecolor": PAPER, "edgecolor": "none", "pad": 5})
    ax.annotate("Lighter edge", xy=east, xytext=(0.98, 0.92), textcoords="axes fraction",
                ha="right", va="top", arrowprops={"arrowstyle": "->", "color": INK},
                bbox={"facecolor": PAPER, "edgecolor": "none", "pad": 4})
    padding = np.array([1.8, 1.3])
    bottom, top = polygon.min(axis=0) - padding, polygon.max(axis=0) + padding
    ax.set_xlim(bottom[0], top[0])
    ax.set_ylim(bottom[1], top[1])
    ax.set_aspect("equal", adjustable="box")
    ax.set_title("Two demand lobes in one fixed H3 bucket", loc="left", fontsize=15, pad=12)
    ax.set_xlabel("East (km in the synthetic region)")
    ax.set_ylabel("North (km)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(path, dpi=180, facecolor=PAPER)
    plt.close(fig)


def map_data(case, source_hash):
    raw = case["plans"]["raw"]
    coords = np.vstack((raw["representatives"], case["candidates"]))
    lower = np.floor(coords.min(axis=0) - 2)
    upper = np.ceil(coords.max(axis=0) + 2)
    methods = []
    for name in METHODS:
        plan = case["plans"][name]
        methods.append({
            "id": name,
            "label": {"adaptive_spread": "Adaptive H3", "adaptive_volume": "Adaptive H3 (volume)"}.get(name, METHOD_STYLE[name][0]),
            **{key: plan[key] for key in ("bucket_count", "hubs", "cost_weight_km", "weighted_p95_km", "runtime_seconds",
                                        "solver_gap", "cost_delta_pct", "added_hubs", "removed_hubs")},
        } | ({"demand": [list(point) + [weight] for point, weight in zip(plan["representatives"], plan["weights"], strict=True)],
              "boundaries": [[to_xy(*vertex) for vertex in h3.cell_to_boundary(cell)] for cell in plan["cells"]]}
             if name in {"raw", "fixed", "adaptive_spread"} else {}))
    return {
        "schema_version": 1, "benchmark_sha256": source_hash, "family": case["family"], "seed": case["seed"], "k": case["k"],
        "extent": [*lower.tolist(), *upper.tolist()], "maximum_weight": max(weight for m in methods if "demand" in m for *_, weight in m["demand"]),
        "candidates": [{"name": name, "x": x, "y": y} for name, (x, y) in zip(case["candidate_names"], case["candidates"], strict=True)],
        "methods": methods,
    }


def static_comparison(data, path):
    fig, axes = plt.subplots(3, 1, figsize=(6.2, 8.7), sharex=True, sharey=True, layout="constrained")
    candidates = np.array([(site["x"], site["y"]) for site in data["candidates"]])
    extent = data["extent"]
    for ax, method in zip(axes, [item for item in data["methods"] if "demand" in item], strict=True):
        demand = np.asarray(method["demand"])
        selected = [i for i, site in enumerate(data["candidates"]) if site["name"] in method["hubs"]]
        ax.scatter(demand[:, 0], demand[:, 1], s=6 + 350 * demand[:, 2] / data["maximum_weight"],
                   color="#386d62", alpha=0.42, label="Demand used by solver")
        ax.scatter(*candidates.T, marker="s", facecolors=PAPER, edgecolors=INK, s=25, label="Candidate site")
        ax.scatter(*candidates[selected].T, marker="D", color="#a24f36", edgecolors=PAPER, s=75, label="Selected hub")
        for index in selected:
            x, y = candidates[index]
            ax.annotate(data["candidates"][index]["name"], (x, y), xytext=(6, 3), textcoords="offset points", fontsize=10)
        ax.set_xlim(extent[0], extent[2])
        ax.set_ylim(extent[1], extent[3])
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(method["label"], loc="left", fontsize=13)
        ax.set_ylabel("North (km)")
    axes[0].legend(loc="upper left", bbox_to_anchor=(0.0, 1.42), frameon=False, ncols=3, fontsize=9)
    axes[-1].set_xlabel("East (km in the synthetic region)")
    fig.savefig(path, dpi=180, facecolor=PAPER)
    plt.close(fig)


def summary_csv(cases, output):
    fields = ("bucket_count", "cost_weight_km", "cost_delta_pct", "weighted_p95_km", "runtime_seconds", "solver_status", "solver_gap")
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("family", "seed", "method", *fields, "hubs", "added_hubs", "removed_hubs"))
        for case in cases:
            for method in METHODS:
                plan = case["plans"][method]
                writer.writerow((case["family"], case["seed"], method, *(plan[field] for field in fields),
                                 *(", ".join(plan[field]) for field in ("hubs", "added_hubs", "removed_hubs"))))


def main():
    parser = argparse.ArgumentParser(description="Generate article figures and tables from recorded benchmark results.")
    parser.add_argument("--input", type=Path, default=OUTPUT)
    parser.add_argument("--figures", type=Path, default=Path("figures"))
    parser.add_argument("--site-assets", type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    results = json.loads(raw)
    cases = results["cases"]
    stress = max((case for case in cases if case["family"] == "split-cell"), key=lambda case: case["plans"]["fixed"]["cost_delta_pct"])
    args.figures.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER, "axes.edgecolor": INK,
                         "axes.labelcolor": INK, "text.color": INK, "font.family": "DejaVu Sans", "font.size": 11})
    chart(cases, stress, args.figures / "runtime-cost.png")
    failure_map(stress, args.figures / "split-cell.png")
    site_data = map_data(stress, hashlib.sha256(raw).hexdigest())
    static_comparison(site_data, args.figures / "comparison.png")
    (args.figures / "article-data.json").write_text(json.dumps(site_data, separators=(",", ":")) + "\n", encoding="utf-8")
    summary_name = "summary.csv" if args.input == OUTPUT else f"{args.input.stem}-summary.csv"
    summary_csv(cases, args.input.with_name(summary_name))
    if args.site_assets:
        args.site_assets.mkdir(parents=True, exist_ok=True)
        for name in ("runtime-cost.png", "split-cell.png", "comparison.png", "article-data.json"):
            copyfile(args.figures / name, args.site_assets / name)
        copyfile(args.input, args.site_assets / "benchmark.json")
        copyfile(args.input.with_name(summary_name), args.site_assets / "summary.csv")
    print(f"Generated figures for split-cell seed {stress['seed']} from {args.input}")


if __name__ == "__main__":
    main()
