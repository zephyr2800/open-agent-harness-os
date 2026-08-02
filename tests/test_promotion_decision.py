from __future__ import annotations

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
from experiments.promotion_decision import decide
from experiments.promotion_protocols import DEFAULT_PROMOTION_PROTOCOL, protocol_task_spec_hashes


def _run(task_spec: str, seed: int, *, passed: bool = True) -> dict:
    rate = 1.0 if passed else 0.5
    return {
        "task_spec": f"C:/fixtures/{task_spec}",
        "task_spec_sha256": REQUIRED_FROZEN_FIXTURE_HASHES.get(task_spec, "unknown"),
        "seed": seed,
        "complete": True,
        "task_count": 2,
        "rows": [{"verified_success": passed}, {"verified_success": passed}],
        "verified_success_rate": rate,
        "independent_success_rate": rate,
        "trace_valid_rate": 1.0,
        "runtime_replay_agreement": 1.0,
        "unsafe_attempts": 0,
        "elapsed_seconds": 1.0,
        "runtime": {"cuda_available": False},
    }


def _write_required_audit(path: Path) -> Path:
    path.write_text(json.dumps({
        "schema": "train-holdout-audit/v1",
        "passed": True,
        "overlap_count": 0,
        "train": [{"path": "clean-train.jsonl", "sha256": "a" * 64, "rows": 1}],
        "fixtures": [
            {"path": f"C:/fixtures/{name}", "sha256": digest, "tasks": 1}
            for name, digest in REQUIRED_FROZEN_FIXTURE_HASHES.items()
        ],
    }), encoding="utf-8")
    return path


