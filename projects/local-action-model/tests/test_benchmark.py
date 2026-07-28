import unittest
from pathlib import Path

from eval.benchmark import TASKS, evaluate, reference_policy, run_reference_benchmark
from eval.task_spec import load_tasks


class BenchmarkTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_reference_fixture_is_perfect(self):
        result = run_reference_benchmark()
        self.assertEqual(result["metrics"]["task_count"], len(TASKS))
        self.assertEqual(result["metrics"]["verified_task_success"], 1.0)
        self.assertEqual(result["metrics"]["invalid_action_rate"], 0.0)
        self.assertGreater(result["metrics"]["useful_state_transitions_per_token"], 0.0)
        self.assertGreater(result["metrics"]["structured_information_density"], 0.0)

    def test_invalid_output_is_counted_as_failure(self):
        def bad_policy(task):
            return {"schema": "action-ir/v0", "task_id": task.task_id, "step_id": "x", "kind": "act"}

        result = evaluate(bad_policy, tasks=TASKS[:1])
        self.assertEqual(result["metrics"]["verified_task_success"], 0.0)
        self.assertEqual(result["metrics"]["invalid_action_rate"], 1.0)

    def test_versioned_task_spec_loads_with_unique_ids(self):
        path = self.ROOT / "fixtures" / "tasks" / "task-spec-v0.json"
        tasks = load_tasks(path)
        self.assertEqual(len(tasks), 8)
        self.assertEqual(len({task.task_id for task in tasks}), 8)
        self.assertEqual(sum(task.split == "held_out" for task in tasks), 6)
        result = evaluate(reference_policy, tasks=tasks)
        self.assertEqual(result["metrics"]["verified_task_success"], 1.0)
        self.assertEqual(result["metrics"]["correct_abstention_rate"], 1.0)
