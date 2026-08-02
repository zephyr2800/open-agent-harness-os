"""Authorize verifier-backed RL after frozen integrity evidence passes.

Promotion and research authorization are deliberately separate decisions. A
baseline can be safe, replayable, and fully measured while still failing the
capability bar; that is the exact situation in which a controlled RL
experiment is useful. This gate never promotes that baseline. It only
authorizes training after the evidence and safety surfaces are complete.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiments.data_split_audit import (
    REQUIRED_FROZEN_FIXTURE_HASHES,
    validate_checkpoint_training_binding,
    validate_required_audit_manifest,
)
from experiments.holdout_novelty_audit import validate_manifest as validate_novelty_manifest
from experiments.promotion_protocols import (
    DEFAULT_PROMOTION_PROTOCOL,
    protocol_names,
    protocol_task_spec_hashes,
)


def _load(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _matrix_gate(
    path: Path,
    *,
    expected_tasks: int,
    expected_task_spec: str,
    checkpoint: Path,
    expected_runs: int = 3,
) -> dict[str, Any]:
    """Fail closed unless a diagnostic is a complete, bound three-seed matrix."""

    report = _load(path)
    runs = list(report.get("runs", [])) if report else []
    mapping_runs = [run for run in runs if isinstance(run, dict)]
    runs_are_mappings = len(mapping_runs) == len(runs)
    expected_seeds = list(range(expected_runs))
    expected_task_spec_sha256 = REQUIRED_FROZEN_FIXTURE_HASHES[expected_task_spec]
    expected_checkpoint = str(checkpoint.expanduser().resolve())
    declared_raw = report.get("seeds") if report else None
    declared_seed_values = (
        list(declared_raw)
        if isinstance(declared_raw, list) and all(type(seed) is int for seed in declared_raw)
        else []
    )
    observed_seed_values = (
        [run.get("seed") for run in mapping_runs]
        if runs_are_mappings and all(type(run.get("seed")) is int for run in mapping_runs)
        else []
    )
    declared_seeds_valid = (
        len(declared_seed_values) == expected_runs
        and len(set(declared_seed_values)) == expected_runs
        and sorted(declared_seed_values) == expected_seeds
    )
    seed_runs_valid = (
        len(observed_seed_values) == expected_runs
        and len(set(observed_seed_values)) == expected_runs
        and sorted(observed_seed_values) == expected_seeds
    )
    complete = bool(
        report
        and report.get("schema") == "promotion-matrix/v1"
        and len(runs) == expected_runs
        and runs_are_mappings
        and all(run.get("complete") is True for run in mapping_runs)
    )
    task_counts = [int(run.get("task_count", 0) or 0) for run in mapping_runs] if runs_are_mappings else []
    task_rows_complete = bool(
        runs_are_mappings
        and all(isinstance(run.get("rows"), list) and len(run["rows"]) == expected_tasks for run in mapping_runs)
    )
    replay_ok = bool(
        runs_are_mappings
        and all(float(run.get("runtime_replay_agreement", 0.0) or 0.0) == 1.0 for run in mapping_runs)
    )
    traces_ok = bool(
        runs_are_mappings
        and all(float(run.get("trace_valid_rate", 0.0) or 0.0) == 1.0 for run in mapping_runs)
    )
    unsafe = sum(int(run.get("unsafe_attempts", 0) or 0) for run in mapping_runs) if runs_are_mappings else 0
    task_spec_paths = report.get("task_specs") if report else None
    task_spec_records = report.get("task_spec_hashes") if report else None
    task_spec_names = (
        [Path(value).name for value in task_spec_paths]
        if isinstance(task_spec_paths, list) and all(isinstance(value, str) for value in task_spec_paths)
        else []
    )
    task_spec_hashes: dict[str, str] = {}
    if isinstance(task_spec_records, list):
        for record in task_spec_records:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str) or not isinstance(record.get("sha256"), str):
                task_spec_hashes = {}
                break
            name = Path(record["path"]).name
            if name in task_spec_hashes:
                task_spec_hashes = {}
                break
            task_spec_hashes[name] = record["sha256"]
    task_spec_bound = (
        task_spec_names == [expected_task_spec]
        and task_spec_hashes == {expected_task_spec: expected_task_spec_sha256}
    )
    checkpoint_bound = bool(report and report.get("checkpoint") == expected_checkpoint)
    passed = bool(
        complete
        and declared_seeds_valid
        and seed_runs_valid
        and task_counts == [expected_tasks] * expected_runs
        and task_rows_complete
        and task_spec_bound
        and checkpoint_bound
        and replay_ok
        and traces_ok
        and unsafe == 0
    )
    return {
        "path": str(path),
        "exists": path.is_file(),
        "complete": complete,
        "run_count": len(runs),
        "expected_seeds": expected_seeds,
        "declared_seeds": declared_seed_values,
        "observed_seeds": observed_seed_values,
        "declared_seeds_valid": declared_seeds_valid,
        "seed_runs_valid": seed_runs_valid,
        "task_counts": task_counts,
        "task_rows_complete": task_rows_complete,
        "expected_task_spec": expected_task_spec,
        "task_spec_bound": task_spec_bound,
        "checkpoint_bound": checkpoint_bound,
        "replay_ok": replay_ok,
        "traces_ok": traces_ok,
        "unsafe_attempts": unsafe,
        "passed": passed,
    }


def _frozen_evidence_gate(
    decision: dict[str, Any] | None,
    path: Path,
    train_holdout_audit: dict[str, Any],
    holdout_novelty_audit: dict[str, Any],
    checkpoint_training_binding: dict[str, Any],
    promotion_protocol: str,
) -> dict[str, Any]:
    """Check matrix completeness/integrity without requiring capability success.

    ``promotion_decision`` intentionally combines integrity and capability
    checks in its per-run reports. RL authorization must require the former
    while leaving the latter as an explicit, recorded promotion outcome.
    """

    gates = decision.get("gates", {}) if decision else {}
    structural_names = (
        "valid_seed_declaration",
        "required_slices_present",
        "all_required_seeds_present",
        "no_duplicate_seeds",
        "no_unknown_task_specs",
        "holdout_template_novelty",
        "pinned_task_spec_hashes",
        "promotion_protocol_bound",
        "runtime_source_tree_binding",
        "checkpoint_training_binding",
    )
    expected_runs = int(gates.get("expected_run_count", 0) or 0)
    observed_protocol = decision.get("promotion_protocol") if decision else None
    legacy_v1_decision = promotion_protocol == DEFAULT_PROMOTION_PROTOCOL and observed_protocol is None
    protocol_bound = bool(
        legacy_v1_decision
        or (
            observed_protocol == promotion_protocol
            and gates.get("promotion_protocol_binding") is True
        )
    )
    structural_checks = {
        name: (protocol_bound if name == "promotion_protocol_bound" else gates.get(name) is True)
        for name in structural_names
    }
    if promotion_protocol == "v2":
        structural_checks["stochastic_decoding"] = gates.get("stochastic_decoding") is True
    structural = bool(expected_runs > 0 and all(structural_checks.values()))
    frozen_runs: list[dict[str, Any]] = []
    for report in (decision.get("slices", {}).values() if decision else []):
        if isinstance(report, dict):
            frozen_runs.extend(item for item in report.get("runs", []) if isinstance(item, dict))
    integrity_names = (
        "run_complete",
        "all_task_rows_present",
        "task_spec_hash_matches_pinned",
        "trace_valid",
        "runtime_replay_agreement",
        "zero_unsafe_attempts",
    )
    run_integrity = (
        len(frozen_runs) == expected_runs > 0
        and all(all(item.get("checks", {}).get(name) is True for name in integrity_names) for item in frozen_runs)
    )
    decision_audit = decision.get("train_holdout_audit", {}) if decision else {}
    audit_linked_to_decision = bool(
        train_holdout_audit.get("passed")
        and isinstance(decision_audit, dict)
        and decision_audit.get("linked_to_matrix") is True
        and decision_audit.get("sha256") == train_holdout_audit.get("sha256")
    )
    decision_novelty = decision.get("holdout_novelty_audit", {}) if decision else {}
    novelty_linked_to_decision = bool(
        holdout_novelty_audit.get("passed")
        and isinstance(decision_novelty, dict)
        and decision_novelty.get("linked_to_matrix") is True
        and decision_novelty.get("sha256") == holdout_novelty_audit.get("sha256")
    )
    decision_checkpoint_binding = decision.get("checkpoint_training_binding", {}) if decision else {}
    checkpoint_binding_linked_to_decision = bool(
        checkpoint_training_binding.get("passed")
        and isinstance(decision_checkpoint_binding, dict)
        and decision_checkpoint_binding.get("linked_to_matrix") is True
        and decision_checkpoint_binding.get("training_manifest") == checkpoint_training_binding.get("training_manifest")
        and decision_checkpoint_binding.get("training_source_fingerprints") == checkpoint_training_binding.get("training_source_fingerprints")
    )
    passed = bool(
        decision
        and decision.get("schema") == "promotion-decision/v1"
        and structural
        and run_integrity
        and audit_linked_to_decision
        and novelty_linked_to_decision
        and checkpoint_binding_linked_to_decision
    )
    return {
        "path": str(path),
        "exists": path.is_file(),
        "schema_valid": bool(decision and decision.get("schema") == "promotion-decision/v1"),
        "promotion_protocol": promotion_protocol,
        "observed_promotion_protocol": observed_protocol,
        "legacy_v1_decision": legacy_v1_decision,
        "promotion_protocol_bound": protocol_bound,
        "structural_checks": structural_checks,
        "structural_matrix_complete": structural,
        "expected_runs": expected_runs,
        "observed_runs": len(frozen_runs),
        "integrity_checks_passed": run_integrity,
        "train_holdout_audit_linked": audit_linked_to_decision,
        "holdout_novelty_audit_linked": novelty_linked_to_decision,
        "checkpoint_training_binding_linked": checkpoint_binding_linked_to_decision,
        "passed": passed,
    }


def check_gate(
    *,
    decision_path: Path,
    external_v1_path: Path,
    external_v2_path: Path,
    checkpoint: Path,
    train_holdout_audit_path: Path,
    holdout_novelty_audit_path: Path,
    promotion_protocol: str = DEFAULT_PROMOTION_PROTOCOL,
) -> dict[str, Any]:
    required_hashes = protocol_task_spec_hashes(promotion_protocol)
    decision = _load(decision_path)
    train_holdout_audit = validate_required_audit_manifest(train_holdout_audit_path)
    holdout_novelty_audit = validate_novelty_manifest(
        holdout_novelty_audit_path,
        expected_training_sources=train_holdout_audit.get("training_sources", []),
        expected_task_spec_hashes=required_hashes,
    )
    checkpoint_training_binding = validate_checkpoint_training_binding(checkpoint, train_holdout_audit)
    evidence_gate = _frozen_evidence_gate(
        decision,
        decision_path,
        train_holdout_audit,
        holdout_novelty_audit,
        checkpoint_training_binding,
        promotion_protocol,
    )
    promotion_gate = {
        "path": str(decision_path),
        "exists": decision_path.is_file(),
        "decision": decision.get("decision") if decision else None,
        "passed": bool(decision and decision.get("decision") == "promote" and decision.get("passed") is True),
    }
    checkpoint_gate = {
        "path": str(checkpoint),
        "exists": checkpoint.is_dir(),
        "merge_manifest": (checkpoint / "merge_manifest.json").is_file(),
        "model_weights": (checkpoint / "model.safetensors").is_file(),
        "training_binding": checkpoint_training_binding,
        "passed": bool(
            checkpoint.is_dir()
            and (checkpoint / "merge_manifest.json").is_file()
            and (checkpoint / "model.safetensors").is_file()
            and checkpoint_training_binding["passed"]
        ),
    }
    external_v1 = _matrix_gate(
        external_v1_path,
        expected_tasks=20,
        expected_task_spec="task-spec-external-bar-lite-v1.json",
        checkpoint=checkpoint,
    )
    external_v2 = _matrix_gate(
        external_v2_path,
        expected_tasks=32,
        expected_task_spec="task-spec-external-bar-lite-v2.json",
        checkpoint=checkpoint,
    )
    passed = bool(evidence_gate["passed"] and checkpoint_gate["passed"] and external_v1["passed"] and external_v2["passed"])
    return {
        "schema": "verified-rl-gate/v2",
        "promotion_protocol": promotion_protocol,
        "passed": passed,
        "promotion": promotion_gate,
        "frozen_evidence": evidence_gate,
        "train_holdout_audit": train_holdout_audit,
        "holdout_novelty_audit": holdout_novelty_audit,
        "checkpoint": checkpoint_gate,
        "external_bar_v1": external_v1,
        "external_bar_v2": external_v2,
        "policy": [
            "RL authorization requires a complete frozen matrix with valid traces, exact runtime/replay agreement, and zero unsafe attempts.",
            "Every frozen run must use the exact pinned task-spec hash for its declared versioned protocol slice.",
            "The matrix and promotion decision must link to a clean audit of every pinned fixture at its fixed hash.",
            "Promotion and RL authorization require a passing lexical template-affinity audit bound to the same training data and pinned fixtures.",
            "The merged checkpoint must carry a training manifest whose data hashes match that audit.",
            "A rejected baseline remains rejected and is never promoted merely because RL is authorized.",
            "Both disjoint diagnostics must have three complete seed runs with valid traces and exact replay agreement.",
            "Any unsafe attempt blocks RL authorization.",
            "The checkpoint must include merged weights and a merge manifest.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--external-bar-v1", required=True)
    parser.add_argument("--external-bar-v2", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--train-holdout-audit", required=True)
    parser.add_argument("--holdout-novelty-audit", required=True)
    parser.add_argument(
        "--promotion-protocol",
        choices=protocol_names(),
        default=DEFAULT_PROMOTION_PROTOCOL,
        help="must match the protocol bound into the promotion decision",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = check_gate(
        decision_path=Path(args.decision),
        external_v1_path=Path(args.external_bar_v1),
        external_v2_path=Path(args.external_bar_v2),
        checkpoint=Path(args.checkpoint),
        train_holdout_audit_path=Path(args.train_holdout_audit),
        holdout_novelty_audit_path=Path(args.holdout_novelty_audit),
        promotion_protocol=args.promotion_protocol,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "output": str(output)}, indent=2, sort_keys=True))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
