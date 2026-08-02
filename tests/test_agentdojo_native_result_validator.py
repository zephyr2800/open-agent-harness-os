from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from experiments.agentdojo_native_result_validator import SCHEMA, main, validate_native_result
from experiments.source_tree import record_source_tree


def _record(path: Path) -> dict[str, object]:
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }


def _write_log(
    path: Path,
    *,
    user_task: str,
    injection_task: str | None,
    attack: str | None,
    utility: bool,
    security: bool,
    injections: dict[str, str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "suite_name": "workspace",
                "pipeline_name": "openai-compatible",
                "user_task_id": user_task,
                "injection_task_id": injection_task,
                "attack_type": attack,
                "injections": injections,
                "messages": [{"role": "system", "content": "test"}, {"role": "user", "content": "task"}],
                "error": None,
                "benchmark_version": "v1.2.2",
                "evaluation_timestamp": "2026-08-02 00:00:00",
                "agentdojo_package_version": "test",
                "utility": utility,
                "security": security,
                "duration": 1.5,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_fixture(root: Path, *, injection: bool = False) -> Path:
    run_dir = root / "run"
    native_logs = run_dir / "native-logs"
    run_dir.mkdir(parents=True)
    checkpoint = root / "checkpoint"
    checkpoint.mkdir()
    (checkpoint / "model.safetensors").write_bytes(b"weights")
    (checkpoint / "merge_manifest.json").write_text("{}\n", encoding="utf-8")
    (checkpoint / "training_manifest.json").write_text("{}\n", encoding="utf-8")
    project1 = root / "project1"
    project1.mkdir()
    (project1 / "policy.py").write_text("POLICY = 'native-test'\n", encoding="utf-8")
    harness = root / "harness"
    adapter_source = harness / "experiments" / "agentdojo_adapter_server.py"
    adapter_source.parent.mkdir(parents=True)
    adapter_source.write_text("def main():\n    return 0\n", encoding="utf-8")
    (harness / "adapters").mkdir()
    (harness / "adapters" / "project1_transformers.py").write_text("class Adapter: ...\n", encoding="utf-8")
    agentdojo_root = root / "agentdojo"
    entrypoint = agentdojo_root / "src" / "agentdojo" / "scripts" / "benchmark.py"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text("def main():\n    return 0\n", encoding="utf-8")
    adapter_log = run_dir / "adapter.jsonl"
    adapter_log.write_text('{"request":"native"}\n', encoding="utf-8")
    user_tasks = ["user_task_1", "user_task_17"]
    injection_tasks = ["injection_task_3"] if injection else []
    if injection:
        _write_log(
            native_logs / "openai-compatible" / "workspace" / "injection_task_3" / "none" / "none.json",
            user_task="injection_task_3",
            injection_task=None,
            attack=None,
            utility=True,
            security=True,
            injections={},
        )
        _write_log(
            native_logs / "openai-compatible" / "workspace" / "user_task_1" / "direct" / "injection_task_3.json",
            user_task="user_task_1",
            injection_task="injection_task_3",
            attack="direct",
            utility=True,
            security=True,
            injections={"email": "untrusted instruction"},
        )
        _write_log(
            native_logs / "openai-compatible" / "workspace" / "user_task_17" / "direct" / "injection_task_3.json",
            user_task="user_task_17",
            injection_task="injection_task_3",
            attack="direct",
            utility=True,
            security=False,
            injections={"email": "untrusted instruction"},
        )
    else:
        _write_log(
            native_logs / "openai-compatible" / "workspace" / "user_task_1" / "none" / "none.json",
            user_task="user_task_1",
            injection_task=None,
            attack=None,
            utility=True,
            security=True,
            injections={},
        )
        _write_log(
            native_logs / "openai-compatible" / "workspace" / "user_task_17" / "none" / "none.json",
            user_task="user_task_17",
            injection_task=None,
            attack=None,
            utility=False,
            security=True,
            injections={},
        )
    native_records = [_record(path) for path in sorted(native_logs.rglob("*.json"))]
    attack = "direct" if injection else None
    python = str(Path(sys.executable).resolve())
    adapter_command = [
        python,
        "-m",
        "experiments.agentdojo_adapter_server",
        "--model-checkpoint",
        str(checkpoint.resolve()),
        "--project1-root",
        str(project1.resolve()),
        "--harness-root",
        str(harness.resolve()),
        "--host",
        "127.0.0.1",
        "--port",
        "8089",
        "--log",
        str(adapter_log.resolve()),
        "--max-new-tokens",
        "256",
        "--seed",
        "0",
        "--harness-variant",
        "H4-agentdojo-native-model-only",
    ]
    benchmark_command = [
        python,
        "-m",
        "agentdojo.scripts.benchmark",
        "--model",
        "openai-compatible",
        "--model-id",
        "local-action-policy",
        "--benchmark-version",
        "v1.2.2",
        "--suite",
        "workspace",
        "--logdir",
        str(native_logs.resolve()),
    ]
    for task in user_tasks:
        benchmark_command.extend(["--user-task", task])
    for task in injection_tasks:
        benchmark_command.extend(["--injection-task", task])
    if attack is not None:
        benchmark_command.extend(["--attack", attack])
    manifest = {
        "schema": "agentdojo-native-run/v1",
        "status": "completed",
        "run_dir": str(run_dir.resolve()),
        "variant": "model-only",
        "checkpoint": {
            "directory": str(checkpoint.resolve()),
            "model_weights": _record(checkpoint / "model.safetensors"),
            "merge_manifest": _record(checkpoint / "merge_manifest.json"),
            "training_manifest": _record(checkpoint / "training_manifest.json"),
            "training_binding": {"passed": True},
        },
        "train_holdout_audit": {"passed": True},
        "agentdojo": {
            "root": str(agentdojo_root.resolve()),
            "commit": "a" * 40,
            "benchmark_version": "v1.2.2",
            "suite": "workspace",
            "user_tasks": user_tasks,
            "injection_tasks": injection_tasks,
            "attack": attack,
            "defense": None,
            "entrypoint": str(entrypoint.resolve()),
            "selector_catalog": {
                "schema": "agentdojo-selector-catalog/v1",
                "benchmark_version": "v1.2.2",
                "suite": "workspace",
                "user_tasks": user_tasks,
                "injection_tasks": ["injection_task_3"],
                "attacks": ["direct"],
                "defenses": [],
                "sha256": "b" * 64,
            },
        },
        "adapter": {
            "source": _record(adapter_source),
            "source_trees": {"project1": record_source_tree(project1), "harness": record_source_tree(harness)},
            "host": "127.0.0.1",
            "port": 8089,
            "harness_variant": "H4-agentdojo-native-model-only",
            "enable_repair": False,
            "lookup_first_enabled": False,
        },
        "policy": {"seed": 0, "do_sample": False, "max_new_tokens": 256, "quantization": "4bit"},
        "commands": {"adapter": adapter_command, "benchmark": benchmark_command},
        "adapter_health": {
            "status": "ok",
            "model_checkpoint_configured": True,
            "model_loaded": True,
            "harness_variant": "H4-agentdojo-native-model-only",
        },
        "adapter_log": _record(adapter_log),
        "benchmark_returncode": 0,
        "native_output": {
            "schema": "agentdojo-native-logs/v1",
            "directory": str(native_logs.resolve()),
            "records": native_records,
        },
    }
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


class AgentDojoNativeResultValidatorTests(unittest.TestCase):
    def test_help_supports_a_legacy_windows_console_encoding(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "0"
        environment["PYTHONIOENCODING"] = "cp1252"
        completed = subprocess.run(
            [sys.executable, "-m", "experiments.agentdojo_native_result_validator", "--help"],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
        self.assertIn(b"--run-manifest", completed.stdout)

    def test_validates_clean_native_utility_without_inventing_security_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = validate_native_result(_write_fixture(Path(temporary)))
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["status"], "locally_consistent")
        self.assertEqual(report["native_metric"]["name"], "utility_rate")
        self.assertEqual(report["native_metric"]["value"], 0.5)
        self.assertEqual(report["run_count"], 2)
        self.assertIn("not applicable", report["native_metrics"]["security_measurement"])
        self.assertIn("Do not infer independent replay", report["claim_boundary"])

    def test_validates_direct_injection_pairs_and_keeps_controls_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = validate_native_result(_write_fixture(Path(temporary), injection=True))
        self.assertEqual(report["native_metric"]["name"], "joint_utility_security_rate")
        self.assertEqual(report["native_metric"]["value"], 0.5)
        self.assertEqual(report["native_metrics"]["utility_rate"], 1.0)
        self.assertEqual(report["native_metrics"]["security_rate"], 0.5)
        self.assertEqual(report["native_metrics"]["injection_control_utility_rate"], 1.0)
        self.assertEqual(report["run_count"], 3)

    def test_rejects_tampered_native_log_and_source_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_fixture(root)
            log = manifest.parent / "native-logs" / "openai-compatible" / "workspace" / "user_task_1" / "none" / "none.json"
            log.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sha256 does not match"):
                validate_native_result(manifest)

            manifest = _write_fixture(root / "source-drift")
            (root / "source-drift" / "project1" / "policy.py").write_text("POLICY = 'changed'\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source_trees.project1"):
                validate_native_result(manifest)

    def test_rejects_unrecorded_extra_native_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = _write_fixture(Path(temporary))
            extra = manifest.parent / "native-logs" / "openai-compatible" / "workspace" / "extra" / "none" / "none.json"
            extra.parent.mkdir(parents=True)
            extra.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "launcher-recorded files"):
                validate_native_result(manifest)

    def test_rejects_native_execution_errors_even_when_the_record_is_rehashed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = _write_fixture(Path(temporary), injection=True)
            log = manifest.parent / "native-logs" / "openai-compatible" / "workspace" / "user_task_1" / "direct" / "injection_task_3.json"
            payload = json.loads(log.read_text(encoding="utf-8"))
            payload["error"] = "adapter response failed"
            log.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            for record in manifest_payload["native_output"]["records"]:
                if Path(record["path"]).resolve() == log.resolve():
                    record.update(_record(log))
            manifest.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "execution error"):
                validate_native_result(manifest)

    def test_cli_refuses_to_overwrite_an_existing_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_fixture(root)
            output = root / "validation.json"
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["--run-manifest", str(manifest), "--output", str(output)]), 0)
            self.assertTrue(output.is_file())
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit):
                    main(["--run-manifest", str(manifest), "--output", str(output)])


if __name__ == "__main__":
    unittest.main()
