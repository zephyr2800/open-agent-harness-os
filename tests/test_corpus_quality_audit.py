from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from experiments.corpus_quality_audit import audit, main


def _row(task_id: str, goal: str, kind: str, *, source: str = "synthetic", stratum: str = "state") -> dict[str, object]:
    return {
        "schema": "action-sft/v0",
        "task_id": task_id,
        "input": {"task_id": task_id, "goal": goal, "state": {}, "available_tools": [], "token_budget": 64},
        "target": {"task_id": task_id, "kind": kind, "schema": "action-ir/v0"},
        "provenance": {"source": source, "sampling_stratum": stratum},
    }


class CorpusQualityAuditTests(unittest.TestCase):
    def test_audit_reports_structural_distributions_without_raw_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "train.jsonl"
            source.write_text(
                "\n".join(json.dumps(row) for row in [
                    _row("a", "private-goal-alpha", "act", source="synthetic-a", stratum="retry"),
                    _row("b", "private-goal-beta", "abstain", source="synthetic-b", stratum="boundary"),
                ]) + "\n",
                encoding="utf-8",
            )
            report = audit([source], require_unique_rows=True, require_unique_inputs=True)
        rendered = json.dumps(report, sort_keys=True)
        self.assertTrue(report["passed"])
        self.assertEqual(report["row_count"], 2)
        self.assertEqual(report["distributions"]["target_kind"], {"abstain": 1, "act": 1})
        self.assertEqual(report["duplicate_checks"]["inputs"]["duplicate_groups"], 0)
        self.assertNotIn("private-goal-alpha", rendered)
        self.assertNotIn("private-goal-beta", rendered)

    def test_audit_fails_closed_for_expected_hash_or_duplicate_input_when_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "train.jsonl"
            first = _row("a", "goal", "act")
            second = dict(first)
            second["target"] = {"task_id": "a", "kind": "finish", "schema": "action-ir/v0"}
            source.write_text("\n".join(json.dumps(row) for row in [first, second]) + "\n", encoding="utf-8")
            report = audit(
                [source],
                expected_sha256=["0" * 64],
                require_unique_rows=True,
                require_unique_inputs=True,
            )
        self.assertFalse(report["passed"])
        self.assertFalse(report["assertions"]["source_hashes_match"])
        self.assertFalse(report["assertions"]["unique_inputs"])
        self.assertTrue(report["assertions"]["unique_rows"])

    def test_explicit_source_label_redacts_the_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "private-source.jsonl"
            source.write_text(json.dumps(_row("a", "goal", "act")) + "\n", encoding="utf-8")
            report = audit([source], source_labels=["work/clean-action-mixture.jsonl"])
        rendered = json.dumps(report, sort_keys=True)
        self.assertEqual(report["sources"][0]["source"], "work/clean-action-mixture.jsonl")
        self.assertNotIn(str(source), rendered)

    def test_cli_writes_a_machine_readable_failure_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "train.jsonl"
            output = root / "audit.json"
            row = _row("a", "goal", "act")
            source.write_text("\n".join([json.dumps(row), json.dumps(row)]) + "\n", encoding="utf-8")
            with mock.patch.object(sys, "argv", [
                "corpus_quality_audit", "--train-jsonl", str(source), "--output", str(output), "--require-unique-rows",
            ]):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(), 2)
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertFalse(report["passed"])
        self.assertEqual(report["duplicate_checks"]["exact_rows"]["excess_rows"], 1)


if __name__ == "__main__":
    unittest.main()