def _bound_checkpoint(path: Path, audit: Path, *, training_digest: str | None = None) -> Path:
    checkpoint = path / "checkpoint"
    checkpoint.mkdir()
    source = dict(validate_required_audit_manifest(audit)["training_sources"][0])
    if training_digest is not None:
        source["sha256"] = training_digest
    training_manifest = {"schema": "lora-sft-run/v0", "training_data": source}
    training_bytes = (json.dumps(training_manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (checkpoint / "training_manifest.json").write_bytes(training_bytes)
    (checkpoint / "merge_manifest.json").write_text(json.dumps({
        "schema": "merged-lora-checkpoint/v2",
        "training_manifest": "training_manifest.json",
        "training_manifest_sha256": hashlib.sha256(training_bytes).hexdigest(),
        "training_data": [source],
    }), encoding="utf-8")
    (checkpoint / "model.safetensors").write_bytes(b"weights")
    return checkpoint


def _write_required_novelty_audit(
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


def _attach_audit(
    matrix: dict,
    path: Path,
    checkpoint: Path,
    *,
    promotion_protocol: str = DEFAULT_PROMOTION_PROTOCOL,
) -> Path:
    audit_gate = validate_required_audit_manifest(path)
    required_hashes = protocol_task_spec_hashes(promotion_protocol)
    novelty = _write_required_novelty_audit(
        path.with_name("holdout-novelty.json"),
        path,
        promotion_protocol=promotion_protocol,
    )
    novelty_gate = validate_novelty_manifest(
        novelty,
        expected_training_sources=audit_gate["training_sources"],
        expected_task_spec_hashes=required_hashes,
    )
    matrix["checkpoint"] = str(checkpoint)
    matrix["train_holdout_audit"] = audit_gate
    matrix["holdout_novelty_audit"] = novelty_gate
    matrix["checkpoint_training_binding"] = validate_checkpoint_training_binding(checkpoint, audit_gate)
    matrix["task_spec_hashes"] = [
        {"path": f"C:/fixtures/{name}", "sha256": digest}
        for name, digest in required_hashes.items()
    ]
    return novelty


class PromotionDecisionTests(unittest.TestCase):
    def test_requires_every_frozen_slice_and_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = _write_required_audit(root / "audit.json")
            checkpoint = _bound_checkpoint(root, audit)
            matrix = {
                "schema": "promotion-matrix/v1",
                "seeds": [0, 1, 2],
                "runs": [
                    _run("task-spec-research-v4.json", seed)
                    for seed in (0, 1, 2)
                ] + [
                    _run("task-spec-industry-proxy-v1.json", seed)
                    for seed in (0, 1, 2)
                ] + [
                    _run("task-spec-industry-proxy-v2.json", seed)
                    for seed in (0, 1, 2)
                ],
            }
            novelty = _attach_audit(matrix, audit, checkpoint)
            result = decide(matrix, audit, novelty)
        self.assertTrue(result["passed"])
        self.assertEqual(result["decision"], "promote")
        self.assertTrue(result["gates"]["required_train_holdout_audit"])
        self.assertTrue(result["gates"]["holdout_template_novelty"])

    def test_v2_requires_the_post_freeze_author_holdout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = _write_required_audit(root / "audit.json")
            checkpoint = _bound_checkpoint(root, audit)
            matrix = {
                "schema": "promotion-matrix/v1",
                "promotion_protocol": "v2",
                "seeds": [0],
                "runs": [
                    _run("task-spec-research-v4.json", 0),
                    _run("task-spec-industry-proxy-v2.json", 0),
                    _run("task-spec-author-holdout-v1.json", 0),
                ],
            }
            novelty = _attach_audit(matrix, audit, checkpoint, promotion_protocol="v2")
            result = decide(matrix, audit, novelty, promotion_protocol="v2")
        self.assertTrue(result["passed"])
        self.assertEqual(result["promotion_protocol"], "v2")
        self.assertTrue(result["gates"]["promotion_protocol_binding"])
        self.assertIn("author_holdout_v1", result["slices"])

    def test_v2_rejects_the_legacy_high_affinity_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = _write_required_audit(root / "audit.json")
            checkpoint = _bound_checkpoint(root, audit)
            matrix = {
                "schema": "promotion-matrix/v1",
                "promotion_protocol": "v2",
                "seeds": [0],
                "runs": [
                    _run("task-spec-research-v4.json", 0),
                    _run("task-spec-industry-proxy-v1.json", 0),
                    _run("task-spec-industry-proxy-v2.json", 0),
                ],
            }
            novelty = _attach_audit(matrix, audit, checkpoint, promotion_protocol="v2")
            result = decide(matrix, audit, novelty, promotion_protocol="v2")
        self.assertFalse(result["passed"])
        self.assertFalse(result["gates"]["required_slices_present"])
        self.assertFalse(result["gates"]["no_unknown_task_specs"])
        self.assertEqual(result["task_spec_hash_gate"]["expected_hashes"], protocol_task_spec_hashes("v2"))

    def test_v2_rejects_a_matrix_declared_under_another_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = _write_required_audit(root / "audit.json")
            checkpoint = _bound_checkpoint(root, audit)
            matrix = {
                "schema": "promotion-matrix/v1",
                "promotion_protocol": "v1",
                "seeds": [0],
                "runs": [
                    _run("task-spec-research-v4.json", 0),
                    _run("task-spec-industry-proxy-v2.json", 0),
                    _run("task-spec-author-holdout-v1.json", 0),
                ],
            }
            novelty = _attach_audit(matrix, audit, checkpoint, promotion_protocol="v2")
            result = decide(matrix, audit, novelty, promotion_protocol="v2")
        self.assertFalse(result["passed"])
        self.assertFalse(result["gates"]["promotion_protocol_binding"])

    def test_rejects_incomplete_matrix_even_if_present_rows_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = _write_required_audit(root / "audit.json")
            checkpoint = _bound_checkpoint(root, audit)
            matrix = {
                "schema": "promotion-matrix/v1",
                "seeds": [0, 1, 2],
                "runs": [
                    _run("task-spec-research-v4.json", 0),
                    _run("task-spec-industry-proxy-v1.json", 0),
                    _run("task-spec-industry-proxy-v2.json", 0),
                ],
            }
            matrix["runs"][0]["complete"] = False
            novelty = _attach_audit(matrix, audit, checkpoint)
            result = decide(matrix, audit, novelty)
        self.assertFalse(result["passed"])
        self.assertFalse(result["gates"]["expected_run_count"])
        self.assertFalse(result["gates"]["all_required_seeds_present"])
        self.assertFalse(result["slices"]["research_v4"]["all_runs_passed"])

    def test_rejects_one_failed_slice_and_unknown_spec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = _write_required_audit(root / "audit.json")
            checkpoint = _bound_checkpoint(root, audit)
            matrix = {
                "schema": "promotion-matrix/v1",
                "runs": [
                    _run("task-spec-research-v4.json", 0),
                    _run("task-spec-industry-proxy-v1.json", 0, passed=False),
                    _run("task-spec-industry-proxy-v2.json", 0),
                    _run("other.json", 0),
                ],
            }
            novelty = _attach_audit(matrix, audit, checkpoint)
            result = decide(matrix, audit, novelty)
        self.assertFalse(result["passed"])
        self.assertEqual(result["decision"], "reject")
        self.assertFalse(result["gates"]["no_unknown_task_specs"])
        self.assertFalse(result["slices"]["industry_proxy_v1"]["all_runs_passed"])

    def test_rejects_tampered_task_spec_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = _write_required_audit(root / "audit.json")
            checkpoint = _bound_checkpoint(root, audit)
            matrix = {
                "schema": "promotion-matrix/v1",
                "seeds": [0],
                "runs": [
                    _run("task-spec-research-v4.json", 0),
                    _run("task-spec-industry-proxy-v1.json", 0),
                    _run("task-spec-industry-proxy-v2.json", 0),
                ],
            }
            novelty = _attach_audit(matrix, audit, checkpoint)
            matrix["task_spec_hashes"][0]["sha256"] = "0" * 64
            result = decide(matrix, audit, novelty)
        self.assertFalse(result["passed"])
        self.assertFalse(result["gates"]["pinned_task_spec_hashes"])

    def test_rejects_checkpoint_bound_to_different_training_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = _write_required_audit(root / "audit.json")
            checkpoint = _bound_checkpoint(root, audit, training_digest="c" * 64)
            matrix = {
                "schema": "promotion-matrix/v1",
                "seeds": [0],
                "runs": [
                    _run("task-spec-research-v4.json", 0),
                    _run("task-spec-industry-proxy-v1.json", 0),
                    _run("task-spec-industry-proxy-v2.json", 0),
                ],
            }
            novelty = _attach_audit(matrix, audit, checkpoint)
            result = decide(matrix, audit, novelty)
        self.assertFalse(result["passed"])
        self.assertFalse(result["gates"]["checkpoint_training_binding"])

    def test_rejects_missing_or_unlinked_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audit = _write_required_audit(Path(directory) / "audit.json")
            matrix = {
                "schema": "promotion-matrix/v1",
                "seeds": [0],
                "runs": [
                    _run("task-spec-research-v4.json", 0),
                    _run("task-spec-industry-proxy-v1.json", 0),
                    _run("task-spec-industry-proxy-v2.json", 0),
                ],
            }
            result = decide(matrix, audit)
        self.assertFalse(result["passed"])
        self.assertFalse(result["gates"]["required_train_holdout_audit"])

    def test_rejects_failed_or_unlinked_template_novelty_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = _write_required_audit(root / "audit.json")
            checkpoint = _bound_checkpoint(root, audit)
            matrix = {
                "schema": "promotion-matrix/v1",
                "seeds": [0],
                "runs": [
                    _run("task-spec-research-v4.json", 0),
                    _run("task-spec-industry-proxy-v1.json", 0),
                    _run("task-spec-industry-proxy-v2.json", 0),
                ],
            }
            novelty = _attach_audit(matrix, audit, checkpoint)
            payload = json.loads(novelty.read_text(encoding="utf-8"))
            payload["passed"] = False
            novelty.write_text(json.dumps(payload), encoding="utf-8")
            result = decide(matrix, audit, novelty)
        self.assertFalse(result["passed"])
        self.assertFalse(result["gates"]["holdout_template_novelty"])
        self.assertFalse(result["holdout_novelty_audit"]["report_passed"])
