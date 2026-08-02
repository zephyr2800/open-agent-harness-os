"""Bind external native evaluations to a checked-in preregistration.

The native launchers already prove that a completed run used a clean benchmark
checkout, a bound checkpoint, and the benchmark's own runner.  This module
adds the missing experimental-control boundary: an executed external run must
also match a committed task selection and budget that existed before the
checkpoint was evaluated.

It deliberately validates a narrow, versioned document rather than accepting
an arbitrary scorecard configuration.  A caller may create an unregistered
dry plan for local inspection, but execution is required to carry the returned
registration record.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


SCHEMA = "native-external-evaluation-registration/v1"
RECORD_SCHEMA = "native-external-evaluation-registration-record/v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
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


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{field} must be a non-empty list of strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{field} must not contain duplicate selectors")
    return list(value)


def _nullable_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _string(value, field)


def _require_equal(actual: Any, expected: Any, field: str) -> None:
    if actual != expected:
        raise ValueError(f"{field} does not match the preregistration")


def _source_fingerprints(value: Any, field: str) -> list[list[Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ValueError(f"{field} must be a non-empty list of training-source records")
    records: list[list[Any]] = []
    for index, item in enumerate(value):
        record = _mapping(item, f"{field}[{index}]")
        digest = _string(record.get("sha256"), f"{field}[{index}].sha256").lower()
        if not _SHA256_RE.fullmatch(digest):
            raise ValueError(f"{field}[{index}].sha256 must be a SHA-256 digest")
        rows = _integer(record.get("rows"), f"{field}[{index}].rows", minimum=1)
        records.append([digest, rows])
    if len({tuple(record) for record in records}) != len(records):
        raise ValueError(f"{field} must not contain duplicate training-source records")
    return sorted(records)


def load_registration(path: Path) -> tuple[Path, dict[str, Any]]:
    """Read a well-formed immutable registration document from disk."""

    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"--registration does not exist: {resolved}")
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"--registration is not valid JSON: {resolved}") from error
    document = dict(_mapping(document, "registration"))
    if document.get("schema") != SCHEMA:
        raise ValueError(f"registration.schema must equal {SCHEMA!r}")
    _string(document.get("registration_id"), "registration.registration_id")
    _string(document.get("created_before_checkpoint"), "registration.created_before_checkpoint")
    _mapping(document.get("checkpoint_scope"), "registration.checkpoint_scope")
    variants = _string_list(document.get("variants"), "registration.variants")
    if set(variants) != {"model-only", "repair"}:
        raise ValueError("registration.variants must declare exactly model-only and repair")
    return resolved, document


def _base_record(path: Path, document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": RECORD_SCHEMA,
        "path": str(path),
        "sha256": _sha256(path),
        "registration_id": _string(document.get("registration_id"), "registration.registration_id"),
        "created_before_checkpoint": _string(
            document.get("created_before_checkpoint"), "registration.created_before_checkpoint"
        ),
    }


def verify_registration_record(value: Any) -> dict[str, Any]:
    """Verify that a persisted run-manifest record still names unchanged bytes."""

    record = _mapping(value, "manifest.registration")
    if record.get("schema") != RECORD_SCHEMA:
        raise ValueError(f"manifest.registration.schema must equal {RECORD_SCHEMA!r}")
    path = Path(_string(record.get("path"), "manifest.registration.path")).expanduser().resolve()
    expected_sha256 = _string(record.get("sha256"), "manifest.registration.sha256").lower()
    if not _SHA256_RE.fullmatch(expected_sha256):
        raise ValueError("manifest.registration.sha256 must be a SHA-256 digest")
    resolved, document = load_registration(path)
    if _sha256(resolved) != expected_sha256:
        raise ValueError("manifest.registration.sha256 does not match the preregistration file")
    _require_equal(
        _string(record.get("registration_id"), "manifest.registration.registration_id"),
        _string(document.get("registration_id"), "registration.registration_id"),
        "manifest registration ID",
    )
    _require_equal(
        _string(record.get("created_before_checkpoint"), "manifest.registration.created_before_checkpoint"),
        _string(document.get("created_before_checkpoint"), "registration.created_before_checkpoint"),
        "manifest registration creation time",
    )
    benchmark = _string(record.get("benchmark"), "manifest.registration.benchmark")
    if benchmark not in {"agentdojo", "tau2"}:
        raise ValueError("manifest.registration.benchmark is not supported")
    return dict(record)


def _validate_checkpoint_scope(document: Mapping[str, Any], training_sources: Any) -> list[list[Any]]:
    scope = _mapping(document.get("checkpoint_scope"), "registration.checkpoint_scope")
    expected = _source_fingerprints(scope.get("training_sources"), "registration.checkpoint_scope.training_sources")
    actual = _source_fingerprints(training_sources, "run.train_holdout_audit.training_sources")
    _require_equal(actual, expected, "checkpoint training sources")
    return actual


def _registered_variants(document: Mapping[str, Any], variant: str) -> None:
    variants = _string_list(document.get("variants"), "registration.variants")
    if variant not in variants:
        raise ValueError("run.variant is not preregistered")


def _registration_commit(value: Any, field: str) -> str:
    commit = _string(value, field).lower()
    if not _GIT_COMMIT_RE.fullmatch(commit):
        raise ValueError(f"{field} must be a full Git commit hash")
    return commit


def validate_agentdojo_registration(
    registration_path: Path,
    *,
    training_sources: Any,
    variant: str,
    source_commit: str,
    benchmark_version: str,
    suite: str,
    user_tasks: Sequence[str],
    injection_tasks: Sequence[str],
    attack: str | None,
    defense: str | None,
    seed: int,
    max_new_tokens: int,
    quantization: str | None,
) -> dict[str, Any]:
    """Fail closed unless one AgentDojo configuration exactly matches registration."""

    path, document = load_registration(registration_path)
    fingerprints = _validate_checkpoint_scope(document, training_sources)
    _registered_variants(document, variant)
    registered = _mapping(document.get("agentdojo"), "registration.agentdojo")
    _require_equal(source_commit.lower(), _registration_commit(registered.get("source_commit"), "registration.agentdojo.source_commit"), "AgentDojo source commit")
    _require_equal(benchmark_version, _string(registered.get("benchmark_version"), "registration.agentdojo.benchmark_version"), "AgentDojo benchmark version")
    _require_equal(suite, _string(registered.get("suite"), "registration.agentdojo.suite"), "AgentDojo suite")
    _require_equal("openai-compatible", _string(registered.get("model"), "registration.agentdojo.model"), "AgentDojo model pipeline")
    policy = _mapping(registered.get("policy"), "registration.agentdojo.policy")
    _require_equal(seed, _integer(policy.get("seed"), "registration.agentdojo.policy.seed"), "AgentDojo policy seed")
    _require_equal(False, _boolean(policy.get("do_sample"), "registration.agentdojo.policy.do_sample"), "AgentDojo sampling mode")
    _require_equal(max_new_tokens, _integer(policy.get("max_new_tokens"), "registration.agentdojo.policy.max_new_tokens", minimum=1), "AgentDojo token budget")
    _require_equal(quantization, _nullable_string(policy.get("quantization"), "registration.agentdojo.policy.quantization"), "AgentDojo quantization")

    condition_name = "direct_injection" if injection_tasks else "clean"
    conditions = _mapping(registered.get("conditions"), "registration.agentdojo.conditions")
    condition = _mapping(conditions.get(condition_name), f"registration.agentdojo.conditions.{condition_name}")
    _require_equal(list(user_tasks), _string_list(condition.get("user_tasks"), f"registration.agentdojo.conditions.{condition_name}.user_tasks"), "AgentDojo user-task selectors")
    expected_injections = condition.get("injection_tasks")
    if expected_injections == []:
        expected_injections_list: list[str] = []
    else:
        expected_injections_list = _string_list(expected_injections, f"registration.agentdojo.conditions.{condition_name}.injection_tasks")
    _require_equal(list(injection_tasks), expected_injections_list, "AgentDojo injection-task selectors")
    _require_equal(attack, _nullable_string(condition.get("attack"), f"registration.agentdojo.conditions.{condition_name}.attack"), "AgentDojo attack")
    _require_equal(defense, _nullable_string(condition.get("defense"), f"registration.agentdojo.conditions.{condition_name}.defense"), "AgentDojo defense")
    return {
        **_base_record(path, document),
        "benchmark": "agentdojo",
        "condition": condition_name,
        "training_source_fingerprints": fingerprints,
    }


def validate_tau2_registration(
    registration_path: Path,
    *,
    training_sources: Any,
    variant: str,
    source_commit: str,
    tau2_version: str | None,
    python_version: str | None,
    domain: str,
    task_set: str,
    task_split: str,
    task_ids: Sequence[str],
    seed: int,
    max_new_tokens: int,
    quantization: str | None,
    num_trials: int,
    max_steps: int,
    max_errors: int,
    max_concurrency: int,
    max_retries: int,
) -> dict[str, Any]:
    """Fail closed unless the tau2 solo configuration exactly matches registration."""

    path, document = load_registration(registration_path)
    fingerprints = _validate_checkpoint_scope(document, training_sources)
    _registered_variants(document, variant)
    registered = _mapping(document.get("tau2"), "registration.tau2")
    _require_equal(source_commit.lower(), _registration_commit(registered.get("source_commit"), "registration.tau2.source_commit"), "tau2 source commit")
    runtime = _mapping(registered.get("runtime"), "registration.tau2.runtime")
    _require_equal(tau2_version, _string(runtime.get("tau2_version"), "registration.tau2.runtime.tau2_version"), "tau2 package version")
    python_prefix = _string(runtime.get("python_version_prefix"), "registration.tau2.runtime.python_version_prefix")
    if not isinstance(python_version, str) or not python_version.startswith(python_prefix):
        raise ValueError("tau2 Python runtime does not match the preregistration")
    for field, actual in (("domain", domain), ("task_set", task_set), ("task_split", task_split)):
        _require_equal(actual, _string(registered.get(field), f"registration.tau2.{field}"), f"tau2 {field}")
    _require_equal(list(task_ids), _string_list(registered.get("task_ids"), "registration.tau2.task_ids"), "tau2 task selectors")
    policy = _mapping(registered.get("policy"), "registration.tau2.policy")
    _require_equal(seed, _integer(policy.get("seed"), "registration.tau2.policy.seed"), "tau2 policy seed")
    _require_equal(False, _boolean(policy.get("do_sample"), "registration.tau2.policy.do_sample"), "tau2 sampling mode")
    _require_equal(max_new_tokens, _integer(policy.get("max_new_tokens"), "registration.tau2.policy.max_new_tokens", minimum=1), "tau2 token budget")
    _require_equal(quantization, _nullable_string(policy.get("quantization"), "registration.tau2.policy.quantization"), "tau2 quantization")
    budget = _mapping(registered.get("budget"), "registration.tau2.budget")
    for field, actual in (
        ("num_trials", num_trials),
        ("max_steps", max_steps),
        ("max_errors", max_errors),
        ("max_concurrency", max_concurrency),
        ("max_retries", max_retries),
    ):
        _require_equal(actual, _integer(budget.get(field), f"registration.tau2.budget.{field}", minimum=0), f"tau2 {field}")
    return {
        **_base_record(path, document),
        "benchmark": "tau2",
        "condition": "official-solo-telecom",
        "training_source_fingerprints": fingerprints,
    }
