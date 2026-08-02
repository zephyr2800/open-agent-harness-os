"""Plan or execute one checkpoint-bound native τ³-bench (``tau2``) evaluation.

The launcher uses τ³-bench's official command-line runner and native grader.
It supplies only a loopback OpenAI-compatible endpoint for the local policy,
then records the exact checkpoint, benchmark checkout, task selectors, runtime,
and adapter settings beside the benchmark's own artifacts.  The registered
local-only condition is deliberately narrow: τ³-bench telecom/base in its
official solo mode.  That condition uses ``DummyUser`` and never silently
falls back to a paid or external user simulator.

τ³-bench v1.0.1 needs a transparent in-memory constructor compatibility shim
for its documented ``DummyUser`` solo condition.  The plan records the shim's
source hash and whether the pinned runtime requires it; the benchmark checkout
itself remains clean and unmodified.

By default this module only validates inputs and writes an immutable plan.
``--execute`` is explicit because it loads the policy onto the local GPU.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from experiments.data_split_audit import (
    validate_checkpoint_training_binding,
    validate_required_audit_manifest,
)
from experiments.native_evaluation_registration import validate_tau2_registration
from experiments.source_tree import record_source_tree


REPO_ROOT = Path(__file__).resolve().parents[1]
SOLO_PROTOCOL = {
    "domain": "telecom",
    "task_set": "telecom",
    "task_split": "base",
    "agent": "llm_agent_solo",
    "user": "dummy_user",
}
VARIANTS = {
    "model-only": {
        "harness_variant": "H5-tau2-native-model-only",
        "enable_repair": False,
    },
    "repair": {
        "harness_variant": "H5-tau2-native-repair",
        "enable_repair": True,
    },
}


_RUNTIME_PROBE_SCRIPT = """
import importlib.metadata
import json
import pathlib
import sys

import tau2

try:
    version = importlib.metadata.version("tau2")
except importlib.metadata.PackageNotFoundError:
    version = None

print(json.dumps({
    "package_file": str(pathlib.Path(tau2.__file__).resolve()),
    "python_version": sys.version,
    "tau2_version": version,
}, sort_keys=True))
"""


_SELECTOR_CATALOG_SCRIPT = """
import json
import sys

from tau2.agent.llm_agent import LLMSoloAgent
from tau2.run import get_tasks

task_set, task_split = sys.argv[1:]
tasks = get_tasks(task_set, task_split_name=task_split)
print(json.dumps({
    "task_ids": [str(task.id) for task in tasks],
    "solo_task_ids": [str(task.id) for task in tasks if LLMSoloAgent.check_valid_task(task)],
}, sort_keys=True))
"""


_COMPATIBILITY_PROBE_SCRIPT = """
import json

from experiments.tau2_native_runner import compatibility_metadata
from tau2.user.user_simulator import DummyUser

print(json.dumps(compatibility_metadata(DummyUser), sort_keys=True))
"""


_NATIVE_RESULT_SCHEMA_PROBE_SCRIPT = """
import json
import pathlib
import sys

import tau2
from tau2.data_model.simulation import Results

results_path = pathlib.Path(sys.argv[1])
try:
    results = Results.model_validate_json(results_path.read_text(encoding="utf-8"))
except Exception as error:
    print(json.dumps({
        "schema": "tau2-results-pydantic/v1",
        "passed": False,
        "error": repr(error),
    }, sort_keys=True))
    raise

