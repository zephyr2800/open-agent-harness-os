import unittest
from pathlib import Path

from eval.task_spec import load_tasks
from experiments.factorial import interaction_term, run_factorial


class FactorialTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_interaction_arithmetic_requires_all_cells(self):
        scores = {
            "generic_baseline": 0.25,
            "specialized_baseline": 0.50,
            "generic_advanced": 0.40,
            "specialized_advanced": 0.90,
        }
        self.assertAlmostEqual(interaction_term(scores), 0.25)
        with self.assertRaisesRegex(ValueError, "missing factorial cells"):
            interaction_term({"generic_baseline": 0.25})

    def test_fixture_runs_all_four_cells_and_records_negative_smoke_result(self):
        tasks = load_tasks(self.ROOT / "fixtures" / "tasks" / "task-spec-v0.json")
        result = run_factorial(tasks)
        self.assertEqual(set(result["cells"]), {"generic_baseline", "specialized_baseline", "generic_advanced", "specialized_advanced"})
        self.assertEqual(result["task_count"], 8)
        self.assertAlmostEqual(result["interaction"]["verified_task_success"], -0.125)
        self.assertEqual(result["interaction"]["interpretation"], "fixture wiring only; not evidence about trained models")
        self.assertGreaterEqual(result["cells"]["generic_advanced"]["metrics"]["valid_decision_rate"], result["cells"]["generic_baseline"]["metrics"]["valid_decision_rate"])
