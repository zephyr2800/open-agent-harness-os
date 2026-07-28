import json
import unittest

from model.adapter import ModelOutputError, ModelRequest, StaticPolicy, parse_decision


def decision(task_id="task-1", intent="read_file"):
    return {
        "schema": "action-ir/v0",
        "task_id": task_id,
        "step_id": "step-1",
        "kind": "act",
        "action": {
            "intent": intent,
            "arguments": {"path": "STATUS.md"},
            "preconditions": [],
            "risk": "low",
            "expected_effect": "file_contents_observed",
            "escalate_if": [],
        },
        "uncertainty": {"confidence": 0.8, "basis": "fixture"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
    }


class ModelAdapterTests(unittest.TestCase):
    def setUp(self):
        self.request = ModelRequest("task-1", "read status", {}, ("read_file", "abstain"), 128)

    def test_parse_decision_checks_tool_surface(self):
        self.assertEqual(parse_decision(json.dumps(decision()), self.request)["kind"], "act")
        with self.assertRaisesRegex(ModelOutputError, "available tool surface"):
            parse_decision(json.dumps(decision(intent="write_file")), self.request)

    def test_parse_decision_rejects_non_json(self):
        with self.assertRaisesRegex(ModelOutputError, "not valid JSON"):
            parse_decision("not-json", self.request)

    def test_static_policy_uses_same_validation_path(self):
        policy = StaticPolicy(lambda request: decision(request.task_id))
        self.assertEqual(policy.decide(self.request)["task_id"], "task-1")

    def test_finish_binds_only_existing_verified_evidence(self):
        request = ModelRequest(
            "task-1", "finish", {"verified_evidence": ["sha256:verified"]}, ("abstain", "finish"), 128
        )
        raw = json.dumps({
            "schema": "action-ir/v0",
            "task_id": "task-1",
            "step_id": "step-1",
            "kind": "finish",
            "finish": {"result": "done", "evidence": [], "verified": True},
            "uncertainty": {"confidence": 0.9, "basis": "verified state"},
            "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
        })
        self.assertEqual(parse_decision(raw, request)["finish"]["evidence"], ["sha256:verified"])
