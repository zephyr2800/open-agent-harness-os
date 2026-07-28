"""Multi-seed fixture and optional real-local-model evaluation runner."""

from __future__ import annotations

import argparse
import json
import math
import platform
import sys
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Iterable

from benchmarks.tasks import load_tasks
from experiments.factorial import run_factorial
from runtime.orchestrator import Harness, HarnessConfig, TaskRequest
from tools.memory_workspace import make_memory_registry
from adapters.project1_transformers import Project1TransformersAdapter
from experiments.project1_transformers_run import _runtime_manifest


def _summary(values: Iterable[float]) -> dict[str, float]:
    values = list(values)
    if not values:
        return {"n": 0.0, "mean": 0.0, "std": 0.0, "ci95": 0.0}
    deviation = stdev(values) if len(values) > 1 else 0.0
    return {"n": float(len(values)), "mean": mean(values), "std": deviation, "ci95": 1.96 * deviation / math.sqrt(len(values))}


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
    return {"schema": "multiseed-fixture/v0", "task_spec": str(task_spec), "seed_count": len(runs), "runs": runs, "interaction_summary": interaction_summary}


def run_real(project1_root: str | Path, task_spec: str | Path, *, model_specs: list[dict[str, str]], seeds: Iterable[int], variants: tuple[str, ...], do_sample: bool, splits: tuple[str, ...] = (), goal_source: str = "context") -> dict[str, Any]:
    tasks = tuple(task for task in load_tasks(task_spec) if not splits or task.split in splits)
    rows: list[dict[str, Any]] = []
    for model_spec in model_specs:
        model_name = model_spec["name"]
        model_id = model_spec["model_id"]
        revision = model_spec.get("revision")
        for seed in seeds:
            adapter = Project1TransformersAdapter(project1_root, model_id=model_id, revision=revision, seed=seed, do_sample=do_sample, goal_source=goal_source)
            for variant in variants:
                for task in tasks:
                    _, registry = make_memory_registry(task.initial_files)
                    harness = Harness(adapter, registry, config=HarnessConfig(variant=variant, model_name=model_name, max_steps=6))
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
                    rows.append({
                        "model": model_name,
                        "model_id": model_id,
                        "revision": revision,
                        "seed": seed,
                        "variant": variant,
                        "task_id": task.task_id,
                        "split": task.split,
                        "protocol_valid": result.protocol_valid,
                        "verified_success": result.verified_success,
                        "error": result.error,
                        "metrics": dict(result.metrics),
                        "trace_jsonl": result.trace_jsonl,
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
        "schema": "multiseed-project1-harness/v0",
        "python": platform.python_version(),
        "runtime": _runtime_manifest(),
        "task_spec": str(task_spec),
        "splits": list(splits),
        "seeds": list(seeds),
        "variants": list(variants),
        "do_sample": do_sample,
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
    parser.add_argument("--variants", default="H1,H3")
    parser.add_argument("--splits", default="", help="comma-separated task splits to include in real mode")
    parser.add_argument("--goal-source", choices=("context", "prompt"), default="context")
    parser.add_argument("--do-sample", action="store_true")
    args = parser.parse_args()
    seeds = [int(item) for item in args.seeds.split(",") if item.strip()]
    if args.mode == "fixture":
        report = run_fixture(args.task_spec, seeds)
    else:
        if not args.project1_root or not args.model:
            parser.error("real mode requires --project1-root and at least one --model")
        specs = []
        for item in args.model:
            name, value = item.split("=", 1)
            model_id, _, revision = value.partition("@")
            specs.append({"name": name, "model_id": model_id, "revision": revision or None})
        report = run_real(args.project1_root, args.task_spec, model_specs=specs, seeds=seeds, variants=tuple(args.variants.split(",")), do_sample=args.do_sample, splits=tuple(item for item in args.splits.split(",") if item), goal_source=args.goal_source)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("schema", "seed_count", "interaction_summary") if key in report}, indent=2))
    if "summaries" in report:
        print(json.dumps(report["summaries"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
