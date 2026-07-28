import unittest

from eval.task_spec import load_tasks
from experiments.checkpoint_factorial import _run_cell
from experiments.factorial import FixtureModel, BaselineHarness


class CheckpointFactorialTests(unittest.TestCase):
    ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]

    def test_real_runner_cell_shape_accepts_provider_neutral_policy(self):
        tasks = load_tasks(self.ROOT / "fixtures" / "tasks" / "task-spec-v0.json")
        result = _run_cell(tasks, FixtureModel("specialized", tasks), BaselineHarness())
        self.assertEqual(result["metrics"]["task_count"], 8)
        self.assertEqual(result["metrics"]["protocol_valid_rate"], 1.0)
        self.assertEqual(len(result["tasks"]), 8)
        self.assertIn("raw_output", result["tasks"][0])
