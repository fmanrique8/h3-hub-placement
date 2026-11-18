import json
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.spatial import cKDTree

from hub_placement.metro import compare_gate, travel_times


class MetroChecks(unittest.TestCase):
    def test_connectors_apply_to_all_candidate_times(self):
        metro = SimpleNamespace(node_index=cKDTree([[0, 0], [1, 0]]))
        network = np.array([[0, 5], [5, 0]])
        result = travel_times(metro, network, [[0.1, 0], [0.8, 0]])
        np.testing.assert_allclose(result, [[0.3, 5.3], [5.6, 0.6]])

    def test_saved_budget_decisions_and_independent_bound(self):
        report = json.loads(Path("outputs/metro.json").read_bytes())
        reference = report["raw"]
        self.assertEqual(len(reference["runs"]), 3)
        self.assertLessEqual(report["exhaustive"]["cost_resident_minutes"], reference["cost_resident_minutes"] + 1e-5)
        self.assertEqual([budget["resolution"] for budget in report["budgets"]], [6, 7])
        for budget in report["budgets"]:
            self.assertEqual(compare_gate(budget["methods"], reference), budget["decision"])
            for method in budget["methods"].values():
                self.assertEqual(len(method["runs"]), report["repeat_count"])
                self.assertEqual(len(method["hubs"]), report["k"])
                self.assertTrue(set(method["hubs"]).issubset(report["candidates"]))
                self.assertGreaterEqual(method["cost_resident_minutes"] + 1e-5, report["exhaustive"]["cost_resident_minutes"])
