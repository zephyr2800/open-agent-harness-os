from __future__ import annotations

import hashlib
import json
import socket
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from experiments.agentdojo_native_launcher import NativeRunConfig, _assert_port_available, build_plan
from experiments.data_split_audit import REQUIRED_FROZEN_FIXTURE_HASHES, validate_required_audit_manifest


def _audit(path: Path) -> Path:
    path.write_text(json.dumps({
        "schema": "train-holdout-audit/v1",
        "passed": True,
        "overlap_count": 0,
        "train": [{"path": "clean-mixture.jsonl", "sha256": "a" * 64, "rows": 3232}],
        "fixtures": [
            {"path": f"C:/fixtures/{name}", "sha256": digest, "tasks": 1}
            for name, digest in REQUIRED_FROZEN_FIXTURE_HASHES.items()
        ],
    }), encoding="utf-8")
    return path


def _checkpoint(root: Path, audit: Path) -> Path:
    checkpoint = root / "checkpoint"
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


def _selector_catalog() -> dict[str, object]:
    return {
        "schema": "agentdojo-selector-catalog/v1",
        "benchmark_version": "v1.2.2",
        "suite": "workspace",
        "user_tasks": ["user_task_17", "user_task_18"],
        "injection_tasks": ["injection_task_3"],
        "attacks": ["direct"],
        "defenses": ["tool_filter"],
        "sha256": "e" * 64,
    }


class AgentDojoNativeLauncherTests(unittest.TestCase):
    def _config(self, root: Path, *, variant: str = "model-only") -> NativeRunConfig:
        audit = _audit(root / "audit.json")
        agentdojo = root / "agentdojo"
        entrypoint = agentdojo / "src" / "agentdojo" / "scripts"
        entrypoint.mkdir(parents=True)
        (entrypoint / "benchmark.py").write_text("# benchmark placeholder\n", encoding="utf-8")
        project1 = root / "project1"
        project1.mkdir()
        (project1 / "policy.py").write_text("POLICY = 'native-test'\n", encoding="utf-8")
        runtime = root / "agentdojo-runtime"
        runtime.mkdir()
        return NativeRunConfig(
            checkpoint=_checkpoint(root, audit),
            train_holdout_audit=audit,
            project1_root=project1,
            agentdojo_root=agentdojo,
            agentdojo_runtime=runtime,
            run_dir=root / "native-run",
            python=Path(sys.executable).resolve(),
            user_tasks=("user_task_17",),
            injection_tasks=(),
            variant=variant,
            benchmark_version="v1.2.2",
            suite="workspace",
            attack=None,
            defense=None,
            seed=0,
            max_new_tokens=256,
            quantization="4bit",
            port=8089,
        )

    def test_plan_binds_a_clean_checkpoint_and_keeps_native_metrics_external(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._config(Path(directory))
            with (
                mock.patch("experiments.agentdojo_native_launcher._git", side_effect=["b" * 40, ""]),
                mock.patch("experiments.agentdojo_native_launcher._selector_catalog", return_value=_selector_catalog()),
            ):
                plan = build_plan(config)
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["agentdojo"]["commit"], "b" * 40)
        self.assertTrue(plan["checkpoint"]["training_binding"]["passed"])
        self.assertFalse(plan["adapter"]["lookup_first_enabled"])
        self.assertEqual(plan["agentdojo"]["selector_catalog"]["sha256"], "e" * 64)
        self.assertEqual(plan["adapter"]["source_trees"]["project1"]["schema"], "python-source-tree/v1")
        self.assertGreater(plan["adapter"]["source_trees"]["harness"]["file_count"], 0)
        self.assertIn("openai-compatible", plan["commands"]["benchmark"])
        self.assertIn("--user-task", plan["commands"]["benchmark"])
        self.assertNotIn("--enable-repair", plan["commands"]["adapter"])

    def test_repair_variant_is_explicit_in_the_adapter_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._config(Path(directory), variant="repair")
            with (
                mock.patch("experiments.agentdojo_native_launcher._git", side_effect=["c" * 40, ""]),
                mock.patch("experiments.agentdojo_native_launcher._selector_catalog", return_value=_selector_catalog()),
            ):
                plan = build_plan(config)
        self.assertTrue(plan["adapter"]["enable_repair"])
        self.assertIn("--enable-repair", plan["commands"]["adapter"])
        self.assertEqual(plan["variant"], "repair")

    def test_injection_selector_requires_an_attack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = replace(self._config(Path(directory)), injection_tasks=("injection_task_3",))
            with self.assertRaisesRegex(ValueError, "--attack"):
                build_plan(config)

    def test_unknown_selector_is_rejected_before_an_adapter_can_start(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = replace(self._config(Path(directory)), user_tasks=("user_task_999",))
            with (
                mock.patch("experiments.agentdojo_native_launcher._git", side_effect=["f" * 40, ""]),
                mock.patch("experiments.agentdojo_native_launcher._selector_catalog", return_value=_selector_catalog()),
            ):
                with self.assertRaisesRegex(ValueError, "user_task_999"):
                    build_plan(config)

    def test_duplicate_or_unknown_native_selectors_are_rejected_before_an_adapter_can_start(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            duplicate = replace(self._config(root), user_tasks=("user_task_17", "user_task_17"))
            with (
                mock.patch("experiments.agentdojo_native_launcher._git", side_effect=["1" * 40, ""]),
                mock.patch("experiments.agentdojo_native_launcher._selector_catalog", return_value=_selector_catalog()),
            ):
                with self.assertRaisesRegex(ValueError, "must be unique"):
                    build_plan(duplicate)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid_attack = replace(
                self._config(root),
                injection_tasks=("injection_task_3",),
                attack="not-a-registered-attack",
            )
            with (
                mock.patch("experiments.agentdojo_native_launcher._git", side_effect=["2" * 40, ""]),
                mock.patch("experiments.agentdojo_native_launcher._selector_catalog", return_value=_selector_catalog()),
            ):
                with self.assertRaisesRegex(ValueError, "not-a-registered-attack"):
                    build_plan(invalid_attack)

    def test_dirty_benchmark_checkout_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._config(Path(directory))
            with mock.patch("experiments.agentdojo_native_launcher._git", side_effect=["d" * 40, " M src/agentdojo/models.py"]):
                with self.assertRaisesRegex(ValueError, "must be clean"):
                    build_plan(config)

    def test_launcher_refuses_to_share_an_adapter_port(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            with self.assertRaisesRegex(RuntimeError, "already in use"):
                _assert_port_available(port)
