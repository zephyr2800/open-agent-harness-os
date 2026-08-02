from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.native_evaluation_registration import (
    RECORD_SCHEMA,
    validate_agentdojo_registration,
    validate_tau2_registration,
    verify_registration_record,
)


_TRAINING = [{"path": "clean-mixture.jsonl", "sha256": "a" * 64, "rows": 3232}]


def _registration(path: Path) -> Path:
    path.write_text(json.dumps({
        "schema": "native-external-evaluation-registration/v1",
        "registration_id": "test-registration",
        "created_before_checkpoint": "2026-08-01T00:00:00Z",
        "variants": ["model-only", "repair"],
        "checkpoint_scope": {"training_sources": [{"sha256": "a" * 64, "rows": 3232}]},
        "agentdojo": {
            "source_commit": "b" * 40,
            "benchmark_version": "v1.2.2",
            "suite": "workspace",
            "model": "openai-compatible",
            "policy": {"seed": 0, "do_sample": False, "max_new_tokens": 256, "quantization": "4bit"},
            "conditions": {
                "clean": {
                    "user_tasks": ["user_task_20"], "injection_tasks": [], "attack": None, "defense": None,
                },
                "direct_injection": {
                    "user_tasks": ["user_task_20"], "injection_tasks": ["injection_task_6"],
                    "attack": "direct", "defense": None,
                },
            },
        },
        "tau2": {
            "source_commit": "c" * 40,
            "runtime": {"tau2_version": "1.0.1", "python_version_prefix": "3.12"},
            "domain": "telecom", "task_set": "telecom", "task_split": "base",
            "task_ids": ["[mms_issue]task-a", "[service_issue]task-b"],
            "policy": {"seed": 0, "do_sample": False, "max_new_tokens": 256, "quantization": "4bit"},
            "budget": {"num_trials": 1, "max_steps": 30, "max_errors": 10, "max_concurrency": 1, "max_retries": 0},
        },
    }, indent=2), encoding="utf-8")
    return path


class NativeEvaluationRegistrationTests(unittest.TestCase):
    def test_agentdojo_registration_binds_clean_and_direct_conditions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registration = _registration(Path(directory) / "registration.json")
            clean = validate_agentdojo_registration(
                registration, training_sources=_TRAINING, variant="model-only", source_commit="b" * 40,
                benchmark_version="v1.2.2", suite="workspace", user_tasks=["user_task_20"], injection_tasks=[],
                attack=None, defense=None, seed=0, max_new_tokens=256, quantization="4bit",
            )
            direct = validate_agentdojo_registration(
                registration, training_sources=_TRAINING, variant="repair", source_commit="b" * 40,
                benchmark_version="v1.2.2", suite="workspace", user_tasks=["user_task_20"],
                injection_tasks=["injection_task_6"], attack="direct", defense=None, seed=0,
                max_new_tokens=256, quantization="4bit",
            )
        self.assertEqual(clean["schema"], RECORD_SCHEMA)
        self.assertEqual(clean["condition"], "clean")
        self.assertEqual(direct["condition"], "direct_injection")

    def test_agentdojo_registration_rejects_changed_selector_and_training_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registration = _registration(Path(directory) / "registration.json")
            with self.assertRaisesRegex(ValueError, "user-task selectors"):
                validate_agentdojo_registration(
                    registration, training_sources=_TRAINING, variant="model-only", source_commit="b" * 40,
                    benchmark_version="v1.2.2", suite="workspace", user_tasks=["user_task_99"], injection_tasks=[],
                    attack=None, defense=None, seed=0, max_new_tokens=256, quantization="4bit",
                )

    def test_registration_record_rejects_file_changes_after_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registration = _registration(Path(directory) / "registration.json")
            record = validate_agentdojo_registration(
                registration, training_sources=_TRAINING, variant="model-only", source_commit="b" * 40,
                benchmark_version="v1.2.2", suite="workspace", user_tasks=["user_task_20"], injection_tasks=[],
                attack=None, defense=None, seed=0, max_new_tokens=256, quantization="4bit",
            )
            self.assertEqual(verify_registration_record(record)["registration_id"], "test-registration")
            registration.write_text(registration.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                verify_registration_record(record)
            with self.assertRaisesRegex(ValueError, "training sources"):
                validate_agentdojo_registration(
                    registration, training_sources=[{"sha256": "d" * 64, "rows": 3232}], variant="model-only",
                    source_commit="b" * 40, benchmark_version="v1.2.2", suite="workspace", user_tasks=["user_task_20"],
                    injection_tasks=[], attack=None, defense=None, seed=0, max_new_tokens=256, quantization="4bit",
                )

    def test_tau2_registration_binds_runtime_budget_and_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registration = _registration(Path(directory) / "registration.json")
            record = validate_tau2_registration(
                registration, training_sources=_TRAINING, variant="model-only", source_commit="c" * 40,
                tau2_version="1.0.1", python_version="3.12.4", domain="telecom", task_set="telecom",
                task_split="base", task_ids=["[mms_issue]task-a", "[service_issue]task-b"], seed=0,
                max_new_tokens=256, quantization="4bit", num_trials=1, max_steps=30, max_errors=10,
                max_concurrency=1, max_retries=0,
            )
            with self.assertRaisesRegex(ValueError, "max_steps"):
                validate_tau2_registration(
                    registration, training_sources=_TRAINING, variant="model-only", source_commit="c" * 40,
                    tau2_version="1.0.1", python_version="3.12.4", domain="telecom", task_set="telecom",
                    task_split="base", task_ids=["[mms_issue]task-a", "[service_issue]task-b"], seed=0,
                    max_new_tokens=256, quantization="4bit", num_trials=1, max_steps=31, max_errors=10,
                    max_concurrency=1, max_retries=0,
                )
        self.assertEqual(record["benchmark"], "tau2")
        self.assertEqual(record["training_source_fingerprints"], [["a" * 64, 3232]])
