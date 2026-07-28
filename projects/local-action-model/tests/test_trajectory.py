import unittest

from action_ir.trajectory import append_event, validate_trajectory


class TrajectoryTests(unittest.TestCase):
    def test_append_event_creates_replayable_lineage(self):
        events = []
        append_event(events, "task-1", "decision_request", {"available_actions": ["read_file"]})
        append_event(events, "task-1", "decision", {"kind": "abstain"})
        append_event(events, "task-1", "trajectory_end", {"outcome": "abstained"})
        self.assertEqual(validate_trajectory(events), [])

    def test_detects_tampered_parent_digest(self):
        events = []
        append_event(events, "task-1", "decision_request", {})
        append_event(events, "task-1", "trajectory_end", {})
        events[0]["payload"]["tampered"] = True
        self.assertIn("trajectory[1].parent_digest does not match the previous event", validate_trajectory(events))

    def test_requires_trajectory_end(self):
        events = []
        append_event(events, "task-1", "decision_request", {})
        self.assertIn("trajectory must end with trajectory_end", validate_trajectory(events))
