import json
import math
import unittest
from pathlib import Path

import numpy as np

from hub_placement.aggregation import adaptive_h3, fixed_h3, weighted_kmeans
from hub_placement.benchmark import METHODS, small_verification, summarize
from hub_placement.fixtures import all_instances, split_cell, to_lat_lng, to_xy
from hub_placement.solver import score_plan, weighted_p95


class ResearchTests(unittest.TestCase):
    def test_milp_matches_all_six_subsets(self):
        answer = small_verification()
        self.assertEqual(answer["candidate_subsets"], 6)
        self.assertEqual(answer["hubs_zero_based"], [1, 3])
        self.assertAlmostEqual(answer["objective"], 22.0)
        self.assertAlmostEqual(answer["mip_gap"], 0.0)

    def test_weighted_quantile_uses_demand_not_point_count(self):
        values = np.array([4.0, 1.0, 2.0])
        weights = np.array([5, 94, 1])
        self.assertEqual(weighted_p95(values, weights), 2.0)

    def test_local_coordinate_roundtrip(self):
        np.testing.assert_allclose(to_xy(*to_lat_lng(-14.0, 18.0)), [-14.0, 18.0], atol=1e-10)

    def test_candidate_and_demand_are_deterministic(self):
        first, second = split_cell(271), split_cell(271)
        np.testing.assert_array_equal(first.demand, second.demand)
        np.testing.assert_array_equal(first.candidates, second.candidates)
        np.testing.assert_array_equal(first.weights, second.weights)

    def test_aggregation_preserves_mass_and_exact_bucket_budget(self):
        for case in all_instances():
            with self.subTest(family=case.family, seed=case.seed):
                fixed = fixed_h3(case.demand, case.weights)
                budget = len(fixed.weights)
                alternatives = [adaptive_h3(case.demand, case.weights, budget, mode) for mode in ("spread", "volume")]
                alternatives.append(weighted_kmeans(case.demand, case.weights, budget))
                for buckets in [fixed, *alternatives]:
                    self.assertEqual(len(buckets.weights), budget)
                    self.assertEqual(buckets.weights.sum(), case.weights.sum())
                    np.testing.assert_allclose(
                        np.average(buckets.points, axis=0, weights=buckets.weights),
                        np.average(case.demand, axis=0, weights=case.weights),
                        atol=1e-10,
                    )

    def test_fractional_demand_and_weighted_centroids(self):
        # Two well-separated groups with every group's mass below one.
        points = np.array([[0.0, 0.0], [0.01, 0.0], [20.0, 20.0], [20.03, 20.0]])
        weights = np.array([0.4, 0.4, 0.2, 0.4])
        expected_points = [[0.005, 0.0], [20.02, 20.0]]
        expected_weights = [0.8, 0.6]
        methods = {
            "fixed": fixed_h3(points, weights),
            "spread": adaptive_h3(points, weights, 2, "spread"),
            "volume": adaptive_h3(points, weights, 2, "volume"),
            "kmeans": weighted_kmeans(points, weights, 2),
        }
        for method, buckets in methods.items():
            with self.subTest(method=method):
                self.assertEqual(len(buckets.weights), 2)
                order = np.argsort(buckets.points[:, 0])
                np.testing.assert_allclose(buckets.weights[order], expected_weights, rtol=0, atol=1e-14)
                np.testing.assert_allclose(buckets.points[order], expected_points, rtol=0, atol=1e-12)
                self.assertAlmostEqual(buckets.weights.sum(), weights.sum(), places=14)

    def test_saved_plans_score_against_the_original_demand(self):
        saved = json.loads(Path("outputs/benchmark.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["summary"], summarize(saved["cases"]))
        for row, case in zip(saved["cases"], all_instances(), strict=True):
            self.assertEqual((row["family"], row["seed"], row["k"]), (case.family, case.seed, case.k))
            self.assertEqual(set(row["plans"]), set(METHODS))
            # Geographic conversion can differ in the last bits across platforms.
            # A micrometer in these kilometer coordinates is below model precision.
            np.testing.assert_allclose(row["candidates"], case.candidates, rtol=0, atol=1e-9)
            np.testing.assert_allclose(row["plans"]["raw"]["representatives"], case.demand, rtol=0, atol=1e-9)
            self.assertEqual(tuple(row["candidate_names"]), tuple(case.names))
            np.testing.assert_array_equal(row["plans"]["raw"]["weights"], case.weights)
            for method, plan in row["plans"].items():
                hubs = tuple(case.names.index(name) for name in plan["hubs"])
                with self.subTest(seed=case.seed, family=case.family, method=method):
                    self.assertEqual(len(hubs), case.k)
                    cost, tail = score_plan(case.demand, case.weights, case.candidates, hubs)
                    self.assertTrue(math.isclose(cost, plan["cost_weight_km"], rel_tol=1e-12))
                    self.assertTrue(math.isclose(tail, plan["weighted_p95_km"], rel_tol=1e-12))
                    self.assertEqual(sum(plan["weights"]), case.weights.sum())
                    self.assertGreaterEqual(plan["model_cost_weight_km"] + 1e-6, plan["solver_dual_bound_weight_km"])
                    self.assertGreater(plan["runtime_seconds"], 0)
        failure = next(row for row in saved["cases"] if (row["family"], row["seed"]) == ("split-cell", 271))
        self.assertEqual(failure["plans"]["fixed"]["added_hubs"], ["Middle"])
        self.assertEqual(failure["plans"]["fixed"]["removed_hubs"], ["West"])
        self.assertGreater(failure["plans"]["fixed"]["cost_delta_pct"], 10)
        self.assertEqual(failure["plans"]["adaptive_spread"]["hubs"], failure["plans"]["raw"]["hubs"])
