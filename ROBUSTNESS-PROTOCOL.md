# Madison robustness checks

Before publishing, challenge the original result in three ways. Keep all 3,473 original points and weights, the box, three open sites, road topology, H3 budgets, solver settings, and original-point scoring. Hold candidate sites and travel costs constant across methods within each scenario.

| Scenario | Change from the recorded Madison case | Question |
| --- | --- | --- |
| Original | Repeat the 5-by-5 candidate grid and road speeds. | Does the exact reference reproduce, and how variable is its time? |
| Shifted | Move every 5-by-5 anchor 1 km east and 1 km south before snapping. | Does the adaptive result depend on the candidate grid's placement? |
| Slower highways | Reduce S1100 and S1200 modeled speeds by 25%. | Does the adaptive result depend on two assumed road speeds? |
| Denser | Start from a 9-by-9 grid with the original margins, keeping three hubs. | How much does exact enumeration slow down when the candidate set grows? |

Check the existing 18- and 83-representative budgets in each case. Compare fixed H3, spread refinement, weighted k-means, and the secondary volume rule. Use exhaustive triples on the original points as the exact quality reference. Rotate timed aggregate runs, perform three repeats, and report routing-inclusive medians. Graph preparation remains outside the timings. Run a separately coded triple scorer over the original configuration as a check on the exact result. Scope conclusions to these one-at-a-time perturbations of one geographic instance. Record every case, including any improvements from adaptive H3.
