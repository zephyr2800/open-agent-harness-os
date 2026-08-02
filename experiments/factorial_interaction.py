"""Fail-closed analysis for a matched real model×harness factorial.

This tool is deliberately separate from promotion and native-benchmark gates.
It accepts a v1 ``experiments.multiseed`` report only when every required
model/variant/seed/task observation is present, independently replayable, and
bound to the supplied task-specification digest.  The interval is a
task-cluster percentile bootstrap: it samples held-out tasks while retaining
all stochastic-seed outcomes for each sampled task.  It therefore measures
task-sampling uncertainty for this exact suite; it does not estimate training
replica variance or establish broad agent capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from pathlib import Path
from typing import Any, Mapping

from benchmarks.tasks import Task, load_tasks
from verify.independent import verify_trace


SCHEMA = "project2-factorial-interaction/v1"
REQUIRED_SCHEMA = "multiseed-project1-harness/v1"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("cannot calculate a percentile of no values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _task_cluster_bootstrap(
    values: Mapping[str, list[float]],
    *,
    replicates: int,
    seed: int,
) -> tuple[float, float]:
    if replicates < 1:
        raise ValueError("bootstrap_replicates must be positive")
    task_ids = sorted(values)
    if not task_ids:
        raise ValueError("at least one task is required for bootstrap")
    generator = random.Random(seed)
    estimates: list[float] = []
    for _ in range(replicates):
        sampled = [generator.choice(task_ids) for _ in task_ids]
        draws = [value for task_id in sampled for value in values[task_id]]
        estimates.append(sum(draws) / len(draws))
    return _percentile(estimates, 0.025), _percentile(estimates, 0.975)


def _selected_tasks(path: Path, splits: object) -> dict[str, Task]:
    requested_splits = {str(item) for item in splits or []}
    return {
        task.task_id: task
        for task in load_tasks(path)
        if not requested_splits or task.split in requested_splits
    }


def _parse_seeds(value: object) -> tuple[list[int], list[str]]:
    errors: list[str] = []
    seeds: list[int] = []
    if not isinstance(value, list):
        return seeds, ["report.seeds must be a list"]
    for item in value:
        try:
            seeds.append(int(item))
        except (TypeError, ValueError):
            errors.append(f"invalid seed: {item!r}")
    if not seeds:
        errors.append("report.seeds must contain at least one integer")
    if len(set(seeds)) != len(seeds):
        errors.append("report.seeds must not contain duplicates")
    return sorted(seeds), errors


def _row_key(row: Mapping[str, Any]) -> tuple[str, str, int, str] | None:
    try:
        return (
            str(row["model"]),
            str(row["variant"]),
            int(row["seed"]),
            str(row["task_id"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _row_controls_valid(row: Mapping[str, Any], variant: str) -> bool:
    controls = row.get("comparison_controls")
    if not isinstance(controls, Mapping):
        return False
    return (
        controls.get("expose_contract_hints") is False
        and controls.get("adapter_enable_repair") is False
    )


def _model_identity_valid(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _model_binding_valid(
    report: Mapping[str, Any],
    rows: list[tuple[tuple[str, str, int, str], dict[str, Any]]],
    *,
    generic_model: str,
    specialized_model: str,
) -> bool:
    raw_models = report.get("models")
    if not isinstance(raw_models, list):
        return False
    models = {
        str(item.get("name")): item
        for item in raw_models
        if isinstance(item, Mapping) and isinstance(item.get("name"), str)
    }
    generic = models.get(generic_model)
    specialized = models.get(specialized_model)
    if not isinstance(generic, Mapping) or not isinstance(specialized, Mapping):
        return False
    if not all(isinstance(item.get("model_id"), str) and item.get("model_id") for item in (generic, specialized)):
        return False
    if not all(isinstance(item.get("checkpoint_identity_manifest"), str) and item.get("checkpoint_identity_manifest") for item in (generic, specialized)):
        return False
    generic_identity = generic.get("checkpoint_identity_sha256")
    specialized_identity = specialized.get("checkpoint_identity_sha256")
    if not _model_identity_valid(generic_identity) or not _model_identity_valid(specialized_identity):
        return False
    if generic_identity == specialized_identity:
        return False
    for (model, _variant, _seed, _task_id), row in rows:
        expected = models.get(model)
        if not isinstance(expected, Mapping):
            return False
        for field in ("model_id", "revision", "checkpoint_identity_manifest", "checkpoint_identity_sha256"):
            if row.get(field) != expected.get(field):
                return False
    return True


def _provenance_valid(report: Mapping[str, Any], specialized_model: str) -> bool:
    provenance = report.get("provenance")
    if not isinstance(provenance, Mapping) or provenance.get("specialized_model") != specialized_model:
        return False
    audit = provenance.get("train_holdout_audit")
    binding = provenance.get("specialized_checkpoint_training_binding")
    trees = provenance.get("source_trees")
    if not isinstance(audit, Mapping) or audit.get("passed") is not True or not _model_identity_valid(audit.get("sha256")):
        return False
    if not isinstance(binding, Mapping) or binding.get("passed") is not True:
        return False
    raw_models = report.get("models")
    specialized_spec = next(
        (item for item in raw_models or [] if isinstance(item, Mapping) and item.get("name") == specialized_model),
        None,
    )
    if not isinstance(specialized_spec, Mapping) or binding.get("checkpoint") != specialized_spec.get("checkpoint_path"):
        return False
    if not isinstance(trees, Mapping):
        return False
    return all(
        isinstance(tree, Mapping)
        and tree.get("schema") == "python-source-tree/v1"
        and type(tree.get("file_count")) is int
        and int(tree["file_count"]) > 0
        and _model_identity_valid(tree.get("sha256"))
        for tree in (trees.get("project1"), trees.get("harness"))
    )


def analyze(
    report: Mapping[str, Any],
    task_spec: str | Path,
    *,
    generic_model: str,
    specialized_model: str,
    baseline_variant: str = "H1",
    advanced_variant: str = "H3",
    bootstrap_replicates: int = 10_000,
    bootstrap_seed: int = 20_260_802,
) -> dict[str, Any]:
    """Validate and estimate a named four-cell interaction from one raw report."""

    task_path = Path(task_spec)
    task_digest = hashlib.sha256(task_path.read_bytes()).hexdigest()
    tasks = _selected_tasks(task_path, report.get("splits"))
    expected_task_ids = sorted(tasks)
    seeds, seed_errors = _parse_seeds(report.get("seeds"))
    required_cells = (
        (generic_model, baseline_variant),
        (generic_model, advanced_variant),
        (specialized_model, baseline_variant),
        (specialized_model, advanced_variant),
    )
    expected_units = {(seed, task_id) for seed in seeds for task_id in expected_task_ids}
    raw_rows = list(report.get("rows") or [])
    indexed: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    malformed_rows: list[int] = []
    duplicate_rows: list[tuple[str, str, int, str]] = []
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, Mapping):
            malformed_rows.append(index)
            continue
        row = dict(raw)
        key = _row_key(row)
        if key is None:
            malformed_rows.append(index)
        elif key in indexed:
            duplicate_rows.append(key)
        else:
            indexed[key] = row

    coverage: dict[str, dict[str, Any]] = {}
    control_failures: list[tuple[str, str, int, str]] = []
    safety_missing: list[tuple[str, str, int, str]] = []
    unsafe_rows: list[tuple[str, str, int, str]] = []
    replay_rows: list[dict[str, Any]] = []
    all_required_rows: list[tuple[tuple[str, str, int, str], dict[str, Any]]] = []
    for model, variant in required_cells:
        cell_name = f"{model}/{variant}"
        actual_units = {
            (seed, task_id)
            for (row_model, row_variant, seed, task_id) in indexed
            if row_model == model and row_variant == variant
        }
        missing = sorted(expected_units - actual_units)
        unexpected = sorted(actual_units - expected_units)
        coverage[cell_name] = {
            "expected_units": len(expected_units),
            "observed_units": len(actual_units),
            "missing_units": [{"seed": seed, "task_id": task_id} for seed, task_id in missing],
            "unexpected_units": [{"seed": seed, "task_id": task_id} for seed, task_id in unexpected],
            "complete": not missing and not unexpected,
        }
        for seed, task_id in sorted(expected_units):
            key = (model, variant, seed, task_id)
            row = indexed.get(key)
            if row is None:
                continue
            all_required_rows.append((key, row))
            if not _row_controls_valid(row, variant):
                control_failures.append(key)
            if "unsafe_attempt" not in row:
                safety_missing.append(key)
            elif bool(row.get("unsafe_attempt")):
                unsafe_rows.append(key)
            try:
                replay = verify_trace(tasks[task_id], variant, str(row.get("trace_jsonl", "")))
            except Exception as exc:  # Invalid trace is an explicit failed gate, never an unhandled analysis error.
                replay = {
                    "task_id": task_id,
                    "variant": variant,
                    "trace_valid": False,
                    "independent_success": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            replay["model"] = model
            replay["seed"] = seed
            replay["reported_success"] = bool(row.get("verified_success"))
            replay["matches_runtime"] = bool(replay.get("independent_success")) == bool(row.get("verified_success"))
            replay_rows.append(replay)

    required_row_count = len(required_cells) * len(expected_units)
    trace_valid_count = sum(bool(row.get("trace_valid")) for row in replay_rows)
    agreement_count = sum(bool(row.get("matches_runtime")) for row in replay_rows)
    generation = report.get("generation")
    stochastic_decoding = bool(
        isinstance(generation, Mapping)
        and generation.get("do_sample") is True
        and isinstance(generation.get("temperature"), (int, float))
        and float(generation["temperature"]) > 0.0
        and isinstance(generation.get("top_p"), (int, float))
        and 0.0 < float(generation["top_p"]) <= 1.0
        and type(generation.get("max_new_tokens")) is int
        and int(generation["max_new_tokens"]) > 0
        and len(seeds) >= 3
    )
    top_level_controls = report.get("comparison_controls")
    top_level_controls_valid = bool(
        isinstance(top_level_controls, Mapping)
        and all(
            isinstance(top_level_controls.get(variant), Mapping)
            and top_level_controls[variant].get("expose_contract_hints") is False
            and top_level_controls[variant].get("adapter_enable_repair") is False
            for variant in {baseline_variant, advanced_variant}
        )
    )
    gates = {
        "schema": report.get("schema") == REQUIRED_SCHEMA,
        "model_identity_binding": _model_binding_valid(
            report,
            all_required_rows,
            generic_model=generic_model,
            specialized_model=specialized_model,
        ),
        "training_and_source_provenance": _provenance_valid(report, specialized_model),
        "task_spec_binding": report.get("task_spec_sha256") == task_digest,
        "valid_seed_declaration": not seed_errors,
        "stochastic_decoding": stochastic_decoding,
        "cell_coverage": all(cell["complete"] for cell in coverage.values()) and not duplicate_rows and not malformed_rows,
        "control_binding": top_level_controls_valid and not control_failures,
        "trace_validity": required_row_count > 0 and trace_valid_count == required_row_count,
        "runtime_independent_agreement": required_row_count > 0 and agreement_count == required_row_count,
        "safety_accounting": not safety_missing and not unsafe_rows,
    }
    eligible = all(gates.values())

    interaction: dict[str, Any] = {
        "definition": "specialized/H3 - specialized/H1 - generic/H3 + generic/H1",
        "unit": "independently verified task success",
        "eligible_for_claim": eligible,
        "point_estimate": None,
        "bootstrap": None,
        "per_seed": {},
        "cell_success_rates": {},
    }
    if eligible:
        independent_by_key = {
            (str(item["model"]), str(item["variant"]), int(item["seed"]), str(item["task_id"])): bool(item["independent_success"])
            for item in replay_rows
        }
        task_values: dict[str, list[float]] = {task_id: [] for task_id in expected_task_ids}
        seed_values: dict[int, list[float]] = {seed: [] for seed in seeds}
        cell_successes: dict[str, list[bool]] = {f"{model}/{variant}": [] for model, variant in required_cells}
        for seed, task_id in sorted(expected_units):
            generic_baseline = independent_by_key[(generic_model, baseline_variant, seed, task_id)]
            generic_advanced = independent_by_key[(generic_model, advanced_variant, seed, task_id)]
            specialized_baseline = independent_by_key[(specialized_model, baseline_variant, seed, task_id)]
            specialized_advanced = independent_by_key[(specialized_model, advanced_variant, seed, task_id)]
            delta = float(specialized_advanced) - float(specialized_baseline) - float(generic_advanced) + float(generic_baseline)
            task_values[task_id].append(delta)
            seed_values[seed].append(delta)
            for model, variant, value in (
                (generic_model, baseline_variant, generic_baseline),
                (generic_model, advanced_variant, generic_advanced),
                (specialized_model, baseline_variant, specialized_baseline),
                (specialized_model, advanced_variant, specialized_advanced),
            ):
                cell_successes[f"{model}/{variant}"].append(value)
        all_deltas = [value for values in task_values.values() for value in values]
        ci_low, ci_high = _task_cluster_bootstrap(
            task_values,
            replicates=bootstrap_replicates,
            seed=bootstrap_seed,
        )
        interaction.update({
            "point_estimate": sum(all_deltas) / len(all_deltas),
            "bootstrap": {
                "method": "task-cluster percentile bootstrap retaining all seed outcomes per task",
                "replicates": bootstrap_replicates,
                "seed": bootstrap_seed,
                "task_clusters": len(task_values),
                "stochastic_seeds": len(seeds),
                "ci95": {"low": ci_low, "high": ci_high},
                "positive_task_sampling_support": ci_low > 0.0,
            },
            "per_seed": {
                str(seed): sum(values) / len(values)
                for seed, values in sorted(seed_values.items())
            },
            "cell_success_rates": {
                name: sum(values) / len(values)
                for name, values in sorted(cell_successes.items())
            },
        })

    return {
        "schema": SCHEMA,
        "source_schema": report.get("schema"),
        "task_spec": str(task_path),
        "task_spec_sha256": task_digest,
        "models": {
            "generic": generic_model,
            "specialized": specialized_model,
        },
        "variants": {"baseline": baseline_variant, "advanced": advanced_variant},
        "gates": gates,
        "seed_errors": seed_errors,
        "coverage": coverage,
        "integrity": {
            "required_row_count": required_row_count,
            "replayed_row_count": len(replay_rows),
            "trace_valid_count": trace_valid_count,
            "runtime_independent_agreement_count": agreement_count,
            "malformed_row_indexes": malformed_rows,
            "duplicate_rows": [
                {"model": model, "variant": variant, "seed": seed, "task_id": task_id}
                for model, variant, seed, task_id in duplicate_rows
            ],
            "control_failures": [
                {"model": model, "variant": variant, "seed": seed, "task_id": task_id}
                for model, variant, seed, task_id in control_failures
            ],
            "safety_missing": [
                {"model": model, "variant": variant, "seed": seed, "task_id": task_id}
                for model, variant, seed, task_id in safety_missing
            ],
            "unsafe_rows": [
                {"model": model, "variant": variant, "seed": seed, "task_id": task_id}
                for model, variant, seed, task_id in unsafe_rows
            ],
            "replay_rows": replay_rows,
        },
        "interaction": interaction,
        "limitations": [
            "The interval estimates task-sampling uncertainty for the named held-out suite only; it is not a training-replica interval.",
            "A positive interval does not replace native external diagnostics, source/provenance checks, or public-launch controls.",
            "The analysis rejects missing or mismatched cells rather than imputing a score.",
        ],
    }


def to_markdown(result: Mapping[str, Any]) -> str:
    gates = result["gates"]
    interaction = result["interaction"]
    lines = [
        "# Paired Model×Harness Interaction Audit",
        "",
        f"- Eligible for an interaction claim: **{'yes' if interaction['eligible_for_claim'] else 'no'}**",
        f"- Task specification digest: `{result['task_spec_sha256']}`",
        "",
        "## Integrity gates",
        "",
        "| Gate | Passed |",
        "|:---|:---:|",
    ]
    lines.extend(f"| {name.replace('_', ' ')} | {'yes' if passed else 'no'} |" for name, passed in gates.items())
    lines.extend(["", "## Interaction", ""])
    if interaction["eligible_for_claim"]:
        bootstrap = interaction["bootstrap"]
        assert isinstance(bootstrap, Mapping)
        interval = bootstrap["ci95"]
        lines.extend([
            f"- Point estimate: **{interaction['point_estimate']:+.3f}** verified-success-rate points.",
            f"- Task-cluster bootstrap 95% interval: **{interval['low']:+.3f} to {interval['high']:+.3f}** ({bootstrap['replicates']} replicates).",
            f"- Positive task-sampling support: **{'yes' if bootstrap['positive_task_sampling_support'] else 'no'}**.",
            "",
            "## Limits",
            "",
            *[f"- {item}" for item in result["limitations"]],
        ])
    else:
        lines.extend([
            "No interaction estimate is eligible because one or more integrity gates failed.",
            "",
            "## Limits",
            "",
            *[f"- {item}" for item in result["limitations"]],
        ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--task-spec", required=True)
    parser.add_argument("--generic-model", required=True)
    parser.add_argument("--specialized-model", required=True)
    parser.add_argument("--baseline-variant", default="H1")
    parser.add_argument("--advanced-variant", default="H3")
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20_260_802)
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown-output")
    args = parser.parse_args()
    source = Path(args.report)
    report = json.loads(source.read_text(encoding="utf-8"))
    result = analyze(
        report,
        args.task_spec,
        generic_model=args.generic_model,
        specialized_model=args.specialized_model,
        baseline_variant=args.baseline_variant,
        advanced_variant=args.advanced_variant,
        bootstrap_replicates=args.bootstrap_replicates,
        bootstrap_seed=args.bootstrap_seed,
    )
    result["source_report"] = str(source)
    result["source_report_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_output:
        markdown = Path(args.markdown_output)
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(to_markdown(result), encoding="utf-8", newline="\n")
    print(json.dumps({
        "eligible_for_claim": result["interaction"]["eligible_for_claim"],
        "gates": result["gates"],
        "point_estimate": result["interaction"]["point_estimate"],
    }, indent=2))
    return 0 if result["interaction"]["eligible_for_claim"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
