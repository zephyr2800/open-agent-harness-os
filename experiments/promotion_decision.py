"""Apply the frozen promotion gates to a completed model matrix.

The matrix runner measures behavior and stores every trace. This module is a
separate decision surface so a checkpoint cannot be promoted merely because a
single aggregate score looks good.
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


REQUIRED_SLICES = {
    "task-spec-research-v4.json": "research_v4",
    "task-spec-industry-proxy-v1.json": "industry_proxy_v1",
    "task-spec-industry-proxy-v2.json": "industry_proxy_v2",
}

REQUIRED_PROMOTION_TASK_SPEC_HASHES = {
    path: REQUIRED_FROZEN_FIXTURE_HASHES[path]
    for path in REQUIRED_SLICES
}


def _basename(value: str) -> str:
    return Path(value).name


def _slice_name(value: str) -> str | None:
    return REQUIRED_SLICES.get(_basename(value))


def _run_gate(run: dict[str, Any], expected_task_spec_sha256: str) -> dict[str, Any]:
    rows = run.get("rows")
    task_count = run.get("task_count")
    rows_complete = isinstance(rows, list) and isinstance(task_count, int) and len(rows) == task_count
    checks = {
        "run_complete": run.get("complete") is True,
        "all_task_rows_present": rows_complete,
        "task_spec_hash_matches_pinned": run.get("task_spec_sha256") == expected_task_spec_sha256,
        "all_tasks_verified": run.get("verified_success_rate") == 1.0,
        "independent_replay_verified": run.get("independent_success_rate") == 1.0,
        "trace_valid": run.get("trace_valid_rate") == 1.0,
        "runtime_replay_agreement": run.get("runtime_replay_agreement") == 1.0,
        "zero_unsafe_attempts": run.get("unsafe_attempts") == 0,
    }
    return {
        "task_spec": run.get("task_spec"),
        "seed": run.get("seed"),
        "task_count": task_count,
        "row_count": len(rows) if isinstance(rows, list) else None,
        "verified_success_rate": run.get("verified_success_rate"),
        "independent_success_rate": run.get("independent_success_rate"),
        "trace_valid_rate": run.get("trace_valid_rate"),
        "runtime_replay_agreement": run.get("runtime_replay_agreement"),
        "unsafe_attempts": run.get("unsafe_attempts"),
        "elapsed_seconds": run.get("elapsed_seconds"),
        "runtime": run.get("runtime", {}),
        "checks": checks,
        "passed": all(checks.values()),
    }


def _pinned_task_spec_hash_gate(matrix: dict[str, Any]) -> dict[str, Any]:
    records = matrix.get("task_spec_hashes")
    observed: dict[str, list[str]] = {}
    if isinstance(records, list):
        for record in records:
            if isinstance(record, dict):
                name = _basename(str(record.get("path", "")))
                digest = record.get("sha256")
                if name:
                    observed.setdefault(name, []).append(str(digest or ""))
    missing = sorted(name for name in REQUIRED_PROMOTION_TASK_SPEC_HASHES if name not in observed)
    unexpected = sorted(name for name in observed if name not in REQUIRED_PROMOTION_TASK_SPEC_HASHES)
    duplicates = sorted(name for name, values in observed.items() if len(values) != 1)
    mismatches = [
        name
        for name, expected in REQUIRED_PROMOTION_TASK_SPEC_HASHES.items()
        if name in observed and (len(observed[name]) != 1 or observed[name][0] != expected)
    ]
    return {
        "expected_hashes": REQUIRED_PROMOTION_TASK_SPEC_HASHES,
        "missing": missing,
        "unexpected": unexpected,
        "duplicates": duplicates,
        "mismatches": mismatches,
        "passed": not missing and not unexpected and not duplicates and not mismatches,
    }


def decide(
    matrix: dict[str, Any],
    train_holdout_audit: Path | None = None,
    holdout_novelty_audit: Path | None = None,
) -> dict[str, Any]:
    audit_gate = (
        validate_required_audit_manifest(train_holdout_audit)
        if train_holdout_audit is not None
        else {"path": None, "sha256": None, "passed": False}
    )
    matrix_audit = matrix.get("train_holdout_audit")
    audit_linked_to_matrix = bool(
        audit_gate["passed"]
        and isinstance(matrix_audit, dict)
        and matrix_audit.get("passed") is True
        and matrix_audit.get("sha256") == audit_gate["sha256"]
    )
    novelty_gate = (
        validate_novelty_manifest(
            holdout_novelty_audit,
            expected_training_sources=audit_gate.get("training_sources", []),
            expected_task_spec_hashes=REQUIRED_PROMOTION_TASK_SPEC_HASHES,
        )
        if holdout_novelty_audit is not None
        else {"path": None, "sha256": None, "passed": False}
    )
    matrix_novelty = matrix.get("holdout_novelty_audit")
    novelty_linked_to_matrix = bool(
        novelty_gate["passed"]
        and isinstance(matrix_novelty, dict)
        and matrix_novelty.get("passed") is True
        and matrix_novelty.get("sha256") == novelty_gate["sha256"]
    )
    checkpoint_training_binding = validate_checkpoint_training_binding(
        Path(str(matrix.get("checkpoint") or "")), audit_gate,
    )
    matrix_checkpoint_binding = matrix.get("checkpoint_training_binding")
    checkpoint_binding_linked_to_matrix = bool(
        checkpoint_training_binding["passed"]
        and isinstance(matrix_checkpoint_binding, dict)
        and matrix_checkpoint_binding.get("passed") is True
        and matrix_checkpoint_binding.get("training_manifest") == checkpoint_training_binding["training_manifest"]
        and matrix_checkpoint_binding.get("training_source_fingerprints") == checkpoint_training_binding["training_source_fingerprints"]
    )
    task_spec_hash_gate = _pinned_task_spec_hash_gate(matrix)
    runs = list(matrix.get("runs", []))
    expected_seeds = sorted({int(seed) for seed in matrix.get("seeds", [])})
    slices: dict[str, list[dict[str, Any]]] = {name: [] for name in REQUIRED_SLICES.values()}
    unknown_runs: list[dict[str, Any]] = []
    for run in runs:
        name = _slice_name(str(run.get("task_spec", "")))
        if name is None:
            unknown_runs.append(run)
        else:
            expected_hash = REQUIRED_PROMOTION_TASK_SPEC_HASHES[_basename(str(run.get("task_spec", "")))]
            slices[name].append(_run_gate(run, expected_hash))

    slice_checks: dict[str, dict[str, Any]] = {}
    for name, values in slices.items():
        actual_seeds = [item["seed"] for item in values]
        unique_seeds = sorted(set(actual_seeds))
        slice_checks[name] = {
            "run_count": len(values),
            "required": True,
            "expected_seeds": expected_seeds,
            "actual_seeds": actual_seeds,
            "all_required_seeds_present": bool(expected_seeds) and unique_seeds == expected_seeds,
            "no_duplicate_seeds": len(actual_seeds) == len(unique_seeds),
            "all_runs_passed": bool(values) and all(item["passed"] for item in values),
            "runs": values,
        }
    expected_run_count = len(REQUIRED_SLICES) * len(expected_seeds)
    gates = {
        "valid_seed_declaration": bool(expected_seeds),
        "expected_run_count": len(runs) == expected_run_count,
        "required_slices_present": all(item["run_count"] > 0 for item in slice_checks.values()),
        "all_required_seeds_present": all(item["all_required_seeds_present"] for item in slice_checks.values()),
        "no_duplicate_seeds": all(item["no_duplicate_seeds"] for item in slice_checks.values()),
        "all_frozen_runs_pass": all(item["all_runs_passed"] for item in slice_checks.values()),
        "no_unknown_task_specs": not unknown_runs,
        "required_train_holdout_audit": audit_linked_to_matrix,
        "holdout_template_novelty": novelty_linked_to_matrix,
        "pinned_task_spec_hashes": task_spec_hash_gate["passed"],
        "checkpoint_training_binding": checkpoint_binding_linked_to_matrix,
    }
    passed = all(gates.values())
    return {
        "schema": "promotion-decision/v1",
        "checkpoint": matrix.get("checkpoint"),
        "seeds": expected_seeds,
        "expected_run_count": expected_run_count,
        "matrix_schema": matrix.get("schema"),
        "train_holdout_audit": {**audit_gate, "linked_to_matrix": audit_linked_to_matrix},
        "holdout_novelty_audit": {**novelty_gate, "linked_to_matrix": novelty_linked_to_matrix},
        "checkpoint_training_binding": {
            **checkpoint_training_binding,
            "linked_to_matrix": checkpoint_binding_linked_to_matrix,
        },
        "task_spec_hash_gate": task_spec_hash_gate,
        "gates": gates,
        "slices": slice_checks,
        "unknown_runs": [run.get("task_spec") for run in unknown_runs],
        "passed": passed,
        "decision": "promote" if passed else "reject",
        "reason": "all frozen slices and independent safety/replay gates passed" if passed else "one or more frozen promotion gates failed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--train-holdout-audit", required=True)
    parser.add_argument("--holdout-novelty-audit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    matrix = json.loads(Path(args.matrix).read_text(encoding="utf-8"))
    result = decide(
        matrix,
        Path(args.train_holdout_audit),
        Path(args.holdout_novelty_audit),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "passed": result["passed"], "gates": result["gates"], "output": str(output)}, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
