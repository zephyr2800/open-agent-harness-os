"""Multi-seed fixture and optional real-local-model evaluation runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Iterable

from benchmarks.tasks import load_tasks
from experiments.factorial import run_factorial
from runtime.orchestrator import Harness, HarnessConfig, TaskRequest
from tools.memory_workspace import make_memory_registry
from adapters.project1_transformers import Project1TransformersAdapter
from experiments.data_split_audit import validate_checkpoint_training_binding, validate_required_audit_manifest
from experiments.checkpoint_identity import manifest_sha256, verify_checkpoint_identity_manifest
from experiments.project1_transformers_run import _runtime_manifest
from experiments.source_tree import record_source_tree
from verify.independent import verify_trace


REPO_ROOT = Path(__file__).resolve().parent.parent


def _summary(values: Iterable[float]) -> dict[str, float]:
    values = list(values)
    if not values:
        return {"n": 0.0, "mean": 0.0, "std": 0.0}
    deviation = stdev(values) if len(values) > 1 else 0.0
    return {"n": float(len(values)), "mean": mean(values), "std": deviation}


def _cell_controls(variant: str, repair_variants: frozenset[str]) -> dict[str, bool]:
    """Return the preregistered differences between model×harness cells.

    Evaluation-owned expected-action fields must not be shown to a model in
    any A-D research cell. Deterministic adapter repair is reserved for an
    explicitly named remediation/E arm, not silently inherited by H3.
    """

    return {
        "expose_contract_hints": False,
        "adapter_enable_repair": variant in repair_variants,
    }


def _record_provenance(
    *,
    project1_root: str | Path,
    model_specs: list[dict[str, Any]],
    specialized_model: str,
    train_holdout_audit: str | Path,
) -> dict[str, Any]:
    """Bind the specialized checkpoint to the audited training source pre-load."""

    audit_gate = validate_required_audit_manifest(Path(train_holdout_audit))
    if not audit_gate["passed"]:
        raise ValueError("train_holdout_audit must be a passing complete audit")
    specialized_spec = next((spec for spec in model_specs if spec["name"] == specialized_model), None)
    if specialized_spec is None:
        raise ValueError("specialized_model must name one supplied model spec")
    checkpoint_path = specialized_spec.get("checkpoint_path")
    if not isinstance(checkpoint_path, str) or not checkpoint_path:
        raise ValueError("specialized model requires a checkpoint_path for train/holdout binding")
    checkpoint_training_binding = validate_checkpoint_training_binding(Path(checkpoint_path), audit_gate)
    if not checkpoint_training_binding["passed"]:
        raise ValueError("specialized checkpoint must carry a merge/training manifest bound to the audited data")
    return {
        "train_holdout_audit": audit_gate,
        "specialized_model": specialized_model,
        "specialized_checkpoint_training_binding": checkpoint_training_binding,
        "source_trees": {
            "project1": record_source_tree(project1_root),
            "harness": record_source_tree(REPO_ROOT),
        },
    }


def _bind_model_identities(model_specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Require each claim-eligible adapter to load the locally fingerprinted checkpoint."""

    bound: list[dict[str, Any]] = []
    for raw_spec in model_specs:
        spec = dict(raw_spec)
        model_id = spec.get("model_id")
        checkpoint_path = spec.get("checkpoint_path")
        manifest_path = spec.get("checkpoint_identity_manifest")
        if not isinstance(model_id, str) or not model_id:
            raise ValueError("every model requires a non-empty model_id")
        if not isinstance(checkpoint_path, str) or not checkpoint_path:
            raise ValueError("every claim-eligible model requires a local checkpoint_path")
        if not isinstance(manifest_path, str) or not manifest_path:
            raise ValueError("every claim-eligible model requires a checkpoint_identity_manifest")
        model_path = Path(model_id).expanduser().resolve()
        checkpoint = Path(checkpoint_path).expanduser().resolve()
        if model_path != checkpoint:
            raise ValueError("claim-eligible model_id must resolve to its local checkpoint_path")
        identity = verify_checkpoint_identity_manifest(
            manifest_path,
            model_id=model_id,
            revision=spec.get("revision"),
            checkpoint_path=checkpoint,
        )
        spec["checkpoint_path"] = str(checkpoint)
        spec["checkpoint_identity_manifest"] = str(Path(manifest_path).expanduser().resolve())
        spec["checkpoint_identity_sha256"] = manifest_sha256(manifest_path)
        spec["checkpoint_content_sha256"] = identity["sha256"]
        bound.append(spec)
    return bound


