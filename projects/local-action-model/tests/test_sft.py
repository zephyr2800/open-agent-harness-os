import unittest

from data.sft import trajectory_to_sft_examples
from action_ir.trajectory import append_event


class SFTTests(unittest.TestCase):
    def test_decision_request_and_decision_become_one_example(self):
        events = []
        append_event(events, "task-1", "decision_request", {"goal": "read status", "available_tools": ["read_file"]})
        append_event(events, "task-1", "decision", {"decision": {"kind": "abstain", "reason": "fixture"}})
        append_event(events, "task-1", "trajectory_end", {"outcome": "abstained"})
        examples = trajectory_to_sft_examples(events)
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["schema"], "action-sft/v0")
        self.assertEqual(examples[0]["target"]["kind"], "abstain")

    def test_trajectory_without_decisions_has_no_examples(self):
        events = []
        append_event(events, "task-1", "decision_request", {})
        append_event(events, "task-1", "trajectory_end", {"outcome": "stopped"})
        self.assertEqual(trajectory_to_sft_examples(events), [])
