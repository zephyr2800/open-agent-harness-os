from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from experiments.scorecard import build_scorecard


class ScorecardTests(unittest.TestCase):
    def test_scorecard_reports_macro_family_failures_separately(self) -> None:
        rows = [
            {"task_id": "a-1", "family": "easy", "verified_success": True, "protocol_valid": True, "trace_valid": True, "runtime_replay_agreement": True},
            {"task_id": "a-2", "family": "easy", "verified_success": True, "protocol_valid": True, "trace_valid": True, "runtime_replay_agreement": True},
            {"task_id": "b-1", "family": "hard", "verified_success": False, "protocol_valid": True, "trace_valid": True, "runtime_replay_agreement": True, "false_completion": True},
        ]
        result = build_scorecard(
            rows,
            suite="fixture-v1",
            suite_kind="local_fixture",
            model="m",
            harness="h",
            task_spec_sha256="abc",
            execution_budget={"max_steps": 6},
            runtime={"device": "cpu"},
        )
        self.assertEqual(result["verified_success_rate"], 2 / 3)
        self.assertEqual(result["macro_family_success_rate"], 0.5)
        self.assertEqual(result["by_family"]["hard"]["false_completion_rate"], 1.0)
        self.assertIn("do not describe as an external", result["claim_boundary"])
        self.assertEqual(result["task_spec_sha256"], "abc")
        self.assertEqual(result["execution_budget"]["max_steps"], 6)
        self.assertEqual(result["runtime"]["device"], "cpu")
        self.assertEqual(result["metric_coverage"]["protocol_valid"], 1.0)
        self.assertEqual(result["metric_coverage"]["unsafe_attempt"], 0.0)
        self.assertIsNone(result["unsafe_attempt_rate"])

    def test_independent_trace_fields_are_promoted_from_nested_audit(self) -> None:
        result = build_scorecard(
            [{
                "task_id": "t",
                "family": "security",
                "verified_success": True,
                "protocol_valid": True,
                "independent": {"trace_valid": True, "matches_runtime": True},
                "adversarial": True,
                "abstained": True,
                "unsafe_attempt": False,
                "false_completion": False,
            }],
            suite="fixture-v2",
            suite_kind="local_fixture",
            model="m",
            harness="h",
        )
        self.assertEqual(result["trace_valid_rate"], 1.0)
        self.assertEqual(result["runtime_replay_agreement"], 1.0)
        self.assertEqual(result["safe_abstain_rate"], 1.0)

    def test_safe_abstain_excludes_failed_or_unsafe_abstentions(self) -> None:
        result = build_scorecard(
            [
                {"task_id": "safe", "family": "security", "verified_success": True, "adversarial": True, "abstained": True, "unsafe_attempt": False, "false_completion": False},
                {"task_id": "unsafe", "family": "security", "verified_success": True, "adversarial": True, "abstained": True, "unsafe_attempt": True, "false_completion": False},
                {"task_id": "failed", "family": "security", "verified_success": False, "adversarial": True, "abstained": True, "unsafe_attempt": False, "false_completion": False},
            ],
            suite="fixture-safety-v1",
            suite_kind="local_fixture",
            model="m",
            harness="h",
        )
        self.assertEqual(result["adversarial_task_runs"], 3)
        self.assertEqual(result["safe_abstain_rate"], 1 / 3)

    def test_external_scorecard_requires_native_provenance(self) -> None:
        report_path = Path(__file__)
        report_sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "hexadecimal suite_commit"):
            build_scorecard(
                [{"task_id": "t", "verified_success": True}],
                suite="agentdojo",
                suite_kind="external_native",
                model="m",
                harness="h",
            )
        result = build_scorecard(
            [{"task_id": "t", "verified_success": True}],
            suite="agentdojo",
            suite_kind="external_native",
            suite_commit="abcdef1234567",
            native_metric="utility",
            native_metric_value=0.75,
            native_report_sha256=report_sha256,
            native_report_path=report_path,
            native_grader="agentdojo-native-grader",
            native_environment={"runner": "docker", "runtime": "python-3.12", "platform": "linux-x86_64"},
            model="m",
            harness="h",
        )
        self.assertEqual(result["claim_boundary"], "native external-suite result; report the suite's native metric")
        self.assertEqual(result["native_metric_value"], 0.75)
        self.assertEqual(result["metric_coverage"]["unsafe_attempt"], 0.0)
        self.assertIsNone(result["unsafe_attempt_rate"])

    def test_partial_observation_does_not_publish_a_zero_rate(self) -> None:
        result = build_scorecard(
            [
                {"task_id": "observed", "verified_success": True, "unsafe_attempt": False},
                {"task_id": "unobserved", "verified_success": True},
            ],
            suite="fixture-coverage-v1",
            suite_kind="local_fixture",
            model="m",
            harness="h",
        )
        self.assertEqual(result["metric_coverage"]["unsafe_attempt"], 0.5)
        self.assertIsNone(result["unsafe_attempt_rate"])

    def test_external_scorecard_rejects_empty_or_incomplete_provenance(self) -> None:
        kwargs = {
            "suite": "agentdojo",
            "suite_kind": "external_native",
            "model": "m",
            "harness": "h",
            "suite_commit": "abcdef1234567",
            "native_metric": "utility",
            "native_metric_value": 0.75,
            "native_report_sha256": "0" * 64,
            "native_report_path": Path(__file__),
            "native_grader": "grader",
            "native_environment": {"runner": "docker", "runtime": "python-3.12", "platform": "linux-x86_64"},
        }
        with self.assertRaisesRegex(ValueError, "at least one task row"):
            build_scorecard([], **kwargs)
        with self.assertRaisesRegex(ValueError, "native_metric_value"):
            build_scorecard([{"task_id": "t", "verified_success": True}], **{**kwargs, "native_metric_value": None})
        with self.assertRaisesRegex(ValueError, "incomplete native run"):
            build_scorecard([{"task_id": "t", "verified_success": True}], **{**kwargs, "native_run_complete": False})
        with self.assertRaisesRegex(ValueError, "does not match"):
            build_scorecard([{"task_id": "t", "verified_success": True}], **kwargs)


if __name__ == "__main__":
    unittest.main()
