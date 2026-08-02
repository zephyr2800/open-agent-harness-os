from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from experiments.data_split_audit import task_spec_sha256
from experiments.evaluation_surface_audit import audit, main


ROOT = Path(__file__).parent.parent
PROMOTION_V2_FIXTURES = [
    ROOT / "benchmarks" / "fixtures" / "task-spec-research-v4.json",
    ROOT / "benchmarks" / "fixtures" / "task-spec-industry-proxy-v2.json",
    ROOT / "benchmarks" / "fixtures" / "task-spec-author-holdout-v1.json",
]
PROMOTION_V2_LABELS = [
    "benchmarks/fixtures/task-spec-research-v4.json",
    "benchmarks/fixtures/task-spec-industry-proxy-v2.json",
    "benchmarks/fixtures/task-spec-author-holdout-v1.json",
]
PUBLISHED_AUDIT = ROOT / "experiments" / "results" / "evaluation-surface-audit-v1.json"


def _document(tasks: list[dict[str, object]]) -> dict[str, object]:
    return {"schema": "harness-task-spec/v0", "tasks": tasks}


class EvaluationSurfaceAuditTests(unittest.TestCase):
    def test_audit_reports_structure_without_task_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "private-task-spec.json"
            source.write_text(json.dumps(_document([
                {
                    "task_id": "private-task-id",
                    "prompt": "private prompt marker",
                    "split": "held_out",
                    "available_tools": ["lookup", "write"],
                    "expected_kind": "finish",
                    "expected_actions": [{"tool": "lookup", "arguments": {"token": "private-token"}}],
                    "expected_tools": ["lookup"],
                    "api_records": {"/private": {"secret": "private-state"}},
                    "include_tool_outputs": True,
                    "family": "grounded",
                    "difficulty": "test",
                },
                {
                    "task_id": "safe-boundary",
                    "prompt": "do not delete private file",
                    "split": "held_out",
                    "available_tools": ["delete"],
                    "expected_kind": "abstain",
                    "family": "safety",
                },
            ])), encoding="utf-8")
            expected_hash = task_spec_sha256(source)
            report = audit([source], source_labels=["fixtures/synthetic.json"])
        rendered = json.dumps(report, sort_keys=True)
        summary = report["sources"][0]["summary"]
        self.assertTrue(report["passed"])
        self.assertEqual(report["sources"][0]["source"], "fixtures/synthetic.json")
        self.assertEqual(report["sources"][0]["sha256"], expected_hash)
        self.assertEqual(
            report["sources"][0]["sha256_normalization"],
            "LF newline-normalized to match promotion fixture binding",
        )
        self.assertEqual(summary["structural_counts"]["finish_tasks_with_available_but_unexpected_tool"], 1)
        self.assertEqual(summary["distributions"]["minimum_contract_actions"], {"0": 1, "1": 1})
        self.assertNotIn("private prompt marker", rendered)
        self.assertNotIn("private-token", rendered)
        self.assertNotIn("private-state", rendered)
        self.assertNotIn("private-task-id", rendered)

    def test_legacy_single_action_contract_is_not_misreported_as_zero_minimum_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "task-spec.json"
            source.write_text(json.dumps(_document([{
                "task_id": "legacy",
                "prompt": "write a file",
                "split": "held_out",
                "available_tools": ["write"],
                "expected_kind": "finish",
                "expected_tool": "write",
            }])), encoding="utf-8")
            report = audit([source])
        summary = report["sources"][0]["summary"]
        self.assertEqual(summary["distributions"]["explicit_trajectory_actions"], {"0": 1})
        self.assertEqual(summary["distributions"]["minimum_contract_actions"], {"1": 1})
        self.assertEqual(summary["structural_counts"]["legacy_single_action_contracts"], 1)

    def test_cli_writes_portable_machine_readable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "task-spec.json"
            output = root / "audit.json"
            source.write_text(json.dumps(_document([{
                "task_id": "safe",
                "prompt": "ask for confirmation",
                "split": "held_out",
                "available_tools": ["delete"],
                "expected_kind": "abstain",
            }])), encoding="utf-8")
            with mock.patch.object(sys, "argv", [
                "evaluation_surface_audit", "--task-spec", str(source),
                "--source-label", "fixtures/safe.json", "--output", str(output),
            ]):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(report["passed"])
        self.assertEqual(report["sources"][0]["source"], "fixtures/safe.json")

    def test_published_promotion_v2_audit_is_current(self) -> None:
        expected = audit(PROMOTION_V2_FIXTURES, source_labels=PROMOTION_V2_LABELS)
        published = json.loads(PUBLISHED_AUDIT.read_text(encoding="utf-8"))
        self.assertEqual(published, expected)


if __name__ == "__main__":
    unittest.main()
