import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from experiments.data_split_audit import (
    REQUIRED_FROZEN_FIXTURE_HASHES,
    validate_checkpoint_training_binding,
    validate_required_audit_manifest,
)
from experiments.holdout_novelty_audit import validate_manifest as validate_novelty_manifest
from experiments.promotion_protocols import DEFAULT_PROMOTION_PROTOCOL, protocol_slices, protocol_task_spec_hashes
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


def _audit(path: Path) -> Path:
    path.write_text(json.dumps({
        "schema": "train-holdout-audit/v1",
        "passed": True,
        "overlap_count": 0,
        "train": [{"path": "clean-train.jsonl", "sha256": "b" * 64, "rows": 1}],
        "fixtures": [
            {"path": f"C:/fixtures/{name}", "sha256": digest, "tasks": 1}
            for name, digest in REQUIRED_FROZEN_FIXTURE_HASHES.items()
        ],
    }), encoding="utf-8")
    return path


def _checkpoint(path: Path, audit: Path) -> Path:
    checkpoint = path / "checkpoint"
    checkpoint.mkdir()
    source = validate_required_audit_manifest(audit)["training_sources"][0]
    training = {"schema": "lora-sft-run/v0", "training_data": source}
    training_bytes = (json.dumps(training, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (checkpoint / "training_manifest.json").write_bytes(training_bytes)
    (checkpoint / "merge_manifest.json").write_text(json.dumps({
        "schema": "merged-lora-checkpoint/v2",
        "training_manifest": "training_manifest.json",
        "training_manifest_sha256": hashlib.sha256(training_bytes).hexdigest(),
        "training_data": [source],
    }), encoding="utf-8")
    (checkpoint / "model.safetensors").write_bytes(b"weights")
    return checkpoint


def _novelty(
    path: Path,
    audit: Path,
    *,
    promotion_protocol: str = DEFAULT_PROMOTION_PROTOCOL,
) -> Path:
    audit_gate = validate_required_audit_manifest(audit)
    path.write_text(json.dumps({
        "schema": "holdout-novelty-audit/v1",
        "passed": True,
        "train": audit_gate["training_sources"],
        "task_specs": [
            {"path": f"C:/fixtures/{name}", "sha256": digest}
            for name, digest in protocol_task_spec_hashes(promotion_protocol).items()
        ],
    }), encoding="utf-8")
    return path


def _decision(
    path: Path,
    *,
    promoted: bool,
    audit: Path,
    novelty: Path,
    checkpoint: Path,
    promotion_protocol: str = DEFAULT_PROMOTION_PROTOCOL,
) -> None:
    checks = {
        "run_complete": True,
        "all_task_rows_present": True,
        "task_spec_hash_matches_pinned": True,
        "all_tasks_verified": promoted,
        "independent_replay_verified": promoted,
        "trace_valid": True,
        "runtime_replay_agreement": True,
        "zero_unsafe_attempts": True,
    }
    slices = {
        name: {"runs": [{"checks": checks} for _ in range(3)]}
        for name in protocol_slices(promotion_protocol).values()
    }
    audit_gate = validate_required_audit_manifest(audit)
    novelty_gate = validate_novelty_manifest(
        novelty,
        expected_training_sources=audit_gate["training_sources"],
        expected_task_spec_hashes=protocol_task_spec_hashes(promotion_protocol),
    )
    path.write_text(json.dumps({
        "schema": "promotion-decision/v1",
        "promotion_protocol": promotion_protocol,
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
            "required_train_holdout_audit": True,
            "holdout_template_novelty": True,
            "pinned_task_spec_hashes": True,
            "promotion_protocol_binding": True,
            "checkpoint_training_binding": True,
        },
        "train_holdout_audit": {**audit_gate, "linked_to_matrix": True},
        "holdout_novelty_audit": {**novelty_gate, "linked_to_matrix": True},
        "checkpoint_training_binding": {**validate_checkpoint_training_binding(checkpoint, audit_gate), "linked_to_matrix": True},
        "slices": slices,
    }), encoding="utf-8")


class VerifiedRLGateTests(unittest.TestCase):
    def test_passes_only_after_all_evidence_is_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = root / "decision.json"
            audit = _audit(root / "audit.json")
            novelty = _novelty(root / "novelty.json", audit)
            checkpoint = _checkpoint(root, audit)
            _decision(decision, promoted=True, audit=audit, novelty=novelty, checkpoint=checkpoint)
            external_v1 = root / "external-v1.json"
            external_v2 = root / "external-v2.json"
            _matrix(external_v1, 20)
            _matrix(external_v2, 32)
            report = check_gate(
                decision_path=decision,
                external_v1_path=external_v1,
                external_v2_path=external_v2,
                checkpoint=checkpoint,
                train_holdout_audit_path=audit,
                holdout_novelty_audit_path=novelty,
            )
            self.assertTrue(report["passed"])

    def test_capability_rejection_does_not_block_safe_research_rl(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = root / "decision.json"
            audit = _audit(root / "audit.json")
            novelty = _novelty(root / "novelty.json", audit)
            checkpoint = _checkpoint(root, audit)
            _decision(decision, promoted=False, audit=audit, novelty=novelty, checkpoint=checkpoint)
            external_v1 = root / "external-v1.json"
            external_v2 = root / "external-v2.json"
            _matrix(external_v1, 20)
            _matrix(external_v2, 32)
            report = check_gate(
                decision_path=decision,
                external_v1_path=external_v1,
                external_v2_path=external_v2,
                checkpoint=checkpoint,
                train_holdout_audit_path=audit,
                holdout_novelty_audit_path=novelty,
            )
            self.assertTrue(report["passed"])
            self.assertFalse(report["promotion"]["passed"])
            self.assertTrue(report["frozen_evidence"]["passed"])

    def test_v2_requires_a_matching_protocol_bound_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = root / "decision.json"
            audit = _audit(root / "audit.json")
            novelty = _novelty(root / "novelty.json", audit, promotion_protocol="v2")
            checkpoint = _checkpoint(root, audit)
            _decision(
                decision,
                promoted=False,
                audit=audit,
                novelty=novelty,
                checkpoint=checkpoint,
                promotion_protocol="v2",
            )
            external_v1 = root / "external-v1.json"
            external_v2 = root / "external-v2.json"
            _matrix(external_v1, 20)
            _matrix(external_v2, 32)
            report = check_gate(
                decision_path=decision,
                external_v1_path=external_v1,
                external_v2_path=external_v2,
                checkpoint=checkpoint,
                train_holdout_audit_path=audit,
                holdout_novelty_audit_path=novelty,
                promotion_protocol="v2",
            )
        self.assertTrue(report["passed"])
        self.assertTrue(report["frozen_evidence"]["promotion_protocol_bound"])

    def test_v2_rejects_a_protocol_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = root / "decision.json"
            audit = _audit(root / "audit.json")
            novelty = _novelty(root / "novelty.json", audit, promotion_protocol="v2")
            checkpoint = _checkpoint(root, audit)
            _decision(
                decision,
                promoted=False,
                audit=audit,
                novelty=novelty,
                checkpoint=checkpoint,
                promotion_protocol="v2",
            )
            payload = json.loads(decision.read_text(encoding="utf-8"))
            payload["promotion_protocol"] = "v1"
            payload["gates"]["promotion_protocol_binding"] = False
            decision.write_text(json.dumps(payload), encoding="utf-8")
            external_v1 = root / "external-v1.json"
            external_v2 = root / "external-v2.json"
            _matrix(external_v1, 20)
            _matrix(external_v2, 32)
            report = check_gate(
                decision_path=decision,
                external_v1_path=external_v1,
                external_v2_path=external_v2,
                checkpoint=checkpoint,
                train_holdout_audit_path=audit,
                holdout_novelty_audit_path=novelty,
                promotion_protocol="v2",
            )
        self.assertFalse(report["passed"])
        self.assertFalse(report["frozen_evidence"]["promotion_protocol_bound"])

    def test_historical_v1_decision_without_the_protocol_field_still_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = root / "decision.json"
            audit = _audit(root / "audit.json")
            novelty = _novelty(root / "novelty.json", audit)
            checkpoint = _checkpoint(root, audit)
            _decision(decision, promoted=False, audit=audit, novelty=novelty, checkpoint=checkpoint)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            payload.pop("promotion_protocol")
            payload["gates"].pop("promotion_protocol_binding")
            decision.write_text(json.dumps(payload), encoding="utf-8")
            external_v1 = root / "external-v1.json"
            external_v2 = root / "external-v2.json"
            _matrix(external_v1, 20)
            _matrix(external_v2, 32)
            report = check_gate(
                decision_path=decision,
                external_v1_path=external_v1,
                external_v2_path=external_v2,
                checkpoint=checkpoint,
                train_holdout_audit_path=audit,
                holdout_novelty_audit_path=novelty,
            )
        self.assertTrue(report["passed"])
        self.assertTrue(report["frozen_evidence"]["legacy_v1_decision"])

    def test_per_run_task_spec_hash_mismatch_blocks_research_rl(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = root / "decision.json"
            audit = _audit(root / "audit.json")
            novelty = _novelty(root / "novelty.json", audit)
            checkpoint = _checkpoint(root, audit)
            _decision(decision, promoted=False, audit=audit, novelty=novelty, checkpoint=checkpoint)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            payload["slices"]["research_v4"]["runs"][0]["checks"]["task_spec_hash_matches_pinned"] = False
            decision.write_text(json.dumps(payload), encoding="utf-8")
            external_v1 = root / "external-v1.json"
            external_v2 = root / "external-v2.json"
            _matrix(external_v1, 20)
            _matrix(external_v2, 32)
            report = check_gate(
                decision_path=decision,
                external_v1_path=external_v1,
                external_v2_path=external_v2,
                checkpoint=checkpoint,
                train_holdout_audit_path=audit,
                holdout_novelty_audit_path=novelty,
            )
            self.assertFalse(report["passed"])
            self.assertFalse(report["frozen_evidence"]["integrity_checks_passed"])

    def test_missing_diagnostic_blocks_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = root / "decision.json"
            audit = _audit(root / "audit.json")
            novelty = _novelty(root / "novelty.json", audit)
            checkpoint = _checkpoint(root, audit)
            _decision(decision, promoted=True, audit=audit, novelty=novelty, checkpoint=checkpoint)
            external_v1 = root / "external-v1.json"
            _matrix(external_v1, 20)
            report = check_gate(
                decision_path=decision,
                external_v1_path=external_v1,
                external_v2_path=root / "missing.json",
                checkpoint=checkpoint,
                train_holdout_audit_path=audit,
                holdout_novelty_audit_path=novelty,
            )
            self.assertFalse(report["passed"])

    def test_bad_or_unlinked_audit_blocks_research_rl(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = _audit(root / "audit.json")
            novelty = _novelty(root / "novelty.json", audit)
            decision = root / "decision.json"
            checkpoint = _checkpoint(root, audit)
            _decision(decision, promoted=False, audit=audit, novelty=novelty, checkpoint=checkpoint)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            payload["train_holdout_audit"]["linked_to_matrix"] = False
            decision.write_text(json.dumps(payload), encoding="utf-8")
            external_v1 = root / "external-v1.json"
            external_v2 = root / "external-v2.json"
            _matrix(external_v1, 20)
            _matrix(external_v2, 32)
            report = check_gate(
                decision_path=decision,
                external_v1_path=external_v1,
                external_v2_path=external_v2,
                checkpoint=checkpoint,
                train_holdout_audit_path=audit,
                holdout_novelty_audit_path=novelty,
            )
        self.assertFalse(report["passed"])
        self.assertFalse(report["frozen_evidence"]["train_holdout_audit_linked"])

    def test_failed_or_unlinked_template_novelty_blocks_research_rl(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision = root / "decision.json"
            audit = _audit(root / "audit.json")
            novelty = _novelty(root / "novelty.json", audit)
            checkpoint = _checkpoint(root, audit)
            _decision(decision, promoted=False, audit=audit, novelty=novelty, checkpoint=checkpoint)
            payload = json.loads(decision.read_text(encoding="utf-8"))
            payload["holdout_novelty_audit"]["linked_to_matrix"] = False
            decision.write_text(json.dumps(payload), encoding="utf-8")
            external_v1 = root / "external-v1.json"
            external_v2 = root / "external-v2.json"
            _matrix(external_v1, 20)
            _matrix(external_v2, 32)
            report = check_gate(
                decision_path=decision,
                external_v1_path=external_v1,
                external_v2_path=external_v2,
                checkpoint=checkpoint,
                train_holdout_audit_path=audit,
                holdout_novelty_audit_path=novelty,
            )
        self.assertFalse(report["passed"])
        self.assertFalse(report["frozen_evidence"]["holdout_novelty_audit_linked"])
