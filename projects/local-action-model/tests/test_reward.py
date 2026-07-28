import unittest

from eval.benchmark import reference_policy
from eval.reward import reward_decision
from eval.task_spec import load_tasks
from data.preferences import hard_negative


class RewardTests(unittest.TestCase):
    ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]

    def test_verified_reference_beats_declared_hard_negative(self):
        tasks = load_tasks(self.ROOT / "fixtures" / "tasks" / "task-spec-v0.json")
        for task in tasks:
            chosen = reference_policy(task)
            rejected, _ = hard_negative(task, chosen)
            self.assertGreater(reward_decision(task, chosen)["reward"], reward_decision(task, rejected)["reward"])
