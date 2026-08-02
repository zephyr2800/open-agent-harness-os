from __future__ import annotations

import unittest
from pathlib import Path

from benchmarks.generate_author_holdout_v1 import TASK_COUNT, build_tasks, render
from benchmarks.tasks import load_tasks


ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "benchmarks" / "fixtures" / "task-spec-author-holdout-v1.json"


class AuthorHoldoutV1Tests(unittest.TestCase):
    def test_fixture_is_the_deterministic_generator_output(self) -> None:
        self.assertEqual(FIXTURE.read_text(encoding="utf-8"), render())

    def test_all_tasks_require_grounded_ordered_actions(self) -> None:
        tasks = load_tasks(FIXTURE)
        self.assertEqual(len(tasks), TASK_COUNT)
        self.assertEqual({task.split for task in tasks}, {"author_holdout_v1"})
        self.assertTrue(all(task.expected_kind == "finish" for task in tasks))
        self.assertTrue(all(task.include_tool_outputs and task.adversarial for task in tasks))
        self.assertTrue(all(task.expected_actions and task.expected_files for task in tasks))
        self.assertTrue(all(task.expected_actions[0]["tool"] in {"api_get", "browser_open"} for task in tasks))

    def test_cross_source_and_custody_families_cannot_skip_the_grounding_step(self) -> None:
        tasks = {task.task_id: task for task in load_tasks(FIXTURE)}
        cross_source = tasks["author-v1-cross-source-00"]
        custody = tasks["author-v1-custody-00"]
        self.assertEqual([action["tool"] for action in cross_source.expected_actions], ["api_get", "browser_open", "write_file"])
        self.assertEqual([action["tool"] for action in custody.expected_actions], ["api_get", "write_file", "move_file"])
        self.assertIn("UNTRUSTED", cross_source.api_records["/author-v1/reconcile/00"]["note"])
        self.assertIn("UNTRUSTED", custody.api_records["/author-v1/custody/00"]["message"])


if __name__ == "__main__":
    unittest.main()
