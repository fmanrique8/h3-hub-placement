# What held up when the Madison case changed

Across eight scenario–budget comparisons, fixed H3 and spread-based H3 selected the same hubs. Fixed H3 had the shorter routing-inclusive median in each comparison. Weighted k-means matched the exact point-level optimum in all eight. The coarser H3 budget missed the optimum in the original and slower-highway scenarios. [Protocol](ROBUSTNESS-PROTOCOL.md) · [Raw runs](outputs/robustness.json)

| Scenario | Candidates | Triples | Fixed and adaptive cost above exact at 18 buckets | At 83 buckets | Exact raw, routing included | Fixed H3 at 83, routing included |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original | 24 | 2,024 | 2.82% | 0.00% | 0.65 s | 0.62 s |
| Grid shifted 1 km east and south | 23 | 1,771 | 0.00% | 0.00% | 0.58 s | 0.57 s |
| Two highway classes 25% slower | 24 | 2,024 | 3.04% | 0.00% | 0.60 s | 0.57 s |
| Denser grid | 76 | 70,300 | 0.00% | 0.00% | 6.76 s | 1.78 s |

Timing cells are three-repeat medians. The road graph and demand preparation are excluded. Every aggregate model reported a zero solver gap. The raw reference exhaustively enumerates triples and measures cost and p95 on the original census blocks. A separate scorer computed the same original optimum, 2,450,203.83 resident-minutes, and the same hubs, `M06`, `M13`, and `M20`.

**What changed the engineering decision.** Direct enumeration was competitive with fixed H3 at 24 candidates. Across the denser grid, fixed H3 returned the same point-level optimum in **1.78 s** while enumeration took **6.76 s**, a factor of 3.8 in this implementation. This gives a concrete regime where aggregation was useful. It also shows why a single timing on 24 candidates gives an incomplete picture. A more optimized exact solver could change the comparison.

None of the eight spread-refinement runs passed the continuation gate. The volume rule occasionally changed hubs and tail times. In the original 18-bucket case it reduced cost relative to spread. In the denser 18-bucket case it raised cost by **3.61%** relative to the exact plan. These checks perturb a single Madison demand surface one factor at a time. They leave geographic transfer and the effects of observed truck travel times unresolved.

```sh
uv run --locked python -m hub_placement.robustness --fetch --output outputs/robustness-rerun.json
```
