import json
import unittest
from pathlib import Path

from data.preferences import build_preference_examples
from eval.task_spec import load_tasks
from action_ir.validation import validate_decision


class PreferenceTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_pairs_have_valid_chosen_and_declared_rejected_reason(self):
        tasks = load_tasks(self.ROOT / "fixtures" / "tasks" / "task-spec-v0.json")
        examples = build_preference_examples(tasks)
        self.assertEqual(len(examples), 8)
        self.assertTrue(all(not validate_decision(example["chosen"]) for example in examples))
        self.assertTrue(all(example["rejected_reason"] for example in examples))
        self.assertTrue(all(example["provenance"]["synthetic"] is True for example in examples))

    def test_over_action_negative_is_protocol_valid_but_task_wrong(self):
        tasks = load_tasks(self.ROOT / "fixtures" / "tasks" / "task-spec-v0.json")
        example = next(item for item in build_preference_examples(tasks) if item["task_id"] == "permission_boundary")
        self.assertEqual(example["rejected"]["kind"], "act")
        self.assertEqual(validate_decision(example["rejected"]), [])
