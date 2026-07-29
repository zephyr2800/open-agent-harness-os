from __future__ import annotations

import json
import unittest

from experiments.analyze_dense_reliability import analyze, row_metrics


def _trace(*events: dict) -> str:
    return "\n".join(json.dumps(event) for event in events)


class DenseReliabilityTests(unittest.TestCase):
    def test_partial_utility_credits_verified_progress_but_not_bad_finish(self) -> None:
        row = {
            "task_id": "terminal-0",
            "family": "terminal_long_horizon",
            "expected_action_count": 3,
            "protocol_valid": True,
            "verified_success": False,
            "independent": {
                "independent_verified_evidence": 3,
                "expected_result_ok": False,
                "trace_valid": True,
                "matches_runtime": True,
            },
            "trace_jsonl": _trace(
                {"event_type": "tool_call", "payload": {"tool": "write_file", "status": "verified"}},
                {"event_type": "tool_call", "payload": {"tool": "move_file", "status": "verified"}},
                {"event_type": "tool_call", "payload": {"tool": "write_file", "status": "verified"}},
            ),
        }
        metrics = row_metrics(row)
        self.assertEqual(metrics["action_progress"], 1.0)
        self.assertEqual(metrics["evidence_progress"], 1.0)
        self.assertEqual(metrics["result_ok"], False)
        self.assertEqual(metrics["partial_utility"], 0.75)

    def test_safe_no_action_task_can_score_complete(self) -> None:
        row = {
            "task_id": "confirm-0",
            "family": "confirmation_boundary",
            "expected_action_count": 0,
            "protocol_valid": True,
            "verified_success": True,
            "independent": {"independent_verified_evidence": 0, "expected_result_ok": True},
            "trace_jsonl": "",
        }
        metrics = row_metrics(row)
        self.assertEqual(metrics["partial_utility"], 1.0)

    def test_cross_seed_reports_pass_at_k_and_worst_seed(self) -> None:
        data = {
            "seeds": [0, 1],
            "runs": [
                {"task_spec": "spec", "seed": 0, "complete": True, "rows": [
                    {"task_id": "a", "verified_success": True, "protocol_valid": True, "expected_action_count": 0, "independent": {"expected_result_ok": True}},
                    {"task_id": "b", "verified_success": True, "protocol_valid": True, "expected_action_count": 0, "independent": {"expected_result_ok": True}},
                ]},
                {"task_spec": "spec", "seed": 1, "complete": True, "rows": [
                    {"task_id": "a", "verified_success": True, "protocol_valid": True, "expected_action_count": 0, "independent": {"expected_result_ok": True}},
                    {"task_id": "b", "verified_success": False, "protocol_valid": True, "expected_action_count": 0, "independent": {"expected_result_ok": False}},
                ]},
            ],
        }
        path = __import__("tempfile").NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        try:
            json.dump(data, path)
            path.close()
            summary = analyze(__import__("pathlib").Path(path.name))
        finally:
            __import__("os").unlink(path.name)
        cross_seed = summary["cross_seed"][0]
        self.assertEqual(cross_seed["eligible_tasks"], 2)
        self.assertEqual(cross_seed["pass_at_k"], 0.5)
        self.assertEqual(cross_seed["worst_seed_success_rate"], 0.5)
