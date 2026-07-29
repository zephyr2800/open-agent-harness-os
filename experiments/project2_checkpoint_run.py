"""Evaluate a local Project 1 checkpoint on the Project 2 task contract.

This runner keeps the model-only and verifier-first-repair conditions explicit.
The evaluator, authority policy, tool handlers, and independent verification
remain in Project 2 and are never supplied by the model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from adapters.project1_transformers import Project1TransformersAdapter
from benchmarks.tasks import load_tasks
from experiments.project1_transformers_run import _runtime_manifest
from runtime.orchestrator import Harness, HarnessConfig, TaskRequest
from tools.memory_workspace import make_memory_registry


def run(project1_root: str | Path, task_spec: str | Path, checkpoint: str | Path, *, variant: str = "H3", seed: int = 0, do_sample: bool = False, enable_repair: bool = True, expose_contract_hints: bool = True, splits: tuple[str, ...] = (), quantization: str | None = None) -> dict[str, Any]:
    project1_root = Path(project1_root)
    task_spec = Path(task_spec)
    tasks = tuple(task for task in load_tasks(task_spec) if not splits or task.split in splits)
    adapter = Project1TransformersAdapter(
        project1_root,
        model_id=str(checkpoint),
        revision="main",
        seed=seed,
        do_sample=do_sample,
        enable_repair=enable_repair,
        quantization=quantization,
    )
    rows: list[dict[str, Any]] = []
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
                model_name=str(checkpoint),
                max_steps=6,
                expose_contract_hints=expose_contract_hints,
                include_tool_outputs=task.include_tool_outputs,
            ),
        )
        request = TaskRequest(
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
        )
        result = harness.run(request)
        unsafe_attempt = any(
            event.event_type == "tool_call" and event.payload.get("tool") in {"delete_file"}
            for event in result.trace.events
        )
        rows.append({
            "task_id": task.task_id,
            "family": task.family,
            "difficulty": task.difficulty,
            "adversarial": task.adversarial,
            "expected_kind": task.expected_kind,
            "include_tool_outputs": task.include_tool_outputs,
            "unsafe_attempt": unsafe_attempt,
            "split": task.split,
            "protocol_valid": result.protocol_valid,
            "verified_success": result.verified_success,
            "abstained": result.abstained,
            "steps": result.steps,
            "error": result.error,
            "metrics": dict(result.metrics),
            "trace_jsonl": result.trace_jsonl,
        })
    total = len(rows)
    raw_spec = task_spec.read_bytes()
    return {
        "schema": "project2-checkpoint-run/v1",
        "checkpoint": str(checkpoint),
        "task_spec": str(task_spec),
        "task_spec_sha256": hashlib.sha256(raw_spec).hexdigest(),
        "variant": variant,
        "seed": seed,
        "do_sample": do_sample,
        "enable_repair": enable_repair,
        "quantization": getattr(adapter.policy, "quantization", quantization),
        "quantization_compute_dtype": getattr(adapter.policy, "quantization_compute_dtype", None),
        "runtime": _runtime_manifest(),
        "expose_contract_hints": expose_contract_hints,
        "task_count": total,
        "protocol_valid_rate": sum(bool(row["protocol_valid"]) for row in rows) / total if total else 0.0,
        "verified_success_rate": sum(bool(row["verified_success"]) for row in rows) / total if total else 0.0,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project1-root", required=True)
    parser.add_argument("--task-spec", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--variant", default="H3", choices=("H0", "H1", "H2", "H3", "H4"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--do-sample", action="store_true")
    parser.add_argument("--no-repair", action="store_true")
    parser.add_argument("--hide-contract-hints", action="store_true", help="do not expose evaluator expected-tool hints to the model")
    parser.add_argument("--quantization", choices=("4bit", "int4", "nf4"))
    parser.add_argument("--splits", default="", help="comma-separated task splits")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    splits = tuple(item.strip() for item in args.splits.split(",") if item.strip())
    report = run(
        args.project1_root,
        args.task_spec,
        args.checkpoint,
        variant=args.variant,
        seed=args.seed,
        do_sample=args.do_sample,
        enable_repair=not args.no_repair,
        expose_contract_hints=not args.hide_contract_hints,
        splits=splits,
        quantization=args.quantization,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("task_count", "protocol_valid_rate", "verified_success_rate", "enable_repair", "task_spec_sha256")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
