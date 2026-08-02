from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from experiments.holdout_novelty_audit import audit, main, validate_manifest


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def _write_tasks(path: Path, tasks: list[dict]) -> Path:
    path.write_text(json.dumps({"schema": "harness-task-spec/v0", "tasks": tasks}), encoding="utf-8")
    return path


class HoldoutNoveltyAuditTests(unittest.TestCase):
    def test_reports_high_affinity_after_identifier_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train = _write_jsonl(root / "train.jsonl", [{
                "task_id": "train-1",
                "input": {"goal": "Prepare the bounded release: write recovery_draft_001.cfg, retry publish_001, then write recovery_audit_001.txt after verification."},
            }])
            tasks = _write_tasks(root / "tasks.json", [{
                "task_id": "held-1",
                "prompt": "Prepare the bounded release: write recovery_draft_999.cfg, retry publish_999, then write recovery_audit_999.txt after verification.",
            }])
            report = audit([train], [tasks], max_normalized_token_jaccard=0.55, max_high_affinity_rate=0.0)
        record = report["task_specs"][0]["task_records"][0]
        self.assertGreater(record["max_normalized_token_jaccard"], 0.95)
        self.assertEqual(record["nearest_training_task_id"], "train-1")
        self.assertTrue(record["high_affinity"])
        self.assertFalse(report["passed"])

    def test_manifest_binds_the_exact_training_and_task_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train = _write_jsonl(root / "train.jsonl", [{"task_id": "train-1", "input": {"goal": "Sort the blue inventory records by aisle."}}])
            tasks = _write_tasks(root / "tasks.json", [{"task_id": "held-1", "prompt": "Schedule a ferry crossing for the coastal survey."}])
            report = audit([train], [tasks], max_normalized_token_jaccard=0.55, max_high_affinity_rate=0.0)
            manifest = root / "novelty.json"
            manifest.write_text(json.dumps(report), encoding="utf-8")
            expected_sources = report["train"]
            expected_specs = {tasks.name: report["task_specs"][0]["sha256"]}
            valid = validate_manifest(
                manifest,
                expected_training_sources=expected_sources,
                expected_task_spec_hashes=expected_specs,
            )
            invalid = validate_manifest(
                manifest,
                expected_training_sources=expected_sources,
                expected_task_spec_hashes={tasks.name: "0" * 64},
            )
        self.assertTrue(report["passed"])
        self.assertTrue(valid["passed"])
        self.assertFalse(invalid["passed"])
        self.assertFalse(invalid["task_specs_match"])

    def test_cli_fails_only_when_requested_for_high_affinity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train = _write_jsonl(root / "train.jsonl", [{"task_id": "train-1", "input": {"goal": "Write report_001.txt after verification."}}])
            tasks = _write_tasks(root / "tasks.json", [{"task_id": "held-1", "prompt": "Write report_999.txt after verification."}])
            output = root / "novelty.json"
            with mock.patch.object(sys, "argv", [
                "holdout_novelty_audit", "--train-jsonl", str(train), "--task-spec", str(tasks),
                "--manifest", str(output), "--max-high-affinity-rate", "0", "--fail-on-affinity",
            ]):
                with redirect_stdout(io.StringIO()):
                    exit_code = main()
            self.assertEqual(exit_code, 2)
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
