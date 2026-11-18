import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .figures import INK, LINE, METHOD_STYLE, PAPER


def chart(result, output):
    fig, axes = plt.subplots(1, 2, figsize=(7, 4.3), sharex=True, sharey=True, layout="constrained")
    for panel, axis in zip(result["budgets"], axes, strict=True):
        plans = {"raw": result["raw"]} | panel["methods"]
        for method, metrics in plans.items():
            label, color, marker = METHOD_STYLE[method]
            axis.scatter(metrics["routing_inclusive_seconds_median"], metrics["cost_excess_pct"],
                         color=color, marker=marker, label=label, s=52, alpha=0.78, zorder=3)
        exact = result["exhaustive"]
        axis.scatter(exact["routing_inclusive_seconds"], 0, color=INK, marker="*", s=105,
                     label="Raw · exact enumeration", zorder=3)
        axis.axhline(0, color=LINE, lw=1)
        axis.axhline(1, color="#7b7468", lw=0.9, linestyle=":")
        axis.set_title(f"{panel['bucket_count']} representatives", loc="left", fontsize=12)
        axis.set_xscale("log")
        axis.set_xlabel("Seconds with routing (log)")
        axis.grid(axis="y", color=LINE, alpha=0.7)
        axis.spines[["right", "top"]].set_visible(False)
    axes[0].set_ylabel("Cost above exact raw optimum (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncols=2, frameon=False, fontsize=8.4)
    fig.suptitle("Madison road model", x=0.035, ha="left", fontsize=15, color=INK)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, facecolor=PAPER)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Plot the saved Madison road study.")
    parser.add_argument("--input", type=Path, default=Path("outputs/metro.json"))
    parser.add_argument("--output", type=Path, default=Path("figures/metro-runtime-cost.png"))
    args = parser.parse_args()
    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER, "axes.edgecolor": INK,
                         "axes.labelcolor": INK, "font.family": "DejaVu Sans", "font.size": 10})
    chart(json.loads(args.input.read_bytes()), args.output)


if __name__ == "__main__":
    main()
