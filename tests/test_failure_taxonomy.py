from __future__ import annotations

import json
import unittest

from experiments.analyze_failure_taxonomy import _categories


def _trace(*events: dict) -> str:
    return "\n".join(json.dumps(event) for event in events)


class FailureTaxonomyTests(unittest.TestCase):
    def test_distinguishes_verified_evidence_from_result_mismatch(self) -> None:
        row = {
            "error": "finish lacked independent verified evidence",
            "unverified_action_attempts": 0,
            "trace_jsonl": _trace(
                {"event_type": "verification", "payload": {"independent_evidence": True}},
                {"event_type": "verification", "payload": {"expected_result": False}},
            ),
        }
        categories = _categories(row)
        self.assertIn("finish_result_mismatch", categories)
        self.assertNotIn("finish_evidence_failure", categories)

    def test_classifies_missing_evidence(self) -> None:
        row = {
            "error": "finish lacked independent verified evidence",
            "unverified_action_attempts": 0,
            "trace_jsonl": _trace({"event_type": "trajectory_end", "payload": {"reason": "finish"}}),
        }
        self.assertEqual(_categories(row), ["finish_evidence_failure"])

    def test_classifies_row_level_unverified_attempts(self) -> None:
        row = {
            "error": "step budget exhausted",
            "unverified_action_attempts": 2,
            "trace_jsonl": "",
        }
        self.assertEqual(_categories(row), ["step_budget_exhaustion", "unverified_action"])