def run_fixture(task_spec: str | Path, seeds: Iterable[int]) -> dict[str, Any]:
    runs = []
    for seed in seeds:
        report = run_factorial(task_spec)
        runs.append({
            "seed": int(seed),
            "interaction_vs_H1": report["interaction_vs_H1"],
            "metrics": {
                cell: payload["summary"]["verified_success_rate"]
                for cell, payload in report["cells"].items()
            },
        })
    interaction_summary = {
        variant: _summary(run["interaction_vs_H1"][variant] for run in runs)
        for variant in ("H2", "H3", "H4")
    }
    return {
        "schema": "multiseed-fixture/v0",
        "task_spec": str(task_spec),
        "seed_count": len(runs),
        "seed_semantics": "labels only; fixture policy execution is deterministic and not a stochastic result",
        "runs": runs,
        "interaction_summary": interaction_summary,
    }


def run_real(
    project1_root: str | Path,
    task_spec: str | Path,
    *,
    model_specs: list[dict[str, Any]],
    seeds: Iterable[int],
    variants: tuple[str, ...],
    do_sample: bool,
    splits: tuple[str, ...] = (),
    goal_source: str = "context",
    quantization: str | None = None,
    temperature: float = 0.7,
    top_p: float = 0.9,
    max_new_tokens: int = 256,
    repair_variants: Iterable[str] = (),
    specialized_model: str | None = None,
    train_holdout_audit: str | Path | None = None,
    require_provenance: bool = False,
) -> dict[str, Any]:
    task_spec_path = Path(task_spec)
    model_specs = [dict(spec) for spec in model_specs]
    seeds = tuple(int(seed) for seed in seeds)
    variants = tuple(variant.strip() for variant in variants if variant.strip())
    repair_variants = frozenset(variant.strip() for variant in repair_variants if variant.strip())
    if not seeds:
        raise ValueError("at least one seed is required")
    if not variants:
        raise ValueError("at least one harness variant is required")
    if not repair_variants.issubset(set(variants)):
        raise ValueError("repair_variants must be included in variants")
    if not repair_variants.issubset({"H4"}):
        raise ValueError("deterministic adapter repair is reserved for H4 remediation runs")
    names = [str(spec.get("name", "")) for spec in model_specs]
    if not names or any(not name for name in names) or len(set(names)) != len(names):
        raise ValueError("model_specs must contain unique non-empty names")
    provenance = None
    if require_provenance:
        if specialized_model is None or train_holdout_audit is None:
            raise ValueError("specialized_model and train_holdout_audit are required for a provenance-bound real factorial")
        provenance = _record_provenance(
            project1_root=project1_root,
            model_specs=model_specs,
            specialized_model=specialized_model,
            train_holdout_audit=train_holdout_audit,
        )
        model_specs = _bind_model_identities(model_specs)
    tasks = tuple(task for task in load_tasks(task_spec_path) if not splits or task.split in splits)
    task_spec_sha256 = hashlib.sha256(task_spec_path.read_bytes()).hexdigest()
    rows: list[dict[str, Any]] = []
    for model_spec in model_specs:
        model_name = model_spec["name"]
        model_id = model_spec["model_id"]
        revision = model_spec.get("revision")
        for seed in seeds:
            for variant in variants:
                controls = _cell_controls(variant, repair_variants)
                adapter = Project1TransformersAdapter(
                    project1_root,
                    model_id=model_id,
                    revision=revision,
                    seed=seed,
                    do_sample=do_sample,
                    goal_source=goal_source,
                    quantization=quantization,
                    temperature=temperature,
                    top_p=top_p,
                    max_new_tokens=max_new_tokens,
                    enable_repair=controls["adapter_enable_repair"],
                )
                for task in tasks:
                    _, registry = make_memory_registry(
                        task.initial_files,
                        api_records=task.api_records,
                        browser_pages=task.browser_pages,
                    )
                    harness = Harness(
                        adapter,
                        registry,
                        config=HarnessConfig(
                            variant=variant,
                            model_name=model_name,
                            max_steps=6,
                            expose_contract_hints=controls["expose_contract_hints"],
                            include_tool_outputs=task.include_tool_outputs,
                        ),
                    )
                    result = harness.run(TaskRequest(
                        task.task_id,
                        task.prompt,
                        task.available_tools,
                        task.output_token_budget,
                        task.expected_kind,
                        task.expected_tool,
                        task.expected_arguments,
                        task.split,
                        task.expected_tools,
                        task.expected_actions,
                        task.expected_files,
                        task.expected_result_contains,
                    ))
                    try:
                        independent = verify_trace(task, variant, result.trace_jsonl)
                    except Exception as exc:  # Preserve an invalid replay as evidence, never as success.
                        independent = {
                            "task_id": task.task_id,
                            "variant": variant,
                            "trace_valid": False,
                            "independent_success": False,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    independent["runtime_success"] = bool(result.verified_success)
                    independent["matches_runtime"] = bool(independent.get("independent_success")) == bool(result.verified_success)
                    unsafe_attempt = any(
                        event.event_type == "tool_call" and event.payload.get("tool") == "delete_file"
                        for event in result.trace.events
                    )
                    rows.append({
                        "model": model_name,
                        "model_id": model_id,
                        "revision": revision,
                        "checkpoint_path": model_spec.get("checkpoint_path"),
                        "checkpoint_identity_manifest": model_spec.get("checkpoint_identity_manifest"),
                        "checkpoint_identity_sha256": model_spec.get("checkpoint_identity_sha256"),
                        "checkpoint_content_sha256": model_spec.get("checkpoint_content_sha256"),
                        "seed": seed,
                        "variant": variant,
                        "task_id": task.task_id,
                        "split": task.split,
                        "protocol_valid": result.protocol_valid,
                        "verified_success": result.verified_success,
                        "unsafe_attempt": unsafe_attempt,
                        "error": result.error,
                        "metrics": dict(result.metrics),
                        "trace_jsonl": result.trace_jsonl,
                        "independent": independent,
                        "comparison_controls": controls,
                    })
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(f"{row['model']}/{row['variant']}", []).append(row)
    summaries = {}
    for key, group in groups.items():
        summaries[key] = {
            "task_observations": len(group),
            "protocol_valid_rate": sum(bool(row["protocol_valid"]) for row in group) / len(group),
            "verified_success_rate": sum(bool(row["verified_success"]) for row in group) / len(group),
        }
    seed_groups: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for row in rows:
        seed_groups.setdefault((row["model"], row["variant"], int(row["seed"])), []).append(row)
    seed_summaries = {
        f"{model}/{variant}/seed-{seed}": {
            "protocol_valid_rate": sum(bool(row["protocol_valid"]) for row in group) / len(group),
            "verified_success_rate": sum(bool(row["verified_success"]) for row in group) / len(group),
            "task_count": len(group),
        }
        for (model, variant, seed), group in seed_groups.items()
    }
    across_seed = {
        key: {
            "protocol_valid_rate": _summary(value["protocol_valid_rate"] for name, value in seed_summaries.items() if name.rsplit("/", 1)[0] == key),
            "verified_success_rate": _summary(value["verified_success_rate"] for name, value in seed_summaries.items() if name.rsplit("/", 1)[0] == key),
        }
        for key in {name.rsplit("/", 1)[0] for name in seed_summaries}
    }
    return {
        "schema": "multiseed-project1-harness/v1",
        "python": platform.python_version(),
        "runtime": _runtime_manifest(),
        "task_spec": str(task_spec_path),
        "task_spec_sha256": task_spec_sha256,
        "splits": list(splits),
        "seeds": list(seeds),
        "variants": list(variants),
        "generation": {
            "do_sample": do_sample,
            "temperature": temperature,
            "top_p": top_p,
            "quantization": quantization,
            "max_new_tokens": max_new_tokens,
            "seed_semantics": "per-decision blocked decoding seeds; not independent training replicas",
        },
        "models": [
            {
                "name": spec["name"],
                "model_id": spec["model_id"],
                "revision": spec.get("revision"),
                "checkpoint_path": spec.get("checkpoint_path"),
                "checkpoint_identity_manifest": spec.get("checkpoint_identity_manifest"),
                "checkpoint_identity_sha256": spec.get("checkpoint_identity_sha256"),
                "checkpoint_content_sha256": spec.get("checkpoint_content_sha256"),
            }
            for spec in model_specs
        ],
        "comparison_controls": {variant: _cell_controls(variant, repair_variants) for variant in variants},
        "adapter_repair_variants": sorted(repair_variants),
        "provenance": provenance,
        "summaries": summaries,
        "seed_summaries": seed_summaries,
        "across_seed": across_seed,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fixture", "real"), default="fixture")
    parser.add_argument("--task-spec", default=str(Path(__file__).parent.parent / "benchmarks" / "fixtures" / "task-spec-research-v1.json"))
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--output", required=True)
    parser.add_argument("--project1-root")
    parser.add_argument("--model", action="append", default=[], help="name=model_id or name=model_id@revision")
    parser.add_argument("--model-checkpoint", action="append", default=[], help="name=local merged checkpoint directory")
    parser.add_argument(
        "--model-identity-manifest",
        action="append",
        default=[],
        help="name=path to an immutable checkpoint-identity manifest; its SHA-256 is recorded and required for an interaction claim",
    )
    parser.add_argument("--variants", default="H1,H3")
    parser.add_argument("--splits", default="", help="comma-separated task splits to include in real mode")
    parser.add_argument("--goal-source", choices=("context", "prompt"), default="context")
    parser.add_argument("--do-sample", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--repair-variant", action="append", default=[], help="explicit remediation-only harness variant allowed to use adapter repair")
    parser.add_argument("--specialized-model", help="name of the specialized model supplied via --model; required in real mode")
    parser.add_argument("--train-holdout-audit", help="passing source-bound train/holdout audit; required in real mode")
    parser.add_argument("--quantization", choices=("4bit", "int4", "nf4"))
    args = parser.parse_args()
    seeds = [int(item) for item in args.seeds.split(",") if item.strip()]
    if args.mode == "fixture":
        report = run_fixture(args.task_spec, seeds)
    else:
        if not args.project1_root or not args.model:
            parser.error("real mode requires --project1-root and at least one --model")
        if not args.specialized_model or not args.train_holdout_audit:
            parser.error("real mode requires --specialized-model and --train-holdout-audit")
        specs = []
        identities: dict[str, str] = {}
        for item in args.model_identity_manifest:
            name, raw_path = item.split("=", 1)
            if name in identities:
                parser.error(f"duplicate --model-identity-manifest for {name}")
            path = Path(raw_path)
            if not path.is_file():
                parser.error(f"checkpoint identity manifest does not exist: {path}")
            identities[name] = str(path)
        checkpoints: dict[str, str] = {}
        for item in args.model_checkpoint:
            name, path = item.split("=", 1)
            if name in checkpoints:
                parser.error(f"duplicate --model-checkpoint for {name}")
            checkpoints[name] = path
        for item in args.model:
            name, value = item.split("=", 1)
            model_id, _, revision = value.partition("@")
            specs.append({
                "name": name,
                "model_id": model_id,
                "revision": revision or None,
                "checkpoint_path": checkpoints.get(name),
                "checkpoint_identity_manifest": identities.get(name),
            })
        unknown_identities = sorted(set(identities) - {str(spec["name"]) for spec in specs})
        if unknown_identities:
            parser.error("--model-identity-manifest names must match --model names: " + ", ".join(unknown_identities))
        missing_identities = sorted(str(spec["name"]) for spec in specs if str(spec["name"]) not in identities)
        if missing_identities:
            parser.error("real mode requires --model-identity-manifest for every --model: " + ", ".join(missing_identities))
        unknown_checkpoints = sorted(set(checkpoints) - {str(spec["name"]) for spec in specs})
        if unknown_checkpoints:
            parser.error("--model-checkpoint names must match --model names: " + ", ".join(unknown_checkpoints))
        missing_checkpoints = sorted(str(spec["name"]) for spec in specs if not isinstance(spec.get("checkpoint_path"), str) or not spec["checkpoint_path"])
        if missing_checkpoints:
            parser.error("real mode requires --model-checkpoint for every --model: " + ", ".join(missing_checkpoints))
        report = run_real(
            args.project1_root,
            args.task_spec,
            model_specs=specs,
            seeds=seeds,
            variants=tuple(args.variants.split(",")),
            do_sample=args.do_sample,
            splits=tuple(item for item in args.splits.split(",") if item),
            goal_source=args.goal_source,
            quantization=args.quantization,
            temperature=args.temperature,
            top_p=args.top_p,
            max_new_tokens=args.max_new_tokens,
            repair_variants=tuple(args.repair_variant),
            specialized_model=args.specialized_model,
            train_holdout_audit=args.train_holdout_audit,
            require_provenance=True,
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("schema", "seed_count", "interaction_summary") if key in report}, indent=2))
    if "summaries" in report:
        print(json.dumps(report["summaries"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
