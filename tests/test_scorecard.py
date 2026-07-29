from __future__ import annotations

import unittest

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
                {"task_id": "safe", "family": "security", "verified_success": True, "adversarial": True, "abstained": True},
                {"task_id": "unsafe", "family": "security", "verified_success": True, "adversarial": True, "abstained": True, "unsafe_attempt": True},
                {"task_id": "failed", "family": "security", "verified_success": False, "adversarial": True, "abstained": True},
            ],
            suite="fixture-safety-v1",
            suite_kind="local_fixture",
            model="m",
            harness="h",
        )
        self.assertEqual(result["adversarial_task_runs"], 3)
        self.assertEqual(result["safe_abstain_rate"], 1 / 3)

    def test_external_scorecard_requires_native_provenance(self) -> None:
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
            native_report_sha256="0" * 64,
            native_grader="agentdojo-native-grader",
            native_environment={"runner": "docker", "runtime": "python-3.12", "platform": "linux-x86_64"},
            model="m",
            harness="h",
        )
        self.assertEqual(result["claim_boundary"], "native external-suite result; report the suite's native metric")
        self.assertEqual(result["native_metric_value"], 0.75)

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
            "native_grader": "grader",
            "native_environment": {"runner": "docker", "runtime": "python-3.12", "platform": "linux-x86_64"},
        }
        with self.assertRaisesRegex(ValueError, "at least one task row"):
            build_scorecard([], **kwargs)
        with self.assertRaisesRegex(ValueError, "native_metric_value"):
            build_scorecard([{"task_id": "t", "verified_success": True}], **{**kwargs, "native_metric_value": None})


if __name__ == "__main__":
    unittest.main()
