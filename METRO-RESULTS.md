# Madison follow-up results

**Decision.** Stop developing adaptive H3 for now. In this road-time model it matched fixed H3 at both budgets and took longer. At 83 representatives both recovered the exact raw point plan. At 18 representatives, weighted k-means reached that plan and fixed and spread-based H3 each cost **2.82%** more. Volume-based H3 placed different hubs and cost **1.21%** more, reversing the spread-versus-volume result from the synthetic panel at this budget.

The study covers 3,473 Census block internal points representing 326,762 residents in a rectangle around Madison, Wisconsin. Three hubs are selected from 24 illustrative road nodes. Travel minutes are **modeled** using a bidirectional 2024 TIGER/Line network, assumed roadway-class speeds, and straight connectors. Population is a demand proxy. [2020 Census block layer](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10) · [2024 TIGER/Line technical documentation](https://www2.census.gov/geo/pdfs/maps-data/data/tiger/tgrshp2024/TGRSHP2024_TechDoc.pdf)

## Exact check and matched budgets

| Representatives | Method | Selected hubs | Excess cost | Weighted p95 | Seconds including routing | Solver gap |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 3,473 | Raw, exhaustive | M06, M13, M20 | 0.00% | 13.45 min | 0.579 | 0% |
| 3,473 | Raw, MILP | M06, M13, M24 | 11.56% | 15.71 min | 24.687 | 100% |
| 18 | Fixed H3 | M07, M13, M20 | 2.82% | 13.70 min | 0.495 | 0% |
| 18 | Adaptive H3, spread | M07, M13, M20 | 2.82% | 13.70 min | 0.515 | 0% |
| 18 | Weighted k-means | M06, M13, M20 | 0.00% | 13.45 min | 0.738 | 0% |
| 18 | Adaptive H3, volume | M07, M10, M14 | 1.21% | 13.20 min | 0.513 | 0% |
| 83 | Fixed H3 | M06, M13, M20 | 0.00% | 13.45 min | 0.559 | 0% |
| 83 | Adaptive H3, spread | M06, M13, M20 | 0.00% | 13.45 min | 0.673 | 0% |
| 83 | Weighted k-means | M06, M13, M20 | 0.00% | 13.45 min | 1.052 | 0% |
| 83 | Adaptive H3, volume | M06, M13, M20 | 0.00% | 13.45 min | 0.610 | 0% |

The exact p-median objective was **2,450,203.83 resident-minutes**, or **7.4984 minutes per resident**. The raw MILP row shows the best of three feasible plans and the maximum reported gap. All three reached the 20-second solver limit and returned a zero dual bound. Timings are medians across three repeats for all MILP methods, plus a separate single enumeration time. Median common routing was **0.456 s**. Graph and block ingestion took **9.261 s** once and is reported separately. Zero gap for aggregate runs certifies each aggregate model. Cost and weighted p95 are scored on the original points.

At 18 representatives, adaptive spread missed the 1% cost requirement. At 83, it met the quality limits and ran far faster than the capped raw MILP. It still offered no advantage over fixed H3. Direct enumeration took less routing-inclusive time than spread-based H3 at 83 representatives. The exact approach is practical here because there are only 2,024 candidate triples. It scales with the number of combinations.

These results describe one population proxy, one candidate grid, and a simplified bidirectional road model. A dispatch or warehouse deployment requires observed or validated travel times, truck constraints, suitable sites, and actual order demand.

[Raw results, hashes, and repeats](outputs/metro.json) · [Chart](figures/metro-runtime-cost.png) · [Protocol](METRO-PROTOCOL.md)

```sh
uv run --locked python -m hub_placement.metro --fetch --output outputs/metro-rerun.json
uv run --locked python -m hub_placement.metro_figure
```

The figure command reads the saved report. Pass `--input outputs/metro-rerun.json --output figures/metro-rerun.png` to plot a rerun.