print(json.dumps({
    "schema": "tau2-results-pydantic/v1",
    "passed": True,
    "result_model": f"{type(results).__module__}.{type(results).__name__}",
    "tau2_package_file": str(pathlib.Path(tau2.__file__).resolve()),
    "task_count": len(results.tasks),
    "simulation_count": len(results.simulations),
}, sort_keys=True))
"""


@dataclass(frozen=True)
class Tau2NativeRunConfig:
    checkpoint: Path
    train_holdout_audit: Path
    project1_root: Path
    tau2_root: Path
    tau2_runtime: Path
    run_dir: Path
    python: Path
    domain: str
    task_set: str
    task_split: str
    task_ids: tuple[str, ...]
    variant: str
    seed: int
    num_trials: int
    max_steps: int
    max_errors: int
    max_new_tokens: int
    quantization: str | None
    port: int
    registration: Path | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"required file does not exist: {path}")
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git error"
        raise ValueError(f"could not inspect pinned τ³-bench checkout: {detail}")
    return completed.stdout.strip()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _tau2_environment(config: Tau2NativeRunConfig) -> tuple[dict[str, str], list[str]]:
    """Return a UTF-8-safe, source-bound environment for τ³-bench and the adapter."""

    pythonpath = [
        str(config.tau2_root / "src"),
        str(REPO_ROOT),
        str(config.project1_root),
        str(config.tau2_runtime),
    ]
    inherited_pythonpath = os.environ.get("PYTHONPATH")
    if inherited_pythonpath:
        pythonpath.append(inherited_pythonpath)
    return {
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": os.pathsep.join(pythonpath),
    }, pythonpath


def _runtime_probe(config: Tau2NativeRunConfig, environment: dict[str, str]) -> dict[str, Any]:
    """Verify that the supplied interpreter imports τ³-bench from this checkout."""

    probe_environment = os.environ.copy()
    probe_environment.update(environment)
    try:
        completed = subprocess.run(
            [str(config.python), "-c", _RUNTIME_PROBE_SCRIPT],
            cwd=config.tau2_root,
            env=probe_environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"could not inspect τ³-bench runtime: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown runtime probe error"
        raise ValueError(f"could not import τ³-bench from --python: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except ValueError as error:
        raise ValueError("τ³-bench runtime probe was not valid JSON") from error
    package_file = payload.get("package_file") if isinstance(payload, dict) else None
    if not isinstance(package_file, str) or not package_file:
        raise ValueError("τ³-bench runtime probe did not return a package path")
    package_path = Path(package_file)
    if not _is_within(package_path, config.tau2_root):
        raise ValueError(
            "--python imports τ³-bench from outside --tau2-root; install the pinned checkout "
            "into the supplied runtime before evaluating"
        )
    return {
        "python": str(config.python),
        "python_version": payload.get("python_version"),
        "tau2_version": payload.get("tau2_version"),
        "package_file": str(package_path.resolve()),
        "source_bound": True,
    }


def _selector_catalog(config: Tau2NativeRunConfig, environment: dict[str, str]) -> dict[str, Any]:
    """Read exact task IDs from the pinned τ³-bench checkout without loading a model."""

    selector_environment = os.environ.copy()
    selector_environment.update(environment)
    try:
        completed = subprocess.run(
            [
                str(config.python),
                "-c",
                _SELECTOR_CATALOG_SCRIPT,
                config.task_set,
                config.task_split,
            ],
            cwd=config.tau2_root,
            env=selector_environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"could not inspect task selectors from the pinned τ³-bench checkout: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown selector-catalog error"
        raise ValueError(f"could not inspect task selectors from the pinned τ³-bench checkout: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except ValueError as error:
        raise ValueError("pinned τ³-bench selector catalog was not valid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("pinned τ³-bench selector catalog was not an object")
    task_ids = payload.get("task_ids")
    solo_task_ids = payload.get("solo_task_ids")
    if not (
        isinstance(task_ids, list)
        and isinstance(solo_task_ids, list)
        and all(isinstance(item, str) and item for item in task_ids + solo_task_ids)
    ):
        raise ValueError("pinned τ³-bench selector catalog had invalid task IDs")
    normalized = {
        "schema": "tau2-selector-catalog/v1",
        "domain": config.domain,
        "task_set": config.task_set,
        "task_split": config.task_split,
        "task_ids": sorted(set(task_ids)),
        "solo_task_ids": sorted(set(solo_task_ids)),
    }
    normalized_bytes = (json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return {**normalized, "sha256": hashlib.sha256(normalized_bytes).hexdigest()}


def _compatibility_probe(config: Tau2NativeRunConfig, environment: dict[str, str]) -> dict[str, Any]:
    """Inspect the pinned runtime's solo-mode constructor boundary without running a task."""

    probe_environment = os.environ.copy()
    probe_environment.update(environment)
    try:
        completed = subprocess.run(
            [str(config.python), "-c", _COMPATIBILITY_PROBE_SCRIPT],
            cwd=config.tau2_root,
            env=probe_environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"could not inspect τ³-bench solo-mode compatibility: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown compatibility probe error"
        raise ValueError(f"could not inspect τ³-bench solo-mode compatibility: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except ValueError as error:
        raise ValueError("τ³-bench compatibility probe was not valid JSON") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("required"), bool):
        raise ValueError("τ³-bench compatibility probe returned an invalid payload")
    if payload.get("id") != "tau2-dummy-user-constructor-v1":
        raise ValueError("τ³-bench compatibility probe returned an unexpected shim identity")
    return payload


def _validate_selectors(config: Tau2NativeRunConfig, catalog: dict[str, Any]) -> None:
    if len(set(config.task_ids)) != len(config.task_ids):
        raise ValueError("each --task-id selector must be unique to preserve the registered evaluation budget")
    available = set(catalog["task_ids"])
    solo_available = set(catalog["solo_task_ids"])
    unknown = sorted(set(config.task_ids) - available)
    if unknown:
        raise ValueError(
            "--task-id selector(s) not found in the pinned τ³-bench "
            f"{config.task_set!r}/{config.task_split!r} set: {', '.join(unknown)}"
        )
    not_solo = sorted(set(config.task_ids) - solo_available)
    if not_solo:
        raise ValueError(
            "--task-id selector(s) are not valid for τ³-bench's local-only solo condition: "
            + ", ".join(not_solo)
        )


def _save_name(config: Tau2NativeRunConfig) -> str:
    digest = hashlib.sha256(str(config.run_dir).encode("utf-8")).hexdigest()[:16]
    return f"local-action-tau2-{digest}"


def _native_output_dir(config: Tau2NativeRunConfig) -> Path:
    return config.tau2_root / "data" / "simulations" / _save_name(config)


def _adapter_command(config: Tau2NativeRunConfig) -> list[str]:
    variant = VARIANTS[config.variant]
    command = [
        str(config.python),
        "-m",
        "experiments.agentdojo_adapter_server",
        "--model-checkpoint",
        str(config.checkpoint),
        "--project1-root",
        str(config.project1_root),
        "--harness-root",
        str(REPO_ROOT),
        "--host",
        "127.0.0.1",
        "--port",
        str(config.port),
        "--log",
        str(config.run_dir / "adapter.jsonl"),
        "--max-new-tokens",
        str(config.max_new_tokens),
        "--seed",
        str(config.seed),
        "--harness-variant",
        str(variant["harness_variant"]),
    ]
    if config.quantization:
        command.extend(["--quantization", config.quantization])
    if variant["enable_repair"]:
        command.append("--enable-repair")
    return command


def _agent_llm_args(config: Tau2NativeRunConfig) -> str:
    return json.dumps(
        {
            "api_base": f"http://127.0.0.1:{config.port}/v1",
            "api_key": "local",
            "max_tokens": config.max_new_tokens,
            "temperature": 0.0,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _benchmark_command(config: Tau2NativeRunConfig) -> list[str]:
    """Build the official τ³-bench CLI invocation for the registered solo condition."""

    return [
        str(config.python),
        "-m",
        "experiments.tau2_native_runner",
        "run",
        "--domain",
        config.domain,
        "--task-set-name",
        config.task_set,
        "--task-split-name",
        config.task_split,
        "--task-ids",
        *config.task_ids,
        "--num-trials",
        str(config.num_trials),
        "--agent",
        SOLO_PROTOCOL["agent"],
        "--agent-llm",
        "openai/local-action-policy",
        "--agent-llm-args",
        _agent_llm_args(config),
        "--user",
        SOLO_PROTOCOL["user"],
        "--max-steps",
        str(config.max_steps),
        "--max-errors",
        str(config.max_errors),
        "--max-concurrency",
        "1",
        "--max-retries",
        "0",
        "--seed",
        str(config.seed),
        "--save-to",
        _save_name(config),
        "--log-level",
        "ERROR",
        "--enforce-communication-protocol",
    ]


def build_plan(config: Tau2NativeRunConfig) -> dict[str, Any]:
    """Validate immutable inputs and return an executable native-run plan."""

    if config.variant not in VARIANTS:
        raise ValueError(f"unsupported native-evaluation variant: {config.variant}")
    for field in ("domain", "task_set", "task_split"):
        expected = SOLO_PROTOCOL[field]
        actual = getattr(config, field)
        if actual != expected:
            raise ValueError(
                "the registered local-only τ³-bench protocol requires "
                f"{field}={expected!r}, received {actual!r}"
            )
    if not config.task_ids:
        raise ValueError("at least one --task-id is required; do not accidentally launch an unregistered full suite")
    if config.run_dir.exists():
        raise ValueError(f"--run-dir must be new to preserve immutable native logs: {config.run_dir}")
    if config.num_trials < 1 or config.max_steps < 1 or config.max_errors < 1 or config.max_new_tokens < 1:
        raise ValueError("--num-trials, --max-steps, --max-errors, and --max-new-tokens must all be positive")
    if not 1 <= config.port <= 65535:
        raise ValueError("--port must be between 1 and 65535")
    if not config.python.is_file():
        raise ValueError(f"--python does not identify an executable file: {config.python}")
    if not config.project1_root.is_dir():
        raise ValueError(f"--project1-root is not a directory: {config.project1_root}")
    if not config.tau2_root.is_dir():
        raise ValueError(f"--tau2-root is not a directory: {config.tau2_root}")
    if not config.tau2_runtime.is_dir():
        raise ValueError(f"--tau2-runtime is not a directory: {config.tau2_runtime}")
    cli_entrypoint = config.tau2_root / "src" / "tau2" / "cli.py"
    if not cli_entrypoint.is_file():
        raise ValueError(f"--tau2-root does not contain the official CLI entrypoint: {cli_entrypoint}")
    native_output_dir = _native_output_dir(config)
    if native_output_dir.exists():
        raise ValueError(
            "the selected τ³-bench output directory already exists; use a new --run-dir "
            "rather than resuming or mixing a native result"
        )

    audit_gate = validate_required_audit_manifest(config.train_holdout_audit)
    if not audit_gate["passed"]:
        raise ValueError("--train-holdout-audit must prove clean isolation against every pinned fixture")
    checkpoint_binding = validate_checkpoint_training_binding(config.checkpoint, audit_gate)
    if not checkpoint_binding["passed"]:
        raise ValueError("--checkpoint must be a merged v2 checkpoint bound to the supplied clean training audit")

    tau2_commit = _git(config.tau2_root, "rev-parse", "HEAD")
    tau2_dirty = _git(config.tau2_root, "status", "--porcelain")
    if tau2_dirty:
        raise ValueError("--tau2-root must be clean; commit or discard local benchmark changes before a native run")
    environment, pythonpath = _tau2_environment(config)
    runtime = _runtime_probe(config, environment)
    selector_catalog = _selector_catalog(config, environment)
    _validate_selectors(config, selector_catalog)
    compatibility = _compatibility_probe(config, environment)
    registration = (
        validate_tau2_registration(
            config.registration,
            training_sources=audit_gate["training_sources"],
            variant=config.variant,
            source_commit=tau2_commit,
            tau2_version=runtime.get("tau2_version") if isinstance(runtime.get("tau2_version"), str) else None,
            python_version=runtime.get("python_version") if isinstance(runtime.get("python_version"), str) else None,
            domain=config.domain,
            task_set=config.task_set,
            task_split=config.task_split,
            task_ids=config.task_ids,
            seed=config.seed,
            max_new_tokens=config.max_new_tokens,
            quantization=config.quantization,
            num_trials=config.num_trials,
            max_steps=config.max_steps,
            max_errors=config.max_errors,
            max_concurrency=1,
            max_retries=0,
        )
        if config.registration is not None
        else None
    )
    adapter = REPO_ROOT / "experiments" / "agentdojo_adapter_server.py"
    runner_wrapper = REPO_ROOT / "experiments" / "tau2_native_runner.py"
    plan = {
        "schema": "tau2-native-run/v1",
        "status": "planned",
        "created_at_unix": time.time(),
        "run_dir": str(config.run_dir),
        "variant": config.variant,
        "checkpoint": {
            "directory": str(config.checkpoint),
            "model_weights": _file_record(config.checkpoint / "model.safetensors"),
            "merge_manifest": _file_record(config.checkpoint / "merge_manifest.json"),
            "training_manifest": _file_record(config.checkpoint / "training_manifest.json"),
            "training_binding": checkpoint_binding,
        },
        "train_holdout_audit": audit_gate,
        "tau2": {
            "root": str(config.tau2_root),
            "commit": tau2_commit,
            "domain": config.domain,
            "task_set": config.task_set,
            "task_split": config.task_split,
            "task_ids": list(config.task_ids),
            "selector_catalog": selector_catalog,
            "official_cli_entrypoint": str(cli_entrypoint),
            "native_output_directory": str(native_output_dir),
            "native_results_file": str(native_output_dir / "results.json"),
            "condition": "official-solo-telecom; no external user simulator",
            "verbose_logs": False,
            "verbose_logs_reason": "disabled because τ³-bench v1.0.1 constructs Windows artifact directories from telecom task IDs containing '|'; native results.json and launcher process/adapter logs remain preserved",
        },
        "runner_wrapper": {
            "source": _file_record(runner_wrapper),
            "delegates_to": "tau2.cli.main",
            "compatibility": compatibility,
        },
        "adapter": {
            "source": _file_record(adapter),
            "source_trees": {
                "project1": record_source_tree(config.project1_root),
                "harness": record_source_tree(REPO_ROOT),
            },
            "host": "127.0.0.1",
            "port": config.port,
            "harness_variant": VARIANTS[config.variant]["harness_variant"],
            "enable_repair": VARIANTS[config.variant]["enable_repair"],
            "lookup_first_enabled": False,
        },
        "policy": {
            "model": "openai/local-action-policy",
            "seed": config.seed,
            "do_sample": False,
            "max_new_tokens": config.max_new_tokens,
            "quantization": config.quantization,
        },
        "budget": {
            "num_trials": config.num_trials,
            "max_steps": config.max_steps,
            "max_errors": config.max_errors,
            "max_concurrency": 1,
            "max_retries": 0,
        },
        "runtime": {
            **runtime,
            "platform": platform.platform(),
            "tau2_runtime": str(config.tau2_runtime),
            "pythonpath_entries": pythonpath,
            "utf8_forced": True,
        },
        "commands": {
            "adapter": _adapter_command(config),
            "benchmark": _benchmark_command(config),
        },
        "environment": environment,
    }
    if registration is not None:
        plan["registration"] = registration
    return plan


def _assert_port_available(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(f"adapter port {port} is already in use; select a unique --port") from error


def _wait_for_health(
    port: int,
    *,
    expected_variant: str,
    process: subprocess.Popen[str],
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://127.0.0.1:{port}/health"
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"τ³-bench adapter exited before becoming healthy (return code {process.returncode})")
        try:
            with urlopen(url, timeout=2.0) as response:  # noqa: S310 - fixed loopback URL
                payload = json.loads(response.read().decode("utf-8"))
            if (
                response.status == 200
                and isinstance(payload, dict)
                and payload.get("status") == "ok"
                and payload.get("harness_variant") == expected_variant
            ):
                return payload
        except (OSError, URLError, ValueError) as error:
            last_error = error
            time.sleep(0.25)
    raise RuntimeError(f"τ³-bench adapter did not become healthy on port {port}: {last_error!r}")


def _stop(process: subprocess.Popen[str]) -> dict[str, Any]:
    if process.poll() is not None:
        return {"returncode": process.returncode, "terminated_by_launcher": False}
    process.terminate()
    try:
        returncode = process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        returncode = process.wait(timeout=15)
    return {"returncode": returncode, "terminated_by_launcher": True}


def _preserve_native_output(plan: dict[str, Any], run_dir: Path) -> dict[str, Any] | None:
    source = Path(str(plan["tau2"]["native_output_directory"]))
    if not source.is_dir():
        return None
    destination = run_dir / "tau2-native-results"
    if destination.exists():
        raise RuntimeError(f"refusing to overwrite preserved τ³-bench artifacts: {destination}")
    shutil.copytree(source, destination)
    results = source / "results.json"
    record: dict[str, Any] = {
        "source_directory": str(source),
        "preserved_directory": str(destination),
        "results_file": str(results),
    }
    if results.is_file():
        record["results_record"] = _file_record(results)
        preserved_results = destination / "results.json"
        record["preserved_results_record"] = _file_record(preserved_results)
    return record


def _native_result_schema_validation(
    *,
    python: Path,
    tau2_root: Path,
    environment: dict[str, str],
    native_results_file: Path,
) -> dict[str, Any]:
    """Use the pinned τ³ runtime's own Pydantic model to validate results.json."""

    if not native_results_file.is_file():
        return {
            "schema": "tau2-results-pydantic/v1",
            "passed": False,
            "error": f"native results file does not exist: {native_results_file}",
        }
    try:
        completed = subprocess.run(
            [str(python), "-c", _NATIVE_RESULT_SCHEMA_PROBE_SCRIPT, str(native_results_file)],
            cwd=tau2_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "schema": "tau2-results-pydantic/v1",
            "passed": False,
            "error": repr(error),
        }
    payload: dict[str, Any] | None = None
    for line in reversed(completed.stdout.splitlines()):
        try:
            candidate = json.loads(line)
        except ValueError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    if payload is None:
        detail = completed.stderr.strip() or completed.stdout.strip() or "schema probe returned no JSON payload"
        return {
            "schema": "tau2-results-pydantic/v1",
            "passed": False,
            "error": detail,
        }
    if completed.returncode != 0 or payload.get("passed") is not True:
        return {
            "schema": "tau2-results-pydantic/v1",
            "passed": False,
            "error": str(payload.get("error") or completed.stderr.strip() or "τ³ Pydantic validation failed"),
        }
    if payload.get("schema") != "tau2-results-pydantic/v1":
        return {
            "schema": "tau2-results-pydantic/v1",
            "passed": False,
            "error": "τ³ Pydantic validation returned an unexpected schema marker",
        }
    return {
        **payload,
        "results_record": _file_record(native_results_file),
    }


def execute(plan: dict[str, Any]) -> dict[str, Any]:
    """Run the official benchmark and stop only the adapter launched here."""

    run_dir = Path(str(plan["run_dir"]))
    environment = os.environ.copy()
    environment.update({str(key): str(value) for key, value in dict(plan["environment"]).items()})
    adapter_command = [str(item) for item in plan["commands"]["adapter"]]
    benchmark_command = [str(item) for item in plan["commands"]["benchmark"]]
    tau2_root = Path(str(plan["tau2"]["root"]))
    adapter_stdout = run_dir / "adapter.stdout.log"
    adapter_stderr = run_dir / "adapter.stderr.log"
    benchmark_stdout = run_dir / "benchmark.stdout.log"
    benchmark_stderr = run_dir / "benchmark.stderr.log"
    adapter_log = run_dir / "adapter.jsonl"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process: subprocess.Popen[str] | None = None
    running = {**plan, "status": "running", "started_at_unix": time.time()}
    result: dict[str, Any] = running
    _write_json_atomic(run_dir / "run_manifest.json", running)
    try:
        _assert_port_available(int(plan["adapter"]["port"]))
        with adapter_stdout.open("w", encoding="utf-8") as adapter_out, adapter_stderr.open("w", encoding="utf-8") as adapter_err:
            process = subprocess.Popen(
                adapter_command,
                cwd=REPO_ROOT,
                env=environment,
                stdout=adapter_out,
                stderr=adapter_err,
                text=True,
                creationflags=creationflags,
            )
            health = _wait_for_health(
                int(plan["adapter"]["port"]),
                expected_variant=str(plan["adapter"]["harness_variant"]),
                process=process,
            )
            with benchmark_stdout.open("w", encoding="utf-8") as benchmark_out, benchmark_stderr.open("w", encoding="utf-8") as benchmark_err:
                benchmark = subprocess.run(
                    benchmark_command,
                    cwd=tau2_root,
                    env=environment,
                    stdout=benchmark_out,
                    stderr=benchmark_err,
                    text=True,
                    check=False,
                    creationflags=creationflags,
                )
        native_results_file = Path(str(plan["tau2"]["native_results_file"]))
        native_schema_validation = _native_result_schema_validation(
            python=Path(benchmark_command[0]),
            tau2_root=tau2_root,
            environment=environment,
            native_results_file=native_results_file,
        )
        native_output = _preserve_native_output(plan, run_dir)
        if native_output is not None:
            native_output["schema_validation"] = native_schema_validation
        completed = (
            benchmark.returncode == 0
            and native_results_file.is_file()
            and native_schema_validation.get("passed") is True
        )
        result = {
            **running,
            "status": "completed" if completed else "failed",
            "completed_at_unix": time.time(),
            "adapter_health": health,
            "benchmark_returncode": benchmark.returncode,
            "native_output": native_output,
        }
        if not completed:
            result["error"] = "τ³-bench did not return a successful, schema-valid native results.json artifact"
    except Exception as error:
        result = {
            **running,
            "status": "failed",
            "completed_at_unix": time.time(),
            "error": repr(error),
        }
    finally:
        if process is not None:
            result["adapter_process"] = _stop(process)
    if adapter_log.is_file():
        result["adapter_log"] = _file_record(adapter_log)
    _write_json_atomic(run_dir / "run_manifest.json", result)
    return result


def _config_from_args(args: argparse.Namespace) -> Tau2NativeRunConfig:
    return Tau2NativeRunConfig(
        checkpoint=Path(args.checkpoint).expanduser().resolve(),
        train_holdout_audit=Path(args.train_holdout_audit).expanduser().resolve(),
        project1_root=Path(args.project1_root).expanduser().resolve(),
        tau2_root=Path(args.tau2_root).expanduser().resolve(),
        tau2_runtime=Path(args.tau2_runtime).expanduser().resolve(),
        run_dir=Path(args.run_dir).expanduser().resolve(),
        python=Path(args.python).expanduser().resolve(),
        domain=args.domain,
        task_set=args.task_set,
        task_split=args.task_split,
        task_ids=tuple(args.task_id),
        variant=args.variant,
        seed=args.seed,
        num_trials=args.num_trials,
        max_steps=args.max_steps,
        max_errors=args.max_errors,
        max_new_tokens=args.max_new_tokens,
        quantization=args.quantization,
        port=args.port,
        registration=Path(args.registration).expanduser().resolve() if args.registration else None,
    )


def _configure_utf8_console() -> None:
    """Keep CLI help/errors usable on Windows legacy code pages."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--train-holdout-audit", required=True)
    parser.add_argument("--project1-root", required=True)
    parser.add_argument("--tau2-root", required=True)
    parser.add_argument("--tau2-runtime", required=True)
    parser.add_argument("--run-dir", required=True, help="must be a new directory")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--domain", default=SOLO_PROTOCOL["domain"])
    parser.add_argument("--task-set", default=SOLO_PROTOCOL["task_set"])
    parser.add_argument("--task-split", default=SOLO_PROTOCOL["task_split"])
    parser.add_argument("--task-id", action="append", required=True)
    parser.add_argument("--variant", choices=tuple(VARIANTS), default="model-only")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--num-trials", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--max-errors", type=int, default=10)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--quantization", choices=("4bit", "int4", "nf4"), default="4bit")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--registration", help="checked-in preregistration required with --execute")
    parser.add_argument("--execute", action="store_true", help="start the adapter and invoke τ³-bench; omit to write only a validated plan")
    args = parser.parse_args(argv)
    try:
        config = _config_from_args(args)
        if args.execute and config.registration is None:
            raise ValueError("--execute requires --registration so external task selection and budgets are precommitted")
        plan = build_plan(config)
        config.run_dir.mkdir(parents=True, exist_ok=False)
        _write_json_atomic(config.run_dir / "run_manifest.json", plan)
        result = execute(plan) if args.execute else plan
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    print(json.dumps({
        "status": result["status"],
        "run_manifest": str(config.run_dir / "run_manifest.json"),
        "tau2_commit": result["tau2"]["commit"],
        "variant": result["variant"],
        "executed": bool(args.execute),
    }, indent=2, sort_keys=True))
    return 0 if result["status"] in {"planned", "completed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
