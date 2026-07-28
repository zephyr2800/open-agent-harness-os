import json
import tempfile
import unittest
from pathlib import Path

from experiments.verified_rl_gate import check_gate


def _matrix(path: Path, tasks: int) -> None:
    path.write_text(json.dumps({
        "schema": "promotion-matrix/v1",
        "runs": [
            {
                "task_count": tasks,
                "runtime_replay_agreement": 1.0,
                "trace_valid_rate": 1.0,
                "unsafe_attempts": 0,
            }
            for _ in range(3)
        ],
    }), encoding="utf-8")


def _decision(path: Path, *, promoted: bool) -> None:
    checks = {
        "run_complete": True,
        "all_task_rows_present": True,
        "all_tasks_verified": promoted,
        "independent_replay_verified": promoted,
        "trace_valid": True,
        "runtime_replay_agreement": True,
        "zero_unsafe_attempts": True,
    }
    slices = {
        name: {"runs": [{"checks": checks} for _ in range(3)]}
        for name in ("research_v4", "industry_proxy_v1", "industry_proxy_v2")
    }
    path.write_text(json.dumps({
        "schema": "promotion-decision/v1",
        "decision": "promote" if promoted else "reject",
        "passed": promoted,
        "gates": {
            "valid_seed_declaration": True,
            "expected_run_count": 9,
            "required_slices_present": True,
            "all_required_seeds_present": True,
            "no_duplicate_seeds": True,
            "no_unknown_task_specs": True,
            "all_frozen_runs_pass": promoted,
        },
        "slices": slices,
    }), encoding="utf-8")


class VerifiedRLGateTests(unittest.TestCase):
    def test_passes_only_after_all_evidence_is_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = root / "decision.json"
            _decision(decision, promoted=True)
            external_v1 = root / "external-v1.json"
            external_v2 = root / "external-v2.json"
            _matrix(external_v1, 20)
            _matrix(external_v2, 32)
            checkpoint = root / "checkpoint"
            checkpoint.mkdir()
            (checkpoint / "merge_manifest.json").write_text("{}", encoding="utf-8")
            (checkpoint / "model.safetensors").write_bytes(b"weights")
            report = check_gate(
                decision_path=decision,
                external_v1_path=external_v1,
                external_v2_path=external_v2,
                checkpoint=checkpoint,
            )
            self.assertTrue(report["passed"])

    def test_capability_rejection_does_not_block_safe_research_rl(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = root / "decision.json"
            _decision(decision, promoted=False)
            external_v1 = root / "external-v1.json"
            external_v2 = root / "external-v2.json"
            _matrix(external_v1, 20)
            _matrix(external_v2, 32)
            checkpoint = root / "checkpoint"
            checkpoint.mkdir()
            (checkpoint / "merge_manifest.json").write_text("{}", encoding="utf-8")
            (checkpoint / "model.safetensors").write_bytes(b"weights")
            report = check_gate(
                decision_path=decision,
                external_v1_path=external_v1,
                external_v2_path=external_v2,
                checkpoint=checkpoint,
            )
            self.assertTrue(report["passed"])
            self.assertFalse(report["promotion"]["passed"])
            self.assertTrue(report["frozen_evidence"]["passed"])

    def test_missing_diagnostic_blocks_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = root / "decision.json"
            _decision(decision, promoted=True)
            external_v1 = root / "external-v1.json"
            _matrix(external_v1, 20)
            checkpoint = root / "checkpoint"
            checkpoint.mkdir()
            (checkpoint / "merge_manifest.json").write_text("{}", encoding="utf-8")
            (checkpoint / "model.safetensors").write_bytes(b"weights")
            report = check_gate(
                decision_path=decision,
                external_v1_path=external_v1,
                external_v2_path=root / "missing.json",
                checkpoint=checkpoint,
            )
            self.assertFalse(report["passed"])
