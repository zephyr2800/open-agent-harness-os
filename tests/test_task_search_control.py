from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

from experiments.task_search_control import _run_report, matched_budget


class TaskSearchControlTests(unittest.TestCase):
    def test_budget_is_split_to_match_total_exactly(self) -> None:
        budget = matched_budget(attempts=2, max_steps=6, max_new_tokens=256)
        self.assertEqual(budget["max_steps_per_attempt"], 3)
        self.assertEqual(budget["max_new_tokens_per_decision"], 256)
        self.assertEqual(
            budget["attempts"] * budget["max_steps_per_attempt"],
            budget["total_max_steps"],
        )
        self.assertEqual(
            budget["attempts"] * budget["max_generation_tokens_per_attempt"],
            budget["total_max_generation_tokens"],
        )

    def test_budget_rejects_more_attempts_than_total_steps(self) -> None:
        with self.assertRaises(ValueError):
            matched_budget(attempts=4, max_steps=3, max_new_tokens=256)

    def test_budget_rejects_uneven_step_split_that_would_leave_control_budget_unused(self) -> None:
        with self.assertRaisesRegex(ValueError, "divide evenly"):
            matched_budget(attempts=2, max_steps=7, max_new_tokens=256)
        with self.assertRaisesRegex(ValueError, "positive"):
            matched_budget(attempts=2, max_steps=6, max_new_tokens=0)

    def test_report_records_exact_budget_and_attempt_level_replay(self) -> None:
        budget = matched_budget(attempts=2, max_steps=6, max_new_tokens=256)
        attempts = [
            {"runtime_replay_agreement": True, "metrics": {"output_tokens": 12.0}, "elapsed_seconds": 0.2, "request_output_token_budget": 90, "attempt_seed": 0},
            {"runtime_replay_agreement": True, "metrics": {"output_tokens": 16.0}, "elapsed_seconds": 0.4, "request_output_token_budget": 90, "attempt_seed": 1},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "fixture.json"
            fixture.write_text("{}", encoding="utf-8")
            report = _run_report(
                fixture,
                seed=0,
                checkpoint=Path("checkpoint"),
                budget=budget,
                complete=True,
                rows=[
                    {
                        "selected_independent_success": True,
                        "task_output_token_budget": 180,
                        "attempt_count": 2,
                        "attempts": attempts,
                        "unsafe_attempts": 0,
                        "false_completions": 0,
                        "unverified_action_attempts": 0,
                        "unknown_action_attempts": 0,
                    }
                ],
            )
        self.assertTrue(report["matched_budget"])
        self.assertTrue(report["request_output_budget_matches_baseline"])
        self.assertTrue(report["independent_attempt_seeds"])
        self.assertEqual(report["runtime_replay_agreement"], 1.0)
        self.assertEqual(report["mean_output_tokens"], 14.0)

    def test_report_rejects_duplicate_attempt_seeds(self) -> None:
        budget = matched_budget(attempts=2, max_steps=6, max_new_tokens=256)
        attempts = [
            {"runtime_replay_agreement": True, "metrics": {"output_tokens": 12.0}, "elapsed_seconds": 0.2, "request_output_token_budget": 90, "attempt_seed": 0},
            {"runtime_replay_agreement": True, "metrics": {"output_tokens": 16.0}, "elapsed_seconds": 0.4, "request_output_token_budget": 90, "attempt_seed": 0},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "fixture.json"
            fixture.write_text("{}", encoding="utf-8")
            report = _run_report(
                fixture,
                seed=0,
                checkpoint=Path("checkpoint"),
                budget=budget,
                complete=True,
                rows=[
                    {
                        "selected_independent_success": True,
                        "task_output_token_budget": 180,
                        "attempt_count": 2,
                        "attempts": attempts,
                        "unsafe_attempts": 0,
                        "false_completions": 0,
                        "unverified_action_attempts": 0,
                        "unknown_action_attempts": 0,
                    }
                ],
            )
        self.assertFalse(report["independent_attempt_seeds"])
        self.assertFalse(report["matched_budget"])


if __name__ == "__main__":
    unittest.main()
