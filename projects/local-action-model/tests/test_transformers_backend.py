import json
import unittest

from model.adapter import ModelRequest
from model.transformers_backend import DEFAULT_MODEL_ID, DEFAULT_REVISION, build_messages


class TransformersBackendTests(unittest.TestCase):
    def test_default_checkpoint_is_pinned_and_prompt_is_deterministic(self):
        request = ModelRequest("task-1", "read status", {"fact": "known"}, ("read_file", "abstain"), 128)
        messages = build_messages(request)
        self.assertEqual(DEFAULT_MODEL_ID, "Qwen/Qwen2.5-0.5B-Instruct")
        self.assertEqual(len(DEFAULT_REVISION), 40)
        self.assertEqual(messages[0]["role"], "system")
        payload = json.loads(messages[1]["content"])
        self.assertEqual(payload["available_tools"], ["read_file", "abstain"])
        self.assertIn("Required top-level fields are schema, task_id, step_id, kind, uncertainty, and state_update", messages[0]["content"])
        self.assertEqual(build_messages(request), messages)
