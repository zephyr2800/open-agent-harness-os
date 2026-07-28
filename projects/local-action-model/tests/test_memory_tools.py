import unittest

from runtime.executor import ExecutionDenied
from runtime.memory_tools import ToolExecutionError, make_memory_registry


def action(intent, arguments, risk):
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


class MemoryToolTests(unittest.TestCase):
    def test_write_and_read_are_independently_verified(self):
        workspace, registry = make_memory_registry()
        write = registry.execute(action("write_file", {"path": "notes/today.md", "content": "checkpoint complete"}, "low"))
        self.assertTrue(write.verified)
        read = registry.execute(action("read_file", {"path": "notes/today.md"}, "low"))
        self.assertTrue(read.verified)
        self.assertEqual(read.output["content"], "checkpoint complete")
        self.assertEqual(workspace.files["notes/today.md"], "checkpoint complete")

    def test_move_changes_only_the_in_memory_workspace(self):
        workspace, registry = make_memory_registry({"reports/final.md": "verified"})
        result = registry.execute(action("move_file", {"source": "reports/final.md", "destination": "archive/final.md"}, "medium"))
        self.assertTrue(result.verified)
        self.assertNotIn("reports/final.md", workspace.files)
        self.assertEqual(workspace.files["archive/final.md"], "verified")

    def test_unsafe_paths_and_missing_files_are_rejected(self):
        _, registry = make_memory_registry()
        with self.assertRaises(ToolExecutionError):
            registry.execute(action("write_file", {"path": "../outside.txt", "content": "x"}, "low"))
        with self.assertRaises(ToolExecutionError):
            registry.execute(action("read_file", {"path": "missing.txt"}, "low"))

    def test_tool_risk_is_explicit(self):
        _, registry = make_memory_registry()
        with self.assertRaisesRegex(ExecutionDenied, "risk does not match"):
            registry.execute(action("move_file", {"source": "a", "destination": "b"}, "low"))

    def test_retry_is_verified_only_after_second_attempt(self):
        _, registry = make_memory_registry()
        first = registry.execute(action("retry_operation", {"operation": "read_file", "attempt": 1}, "low"))
        second = registry.execute(action("retry_operation", {"operation": "read_file", "attempt": 2}, "low"))
        self.assertFalse(first.verified)
        self.assertTrue(second.verified)
