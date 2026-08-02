"""Plan or execute one checkpoint-bound native AgentDojo evaluation.

The launcher keeps AgentDojo's own runner and utility/security metrics intact.
It only supplies a local OpenAI-compatible endpoint for the policy and writes
the exact benchmark, adapter, checkpoint, and data-split provenance beside the
native logs. By default it is a dry planning command; ``--execute`` is an
explicit opt-in because a benchmark request lazily loads the model onto the
local GPU.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
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
from experiments.native_evaluation_registration import validate_agentdojo_registration
from experiments.source_tree import record_source_tree


REPO_ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {
    "model-only": {
        "harness_variant": "H4-agentdojo-native-model-only",
        "enable_repair": False,
    },
    "repair": {
        "harness_variant": "H4-agentdojo-native-repair",
        "enable_repair": True,
    },
}


_SELECTOR_CATALOG_SCRIPT = """
import json
import sys

from agentdojo.task_suite.load_suites import get_suite
from agentdojo.agent_pipeline.agent_pipeline import DEFENSES
from agentdojo.attacks.attack_registry import ATTACKS

benchmark_version, suite_name = sys.argv[1:]
suite = get_suite(benchmark_version, suite_name)
print(json.dumps({
    "user_tasks": sorted(suite.user_tasks),
    "injection_tasks": sorted(suite.injection_tasks),
    "attacks": sorted(ATTACKS),
    "defenses": sorted(DEFENSES),
}, sort_keys=True))
"""


@dataclass(frozen=True)
class NativeRunConfig:
    checkpoint: Path
    train_holdout_audit: Path
    project1_root: Path
    agentdojo_root: Path
    agentdojo_runtime: Path
    run_dir: Path
    python: Path
    user_tasks: tuple[str, ...]
    injection_tasks: tuple[str, ...]
    variant: str
    benchmark_version: str
    suite: str
    attack: str | None
    defense: str | None
    seed: int
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


def _native_log_records(log_directory: Path) -> dict[str, Any]:
    """Bind every official AgentDojo JSON log emitted by a completed run."""

    native_logs = log_directory.resolve()
    if not native_logs.is_dir():
        raise ValueError(f"native AgentDojo log directory does not exist: {native_logs}")
    records = [_file_record(path) for path in sorted(native_logs.rglob("*.json")) if path.is_file()]
    if not records:
        raise ValueError(f"native AgentDojo log directory contains no JSON task results: {native_logs}")
    return {
        "schema": "agentdojo-native-logs/v1",
        "directory": str(native_logs),
        "records": records,
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
        raise ValueError(f"could not inspect pinned AgentDojo checkout: {detail}")
    return completed.stdout.strip()


def _agentdojo_environment(config: NativeRunConfig) -> tuple[dict[str, str], list[str]]:
    pythonpath = [
        str(config.agentdojo_root / "src"),
        str(config.agentdojo_root.parent),
        str(config.agentdojo_runtime),
        str(config.project1_root),
        str(REPO_ROOT),
    ]
    environment = {
        "OPENAI_COMPATIBLE_BASE_URL": f"http://127.0.0.1:{config.port}/v1",
        "OPENAI_COMPATIBLE_API_KEY": "local",
        "PYTHONPATH": os.pathsep.join(pythonpath + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])),
    }
    return environment, pythonpath


def _adapter_command(config: NativeRunConfig) -> list[str]:
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


def _benchmark_command(config: NativeRunConfig) -> list[str]:
    command = [
        str(config.python),
        "-m",
        "agentdojo.scripts.benchmark",
        "--model",
        "openai-compatible",
        "--model-id",
        "local-action-policy",
        "--benchmark-version",
        config.benchmark_version,
        "--suite",
        config.suite,
        "--logdir",
        str(config.run_dir / "native-logs"),
    ]
    for task_id in config.user_tasks:
        command.extend(["--user-task", task_id])
    for task_id in config.injection_tasks:
        command.extend(["--injection-task", task_id])
    if config.attack:
        command.extend(["--attack", config.attack])
    if config.defense:
        command.extend(["--defense", config.defense])
    return command


def _selector_catalog(config: NativeRunConfig, environment: dict[str, str]) -> dict[str, Any]:
    """Read valid selectors from the pinned benchmark without loading the policy."""

    selector_environment = os.environ.copy()
    selector_environment.update(environment)
    try:
        completed = subprocess.run(
            [
                str(config.python),
                "-c",
                _SELECTOR_CATALOG_SCRIPT,
                config.benchmark_version,
                config.suite,
            ],
            cwd=config.agentdojo_root,
            env=selector_environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"could not inspect task selectors from the pinned AgentDojo checkout: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown selector-catalog error"
        raise ValueError(f"could not inspect task selectors from the pinned AgentDojo checkout: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except ValueError as error:
        raise ValueError("pinned AgentDojo selector catalog was not valid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("pinned AgentDojo selector catalog was not an object")
    user_tasks = payload.get("user_tasks")
    injection_tasks = payload.get("injection_tasks")
    attacks = payload.get("attacks")
    defenses = payload.get("defenses")
    if not (
        isinstance(user_tasks, list)
        and isinstance(injection_tasks, list)
        and isinstance(attacks, list)
        and isinstance(defenses, list)
        and all(isinstance(item, str) and item for item in user_tasks + injection_tasks + attacks + defenses)
    ):
        raise ValueError("pinned AgentDojo selector catalog had invalid task IDs")
    normalized = {
        "schema": "agentdojo-selector-catalog/v1",
        "benchmark_version": config.benchmark_version,
        "suite": config.suite,
        "user_tasks": sorted(set(user_tasks)),
        "injection_tasks": sorted(set(injection_tasks)),
        "attacks": sorted(set(attacks)),
        "defenses": sorted(set(defenses)),
    }
    normalized_bytes = (json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return {**normalized, "sha256": hashlib.sha256(normalized_bytes).hexdigest()}


def _validate_selectors(config: NativeRunConfig, catalog: dict[str, Any]) -> None:
    available_user_tasks = set(catalog["user_tasks"])
    available_injection_tasks = set(catalog["injection_tasks"])
    available_attacks = set(catalog["attacks"])
    available_defenses = set(catalog["defenses"])
    if len(set(config.user_tasks)) != len(config.user_tasks):
        raise ValueError("each --user-task selector must be unique to preserve the registered evaluation budget")
    if len(set(config.injection_tasks)) != len(config.injection_tasks):
        raise ValueError("each --injection-task selector must be unique to preserve the registered evaluation budget")
    unknown_user_tasks = sorted(set(config.user_tasks) - available_user_tasks)
    unknown_injection_tasks = sorted(set(config.injection_tasks) - available_injection_tasks)
    if unknown_user_tasks:
        raise ValueError(
            "--user-task selector(s) not found in the pinned "
            f"AgentDojo {config.suite!r} suite at {config.benchmark_version}: {', '.join(unknown_user_tasks)}"
        )
    if unknown_injection_tasks:
        raise ValueError(
            "--injection-task selector(s) not found in the pinned "
            f"AgentDojo {config.suite!r} suite at {config.benchmark_version}: {', '.join(unknown_injection_tasks)}"
        )
    if config.attack and config.attack not in available_attacks:
        raise ValueError(f"--attack is not registered by the pinned AgentDojo checkout: {config.attack}")
    if config.defense and config.defense not in available_defenses:
        raise ValueError(f"--defense is not registered by the pinned AgentDojo checkout: {config.defense}")


def build_plan(config: NativeRunConfig) -> dict[str, Any]:
    """Validate immutable inputs and return an executable native-run plan."""

    if config.variant not in VARIANTS:
        raise ValueError(f"unsupported native-evaluation variant: {config.variant}")
    if not config.user_tasks:
        raise ValueError("at least one --user-task is required; do not accidentally launch an unregistered full suite")
    if bool(config.injection_tasks) != bool(config.attack):
        raise ValueError("--attack and at least one --injection-task must be supplied together")
    if config.run_dir.exists():
        raise ValueError(f"--run-dir must be new to preserve immutable native logs: {config.run_dir}")
    if not config.python.is_file():
        raise ValueError(f"--python does not identify an executable file: {config.python}")
    if not config.project1_root.is_dir():
        raise ValueError(f"--project1-root is not a directory: {config.project1_root}")
    if not config.agentdojo_runtime.is_dir():
        raise ValueError(f"--agentdojo-runtime is not a directory: {config.agentdojo_runtime}")
    benchmark_entrypoint = config.agentdojo_root / "src" / "agentdojo" / "scripts" / "benchmark.py"
    if not benchmark_entrypoint.is_file():
        raise ValueError(f"--agentdojo-root does not contain the official benchmark entrypoint: {benchmark_entrypoint}")

    audit_gate = validate_required_audit_manifest(config.train_holdout_audit)
    if not audit_gate["passed"]:
        raise ValueError("--train-holdout-audit must prove clean isolation against every pinned fixture")
    checkpoint_binding = validate_checkpoint_training_binding(config.checkpoint, audit_gate)
    if not checkpoint_binding["passed"]:
        raise ValueError("--checkpoint must be a merged v2 checkpoint bound to the supplied clean training audit")

    agentdojo_commit = _git(config.agentdojo_root, "rev-parse", "HEAD")
    agentdojo_dirty = _git(config.agentdojo_root, "status", "--porcelain")
    if agentdojo_dirty:
        raise ValueError("--agentdojo-root must be clean; commit or discard local benchmark changes before a native run")
    environment, pythonpath = _agentdojo_environment(config)
    selector_catalog = _selector_catalog(config, environment)
    _validate_selectors(config, selector_catalog)
    registration = (
        validate_agentdojo_registration(
            config.registration,
            training_sources=audit_gate["training_sources"],
            variant=config.variant,
            source_commit=agentdojo_commit,
            benchmark_version=config.benchmark_version,
            suite=config.suite,
            user_tasks=config.user_tasks,
            injection_tasks=config.injection_tasks,
            attack=config.attack,
            defense=config.defense,
            seed=config.seed,
            max_new_tokens=config.max_new_tokens,
            quantization=config.quantization,
        )
        if config.registration is not None
        else None
    )
    adapter = REPO_ROOT / "experiments" / "agentdojo_adapter_server.py"
    plan = {
        "schema": "agentdojo-native-run/v1",
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
        "agentdojo": {
            "root": str(config.agentdojo_root),
            "commit": agentdojo_commit,
            "source_tree": record_source_tree(config.agentdojo_root),
            "benchmark_version": config.benchmark_version,
            "suite": config.suite,
            "user_tasks": list(config.user_tasks),
            "injection_tasks": list(config.injection_tasks),
            "attack": config.attack,
            "defense": config.defense,
            "entrypoint": str(benchmark_entrypoint),
            "selector_catalog": selector_catalog,
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
            "lookup_first_reason": "AgentDojo's OpenAI-compatible pipeline does not attach the task-bound metadata required for a fair lookup-first ablation.",
        },
        "policy": {
            "seed": config.seed,
            "do_sample": False,
            "max_new_tokens": config.max_new_tokens,
            "quantization": config.quantization,
        },
        "runtime": {
            "python": str(config.python),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "agentdojo_runtime": str(config.agentdojo_runtime),
            "pythonpath_entries": pythonpath,
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
            raise RuntimeError(f"AgentDojo adapter exited before becoming healthy (return code {process.returncode})")
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
    raise RuntimeError(f"AgentDojo adapter did not become healthy on port {port}: {last_error!r}")


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


def execute(plan: dict[str, Any]) -> dict[str, Any]:
    """Run the benchmark and always stop only the adapter launched here."""

    run_dir = Path(str(plan["run_dir"]))
    environment = os.environ.copy()
    environment.update({str(key): str(value) for key, value in dict(plan["environment"]).items()})
    adapter_command = [str(item) for item in plan["commands"]["adapter"]]
    benchmark_command = [str(item) for item in plan["commands"]["benchmark"]]
    agentdojo_root = Path(str(plan["agentdojo"]["root"]))
    adapter_stdout = run_dir / "adapter.stdout.log"
    adapter_stderr = run_dir / "adapter.stderr.log"
    benchmark_stdout = run_dir / "benchmark.stdout.log"
    benchmark_stderr = run_dir / "benchmark.stderr.log"
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
                    cwd=agentdojo_root,
                    env=environment,
                    stdout=benchmark_out,
                    stderr=benchmark_err,
                    text=True,
                    check=False,
                    creationflags=creationflags,
                )
        native_output = _native_log_records(run_dir / "native-logs") if benchmark.returncode == 0 else None
        result = {
            **running,
            "status": "completed" if benchmark.returncode == 0 else "failed",
            "completed_at_unix": time.time(),
            "adapter_health": health,
            "benchmark_returncode": benchmark.returncode,
        }
        if native_output is not None:
            result["native_output"] = native_output
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
        if result.get("status") == "completed":
            try:
                result["adapter_log"] = _file_record(run_dir / "adapter.jsonl")
            except (OSError, ValueError) as error:
                result = {**result, "status": "failed", "error": repr(error)}
    _write_json_atomic(run_dir / "run_manifest.json", result)
    return result


def _config_from_args(args: argparse.Namespace) -> NativeRunConfig:
    return NativeRunConfig(
        checkpoint=Path(args.checkpoint).expanduser().resolve(),
        train_holdout_audit=Path(args.train_holdout_audit).expanduser().resolve(),
        project1_root=Path(args.project1_root).expanduser().resolve(),
        agentdojo_root=Path(args.agentdojo_root).expanduser().resolve(),
        agentdojo_runtime=Path(args.agentdojo_runtime).expanduser().resolve(),
        run_dir=Path(args.run_dir).expanduser().resolve(),
        python=Path(args.python).expanduser().resolve(),
        user_tasks=tuple(args.user_task),
        injection_tasks=tuple(args.injection_task),
        variant=args.variant,
        benchmark_version=args.benchmark_version,
        suite=args.suite,
        attack=args.attack,
        defense=args.defense,
        seed=args.seed,
        max_new_tokens=args.max_new_tokens,
        quantization=args.quantization,
        port=args.port,
        registration=Path(args.registration).expanduser().resolve() if args.registration else None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--train-holdout-audit", required=True)
    parser.add_argument("--project1-root", required=True)
    parser.add_argument("--agentdojo-root", required=True)
    parser.add_argument("--agentdojo-runtime", required=True)
    parser.add_argument("--run-dir", required=True, help="must be a new directory")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--variant", choices=tuple(VARIANTS), default="model-only")
    parser.add_argument("--benchmark-version", default="v1.2.2")
    parser.add_argument("--suite", default="workspace")
    parser.add_argument("--user-task", action="append", required=True)
    parser.add_argument("--injection-task", action="append", default=[])
    parser.add_argument("--attack")
    parser.add_argument("--defense")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--quantization", choices=("4bit", "int4", "nf4"), default="4bit")
    parser.add_argument("--port", type=int, default=8089)
    parser.add_argument("--registration", help="checked-in preregistration required with --execute")
    parser.add_argument("--execute", action="store_true", help="start the adapter and invoke AgentDojo; omit to write only a validated plan")
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
        "agentdojo_commit": result["agentdojo"]["commit"],
        "variant": result["variant"],
        "executed": bool(args.execute),
    }, indent=2, sort_keys=True))
    return 0 if result["status"] in {"planned", "completed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
