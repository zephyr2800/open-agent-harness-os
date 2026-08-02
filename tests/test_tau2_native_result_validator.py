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

from experiments.source_tree import record_source_tree
from experiments.tau2_native_result_validator import SCHEMA, main, validate_native_result


def _record(path: Path) -> dict[str, object]:
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }


def _task(task_id: str) -> dict[str, object]:
    return {"id": task_id, "description": "synthetic unit-test task"}


def _simulation(task_id: str, reward: float, *, termination: str = "agent_stop", trial: int = 0) -> dict[str, object]:
    return {
        "id": f"{task_id}-{trial}",
        "task_id": task_id,
        "trial": trial,
        "seed": 123 + trial,
        "termination_reason": termination,
        "duration": 1.25,
        "agent_cost": 0.0,
        "user_cost": 0.0,
        "messages": [{"role": "user", "content": "help"}],
        "reward_info": {"reward": reward},
    }


def _selector_catalog(task_ids: tuple[str, ...]) -> dict[str, object]:
    normalized = {
        "schema": "tau2-selector-catalog/v1",
        "domain": "telecom",
        "task_set": "telecom",
        "task_split": "base",
        "task_ids": sorted(task_ids),
        "solo_task_ids": sorted(task_ids),
    }
    digest = hashlib.sha256(
        (json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    ).hexdigest()
    return {**normalized, "sha256": digest}


def _write_fixture(
    root: Path,
    *,
    termination: str = "agent_stop",
    task_ids: tuple[str, str] = (
        "[mobile_data_issue]airplane_mode_on",
        "[billing]overdue_payment",
    ),
) -> Path:
    run_dir = root / "run"
    preserved = run_dir / "tau2-native-results"
    preserved.mkdir(parents=True)
    tau2_root = root / "tau2"
    package_file = tau2_root / "src" / "tau2" / "__init__.py"
    package_file.parent.mkdir(parents=True)
    package_file.write_text("__version__ = '1.0.1'\n", encoding="utf-8")
    (tau2_root / "data").mkdir()
    (tau2_root / "data" / "telecom.json").write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tau2_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=tau2_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"],
        cwd=tau2_root,
        check=True,
        capture_output=True,
        text=True,
    )
    tau2_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tau2_root, check=True, capture_output=True, text=True
    ).stdout.strip()
    checkpoint = root / "checkpoint"
    checkpoint.mkdir()
    (checkpoint / "model.safetensors").write_bytes(b"weights")
    (checkpoint / "merge_manifest.json").write_text("{}\n", encoding="utf-8")
    (checkpoint / "training_manifest.json").write_text("{}\n", encoding="utf-8")
    harness_root = root / "harness"
    adapter_source = harness_root / "experiments" / "agentdojo_adapter_server.py"
    adapter_source.parent.mkdir(parents=True)
    adapter_source.write_text("def main():\n    return 0\n", encoding="utf-8")
    (harness_root / "adapters").mkdir()
    (harness_root / "adapters" / "project1_transformers.py").write_text(
        "class Project1TransformersAdapter: ...\n",
        encoding="utf-8",
    )
    project1_root = root / "project1"
    (project1_root / "model").mkdir(parents=True)
    (project1_root / "model" / "transformers_backend.py").write_text(
        "class TransformersActionPolicy: ...\n",
        encoding="utf-8",
    )
    wrapper_source = harness_root / "experiments" / "tau2_native_runner.py"
    wrapper_source.write_text("def main():\n    return 0\n", encoding="utf-8")
    adapter_log = run_dir / "adapter.jsonl"
    adapter_log.write_text("{\"request\":\"native\"}\n", encoding="utf-8")
    results_path = preserved / "results.json"
    results = {
        "timestamp": "2026-08-02T00:00:00",
        "info": {
            "git_commit": tau2_commit,
            "seed": 0,
            "num_trials": 1,
            "max_steps": 30,
            "max_errors": 10,
            "agent_info": {
                "implementation": "llm_agent_solo",
                "llm": "openai/local-action-policy",
                "llm_args": {
                    "api_base": "http://127.0.0.1:8090/v1",
                    "temperature": 0.0,
                    "max_tokens": 256,
                },
            },
            "user_info": {"implementation": "dummy_user"},
            "environment_info": {"domain_name": "telecom"},
        },
        "tasks": [_task(task_id) for task_id in task_ids],
        "simulations": [
            _simulation(task_ids[0], 1.0, termination=termination),
            _simulation(task_ids[1], 0.5),
        ],
    }
    results_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    results_record = _record(results_path)
    manifest = {
        "schema": "tau2-native-run/v1",
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
        "tau2": {
            "root": str(tau2_root.resolve()),
            "commit": tau2_commit,
            "source_tree": record_source_tree(tau2_root),
            "domain": "telecom",
            "task_set": "telecom",
            "task_split": "base",
            "task_ids": list(task_ids),
            "selector_catalog": _selector_catalog(task_ids),
            "condition": "official-solo-telecom; no external user simulator",
        },
        "policy": {
            "model": "openai/local-action-policy",
            "seed": 0,
            "do_sample": False,
            "max_new_tokens": 256,
        },
        "budget": {
            "num_trials": 1,
            "max_steps": 30,
            "max_errors": 10,
            "max_concurrency": 1,
            "max_retries": 0,
        },
        "adapter": {
            "host": "127.0.0.1",
            "port": 8090,
            "harness_variant": "H5-tau2-native-model-only",
            "source": _record(adapter_source),
            "source_trees": {
                "project1": record_source_tree(project1_root),
                "harness": record_source_tree(harness_root),
            },
        },
        "adapter_health": {
            "status": "ok",
            "model_checkpoint_configured": True,
            "model_loaded": True,
            "harness_variant": "H5-tau2-native-model-only",
        },
        "adapter_log": _record(adapter_log),
        "runtime": {
            "source_bound": True,
            "package_file": str(package_file.resolve()),
            "module_files": {
                "experiments.agentdojo_adapter_server": str(adapter_source.resolve()),
                "experiments.tau2_native_runner": str(wrapper_source.resolve()),
            },
            "python_version": "3.12.0",
            "tau2_version": "1.0.1",
            "tau2_runtime": str(root / "runtime"),
            "platform": "test-platform",
        },
        "runner_wrapper": {
            "source": _record(wrapper_source),
            "delegates_to": "tau2.cli.main",
            "compatibility": {"id": "tau2-dummy-user-constructor-v1", "required": True},
        },
        "commands": {
            "adapter": [
                str(Path(sys.executable).resolve()),
                "-m",
                "experiments.agentdojo_adapter_server",
                "--model-checkpoint",
                str(checkpoint.resolve()),
                "--project1-root",
                str(project1_root.resolve()),
                "--harness-root",
                str(harness_root.resolve()),
                "--host",
                "127.0.0.1",
                "--port",
                "8090",
                "--log",
                str(adapter_log.resolve()),
                "--max-new-tokens",
                "256",
                "--seed",
                "0",
                "--harness-variant",
                "H5-tau2-native-model-only",
            ],
            "benchmark": [str(Path(sys.executable).resolve()), "-m", "experiments.tau2_native_runner", "run"],
        },
        "native_output": {
            "preserved_directory": str(preserved.resolve()),
            "results_record": results_record,
            "preserved_results_record": results_record,
            "schema_validation": {
                "schema": "tau2-results-pydantic/v1",
                "passed": True,
                "result_model": "tau2.data_model.simulation.Results",
                "tau2_package_file": str(package_file.resolve()),
                "task_count": len(task_ids),
                "simulation_count": len(task_ids),
                "results_record": results_record,
            },
        },
    }
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _rewrite_results_and_refresh_records(manifest: Path, payload: dict[str, object]) -> None:
    results = manifest.parent / "tau2-native-results" / "results.json"
    results.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    record = _record(results)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_payload["native_output"]["results_record"] = record
    manifest_payload["native_output"]["preserved_results_record"] = record
    manifest_payload["native_output"]["schema_validation"]["results_record"] = record
    manifest.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")


