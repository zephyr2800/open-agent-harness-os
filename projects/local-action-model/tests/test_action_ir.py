import unittest

from action_ir.validation import validate_decision


def valid_action():
    return {
        "schema": "action-ir/v0",
        "task_id": "task-1",
        "step_id": "step-1",
        "kind": "act",
        "action": {
            "intent": "read_file",
            "arguments": {"path": "STATUS.md"},
            "preconditions": [],
            "risk": "low",
            "expected_effect": "file_contents_observed",
            "escalate_if": ["permission_denied"],
        },
        "uncertainty": {"confidence": 0.8, "basis": "path is explicitly requested"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
    }


class ActionIRTests(unittest.TestCase):
    def test_valid_action(self):
        self.assertEqual(validate_decision(valid_action()), [])

    def test_rejects_confidence_outside_range_and_missing_state_fields(self):
        decision = valid_action()
        decision["uncertainty"]["confidence"] = 1.1
        decision["state_update"].pop("facts")
        issues = validate_decision(decision)
        self.assertIn("uncertainty.confidence must be a number between 0 and 1", issues)
        self.assertIn("state_update.facts must be a list of non-empty strings", issues)

    def test_rejects_unhashable_enum_values_without_raising(self):
        decision = valid_action()
        decision["kind"] = {"unexpected": "object"}
        issues = validate_decision(decision)
        self.assertTrue(any(issue.startswith("kind must be one of") for issue in issues))
        decision["kind"] = "act"
        decision["action"]["risk"] = {"level": "low"}
        decision["recovery"] = {"strategy": ["retry"], "reason": "bad shape"}
        issues = validate_decision(decision)
        self.assertTrue(any(issue.startswith("action.risk must be one of") for issue in issues))
        self.assertTrue(any(issue.startswith("recovery.strategy must be one of") for issue in issues))

    def test_finish_requires_independent_verification(self):
        decision = valid_action()
        decision.pop("action")
        decision["kind"] = "finish"
        decision["finish"] = {"result": "done", "evidence": ["artifact:x"], "verified": False}
        self.assertIn("finish.verified must be true", validate_decision(decision))

    def test_action_cannot_be_combined_with_abstention(self):
        decision = valid_action()
        decision["abstention"] = {"reason": "uncertain", "alternatives": []}
        self.assertIn("abstention is not allowed for kind=act", validate_decision(decision))
