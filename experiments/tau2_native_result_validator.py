"""Validate and summarize completed native τ³-bench solo results.

This is deliberately not a generic scorecard adapter. τ³-bench owns its
reward and grader semantics, while this module verifies that the preserved
native artifact is bound to a completed launcher manifest and emits only
measurements the native artifact actually contains. Native messages are not
represented as independently replayed traces, and the registered DummyUser
condition is not represented as interactive-user or safety evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import urlparse

from experiments.source_tree import verify_source_tree_record
from experiments.native_evaluation_registration import validate_tau2_registration, verify_registration_record


SCHEMA = "tau2-native-result-validation/v1"
RUN_SCHEMA = "tau2-native-run/v1"
COMPATIBILITY_ID = "tau2-dummy-user-constructor-v1"
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
_FAMILY_RE = re.compile(r"^\[([^\]]+)\]")
_SUCCESS_EPSILON = 1e-6


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


def _integer(value: Any, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return value


def _number(value: Any, field: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be a finite number")
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    if maximum is not None and numeric > maximum:
        raise ValueError(f"{field} must be at most {maximum}")
    return numeric


def _record_metadata(value: Any, field: str) -> dict[str, Any]:
    record = _mapping(value, field)
    path = _string(record.get("path"), f"{field}.path")
    sha256 = _string(record.get("sha256"), f"{field}.sha256").lower()
    if not _SHA256_RE.fullmatch(sha256):
        raise ValueError(f"{field}.sha256 must be a SHA-256 digest")
    bytes_count = _integer(record.get("bytes"), f"{field}.bytes", minimum=0)
    return {"path": path, "sha256": sha256, "bytes": bytes_count}


def _verify_file_record(value: Any, field: str, *, expected_path: Path | None = None) -> dict[str, Any]:
    record = _record_metadata(value, field)
    path = Path(record["path"]).expanduser().resolve()
    if expected_path is not None and path != expected_path.resolve():
        raise ValueError(f"{field}.path does not match the immutable expected artifact location")
    if not path.is_file():
        raise ValueError(f"{field}.path does not exist: {path}")
    actual_sha256 = _sha256(path)
    if actual_sha256 != record["sha256"]:
        raise ValueError(f"{field}.sha256 does not match its file")
    if path.stat().st_size != record["bytes"]:
        raise ValueError(f"{field}.bytes does not match its file")
    return {**record, "path": str(path)}


def _command_values(command: Any, field: str) -> list[str]:
    values = [_string(value, f"{field}[]") for value in _list(command, field)]
    if not values:
        raise ValueError(f"{field} must be a non-empty command")
    return values


def _require_module_command(command: Any, module: str, field: str) -> list[str]:
    values = _command_values(command, field)
    if len(values) < 3 or values[1] != "-m" or values[2] != module:
        raise ValueError(f"{field} must start with its Python runtime followed by -m {module}")
    return values


def _command_flag(command: Any, flag: str, field: str) -> str:
    values = _command_values(command, field)
    indices = [index for index, value in enumerate(values) if value == flag]
    if len(indices) != 1 or indices[0] == len(values) - 1:
        raise ValueError(f"{field} must contain exactly one {flag} value")
    return values[indices[0] + 1]


def _command_path(command: Any, flag: str, field: str) -> Path:
    return Path(_command_flag(command, flag, field)).expanduser().resolve()


def _family(task_id: str) -> str:
    match = _FAMILY_RE.match(task_id)
    return match.group(1) if match else "unparsed"


def _assert_loopback_api_base(value: Any, *, expected_port: int) -> None:
    api_base = _string(value, "native results.info.agent_info.llm_args.api_base")
    try:
        parsed = urlparse(api_base)
        port = parsed.port
    except ValueError as error:
        raise ValueError("native results must bind the policy to a valid loopback OpenAI-compatible endpoint") from error
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port != expected_port
        or parsed.path.rstrip("/") != "/v1"
        or parsed.params
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("native results must bind the policy to the recorded loopback adapter host, port, and /v1 endpoint")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git error"
        raise ValueError(f"could not inspect the pinned τ³-bench checkout: {detail}")
    return completed.stdout.strip()


def _catalog_strings(value: Any, field: str) -> list[str]:
    values = [_string(item, f"{field}[]") for item in _list(value, field)]
    if not values:
        raise ValueError(f"{field} must be a non-empty list")
    if values != sorted(set(values)):
        raise ValueError(f"{field} must be sorted and unique as emitted by the pinned selector probe")
    return values


def _validate_selector_catalog(tau2: Mapping[str, Any], selectors: list[str]) -> dict[str, Any]:
    catalog = _mapping(tau2.get("selector_catalog"), "manifest.tau2.selector_catalog")
    if catalog.get("schema") != "tau2-selector-catalog/v1":
        raise ValueError("manifest.tau2.selector_catalog has an unexpected schema")
    normalized = {
        "schema": "tau2-selector-catalog/v1",
        "domain": _string(catalog.get("domain"), "manifest.tau2.selector_catalog.domain"),
        "task_set": _string(catalog.get("task_set"), "manifest.tau2.selector_catalog.task_set"),
        "task_split": _string(catalog.get("task_split"), "manifest.tau2.selector_catalog.task_split"),
        "task_ids": _catalog_strings(catalog.get("task_ids"), "manifest.tau2.selector_catalog.task_ids"),
        "solo_task_ids": _catalog_strings(catalog.get("solo_task_ids"), "manifest.tau2.selector_catalog.solo_task_ids"),
    }
    if (
        normalized["domain"] != tau2["domain"]
        or normalized["task_set"] != tau2["task_set"]
        or normalized["task_split"] != tau2["task_split"]
    ):
        raise ValueError("manifest.tau2.selector_catalog does not match the registered τ³ condition")
    digest = hashlib.sha256(
        (json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    ).hexdigest()
    if _string(catalog.get("sha256"), "manifest.tau2.selector_catalog.sha256").lower() != digest:
        raise ValueError("manifest.tau2.selector_catalog.sha256 does not match its selector catalog")
    if not set(selectors).issubset(set(normalized["task_ids"])):
        raise ValueError("manifest.tau2.task_ids are not present in the pinned τ³ selector catalog")
    if not set(selectors).issubset(set(normalized["solo_task_ids"])):
        raise ValueError("manifest.tau2.task_ids are not valid for the pinned τ³ solo condition")
    return {**normalized, "sha256": digest}


def _validate_tau2_checkout(tau2: Mapping[str, Any], *, root: Path, commit: str) -> dict[str, Any]:
    source_tree = verify_source_tree_record(
        tau2.get("source_tree"),
        field="manifest.tau2.source_tree",
        expected_root=root,
    )
    current_commit = _git(root, "rev-parse", "HEAD").lower()
    if current_commit != commit.lower():
        raise ValueError("manifest.tau2.commit does not match the current pinned τ³ checkout")
    if _git(root, "status", "--porcelain"):
        raise ValueError("pinned τ³ checkout is dirty and cannot support a source-bound native result")
    return source_tree


def _runtime_module_file(runtime: Mapping[str, Any], module: str) -> Path:
    module_files = _mapping(runtime.get("module_files"), "manifest.runtime.module_files")
    path = Path(_string(module_files.get(module), f"manifest.runtime.module_files.{module}")).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"manifest runtime-resolved module file is unavailable: {module}")
    return path


def _positive_budget(manifest: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    policy = _mapping(manifest.get("policy"), "manifest.policy")
    budget = _mapping(manifest.get("budget"), "manifest.budget")
    if policy.get("model") != "openai/local-action-policy":
        raise ValueError("manifest.policy.model must be the registered local action policy")
    if policy.get("do_sample") is not False:
        raise ValueError("manifest.policy.do_sample must be false")
    _integer(policy.get("seed"), "manifest.policy.seed")
    _integer(policy.get("max_new_tokens"), "manifest.policy.max_new_tokens", minimum=1)
    for key in ("num_trials", "max_steps", "max_errors", "max_concurrency"):
        _integer(budget.get(key), f"manifest.budget.{key}", minimum=1)
    if budget.get("max_retries") != 0:
        raise ValueError("manifest.budget.max_retries must be zero")
    return policy, budget


def _validate_checkpoint_records(checkpoint: Mapping[str, Any]) -> tuple[Path, dict[str, dict[str, Any]]]:
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


def _validate_adapter_binding(
    manifest: Mapping[str, Any],
    *,
    adapter: Mapping[str, Any],
    policy: Mapping[str, Any],
    checkpoint_directory: Path,
    run_dir: Path,
) -> dict[str, Any]:
    source_record = _verify_file_record(adapter.get("source"), "manifest.adapter.source")
    adapter_command = _mapping(manifest.get("commands"), "manifest.commands").get("adapter")
    _require_module_command(adapter_command, "experiments.agentdojo_adapter_server", "commands.adapter")
    if _command_path(adapter_command, "--model-checkpoint", "commands.adapter") != checkpoint_directory:
        raise ValueError("manifest adapter command is not bound to the recorded merged checkpoint")
    if _command_flag(adapter_command, "--host", "commands.adapter") != "127.0.0.1":
        raise ValueError("manifest adapter command is not loopback-only")
    port = _integer(adapter.get("port"), "manifest.adapter.port", minimum=1)
    if _command_flag(adapter_command, "--port", "commands.adapter") != str(port):
        raise ValueError("manifest adapter command port does not match the registered adapter")
    if _command_flag(adapter_command, "--seed", "commands.adapter") != str(policy["seed"]):
        raise ValueError("manifest adapter command seed does not match the registered policy seed")
    if _command_flag(adapter_command, "--max-new-tokens", "commands.adapter") != str(policy["max_new_tokens"]):
        raise ValueError("manifest adapter command token limit does not match the registered policy")
    harness_variant = _string(adapter.get("harness_variant"), "manifest.adapter.harness_variant")
    if _command_flag(adapter_command, "--harness-variant", "commands.adapter") != harness_variant:
        raise ValueError("manifest adapter command harness variant does not match the registered adapter")
    harness_root = _command_path(adapter_command, "--harness-root", "commands.adapter")
    try:
        Path(source_record["path"]).relative_to(harness_root)
    except ValueError as error:
        raise ValueError("manifest.adapter.source is not contained in the adapter command harness root") from error
    project1_root = _command_path(adapter_command, "--project1-root", "commands.adapter")
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
    expected_log = run_dir / "adapter.jsonl"
    if _command_path(adapter_command, "--log", "commands.adapter") != expected_log:
        raise ValueError("manifest adapter command does not preserve its log in the immutable run directory")
    adapter_log = _verify_file_record(manifest.get("adapter_log"), "manifest.adapter_log", expected_path=expected_log)
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


def _validate_manifest(manifest: Mapping[str, Any], manifest_path: Path) -> dict[str, Any]:
    if manifest.get("schema") != RUN_SCHEMA:
        raise ValueError(f"run manifest must use {RUN_SCHEMA}")
    if manifest.get("status") != "completed":
        raise ValueError("run manifest must be completed before native results can be summarized")
    run_dir = Path(_string(manifest.get("run_dir"), "manifest.run_dir")).expanduser().resolve()
    if run_dir != manifest_path.parent.resolve():
        raise ValueError("run manifest must be stored in its declared immutable run directory")

    checkpoint = _mapping(manifest.get("checkpoint"), "manifest.checkpoint")
    training_binding = _mapping(checkpoint.get("training_binding"), "manifest.checkpoint.training_binding")
    audit = _mapping(manifest.get("train_holdout_audit"), "manifest.train_holdout_audit")
    if training_binding.get("passed") is not True or audit.get("passed") is not True:
        raise ValueError("native results require a checkpoint bound to a passed clean train/holdout audit")
    checkpoint_directory, checkpoint_records = _validate_checkpoint_records(checkpoint)

    tau2 = _mapping(manifest.get("tau2"), "manifest.tau2")
    if tau2.get("domain") != "telecom" or tau2.get("task_set") != "telecom" or tau2.get("task_split") != "base":
        raise ValueError("native results must use the registered τ³-bench telecom/base condition")
    if tau2.get("condition") != "official-solo-telecom; no external user simulator":
        raise ValueError("native result condition is not the registered official solo condition")
    commit = _string(tau2.get("commit"), "manifest.tau2.commit")
    if not _GIT_COMMIT_RE.fullmatch(commit):
        raise ValueError("manifest.tau2.commit must be a hexadecimal Git commit")
    tau2_root = Path(_string(tau2.get("root"), "manifest.tau2.root")).expanduser().resolve()
    tau2_source_tree = _validate_tau2_checkout(tau2, root=tau2_root, commit=commit)
    selectors = [_string(value, "manifest.tau2.task_ids[]") for value in _list(tau2.get("task_ids"), "manifest.tau2.task_ids")]
    if not selectors or len(set(selectors)) != len(selectors):
        raise ValueError("manifest.tau2.task_ids must be a non-empty, unique selector list")
    selector_catalog = _validate_selector_catalog(tau2, selectors)

    variant = _string(manifest.get("variant"), "manifest.variant")
    if variant not in {"model-only", "repair"}:
        raise ValueError("manifest.variant must be model-only or repair")
    policy, budget = _positive_budget(manifest)
    adapter = _mapping(manifest.get("adapter"), "manifest.adapter")
    if adapter.get("host") != "127.0.0.1" or not isinstance(adapter.get("harness_variant"), str) or not adapter["harness_variant"]:
        raise ValueError("manifest.adapter must bind a named harness variant to loopback")
    adapter_binding = _validate_adapter_binding(
        manifest,
        adapter=adapter,
        policy=policy,
        checkpoint_directory=checkpoint_directory,
        run_dir=run_dir,
    )
    runtime = _mapping(manifest.get("runtime"), "manifest.runtime")
    if runtime.get("source_bound") is not True:
        raise ValueError("manifest.runtime.source_bound must be true")
    package_file = Path(_string(runtime.get("package_file"), "manifest.runtime.package_file")).expanduser().resolve()
    try:
        package_file.relative_to(tau2_root)
    except ValueError as error:
        raise ValueError("manifest.runtime.package_file is not imported from the pinned τ³ checkout") from error
    if not package_file.is_file():
        raise ValueError("manifest.runtime.package_file is not available for source-bound verification")

    wrapper = _mapping(manifest.get("runner_wrapper"), "manifest.runner_wrapper")
    if wrapper.get("delegates_to") != "tau2.cli.main":
        raise ValueError("manifest.runner_wrapper must delegate directly to tau2.cli.main")
    wrapper_record = _verify_file_record(wrapper.get("source"), "manifest.runner_wrapper.source")
    adapter_module_file = _runtime_module_file(runtime, "experiments.agentdojo_adapter_server")
    runner_module_file = _runtime_module_file(runtime, "experiments.tau2_native_runner")
    if adapter_module_file != Path(adapter_binding["source"]["path"]).resolve():
        raise ValueError("manifest runtime did not resolve the recorded adapter source module")
    if runner_module_file != Path(wrapper_record["path"]).resolve():
        raise ValueError("manifest runtime did not resolve the recorded τ³ runner-wrapper module")
    harness_root = Path(adapter_binding["source_trees"]["harness"]["root"]).resolve()
    try:
        runner_module_file.relative_to(harness_root)
    except ValueError as error:
        raise ValueError("manifest τ³ runner-wrapper source is outside the recorded harness source tree") from error
    compatibility = _mapping(wrapper.get("compatibility"), "manifest.runner_wrapper.compatibility")
    if compatibility.get("id") != COMPATIBILITY_ID or not isinstance(compatibility.get("required"), bool):
        raise ValueError("manifest.runner_wrapper compatibility metadata is incomplete or unexpected")
    commands = _mapping(manifest.get("commands"), "manifest.commands")
    benchmark_command = _require_module_command(
        commands.get("benchmark"), "experiments.tau2_native_runner", "commands.benchmark"
    )
    adapter_command = _command_values(commands.get("adapter"), "commands.adapter")
    if Path(benchmark_command[0]).expanduser().resolve() != Path(adapter_command[0]).expanduser().resolve():
        raise ValueError("manifest benchmark and adapter must use the same recorded τ³ Python runtime")
    if not Path(benchmark_command[0]).is_file():
        raise ValueError("manifest benchmark Python runtime is no longer available for source-bound verification")

    native_output = _mapping(manifest.get("native_output"), "manifest.native_output")
    preserved_directory = Path(_string(native_output.get("preserved_directory"), "manifest.native_output.preserved_directory")).expanduser().resolve()
    expected_directory = run_dir / "tau2-native-results"
    if preserved_directory != expected_directory:
        raise ValueError("native results must be preserved inside the immutable run directory")
    preserved_results = preserved_directory / "results.json"
    source_record = _record_metadata(native_output.get("results_record"), "manifest.native_output.results_record")
    preserved_record = _verify_file_record(
        native_output.get("preserved_results_record"),
        "manifest.native_output.preserved_results_record",
        expected_path=preserved_results,
    )
    if source_record["sha256"] != preserved_record["sha256"] or source_record["bytes"] != preserved_record["bytes"]:
        raise ValueError("preserved native results do not match the launcher-recorded τ³ results artifact")
    schema_validation = _mapping(native_output.get("schema_validation"), "manifest.native_output.schema_validation")
    if schema_validation.get("schema") != "tau2-results-pydantic/v1" or schema_validation.get("passed") is not True:
        raise ValueError("native results were not accepted by the pinned τ³ Pydantic Results schema")
    if schema_validation.get("result_model") != "tau2.data_model.simulation.Results":
        raise ValueError("native results schema validation did not use τ³'s Results model")
    schema_package_file = Path(
        _string(schema_validation.get("tau2_package_file"), "manifest.native_output.schema_validation.tau2_package_file")
    ).expanduser().resolve()
    if schema_package_file != package_file:
        raise ValueError("native results schema validation did not run against the recorded source-bound τ³ package")
    schema_record = _record_metadata(
        schema_validation.get("results_record"),
        "manifest.native_output.schema_validation.results_record",
    )
    if schema_record["sha256"] != preserved_record["sha256"] or schema_record["bytes"] != preserved_record["bytes"]:
        raise ValueError("native results schema validation is not bound to the preserved results bytes")

    registration_record = verify_registration_record(manifest["registration"]) if "registration" in manifest else None
    registration = None
    if registration_record is not None:
        if registration_record["benchmark"] != "tau2":
            raise ValueError("manifest preregistration is not a tau2 registration")
        if registration_record.get("condition") != "official-solo-telecom":
            raise ValueError("manifest preregistration condition does not match the native tau2 solo condition")
        quantization_value = policy.get("quantization")
        quantization = (
            None
            if quantization_value is None
            else _string(quantization_value, "manifest.policy.quantization")
        )
        registration = validate_tau2_registration(
            Path(registration_record["path"]),
            training_sources=audit.get("training_sources"),
            variant=variant,
            source_commit=commit,
            tau2_version=_string(runtime.get("tau2_version"), "manifest.runtime.tau2_version"),
            python_version=_string(runtime.get("python_version"), "manifest.runtime.python_version"),
            domain=_string(tau2.get("domain"), "manifest.tau2.domain"),
            task_set=_string(tau2.get("task_set"), "manifest.tau2.task_set"),
            task_split=_string(tau2.get("task_split"), "manifest.tau2.task_split"),
            task_ids=selectors,
            seed=_integer(policy.get("seed"), "manifest.policy.seed"),
            max_new_tokens=_integer(policy.get("max_new_tokens"), "manifest.policy.max_new_tokens", minimum=1),
            quantization=quantization,
            num_trials=_integer(budget.get("num_trials"), "manifest.budget.num_trials", minimum=1),
            max_steps=_integer(budget.get("max_steps"), "manifest.budget.max_steps", minimum=1),
            max_errors=_integer(budget.get("max_errors"), "manifest.budget.max_errors", minimum=1),
            max_concurrency=_integer(budget.get("max_concurrency"), "manifest.budget.max_concurrency", minimum=1),
            max_retries=_integer(budget.get("max_retries"), "manifest.budget.max_retries", minimum=0),
        )

    return {
        "run_dir": run_dir,
        "checkpoint_directory": checkpoint_directory,
        "checkpoint_records": checkpoint_records,
        "tau2": tau2,
        "tau2_source_tree": tau2_source_tree,
        "selector_catalog": selector_catalog,
        "variant": variant,
        "policy": policy,
        "budget": budget,
        "adapter": adapter,
        "adapter_binding": adapter_binding,
        "runtime": runtime,
        "wrapper_record": wrapper_record,
        "compatibility": dict(compatibility),
        "native_results": Path(preserved_record["path"]),
        "native_results_record": preserved_record,
        "schema_validation": dict(schema_validation),
        "registration": registration,
    }


def _validate_native_identity(
    results: Mapping[str, Any],
    *,
    tau2: Mapping[str, Any],
    policy: Mapping[str, Any],
    budget: Mapping[str, Any],
    adapter: Mapping[str, Any],
) -> Mapping[str, Any]:
    info = _mapping(results.get("info"), "native results.info")
    if _string(info.get("git_commit"), "native results.info.git_commit").lower() != str(tau2["commit"]).lower():
        raise ValueError("native results.info.git_commit does not match the pinned τ³ checkout")
    for key in ("num_trials", "max_steps", "max_errors"):
        if _integer(info.get(key), f"native results.info.{key}", minimum=1) != _integer(
            budget[key], f"manifest.budget.{key}", minimum=1
        ):
            raise ValueError(f"native results.info.{key} does not match the registered execution budget")
    if _integer(info.get("seed"), "native results.info.seed") != _integer(policy["seed"], "manifest.policy.seed"):
        raise ValueError("native results.info.seed does not match the registered policy seed")

    agent = _mapping(info.get("agent_info"), "native results.info.agent_info")
    if (
        _string(agent.get("implementation"), "native results.info.agent_info.implementation") != "llm_agent_solo"
        or _string(agent.get("llm"), "native results.info.agent_info.llm") != _string(policy["model"], "manifest.policy.model")
    ):
        raise ValueError("native results agent identity does not match the registered official solo condition")
    llm_args = _mapping(agent.get("llm_args"), "native results.info.agent_info.llm_args")
    _assert_loopback_api_base(
        llm_args.get("api_base"),
        expected_port=_integer(adapter.get("port"), "manifest.adapter.port", minimum=1),
    )
    if _number(llm_args.get("temperature"), "native results.info.agent_info.llm_args.temperature") != 0.0:
        raise ValueError("native results must be deterministic with temperature zero")
    if _integer(llm_args.get("max_tokens"), "native results.info.agent_info.llm_args.max_tokens", minimum=1) != _integer(
        policy["max_new_tokens"], "manifest.policy.max_new_tokens", minimum=1
    ):
        raise ValueError("native results max_tokens does not match the registered local policy limit")

    user = _mapping(info.get("user_info"), "native results.info.user_info")
    if _string(user.get("implementation"), "native results.info.user_info.implementation") != "dummy_user":
        raise ValueError("native results must use τ³-bench's official DummyUser solo condition")
    environment = _mapping(info.get("environment_info"), "native results.info.environment_info")
    if _string(environment.get("domain_name"), "native results.info.environment_info.domain_name") != "telecom":
        raise ValueError("native results must be from the registered telecom domain")
    return info


def _validate_rows(
    results: Mapping[str, Any],
    *,
    task_ids: list[str],
    num_trials: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    tasks = _list(results.get("tasks"), "native results.tasks")
    native_task_ids = [_string(_mapping(task, "native results.tasks[]").get("id"), "native results.tasks[].id") for task in tasks]
    if len(native_task_ids) != len(task_ids) or set(native_task_ids) != set(task_ids) or len(set(native_task_ids)) != len(native_task_ids):
        raise ValueError("native results.tasks do not exactly match the registered task selectors")

    simulations = _list(results.get("simulations"), "native results.simulations")
    expected_pairs = {(task_id, trial) for task_id in task_ids for trial in range(num_trials)}
    if len(simulations) != len(expected_pairs):
        raise ValueError("native results do not contain exactly one simulation for every task/trial pair")
    rows: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, int]] = set()
    termination_reasons: list[str] = []
    for index, value in enumerate(simulations):
        simulation = _mapping(value, f"native results.simulations[{index}]")
        task_id = _string(simulation.get("task_id"), f"native results.simulations[{index}].task_id")
        trial = _integer(simulation.get("trial"), f"native results.simulations[{index}].trial", minimum=0)
        pair = (task_id, trial)
        if pair not in expected_pairs or pair in seen_pairs:
            raise ValueError("native results contain an unexpected or duplicate task/trial pair")
        seen_pairs.add(pair)
        termination = _string(simulation.get("termination_reason"), f"native results.simulations[{index}].termination_reason")
        if termination == "infrastructure_error":
            raise ValueError("native results contain an infrastructure_error; repair the run before reporting a score")
        reward_info = _mapping(simulation.get("reward_info"), f"native results.simulations[{index}].reward_info")
        reward = _number(
            reward_info.get("reward"),
            f"native results.simulations[{index}].reward_info.reward",
            minimum=0.0,
            maximum=1.0 + _SUCCESS_EPSILON,
        )
        messages = simulation.get("messages")
        if messages is not None and not isinstance(messages, list):
            raise ValueError(f"native results.simulations[{index}].messages must be a list when present")
        duration = simulation.get("duration")
        duration_seconds = _number(duration, f"native results.simulations[{index}].duration", minimum=0.0) if duration is not None else None
        agent_cost = simulation.get("agent_cost")
        agent_cost_reported = _number(agent_cost, f"native results.simulations[{index}].agent_cost", minimum=0.0) if agent_cost is not None else None
        user_cost = simulation.get("user_cost")
        user_cost_reported = _number(user_cost, f"native results.simulations[{index}].user_cost", minimum=0.0) if user_cost is not None else None
        rows.append(
            {
                "task_id": task_id,
                "trial": trial,
                "family": _family(task_id),
                "reward": reward,
                "reward_is_one": (1.0 - _SUCCESS_EPSILON) <= reward <= (1.0 + _SUCCESS_EPSILON),
                "termination_reason": termination,
                "duration_seconds": duration_seconds,
                "native_message_array_present": messages is not None,
                "native_message_count": len(messages) if messages is not None else None,
                "agent_cost_reported": agent_cost_reported,
                "user_cost_reported": user_cost_reported,
            }
        )
        termination_reasons.append(termination)
    if seen_pairs != expected_pairs:
        raise ValueError("native results are missing registered task/trial pairs")
    return rows, termination_reasons


def _family_summary(rows: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["family"])].append(row)
    result: dict[str, dict[str, Any]] = {}
    for family, group in sorted(groups.items()):
        rewards = [float(row["reward"]) for row in group]
        result[family] = {
            "simulation_runs": len(group),
            "mean_reward": mean(rewards),
            "reward_one_rate": sum(bool(row["reward_is_one"]) for row in group) / len(group),
            "termination_reasons": dict(sorted(Counter(str(row["termination_reason"]) for row in group).items())),
        }
    return result


def validate_native_result(run_manifest_path: str | Path) -> dict[str, Any]:
    """Return a claim-safe summary of one completed, source-bound τ³ run."""

    manifest_path = Path(run_manifest_path).expanduser().resolve()
    manifest = _read_json_mapping(manifest_path, "run manifest")
    validated = _validate_manifest(manifest, manifest_path)
    results_path = validated["native_results"]
    results = _read_json_mapping(results_path, "preserved native τ³ results")
    _validate_native_identity(
        results,
        tau2=validated["tau2"],
        policy=validated["policy"],
        budget=validated["budget"],
        adapter=validated["adapter"],
    )
    rows, termination_reasons = _validate_rows(
        results,
        task_ids=list(validated["tau2"]["task_ids"]),
        num_trials=int(validated["budget"]["num_trials"]),
    )
    rewards = [float(row["reward"]) for row in rows]
    durations = [float(row["duration_seconds"]) for row in rows if row["duration_seconds"] is not None]
    agent_costs = [float(row["agent_cost_reported"]) for row in rows if row["agent_cost_reported"] is not None]
    user_costs = [float(row["user_cost_reported"]) for row in rows if row["user_cost_reported"] is not None]
    native_message_arrays = sum(bool(row["native_message_array_present"]) for row in rows)
    nonempty_messages = sum(bool(row["native_message_count"]) for row in rows)

    return {
        "schema": SCHEMA,
        "status": "locally_consistent",
        "condition": str(validated["tau2"]["condition"]),
        "provenance": {
            "run_manifest": {
                "path": str(manifest_path),
                "sha256": _sha256(manifest_path),
            },
            "native_results": validated["native_results_record"],
            "tau2_commit": str(validated["tau2"]["commit"]),
            "checkpoint": validated["checkpoint_records"],
            "adapter": validated["adapter_binding"],
            "runner_wrapper": validated["wrapper_record"],
            "runner_compatibility": validated["compatibility"],
            "native_schema_validation": validated["schema_validation"],
            **({"registration": validated["registration"]} if validated["registration"] is not None else {}),
        },
        "attestation": {
            "status": "not_provided",
            "meaning": (
                "local file-record hashes provide consistency checks against the launcher manifest, "
                "not an independent cryptographic attestation of the run"
            ),
        },
        "configuration": {
            "model": str(validated["policy"]["model"]),
            "harness_variant": str(validated["adapter"]["harness_variant"]),
            "seed": int(validated["policy"]["seed"]),
            "task_ids": list(validated["tau2"]["task_ids"]),
            "execution_budget": dict(validated["budget"]),
            "runtime": {
                "package_file": str(validated["runtime"]["package_file"]),
                "tau2_runtime": validated["runtime"].get("tau2_runtime"),
                "platform": validated["runtime"].get("platform"),
            },
        },
        "native_metric": {
            "name": "mean_reward",
            "value": mean(rewards),
            "source": "τ³-bench native reward_info.reward",
        },
        "reward_one_rate": sum(bool(row["reward_is_one"]) for row in rows) / len(rows),
        "simulation_runs": len(rows),
        "by_family": _family_summary(rows),
        "termination_reasons": dict(sorted(Counter(termination_reasons).items())),
        "trace_availability": {
            "native_message_arrays_present": native_message_arrays,
            "nonempty_native_message_arrays": nonempty_messages,
            "all_simulations_have_native_message_arrays": native_message_arrays == len(rows),
            "all_simulations_have_nonempty_native_messages": nonempty_messages == len(rows),
        },
        "timing": {
            "reported_duration_seconds": {
                "simulations_with_duration": len(durations),
                "total": sum(durations) if durations else None,
                "mean": mean(durations) if durations else None,
            }
        },
        "cost_reporting": {
            "status": "reported-but-not-price-validated",
            "reason": "the local generic LiteLLM endpoint does not provide independently validated model pricing",
            "simulations_with_agent_cost": len(agent_costs),
            "reported_agent_cost_sum": sum(agent_costs) if agent_costs else None,
            "simulations_with_user_cost": len(user_costs),
            "reported_user_cost_sum": sum(user_costs) if user_costs else None,
        },
        "rows": rows,
        "not_measured": {
            "independent_trace_replay": "not measured: native message records are retained, but no independent replay verifier ran",
            "safety": "not measured: τ³ reward is not converted into a safety metric",
            "interactive_user_simulation": "not measured: the registered condition uses the official DummyUser solo mode",
            "price_calibration": "not measured: reported LiteLLM costs are not independently price-validated",
        },
        "claim_boundary": (
            "native τ³-bench telecom/base official-solo result; report mean_reward and reward_one_rate only. "
            "This report is locally consistent with its launcher manifest, not independently cryptographically attested. "
            "Do not infer independent replay, safety, interactive-user coverage, or calibrated cost from this report."
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
    parser.add_argument("--run-manifest", required=True, help="completed τ³ launcher run_manifest.json")
    parser.add_argument("--output", required=True, help="new JSON output path")
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
                "simulation_runs": result["simulation_runs"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