class Tau2NativeResultValidatorTests(unittest.TestCase):
    def test_help_supports_a_legacy_windows_console_encoding(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "0"
        environment["PYTHONIOENCODING"] = "cp1252"
        completed = subprocess.run(
            [sys.executable, "-m", "experiments.tau2_native_result_validator", "--help"],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
        self.assertIn(b"--run-manifest", completed.stdout)

    def test_validates_completed_native_result_without_inventing_unmeasured_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_fixture(root)
            report = validate_native_result(manifest)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["status"], "locally_consistent")
        self.assertEqual(report["native_metric"], {"name": "mean_reward", "value": 0.75, "source": "τ³-bench native reward_info.reward"})
        self.assertEqual(report["reward_one_rate"], 0.5)
        self.assertEqual(report["by_family"]["billing"]["mean_reward"], 0.5)
        self.assertTrue(report["trace_availability"]["all_simulations_have_nonempty_native_messages"])
        self.assertIn("not measured", report["not_measured"]["safety"])
        self.assertEqual(report["attestation"]["status"], "not_provided")
        self.assertIn("Do not infer independent replay", report["claim_boundary"])

    def test_rejects_tampered_preserved_native_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_fixture(root)
            results = manifest.parent / "tau2-native-results" / "results.json"
            results.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sha256 does not match"):
                validate_native_result(manifest)

    def test_rejects_a_result_bound_to_a_different_loopback_adapter_port(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_fixture(root)
            results = manifest.parent / "tau2-native-results" / "results.json"
            payload = json.loads(results.read_text(encoding="utf-8"))
            payload["info"]["agent_info"]["llm_args"]["api_base"] = "http://127.0.0.1:8091/v1"
            _rewrite_results_and_refresh_records(manifest, payload)
            with self.assertRaisesRegex(ValueError, "recorded loopback adapter host, port, and /v1 endpoint"):
                validate_native_result(manifest)

    def test_rejects_non_module_execution_and_runtime_module_rebinding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_fixture(root)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            python = payload["commands"]["benchmark"][0]
            payload["commands"]["benchmark"] = [
                python,
                "-c",
                "print('unrelated')",
                "-m",
                "experiments.tau2_native_runner",
                "run",
            ]
            manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must start with its Python runtime followed by -m"):
                validate_native_result(manifest)

            manifest = _write_fixture(root / "runtime-module")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["runtime"]["module_files"]["experiments.tau2_native_runner"] = payload["adapter"]["source"]["path"]
            manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "did not resolve the recorded τ³ runner-wrapper module"):
                validate_native_result(manifest)

    def test_rejects_tampered_selector_catalog_or_dirty_tau2_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_fixture(root)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["tau2"]["selector_catalog"]["sha256"] = "0" * 64
            manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "selector_catalog.sha256"):
                validate_native_result(manifest)

            manifest = _write_fixture(root / "dirty-checkout")
            (root / "dirty-checkout" / "tau2" / "data" / "telecom.json").write_text('{"changed": true}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checkout is dirty"):
                validate_native_result(manifest)

    def test_rejects_boolean_identity_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_fixture(root)
            results = manifest.parent / "tau2-native-results" / "results.json"
            payload = json.loads(results.read_text(encoding="utf-8"))
            payload["info"]["seed"] = True
            _rewrite_results_and_refresh_records(manifest, payload)
            with self.assertRaisesRegex(ValueError, "native results.info.seed must be an integer"):
                validate_native_result(manifest)

    def test_rejects_infrastructure_error_and_refuses_to_overwrite_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_fixture(root, termination="infrastructure_error")
            results = manifest.parent / "tau2-native-results" / "results.json"
            payload = json.loads(results.read_text(encoding="utf-8"))
            payload["simulations"][0]["termination_reason"] = "infrastructure_error"
            results.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            updated = _record(results)
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload["native_output"]["results_record"] = updated
            manifest_payload["native_output"]["preserved_results_record"] = updated
            manifest.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "infrastructure_error"):
                validate_native_result(manifest)

            valid_manifest = _write_fixture(root / "second")
            output = root / "validation.json"
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["--run-manifest", str(valid_manifest), "--output", str(output)]), 0)
            self.assertTrue(output.is_file())
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit):
                    main(["--run-manifest", str(valid_manifest), "--output", str(output)])

    def test_rejects_rebound_checkpoint_or_missing_native_schema_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_fixture(root)
            (root / "checkpoint" / "model.safetensors").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "model_weights.sha256"):
                validate_native_result(manifest)

            manifest = _write_fixture(root / "second")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["native_output"]["schema_validation"]["passed"] = False
            manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Pydantic Results schema"):
                validate_native_result(manifest)

            manifest = _write_fixture(root / "third")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            command = payload["commands"]["adapter"]
            command[command.index("--model-checkpoint") + 1] = str(root / "different-checkpoint")
            manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bound to the recorded merged checkpoint"):
                validate_native_result(manifest)

            manifest = _write_fixture(root / "fourth")
            (root / "fourth" / "project1" / "model" / "transformers_backend.py").write_text(
                "class TransformersActionPolicy:\n    changed = True\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "source_trees.project1"):
                validate_native_result(manifest)

    def test_matches_tau2_success_tolerance_at_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _write_fixture(root)
            results = manifest.parent / "tau2-native-results" / "results.json"
            payload = json.loads(results.read_text(encoding="utf-8"))
            payload["simulations"][0]["reward_info"]["reward"] = 1.0 + 5e-7
            results.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            updated = _record(results)
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload["native_output"]["results_record"] = updated
            manifest_payload["native_output"]["preserved_results_record"] = updated
            manifest_payload["native_output"]["schema_validation"]["results_record"] = updated
            manifest.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
            report = validate_native_result(manifest)
        self.assertEqual(report["reward_one_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
