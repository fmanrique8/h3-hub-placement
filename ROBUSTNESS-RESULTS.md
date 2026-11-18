# What held up when the Madison case changed

Across eight scenario–budget comparisons, fixed H3 and spread-based H3 selected the same hubs. Fixed H3 had the shorter routing-inclusive median in each comparison. Weighted k-means matched the exact point-level optimum in all eight. The coarser H3 budget missed the optimum in the original and slower-highway scenarios. [Protocol](ROBUSTNESS-PROTOCOL.md) · [Raw runs](outputs/robustness.json)

## Historical sensitivity run

| Scenario | Candidates | Triples | Fixed and adaptive cost above exact at 18 buckets | At 83 buckets | Simple exact, routing included | Fixed H3 at 83, routing included |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original | 24 | 2,024 | 2.82% | 0.00% | 0.65 s | 0.62 s |
| Grid shifted 1 km east and south | 23 | 1,771 | 0.00% | 0.00% | 0.58 s | 0.57 s |
| Two highway classes 25% slower | 24 | 2,024 | 3.04% | 0.00% | 0.60 s | 0.57 s |
| Denser grid | 76 | 70,300 | 0.00% | 0.00% | 6.76 s | 1.78 s |

Timing cells are three-repeat medians. The road graph and demand preparation are excluded. Every aggregate model reported a zero solver gap. The raw reference exhaustively enumerates triples and measures cost and p95 on the original census blocks. A separate scorer computed the same original optimum, 2,450,203.83 resident-minutes, and the same hubs, `M06`, `M13`, and `M20`.

None of the eight spread-refinement runs passed the continuation gate. The volume rule occasionally changed hubs and tail times. In the original 18-bucket case it reduced cost relative to spread. In the denser 18-bucket case it raised cost by **3.61%** relative to the exact plan. These checks perturb a single Madison demand surface one factor at a time. They leave geographic transfer and the effects of observed truck travel times unresolved.

```sh
uv run --locked python -m hub_placement.robustness --fetch --output outputs/robustness-rerun.json
```

## Stronger exact baseline

This separate run repeats the pinned dense case with 3,473 blocks, 76 candidates, and three hubs. The simple loop and pairwise-minimum vectorized implementation score all 70,300 candidate triples on original demand. Fixed H3 solves an 83-bucket model with the recorded HiGHS options. Each repetition computes one shared route matrix and each method is timed in a different order. Timings include candidate-to-network routing, original-point lookup, the method, and original-point rescoring. They exclude download, input loading and graph construction. The fixed-H3 timer also includes aggregation, bucket lookup, and construction of the p-median model.

| Method | Median method and scoring | Median with routing | Hubs in all three trials |
| --- | ---: | ---: | --- |
| Fixed H3, resolution 7 | 0.24 s | 1.65 s | M12, M33, M62 |
| Simple exact enumeration | 4.56 s | 5.96 s | M12, M33, M62 |
| Vectorized exact enumeration | 2.74 s | 4.15 s | M12, M33, M62 |

All methods selected the same hubs at **2,165,118.79 resident-minutes** and a weighted **p95 of 13.28 minutes**. No different equal-cost selections appeared. The script checks objective agreement independently of hub identity so a different optimum can be examined directly. Fixed H3's routing-inclusive median was about **2.5× shorter** than vectorized enumeration on this Windows 11 / Intel i7-8750H run with single-threaded BLAS. The result is specific to these implementations, inputs, and machine. The exact methods certify this original-demand objective. Fixed H3's solver gap applies to its 83-bucket objective.

The [raw records](outputs/exact-baselines.json) include input URLs and checksums, package versions, settings, method order, routing components, and every observed time. The historical sensitivity measurements above are retained as recorded.

```sh
uv run --locked python -m hub_placement.exact_baselines --fetch --output outputs/exact-baselines-rerun.json
```
