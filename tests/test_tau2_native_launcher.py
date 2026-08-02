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

from experiments.data_split_audit import REQUIRED_FROZEN_FIXTURE_HASHES, validate_required_audit_manifest
from experiments.tau2_native_launcher import Tau2NativeRunConfig, _assert_port_available, build_plan


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


def _runtime_probe() -> dict[str, object]:
    return {
        "python": "C:/runtime/python.exe",
        "python_version": "3.12.0",
        "tau2_version": "1.0.1",
        "package_file": "C:/tau2/src/tau2/__init__.py",
        "source_bound": True,
    }


def _selector_catalog() -> dict[str, object]:
    return {
        "schema": "tau2-selector-catalog/v1",
        "domain": "telecom",
        "task_set": "telecom",
        "task_split": "base",
        "task_ids": ["task-1", "task-2", "not-solo"],
        "solo_task_ids": ["task-1", "task-2"],
        "sha256": "e" * 64,
    }


class Tau2NativeLauncherTests(unittest.TestCase):
    def _config(self, root: Path, *, variant: str = "model-only") -> Tau2NativeRunConfig:
        audit = _audit(root / "audit.json")
        tau2 = root / "tau2"
        entrypoint = tau2 / "src" / "tau2"
        entrypoint.mkdir(parents=True)
        (entrypoint / "cli.py").write_text("# cli placeholder\n", encoding="utf-8")
        project1 = root / "project1"
        project1.mkdir()
        runtime = root / "tau2-runtime"
        runtime.mkdir()
        return Tau2NativeRunConfig(
            checkpoint=_checkpoint(root, audit),
            train_holdout_audit=audit,
            project1_root=project1,
            tau2_root=tau2,
            tau2_runtime=runtime,
            run_dir=root / "native-run",
            python=Path(sys.executable).resolve(),
            domain="telecom",
            task_set="telecom",
            task_split="base",
            task_ids=("task-1",),
            variant=variant,
            seed=0,
            num_trials=1,
            max_steps=30,
            max_errors=10,
            max_new_tokens=256,
            quantization="4bit",
            port=8090,
        )

    def _plan(self, config: Tau2NativeRunConfig) -> dict[str, object]:
        with (
            mock.patch("experiments.tau2_native_launcher._git", side_effect=["b" * 40, ""]),
            mock.patch("experiments.tau2_native_launcher._runtime_probe", return_value=_runtime_probe()),
            mock.patch("experiments.tau2_native_launcher._selector_catalog", return_value=_selector_catalog()),
        ):
            return build_plan(config)

    def test_plan_binds_a_clean_checkpoint_and_uses_the_official_solo_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = self._plan(self._config(Path(directory)))
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["tau2"]["commit"], "b" * 40)
        self.assertTrue(plan["checkpoint"]["training_binding"]["passed"])
        self.assertEqual(plan["tau2"]["condition"], "official-solo-telecom; no external user simulator")
        self.assertEqual(plan["tau2"]["selector_catalog"]["sha256"], "e" * 64)
        self.assertTrue(plan["runtime"]["source_bound"])
        self.assertEqual(plan["environment"]["PYTHONUTF8"], "1")
        benchmark = plan["commands"]["benchmark"]
        self.assertIn("tau2.cli", benchmark)
        self.assertIn("llm_agent_solo", benchmark)
        self.assertIn("dummy_user", benchmark)
        self.assertIn("openai/local-action-policy", benchmark)
        self.assertIn("--max-retries", benchmark)
        self.assertIn("--enforce-communication-protocol", benchmark)

    def test_repair_variant_is_explicit_in_the_adapter_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = self._plan(self._config(Path(directory), variant="repair"))
        self.assertTrue(plan["adapter"]["enable_repair"])
        self.assertIn("--enable-repair", plan["commands"]["adapter"])
        self.assertEqual(plan["variant"], "repair")

    def test_unknown_duplicate_and_non_solo_selectors_are_rejected_before_an_adapter_can_start(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = replace(self._config(Path(directory)), task_ids=("unknown",))
            with (
                mock.patch("experiments.tau2_native_launcher._git", side_effect=["c" * 40, ""]),
                mock.patch("experiments.tau2_native_launcher._runtime_probe", return_value=_runtime_probe()),
                mock.patch("experiments.tau2_native_launcher._selector_catalog", return_value=_selector_catalog()),
            ):
                with self.assertRaisesRegex(ValueError, "unknown"):
                    build_plan(config)
        with tempfile.TemporaryDirectory() as directory:
            config = replace(self._config(Path(directory)), task_ids=("task-1", "task-1"))
            with (
                mock.patch("experiments.tau2_native_launcher._git", side_effect=["d" * 40, ""]),
                mock.patch("experiments.tau2_native_launcher._runtime_probe", return_value=_runtime_probe()),
                mock.patch("experiments.tau2_native_launcher._selector_catalog", return_value=_selector_catalog()),
            ):
                with self.assertRaisesRegex(ValueError, "must be unique"):
                    build_plan(config)
        with tempfile.TemporaryDirectory() as directory:
            config = replace(self._config(Path(directory)), task_ids=("not-solo",))
            with (
                mock.patch("experiments.tau2_native_launcher._git", side_effect=["f" * 40, ""]),
                mock.patch("experiments.tau2_native_launcher._runtime_probe", return_value=_runtime_probe()),
                mock.patch("experiments.tau2_native_launcher._selector_catalog", return_value=_selector_catalog()),
            ):
                with self.assertRaisesRegex(ValueError, "not valid"):
                    build_plan(config)

    def test_non_registered_protocol_and_dirty_checkout_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = replace(self._config(Path(directory)), domain="airline")
            with self.assertRaisesRegex(ValueError, "domain='telecom'"):
                build_plan(config)
        with tempfile.TemporaryDirectory() as directory:
            config = self._config(Path(directory))
            with mock.patch("experiments.tau2_native_launcher._git", side_effect=["a" * 40, " M src/tau2/cli.py"]):
                with self.assertRaisesRegex(ValueError, "must be clean"):
                    build_plan(config)

    def test_launcher_refuses_to_share_an_adapter_port(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            with self.assertRaisesRegex(RuntimeError, "already in use"):
                _assert_port_available(port)
