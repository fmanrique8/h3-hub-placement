# How much does an H3 grid change where you put a warehouse?

In a Madison road-time model, fixed H3 and direct enumeration both found the same hubs in about **0.6 seconds** with 24 candidates. With 76 candidates, fixed H3 still picked the exact hubs and took **1.78 seconds** compared with **6.76 seconds** for enumerating 70,300 triples. [Companion article on fmanrique.com](https://fmanrique.com/blog/h3-warehouse-placement/) · [Robustness results](ROBUSTNESS-RESULTS.md)

At **23 buckets**, fixed H3 moved one of three hubs and increased demand-weighted distance by **14.77%** in the constructed split-cell case with seed 271. Spreadsheet-sized inputs make the difference easy to inspect. Fixed H3 chose `Middle` in place of `West`, raising cost from **2,328.46 to 2,672.34 demand-unit km** while reducing weighted p95 from **6.96 to 4.95 km**. Spread-based adaptive H3 recovered the raw-demand plan at the same count.

**Madison follow-up.** Fixed and spread-based H3 selected the same sites at both matched budgets in a separate road-time model of 3,473 Census blocks. Shifting the candidate grid, slowing two highway classes, and using more candidates all preserved that finding at both budgets. None passed the threshold for investing more in adaptive refinement. [Madison report](METRO-RESULTS.md)

## Recorded panel

Four regional seeds and three designed split-cell seeds, seven cases in total. Every case opens three sites. Within a case, all methods use the same 10 or 25 candidates, original demand weights, p-median objective, and solver options. The baseline solver uses all 203–242 points. The four aggregate runs each use the same 20–36 representatives as the fixed H3 partition for that case.

| Method | Cases that changed hubs | Median extra cost | Maximum extra cost | Median total time | Maximum solver gap |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw demand | 0/7 | 0% | 0% | 0.317 s | 0% |
| Fixed H3 | 4/7 | 0.57% | 14.77% | 0.028 s | 0% |
| Adaptive H3, spread | 0/7 | 0% | 0% | 0.032 s | 0% |
| Weighted k-means | 0/7 | 0% | 0% | 0.147 s | 0% |
| Adaptive H3, volume | 4/7 | 0.57% | 13.92% | 0.033 s | 0% |

**Refinement comparison.** Spread beat volume on point-level cost in four cases and tied three at identical bucket counts. Weighted k-means also recovered the raw hubs in all seven. This is a small synthetic panel, with three cases deliberately designed to expose a loss of within-cell information. It cannot establish how often a real warehouse plan would move. All distances are planar and omit roads, capacity, operating costs, and land constraints.

Check the [per-case CSV](outputs/summary.csv) for costs, weighted p95, times, gaps, and added or removed hub IDs. The [raw benchmark JSON](outputs/benchmark.json) also includes the inputs, representative points, objective values, dual bounds, runtime breakdown, solver status, and exact options.

## Reproduce

Install [uv](https://docs.astral.sh/uv/) and run these commands from the repository root. `.python-version` pins Python 3.12.13 and `uv.lock` locks the dependency graph.

```sh
uv run --locked python -m unittest discover -s tests -v
uv run --locked python -m hub_placement.benchmark --output outputs/benchmark-rerun.json
uv run --locked python -m hub_placement.figures
```

The last command regenerates the [runtime chart](figures/runtime-cost.png), [annotated failure map](figures/split-cell.png), [static comparison](figures/comparison.png), the interactive map data, and the results CSV from the recorded file. Pass `--input outputs/benchmark-rerun.json --figures rerun-figures` to plot a fresh run while retaining the recorded figures. Use `--site-assets <directory>` to export the same figure set, full data, and CSV for the local article. The interactive data carries a SHA-256 of its source benchmark. Timings vary between runs.

## Methods and checks

- **Objective.** Minimize the sum of demand weights times distance to the nearest selected facility. Binary variables open sites, while continuous assignments can only go to an open site. For a chosen set of sites, each demand row's least-cost assignment is to a nearest site. HiGHS uses a 20 s solve limit, a relative gap target of `1e-6`, one thread, presolve, and random seed 0. Gaps and dual bounds describe the model passed to the solver. The re-score evaluates the selected hubs on the original points. [p-median formulation](https://kar.kent.ac.uk/38849/1/EJOR%28Chandra-Said-Paola-2014%29.pdf) · [SciPy MILP](https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.optimize.milp.html)
- **H3.** Index each original point at resolution 8. For fixed H3, roll up to logical parent resolution 6 and use a demand-weighted centroid. Adaptive H3 starts at resolution 5 and picks the highest-priority split still capable of reaching the same count. It skips single-child levels and considers only occupied children. Volume is the sum of weights. Spread is the sum of weighted distances to the current centroid. The tree's logical parentage is exact. Outlines across resolutions approximate geographic containment. The spread measure also bounds the change in the objective for any fixed set of hubs by the triangle inequality. [H3 indexing and containment](https://h3geo.org/docs/highlights/indexing/) · [Aggregation error analysis](https://www.sciencedirect.com/science/article/abs/pii/S0377221709003531)
- **Non-H3 baseline.** Weighted Lloyd k-means runs at the same occupied bucket count, with ten initializations, K-means++ initialization, and random seed 0. Each cluster becomes a weighted centroid for the same p-median model. This baseline minimizes squared clustering distortion during aggregation. Facility placement still minimizes the same weighted distance as the H3 methods. [K-means parameters and weighting](https://scikit-learn.org/1.6/modules/generated/sklearn.cluster.KMeans.html)
- **Scoring and time.** Weighted p95 is the first distance where cumulative demand weight reaches 95%. Total method time includes aggregation, cost-matrix and MILP construction, solve, and original-point scoring. The shared fixture generation, target bucket-count lookup, and figure export are outside the timer. Each method runs once per case on one machine. The order rotates across cases. Win, tie, and loss for the two rules use original-point cost with a `1e-7` absolute tie tolerance.
- **Checks.** A five-point, four-candidate instance enumerates all six two-hub subsets. Enumeration and MILP both select candidate indices 1 and 3 with objective 22. The tests also check exact bucket budgets, weight and weighted-centroid conservation, weighted p95, deterministic fixtures, and re-score every stored plan directly on its source rows.

See [data and ZIP handling](DATA.md), [bibliography](BIBLIOGRAPHY.md), [citation metadata](CITATION.cff), and the [visual audit](VISUAL-AUDIT.md).
