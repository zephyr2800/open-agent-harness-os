import unittest
from pathlib import Path

from eval.task_spec import load_tasks
from eval.verified import evaluate_verified, verify_decision
from eval.benchmark import reference_policy


class VerifiedEvaluationTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_reference_policy_passes_stateful_verifiers(self):
        tasks = load_tasks(self.ROOT / "fixtures" / "tasks" / "task-spec-v0.json")
        result = evaluate_verified(reference_policy, tasks)
        self.assertEqual(result["metrics"]["verified_task_success"], 1.0)
        self.assertGreater(result["metrics"]["action_execution_rate"], 0.0)
        self.assertEqual(result["metrics"]["independent_verification_rate"], 1.0)

    def test_wrong_write_content_fails_even_if_protocol_is_valid(self):
        tasks = load_tasks(self.ROOT / "fixtures" / "tasks" / "task-spec-v0.json")
        task = next(task for task in tasks if task.task_id == "write_note")
        decision = reference_policy(task)
        decision["action"]["arguments"]["content"] = "wrong"
        outcome = verify_decision(task, decision)
        self.assertTrue(outcome.protocol_valid)
        self.assertTrue(outcome.action_executed)
        self.assertFalse(outcome.success)
        self.assertIn("wrong_arguments", outcome.errors)

    def test_wrong_decision_kind_is_a_structured_failure(self):
        tasks = load_tasks(self.ROOT / "fixtures" / "tasks" / "task-spec-v0.json")
        task = next(task for task in tasks if task.task_id == "verify_finish")
        decision = reference_policy(task)
        decision["kind"] = "abstain"
        decision.pop("finish")
        decision["abstention"] = {"reason": "not ready", "alternatives": ["wait"]}
        outcome = verify_decision(task, decision)
        self.assertTrue(outcome.protocol_valid)
        self.assertFalse(outcome.success)
        self.assertIn("wrong_decision_kind", outcome.errors)

    def test_finish_requires_declared_verifier_receipt_when_task_provides_one(self):
        tasks = load_tasks(self.ROOT / "fixtures" / "tasks" / "task-spec-qwopus35-9b-rl-v1.json")
        task = next(task for task in tasks if task.task_id == "rl-finish-01")
        decision = reference_policy(task)
        decision["finish"]["evidence"] = ["check:invented-by-model"]
        rejected = verify_decision(task, decision)
        self.assertFalse(rejected.success)
        self.assertFalse(rejected.independently_verified)

        decision["finish"]["evidence"] = list(task.verified_evidence)
        accepted = verify_decision(task, decision)
        self.assertTrue(accepted.success)
        self.assertTrue(accepted.independently_verified)
