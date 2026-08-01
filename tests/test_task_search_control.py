from __future__ import annotations

import unittest

from experiments.task_search_control import matched_budget


class TaskSearchControlTests(unittest.TestCase):
    def test_budget_is_split_without_exceeding_total(self) -> None:
        budget = matched_budget(attempts=2, max_steps=6, max_new_tokens=256)
        self.assertEqual(budget["max_steps_per_attempt"], 3)
        self.assertEqual(budget["max_new_tokens_per_attempt"], 128)
        self.assertLessEqual(
            budget["attempts"] * budget["max_steps_per_attempt"],
            budget["total_max_steps"],
        )
        self.assertLessEqual(
            budget["attempts"] * budget["max_new_tokens_per_attempt"],
            budget["total_max_new_tokens"],
        )

    def test_budget_rejects_more_attempts_than_total_steps(self) -> None:
        with self.assertRaises(ValueError):
            matched_budget(attempts=4, max_steps=3, max_new_tokens=256)


if __name__ == "__main__":
    unittest.main()
