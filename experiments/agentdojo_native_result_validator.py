"""Validate and summarize completed source-bound native AgentDojo runs.

AgentDojo owns task execution and utility/security grading. This module only
checks that the immutable launcher manifest, policy implementation, exact
registered selectors, and preserved native JSON logs remain mutually
consistent. It deliberately refuses to infer replay, broader safety coverage,
or a leaderboard result from a local run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from statistics import mean
from typing import Any

from experiments.source_tree import verify_source_tree_record
from experiments.native_evaluation_registration import verify_registration_record


SCHEMA = "agentdojo-native-result-validation/v1"
RUN_SCHEMA = "agentdojo-native-run/v1"
NATIVE_LOG_SCHEMA = "agentdojo-native-logs/v1"
PIPELINE_NAME = "openai-compatible"
DIRECT_ATTACK = "direct"
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_mapping(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not valid JSON: {path}") from error
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return dict(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _string(value, field)


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _integer(value: Any, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return value


def _number(value: Any, field: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be a finite number")
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return numeric


def _record_metadata(value: Any, field: str) -> dict[str, Any]:
    record = _mapping(value, field)
    path = _string(record.get("path"), f"{field}.path")
    digest = _string(record.get("sha256"), f"{field}.sha256").lower()
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError(f"{field}.sha256 must be a SHA-256 digest")
    bytes_count = _integer(record.get("bytes"), f"{field}.bytes", minimum=0)
    return {"path": path, "sha256": digest, "bytes": bytes_count}


def _verify_file_record(value: Any, field: str, *, expected_path: Path | None = None) -> dict[str, Any]:
    record = _record_metadata(value, field)
    path = Path(record["path"]).expanduser().resolve()
    if expected_path is not None and path != expected_path.resolve():
        raise ValueError(f"{field}.path does not match the immutable expected artifact location")
    if not path.is_file():
        raise ValueError(f"{field}.path does not exist: {path}")
    if _sha256(path) != record["sha256"]:
        raise ValueError(f"{field}.sha256 does not match its file")
    if path.stat().st_size != record["bytes"]:
        raise ValueError(f"{field}.bytes does not match its file")
    return {**record, "path": str(path)}


def _command_values(value: Any, field: str) -> list[str]:
    values = [_string(item, f"{field}[]") for item in _list(value, field)]
    if not values:
        raise ValueError(f"{field} must be a non-empty list")
    return values


def _module_in_command(command: Any, module: str, field: str) -> bool:
    values = _command_values(command, field)
    return any(values[index] == "-m" and values[index + 1] == module for index in range(len(values) - 1))


def _command_flag_values(command: Any, flag: str, field: str) -> list[str]:
    values = _command_values(command, field)
    matches = [index for index, value in enumerate(values) if value == flag]
    if any(index == len(values) - 1 for index in matches):
        raise ValueError(f"{field} contains {flag} without a value")
    return [values[index + 1] for index in matches]


def _command_single_flag(command: Any, flag: str, field: str) -> str:
    values = _command_flag_values(command, flag, field)
    if len(values) != 1:
        raise ValueError(f"{field} must contain exactly one {flag} value")
    return values[0]


def _command_optional_flag(command: Any, flag: str, field: str) -> str | None:
    values = _command_flag_values(command, flag, field)
    if len(values) > 1:
        raise ValueError(f"{field} must contain at most one {flag} value")
    return values[0] if values else None


def _command_path(command: Any, flag: str, field: str) -> Path:
    return Path(_command_single_flag(command, flag, field)).expanduser().resolve()


def _selectors(value: Any, field: str, *, allow_empty: bool) -> list[str]:
    items = [_string(item, f"{field}[]") for item in _list(value, field)]
    if not allow_empty and not items:
        raise ValueError(f"{field} must be non-empty")
    if len(set(items)) != len(items):
        raise ValueError(f"{field} must be unique")
    for item in items:
        if item in {".", ".."} or "/" in item or "\\" in item:
            raise ValueError(f"{field} must contain path-safe AgentDojo selector IDs")
    return items


def _validate_checkpoint(checkpoint: Mapping[str, Any]) -> tuple[Path, dict[str, dict[str, Any]]]:
    directory = Path(_string(checkpoint.get("directory"), "manifest.checkpoint.directory")).expanduser().resolve()
    records = {
        "model_weights": _verify_file_record(
            checkpoint.get("model_weights"),
            "manifest.checkpoint.model_weights",
            expected_path=directory / "model.safetensors",
        ),
        "merge_manifest": _verify_file_record(
            checkpoint.get("merge_manifest"),
            "manifest.checkpoint.merge_manifest",
            expected_path=directory / "merge_manifest.json",
        ),
        "training_manifest": _verify_file_record(
            checkpoint.get("training_manifest"),
            "manifest.checkpoint.training_manifest",
            expected_path=directory / "training_manifest.json",
        ),
    }
    return directory, records


def _validate_adapter(
    manifest: Mapping[str, Any],
    *,
    adapter: Mapping[str, Any],
    checkpoint_directory: Path,
    run_dir: Path,
) -> dict[str, Any]:
    commands = _mapping(manifest.get("commands"), "manifest.commands")
    adapter_command = commands.get("adapter")
    if not _module_in_command(adapter_command, "experiments.agentdojo_adapter_server", "manifest.commands.adapter"):
        raise ValueError("manifest adapter command does not invoke the recorded local adapter server")
    command_values = _command_values(adapter_command, "manifest.commands.adapter")
    if not Path(command_values[0]).expanduser().resolve().is_file():
        raise ValueError("manifest adapter Python runtime is no longer available for source-bound verification")
    if _command_path(adapter_command, "--model-checkpoint", "manifest.commands.adapter") != checkpoint_directory:
        raise ValueError("manifest adapter command is not bound to the recorded merged checkpoint")
    if _command_single_flag(adapter_command, "--host", "manifest.commands.adapter") != "127.0.0.1":
        raise ValueError("manifest adapter command must remain loopback-only")

    if adapter.get("host") != "127.0.0.1":
        raise ValueError("manifest.adapter must record a loopback-only host")
    port = _integer(adapter.get("port"), "manifest.adapter.port", minimum=1)
    if port > 65535:
        raise ValueError("manifest.adapter.port must be at most 65535")
    if _command_single_flag(adapter_command, "--port", "manifest.commands.adapter") != str(port):
        raise ValueError("manifest adapter command port does not match the registered adapter")
    policy = _mapping(manifest.get("policy"), "manifest.policy")
    seed = _integer(policy.get("seed"), "manifest.policy.seed")
    max_new_tokens = _integer(policy.get("max_new_tokens"), "manifest.policy.max_new_tokens", minimum=1)
    if _command_single_flag(adapter_command, "--seed", "manifest.commands.adapter") != str(seed):
        raise ValueError("manifest adapter command seed does not match the registered policy")
    if _command_single_flag(adapter_command, "--max-new-tokens", "manifest.commands.adapter") != str(max_new_tokens):
        raise ValueError("manifest adapter command token limit does not match the registered policy")

    harness_variant = _string(adapter.get("harness_variant"), "manifest.adapter.harness_variant")
    if _command_single_flag(adapter_command, "--harness-variant", "manifest.commands.adapter") != harness_variant:
        raise ValueError("manifest adapter command harness variant does not match the registered adapter")
    enable_repair = _boolean(adapter.get("enable_repair"), "manifest.adapter.enable_repair")
    if ("--enable-repair" in command_values) != enable_repair:
        raise ValueError("manifest adapter repair setting does not match the recorded command")
    if adapter.get("lookup_first_enabled") is not False or "--enable-evidence-first-guard" in command_values:
        raise ValueError("native AgentDojo result must not silently enable the unsupported lookup-first condition")

    harness_root = _command_path(adapter_command, "--harness-root", "manifest.commands.adapter")
    project1_root = _command_path(adapter_command, "--project1-root", "manifest.commands.adapter")
    source_record = _verify_file_record(
        adapter.get("source"),
        "manifest.adapter.source",
        expected_path=harness_root / "experiments" / "agentdojo_adapter_server.py",
    )
    source_trees = _mapping(adapter.get("source_trees"), "manifest.adapter.source_trees")
    project1_source = verify_source_tree_record(
        source_trees.get("project1"),
        field="manifest.adapter.source_trees.project1",
        expected_root=project1_root,
    )
    harness_source = verify_source_tree_record(
        source_trees.get("harness"),
        field="manifest.adapter.source_trees.harness",
        expected_root=harness_root,
    )
    adapter_log = _verify_file_record(
        manifest.get("adapter_log"),
        "manifest.adapter_log",
        expected_path=run_dir / "adapter.jsonl",
    )
    health = _mapping(manifest.get("adapter_health"), "manifest.adapter_health")
    if (
        health.get("status") != "ok"
        or health.get("model_checkpoint_configured") is not True
        or health.get("model_loaded") is not True
        or health.get("harness_variant") != harness_variant
    ):
        raise ValueError("manifest.adapter_health does not prove the recorded adapter loaded the registered checkpoint")
    return {
        "source": source_record,
        "source_trees": {"project1": project1_source, "harness": harness_source},
        "log": adapter_log,
        "health": dict(health),
    }


def _expected_logs(
    *,
    suite: str,
    user_tasks: list[str],
    injection_tasks: list[str],
    attack: str | None,
) -> list[dict[str, str | None]]:
    expected: list[dict[str, str | None]] = []
    if attack is None:
        for user_task in user_tasks:
            expected.append(
                {
                    "kind": "clean_user",
                    "user_task_id": user_task,
                    "injection_task_id": None,
                    "attack_type": None,
                    "relative_path": f"{PIPELINE_NAME}/{suite}/{user_task}/none/none.json",
                }
            )
        return expected
    for injection_task in injection_tasks:
        expected.append(
            {
                "kind": "injection_control",
                "user_task_id": injection_task,
                "injection_task_id": None,
                "attack_type": None,
                "relative_path": f"{PIPELINE_NAME}/{suite}/{injection_task}/none/none.json",
            }
        )
    for user_task in user_tasks:
        for injection_task in injection_tasks:
            expected.append(
                {
                    "kind": "injection_composite",
                    "user_task_id": user_task,
                    "injection_task_id": injection_task,
                    "attack_type": attack,
                    "relative_path": f"{PIPELINE_NAME}/{suite}/{user_task}/{attack}/{injection_task}.json",
                }
            )
    return expected


def _validate_native_output(
    manifest: Mapping[str, Any],
    *,
    run_dir: Path,
    expected: list[dict[str, str | None]],
) -> dict[str, dict[str, Any]]:
    output = _mapping(manifest.get("native_output"), "manifest.native_output")
    if output.get("schema") != NATIVE_LOG_SCHEMA:
        raise ValueError(f"manifest.native_output.schema must be {NATIVE_LOG_SCHEMA}")
    directory = Path(_string(output.get("directory"), "manifest.native_output.directory")).expanduser().resolve()
    if directory != (run_dir / "native-logs").resolve():
        raise ValueError("native AgentDojo logs must be preserved inside the immutable run directory")
    records = _list(output.get("records"), "manifest.native_output.records")
    if not records:
        raise ValueError("manifest.native_output.records must be non-empty")

    by_relative_path: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(records):
        record = _verify_file_record(value, f"manifest.native_output.records[{index}]")
        path = Path(record["path"]).resolve()
        try:
            relative_path = path.relative_to(directory).as_posix()
        except ValueError as error:
            raise ValueError("native AgentDojo log record is outside the preserved log directory") from error
        if Path(relative_path).suffix != ".json" or relative_path in by_relative_path:
            raise ValueError("native AgentDojo log records must be unique JSON files")
        by_relative_path[relative_path] = record

    if not directory.is_dir():
        raise ValueError("native AgentDojo log directory no longer exists")
    current_paths = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*.json")
        if path.is_file()
    }
    if current_paths != set(by_relative_path):
        raise ValueError("native AgentDojo JSON files do not exactly match the launcher-recorded files")

    expected_paths = {str(item["relative_path"]) for item in expected}
    if set(by_relative_path) != expected_paths:
        raise ValueError("native AgentDojo log records do not exactly match the registered task selectors")
    return by_relative_path


def _validate_log_row(
    path: Path,
    *,
    expected: Mapping[str, str | None],
    suite: str,
    benchmark_version: str,
) -> dict[str, Any]:
    payload = _read_json_mapping(path, f"native AgentDojo result {path.name}")
    if payload.get("suite_name") != suite or payload.get("pipeline_name") != PIPELINE_NAME:
        raise ValueError("native AgentDojo result does not match the registered suite/pipeline")
    if payload.get("user_task_id") != expected["user_task_id"]:
        raise ValueError("native AgentDojo result user task does not match the registered selector")
    if payload.get("injection_task_id") != expected["injection_task_id"]:
        raise ValueError("native AgentDojo result injection task does not match the registered selector")
    if payload.get("attack_type") != expected["attack_type"]:
        raise ValueError("native AgentDojo result attack does not match the registered condition")
    if payload.get("benchmark_version") != benchmark_version:
        raise ValueError("native AgentDojo result benchmark version does not match the registered condition")
    if payload.get("error") is not None:
        raise ValueError("native AgentDojo result contains an execution error and must not be reported as a score")
    messages = _list(payload.get("messages"), "native AgentDojo result.messages")
    if len(messages) < 2:
        raise ValueError("native AgentDojo result must preserve its native interaction messages")
    injections = _mapping(payload.get("injections"), "native AgentDojo result.injections")
    if expected["kind"] == "injection_composite":
        if not injections:
            raise ValueError("native direct-injection result must record at least one injected payload")
    elif injections:
        raise ValueError("native clean/control result unexpectedly records injected payloads")
    utility = _boolean(payload.get("utility"), "native AgentDojo result.utility")
    security = _boolean(payload.get("security"), "native AgentDojo result.security")
    duration = _number(payload.get("duration"), "native AgentDojo result.duration", minimum=0.0)
    _string(payload.get("evaluation_timestamp"), "native AgentDojo result.evaluation_timestamp")
    _string(payload.get("agentdojo_package_version"), "native AgentDojo result.agentdojo_package_version")
    return {
        "relative_path": str(expected["relative_path"]),
        "kind": str(expected["kind"]),
        "user_task_id": str(expected["user_task_id"]),
        "injection_task_id": expected["injection_task_id"],
        "attack_type": expected["attack_type"],
        "utility": utility,
        "security": security,
        "duration_seconds": duration,
        "native_message_count": len(messages),
    }


def _validate_manifest(manifest: Mapping[str, Any], manifest_path: Path) -> dict[str, Any]:
    if manifest.get("schema") != RUN_SCHEMA:
        raise ValueError(f"run manifest must use {RUN_SCHEMA}")
    if manifest.get("status") != "completed":
        raise ValueError("run manifest must be completed before native results can be summarized")
    if manifest.get("benchmark_returncode") != 0:
        raise ValueError("run manifest must record a zero AgentDojo benchmark return code")
    run_dir = Path(_string(manifest.get("run_dir"), "manifest.run_dir")).expanduser().resolve()
    if run_dir != manifest_path.parent.resolve():
        raise ValueError("run manifest must be stored in its declared immutable run directory")

    checkpoint = _mapping(manifest.get("checkpoint"), "manifest.checkpoint")
    training_binding = _mapping(checkpoint.get("training_binding"), "manifest.checkpoint.training_binding")
    audit = _mapping(manifest.get("train_holdout_audit"), "manifest.train_holdout_audit")
    if training_binding.get("passed") is not True or audit.get("passed") is not True:
        raise ValueError("native results require a checkpoint bound to a passed clean train/holdout audit")
    checkpoint_directory, checkpoint_records = _validate_checkpoint(checkpoint)

    policy = _mapping(manifest.get("policy"), "manifest.policy")
    if policy.get("do_sample") is not False:
        raise ValueError("manifest.policy.do_sample must be false for the registered native condition")
    _integer(policy.get("seed"), "manifest.policy.seed")
    _integer(policy.get("max_new_tokens"), "manifest.policy.max_new_tokens", minimum=1)

    variant = _string(manifest.get("variant"), "manifest.variant")
    if variant not in {"model-only", "repair"}:
        raise ValueError("manifest.variant must be model-only or repair")
    adapter = _mapping(manifest.get("adapter"), "manifest.adapter")
    if _boolean(adapter.get("enable_repair"), "manifest.adapter.enable_repair") != (variant == "repair"):
        raise ValueError("manifest adapter repair setting does not match the registered variant")
    adapter_binding = _validate_adapter(
        manifest,
        adapter=adapter,
        checkpoint_directory=checkpoint_directory,
        run_dir=run_dir,
    )

    agentdojo = _mapping(manifest.get("agentdojo"), "manifest.agentdojo")
    agentdojo_root = Path(_string(agentdojo.get("root"), "manifest.agentdojo.root")).expanduser().resolve()
    entrypoint = Path(_string(agentdojo.get("entrypoint"), "manifest.agentdojo.entrypoint")).expanduser().resolve()
    if entrypoint != (agentdojo_root / "src" / "agentdojo" / "scripts" / "benchmark.py").resolve() or not entrypoint.is_file():
        raise ValueError("manifest AgentDojo entrypoint is not the pinned official benchmark module")
    commit = _string(agentdojo.get("commit"), "manifest.agentdojo.commit")
    if not _GIT_COMMIT_RE.fullmatch(commit):
        raise ValueError("manifest.agentdojo.commit must be a hexadecimal Git commit")
    benchmark_version = _string(agentdojo.get("benchmark_version"), "manifest.agentdojo.benchmark_version")
    suite = _string(agentdojo.get("suite"), "manifest.agentdojo.suite")
    user_tasks = _selectors(agentdojo.get("user_tasks"), "manifest.agentdojo.user_tasks", allow_empty=False)
    injection_tasks = _selectors(agentdojo.get("injection_tasks"), "manifest.agentdojo.injection_tasks", allow_empty=True)
    attack = _optional_string(agentdojo.get("attack"), "manifest.agentdojo.attack")
    defense = _optional_string(agentdojo.get("defense"), "manifest.agentdojo.defense")
    if bool(injection_tasks) != bool(attack):
        raise ValueError("native AgentDojo condition must register attack and injection tasks together")
    if attack is not None and attack != DIRECT_ATTACK:
        raise ValueError("only the registered direct-injection AgentDojo condition is currently reportable")

    catalog = _mapping(agentdojo.get("selector_catalog"), "manifest.agentdojo.selector_catalog")
    if catalog.get("schema") != "agentdojo-selector-catalog/v1":
        raise ValueError("manifest AgentDojo selector catalog has an unexpected schema")
    if catalog.get("benchmark_version") != benchmark_version or catalog.get("suite") != suite:
        raise ValueError("manifest AgentDojo selector catalog does not match the registered condition")
    catalog_digest = _string(catalog.get("sha256"), "manifest.agentdojo.selector_catalog.sha256")
    if not _SHA256_RE.fullmatch(catalog_digest):
        raise ValueError("manifest AgentDojo selector catalog must record a SHA-256 digest")
    catalog_user_tasks = set(_selectors(catalog.get("user_tasks"), "manifest.agentdojo.selector_catalog.user_tasks", allow_empty=True))
    catalog_injection_tasks = set(
        _selectors(catalog.get("injection_tasks"), "manifest.agentdojo.selector_catalog.injection_tasks", allow_empty=True)
    )
    catalog_attacks = set(_selectors(catalog.get("attacks"), "manifest.agentdojo.selector_catalog.attacks", allow_empty=True))
    catalog_defenses = set(_selectors(catalog.get("defenses"), "manifest.agentdojo.selector_catalog.defenses", allow_empty=True))
    if not set(user_tasks).issubset(catalog_user_tasks) or not set(injection_tasks).issubset(catalog_injection_tasks):
        raise ValueError("manifest AgentDojo task selectors are not present in the registered catalog")
    if attack is not None and attack not in catalog_attacks:
        raise ValueError("manifest AgentDojo attack is not present in the registered catalog")
    if defense is not None and defense not in catalog_defenses:
        raise ValueError("manifest AgentDojo defense is not present in the registered catalog")

    commands = _mapping(manifest.get("commands"), "manifest.commands")
    benchmark_command = commands.get("benchmark")
    if not _module_in_command(benchmark_command, "agentdojo.scripts.benchmark", "manifest.commands.benchmark"):
        raise ValueError("manifest benchmark command does not invoke AgentDojo's official benchmark module")
    benchmark_values = _command_values(benchmark_command, "manifest.commands.benchmark")
    adapter_values = _command_values(commands.get("adapter"), "manifest.commands.adapter")
    if Path(benchmark_values[0]).expanduser().resolve() != Path(adapter_values[0]).expanduser().resolve():
        raise ValueError("manifest benchmark and adapter must use the same recorded Python runtime")
    if _command_single_flag(benchmark_command, "--model", "manifest.commands.benchmark") != PIPELINE_NAME:
        raise ValueError("manifest benchmark must use AgentDojo's openai-compatible pipeline")
    if _command_single_flag(benchmark_command, "--model-id", "manifest.commands.benchmark") != "local-action-policy":
        raise ValueError("manifest benchmark is not bound to the registered local policy identifier")
    if _command_single_flag(benchmark_command, "--benchmark-version", "manifest.commands.benchmark") != benchmark_version:
        raise ValueError("manifest benchmark version does not match the registered condition")
    if _command_single_flag(benchmark_command, "--suite", "manifest.commands.benchmark") != suite:
        raise ValueError("manifest benchmark suite does not match the registered condition")
    if _command_path(benchmark_command, "--logdir", "manifest.commands.benchmark") != (run_dir / "native-logs").resolve():
        raise ValueError("manifest benchmark log directory is not the immutable native-log directory")
    if _command_flag_values(benchmark_command, "--user-task", "manifest.commands.benchmark") != user_tasks:
        raise ValueError("manifest benchmark user-task selectors do not match the registered condition")
    if _command_flag_values(benchmark_command, "--injection-task", "manifest.commands.benchmark") != injection_tasks:
        raise ValueError("manifest benchmark injection-task selectors do not match the registered condition")
    if _command_optional_flag(benchmark_command, "--attack", "manifest.commands.benchmark") != attack:
        raise ValueError("manifest benchmark attack does not match the registered condition")
    if _command_optional_flag(benchmark_command, "--defense", "manifest.commands.benchmark") != defense:
        raise ValueError("manifest benchmark defense does not match the registered condition")

    expected = _expected_logs(
        suite=suite,
        user_tasks=user_tasks,
        injection_tasks=injection_tasks,
        attack=attack,
    )
    native_records = _validate_native_output(manifest, run_dir=run_dir, expected=expected)
    registration = verify_registration_record(manifest["registration"]) if "registration" in manifest else None
    if registration is not None:
        if registration["benchmark"] != "agentdojo":
            raise ValueError("manifest preregistration is not an AgentDojo registration")
        expected_condition = "direct_injection" if injection_tasks else "clean"
        if registration.get("condition") != expected_condition:
            raise ValueError("manifest preregistration condition does not match the native AgentDojo selectors")
    return {
        "run_dir": run_dir,
        "checkpoint_records": checkpoint_records,
        "adapter_binding": adapter_binding,
        "agentdojo": dict(agentdojo),
        "variant": variant,
        "policy": dict(policy),
        "condition": {
            "suite": suite,
            "benchmark_version": benchmark_version,
            "user_tasks": user_tasks,
            "injection_tasks": injection_tasks,
            "attack": attack,
            "defense": defense,
        },
        "expected_logs": expected,
        "native_records": native_records,
        "registration": registration,
    }


def validate_native_result(run_manifest_path: str | Path) -> dict[str, Any]:
    """Return a claim-safe summary of one completed source-bound AgentDojo run."""

    manifest_path = Path(run_manifest_path).expanduser().resolve()
    manifest = _read_json_mapping(manifest_path, "run manifest")
    validated = _validate_manifest(manifest, manifest_path)
    condition = validated["condition"]
    rows = []
    for expected in validated["expected_logs"]:
        record = validated["native_records"][str(expected["relative_path"])]
        rows.append(
            _validate_log_row(
                Path(record["path"]),
                expected=expected,
                suite=str(condition["suite"]),
                benchmark_version=str(condition["benchmark_version"]),
            )
        )

    injection_run = condition["attack"] is not None
    if injection_run:
        controls = [row for row in rows if row["kind"] == "injection_control"]
        composites = [row for row in rows if row["kind"] == "injection_composite"]
        primary = {
            "name": "joint_utility_security_rate",
            "value": sum(bool(row["utility"]) and bool(row["security"]) for row in composites) / len(composites),
            "source": "AgentDojo native TaskResults.utility and TaskResults.security",
        }
        metrics: dict[str, Any] = {
            "utility_rate": sum(bool(row["utility"]) for row in composites) / len(composites),
            "security_rate": sum(bool(row["security"]) for row in composites) / len(composites),
            "joint_utility_security_rate": primary["value"],
            "injection_control_utility_rate": sum(bool(row["utility"]) for row in controls) / len(controls),
            "composite_runs": len(composites),
            "injection_control_runs": len(controls),
        }
        condition_label = "native AgentDojo direct-injection condition"
        security_boundary = "measured only for the registered direct-injection task pairs"
    else:
        clean_rows = [row for row in rows if row["kind"] == "clean_user"]
        primary = {
            "name": "utility_rate",
            "value": sum(bool(row["utility"]) for row in clean_rows) / len(clean_rows),
            "source": "AgentDojo native TaskResults.utility",
        }
        metrics = {
            "utility_rate": primary["value"],
            "clean_user_runs": len(clean_rows),
            "security_measurement": "not applicable: clean AgentDojo runs set security true without an injection task",
        }
        condition_label = "native AgentDojo clean utility condition"
        security_boundary = "not measured: this is a clean utility-only condition"

    durations = [float(row["duration_seconds"]) for row in rows]
    native_records = [validated["native_records"][str(expected["relative_path"])] for expected in validated["expected_logs"]]
    return {
        "schema": SCHEMA,
        "status": "locally_consistent",
        "condition": condition_label,
        "provenance": {
            "run_manifest": {"path": str(manifest_path), "sha256": _sha256(manifest_path)},
            "agentdojo": {
                "commit": validated["agentdojo"]["commit"],
                "root": validated["agentdojo"]["root"],
                "selector_catalog_sha256": validated["agentdojo"]["selector_catalog"]["sha256"],
            },
            "checkpoint": validated["checkpoint_records"],
            "adapter": validated["adapter_binding"],
            "native_logs": native_records,
            **({"registration": validated["registration"]} if validated["registration"] is not None else {}),
        },
        "attestation": {
            "status": "not_provided",
            "meaning": "local manifest and file hashes establish consistency, not independent cryptographic attestation of execution",
        },
        "configuration": {
            "variant": validated["variant"],
            "seed": validated["policy"]["seed"],
            "max_new_tokens": validated["policy"]["max_new_tokens"],
            "quantization": validated["policy"].get("quantization"),
            "suite": condition["suite"],
            "benchmark_version": condition["benchmark_version"],
            "user_tasks": condition["user_tasks"],
            "injection_tasks": condition["injection_tasks"],
            "attack": condition["attack"],
            "defense": condition["defense"],
        },
        "native_metric": primary,
        "native_metrics": metrics,
        "run_count": len(rows),
        "timing": {
            "reported_duration_seconds": {
                "total": sum(durations),
                "mean": mean(durations),
            }
        },
        "trace_availability": {
            "native_logs_preserved": len(rows),
            "all_rows_have_native_messages": all(int(row["native_message_count"]) >= 2 for row in rows),
            "independent_trace_replay": "not measured",
        },
        "rows": rows,
        "not_measured": {
            "independent_trace_replay": "not measured: native messages are retained but were not independently replayed",
            "security_scope": security_boundary,
            "full_suite_coverage": "not measured: only the exact registered selectors are included",
            "cross_model_comparison": "not measured: a single checkpoint/variant does not establish a comparative result",
        },
        "claim_boundary": (
            "locally consistent native AgentDojo result for the exact registered condition only. "
            "Report the native metric with its selectors, commit, checkpoint and source bindings. "
            "Do not infer independent replay, full-suite performance, a leaderboard result, or safety beyond the stated condition."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-manifest", required=True, help="completed AgentDojo launcher run_manifest.json")
    parser.add_argument("--output", required=True, help="new JSON validation output path")
    args = parser.parse_args(argv)
    output = Path(args.output).expanduser().resolve()
    try:
        if output.exists():
            raise ValueError(f"refusing to overwrite an existing validation artifact: {output}")
        result = validate_native_result(args.run_manifest)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                "status": result["status"],
                "native_metric": result["native_metric"],
                "run_count": result["run_count"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
