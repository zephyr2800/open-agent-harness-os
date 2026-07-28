import unittest

from data.midtrain import build_midtrain_examples
from eval.task_spec import load_tasks


class MidtrainTests(unittest.TestCase):
    ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]

    def test_midtrain_rows_are_explicitly_synthetic_and_schemaed(self):
        tasks = load_tasks(self.ROOT / "fixtures" / "tasks" / "task-spec-v0.json")
        rows = build_midtrain_examples(tasks)
        self.assertEqual(len(rows), 16)
        self.assertTrue(all(row["schema"] == "action-midtrain/v0" for row in rows))
        self.assertTrue(all(row["provenance"]["synthetic"] for row in rows))
        self.assertTrue(all(row["text"] for row in rows))
