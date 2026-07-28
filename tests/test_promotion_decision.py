from __future__ import annotations

import unittest

from experiments.promotion_decision import decide


def _run(task_spec: str, seed: int, *, passed: bool = True) -> dict:
    rate = 1.0 if passed else 0.5
    return {
        "task_spec": f"C:/fixtures/{task_spec}",
        "seed": seed,
        "complete": True,
        "task_count": 2,
        "rows": [{"verified_success": passed}, {"verified_success": passed}],
        "verified_success_rate": rate,
        "independent_success_rate": rate,
        "trace_valid_rate": 1.0,
        "runtime_replay_agreement": 1.0,
        "unsafe_attempts": 0,
        "elapsed_seconds": 1.0,
        "runtime": {"cuda_available": False},
    }


class PromotionDecisionTests(unittest.TestCase):
    def test_requires_every_frozen_slice_and_seed(self) -> None:
        matrix = {
            "schema": "promotion-matrix/v1",
            "checkpoint": "checkpoint",
            "seeds": [0, 1, 2],
            "runs": [
                _run("task-spec-research-v4.json", seed)
                for seed in (0, 1, 2)
            ] + [
                _run("task-spec-industry-proxy-v1.json", seed)
                for seed in (0, 1, 2)
            ] + [
                _run("task-spec-industry-proxy-v2.json", seed)
                for seed in (0, 1, 2)
            ],
        }
        result = decide(matrix)
        self.assertTrue(result["passed"])
        self.assertEqual(result["decision"], "promote")

    def test_rejects_incomplete_matrix_even_if_present_rows_pass(self) -> None:
        matrix = {
            "schema": "promotion-matrix/v1",
            "seeds": [0, 1, 2],
            "runs": [
                _run("task-spec-research-v4.json", 0),
                _run("task-spec-industry-proxy-v1.json", 0),
                _run("task-spec-industry-proxy-v2.json", 0),
            ],
        }
        matrix["runs"][0]["complete"] = False
        result = decide(matrix)
        self.assertFalse(result["passed"])
        self.assertFalse(result["gates"]["expected_run_count"])
        self.assertFalse(result["gates"]["all_required_seeds_present"])
        self.assertFalse(result["slices"]["research_v4"]["all_runs_passed"])

    def test_rejects_one_failed_slice_and_unknown_spec(self) -> None:
        matrix = {
            "schema": "promotion-matrix/v1",
            "runs": [
                _run("task-spec-research-v4.json", 0),
                _run("task-spec-industry-proxy-v1.json", 0, passed=False),
                _run("task-spec-industry-proxy-v2.json", 0),
                _run("other.json", 0),
            ],
        }
        result = decide(matrix)
        self.assertFalse(result["passed"])
        self.assertEqual(result["decision"], "reject")
        self.assertFalse(result["gates"]["no_unknown_task_specs"])
        self.assertFalse(result["slices"]["industry_proxy_v1"]["all_runs_passed"])
