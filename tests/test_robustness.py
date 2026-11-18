import json
import unittest
from pathlib import Path

import numpy as np

from hub_placement.robustness import independent_triples
from hub_placement.solver import exhaustive


class RobustnessTests(unittest.TestCase):
    def test_second_triple_scorer(self):
        rng = np.random.default_rng(17)
        costs = rng.uniform(0, 30, size=(103, 7))
        weights = rng.integers(1, 45, size=103)
        expected_cost, expected_hubs = exhaustive(costs, weights, 3)
        cost, hubs = independent_triples(costs, weights)
        self.assertAlmostEqual(cost, expected_cost, places=8)
        self.assertEqual(hubs, expected_hubs)

    def test_recorded_original_and_sensitivity_scope(self):
        with Path("outputs/metro.json").open(encoding="utf-8") as file:
            baseline = json.load(file)
        with Path("outputs/robustness.json").open(encoding="utf-8") as file:
            audit = json.load(file)
        self.assertEqual([row["scenario"] for row in audit["scenarios"]],
                         ["original", "shifted", "slower_highways", "denser"])
        original = audit["scenarios"][0]
        self.assertEqual(original["exact"]["hubs"], baseline["exhaustive"]["hubs"])
        self.assertAlmostEqual(original["independent_check"]["cost_resident_minutes"],
                               baseline["exhaustive"]["cost_resident_minutes"], places=6)
        for scenario in audit["scenarios"]:
            self.assertEqual(scenario["block_count"], baseline["block_count"])
            self.assertEqual(len(scenario["exact_runs"]), 3)
            self.assertEqual([row["bucket_count"] for row in scenario["budgets"]], [18, 83])
