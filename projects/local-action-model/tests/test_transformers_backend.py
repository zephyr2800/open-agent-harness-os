import json
import unittest

from model.adapter import ModelRequest
from model.transformers_backend import (
    DEFAULT_MODEL_ID,
    DEFAULT_REVISION,
    TransformersActionPolicy,
    build_messages,
    normalize_quantization,
)


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

    def test_quantized_mode_is_opt_in_and_recorded(self):
        policy = TransformersActionPolicy(
            quantization="4bit",
            tokenizer=object(),
            model=object(),
        )
        self.assertEqual(policy.quantization, "4bit-nf4")

    def test_quantization_aliases_are_canonicalized(self):
        self.assertEqual(normalize_quantization("4bit"), "4bit-nf4")
        self.assertEqual(normalize_quantization("int4"), "4bit-nf4")
        self.assertEqual(normalize_quantization("nf4"), "4bit-nf4")
        self.assertIsNone(normalize_quantization(None))
        with self.assertRaises(ValueError):
            normalize_quantization("8bit")
