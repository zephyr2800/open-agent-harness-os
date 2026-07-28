import json
import unittest
from pathlib import Path

from action_ir.replay import ReplayFormatError, load_jsonl
from action_ir.trajectory import append_event


class ReplayTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_jsonl_round_trip(self):
        events = []
        append_event(events, "task-1", "decision_request", {"available_actions": ["read_file"]})
        append_event(events, "task-1", "decision", {"kind": "abstain"})
        append_event(events, "task-1", "trajectory_end", {"outcome": "abstained"})
        lines = [json.dumps(event, sort_keys=True) for event in events]
        self.assertEqual(load_jsonl(lines), events)

    def test_malformed_json_is_rejected(self):
        with self.assertRaisesRegex(ReplayFormatError, "line 1 is not valid JSON"):
            load_jsonl(["not-json"])

    def test_checked_in_fixture_is_replayable(self):
        fixture = self.ROOT / "fixtures" / "trajectories" / "reference-abstention.jsonl"
        self.assertEqual(load_jsonl(fixture.read_text(encoding="utf-8").splitlines())[-1]["event_type"], "trajectory_end")
