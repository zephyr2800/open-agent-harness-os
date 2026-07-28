import unittest

from runtime.executor import ExecutionDenied, ToolRegistry, ToolSpec


def action(intent, arguments, risk="low"):
    return {
        "schema": "action-ir/v0",
        "task_id": "task-1",
        "step_id": "step-1",
        "kind": "act",
        "action": {
            "intent": intent,
            "arguments": arguments,
            "preconditions": [],
            "risk": risk,
            "expected_effect": "fixture_effect",
            "escalate_if": ["permission_denied"],
        },
        "uncertainty": {"confidence": 0.9, "basis": "fixture"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
    }


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.called = []
        self.registry.register(ToolSpec("echo", "low", lambda args: self.called.append(args) or {"ok": True}, lambda output: output.get("ok") is True))
        self.registry.register(ToolSpec("delete_fixture", "high", lambda args: {"deleted": args["path"]}, lambda output: False))

    def test_registered_tool_requires_independent_verification(self):
        result = self.registry.execute(action("echo", {"value": "hello"}))
        self.assertEqual(result.status, "verified")
        self.assertTrue(result.verified)
        self.assertEqual(self.called, [{"value": "hello"}])

    def test_unknown_tool_is_denied(self):
        with self.assertRaisesRegex(ExecutionDenied, "not registered"):
            self.registry.execute(action("missing", {}))

    def test_high_risk_tool_requires_approval(self):
        with self.assertRaisesRegex(ExecutionDenied, "approval required"):
            self.registry.execute(action("delete_fixture", {"path": "x"}, risk="high"))

    def test_model_cannot_lie_about_registered_tool_risk(self):
        with self.assertRaisesRegex(ExecutionDenied, "risk does not match"):
            self.registry.execute(action("delete_fixture", {"path": "x"}, risk="low"))

    def test_unverified_output_is_not_success(self):
        result = self.registry.execute(action("delete_fixture", {"path": "x"}, risk="high"), approved_risks={"high"})
        self.assertEqual(result.status, "unverified")
        self.assertFalse(result.verified)
