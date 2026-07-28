"""Run a Project 1 task-spec through the Project 2 harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from adapters.project1_transformers import Project1TransformersAdapter
from runtime.orchestrator import Harness, HarnessConfig, TaskRequest
from tools.memory_workspace import make_memory_registry
from experiments.project1_transformers_run import _runtime_manifest


def _load_project1_tasks(project1_root: Path, task_spec: Path):
    sys.path.insert(0, str(project1_root))
    from eval.task_spec import load_tasks

    return load_tasks(task_spec)


def _initial_files(task_id: str) -> dict[str, str]:
    if task_id == "inspect_status":
        return {"STATUS.md": "checkpoint: verified\n"}
    if task_id == "archive_report":
        return {"reports/final.md": "verified report\n"}
    return {}


def run(project1_root: str | Path, task_spec: str | Path, checkpoint: str | Path, *, variant: str = "H3", goal_source: str = "context") -> dict:
    project1_root = Path(project1_root)
    tasks = _load_project1_tasks(project1_root, Path(task_spec))
    model = Project1TransformersAdapter(project1_root, model_id=str(checkpoint), revision="main", goal_source=goal_source)
    rows = []
    for task in tasks:
        _, registry = make_memory_registry(_initial_files(task.task_id))
        harness = Harness(model, registry, config=HarnessConfig(variant=variant, model_name=str(checkpoint), max_steps=6))
        request = TaskRequest(task.task_id, task.prompt, task.available_tools, task.output_token_budget, task.expected_kind, task.expected_intent, task.expected_arguments, task.split)
        result = harness.run(request)
        rows.append({"task_id": task.task_id, "split": task.split, "protocol_valid": result.protocol_valid, "verified_success": result.verified_success, "abstained": result.abstained, "error": result.error, "metrics": dict(result.metrics), "trace_jsonl": result.trace_jsonl})
    total = len(rows)
    return {"schema": "project1-task-harness-run/v0", "checkpoint": str(checkpoint), "variant": variant, "runtime": _runtime_manifest(), "task_count": total, "protocol_valid_rate": sum(row["protocol_valid"] for row in rows) / total if total else 0.0, "verified_success_rate": sum(row["verified_success"] for row in rows) / total if total else 0.0, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project1-root", required=True)
    parser.add_argument("--task-spec", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--variant", default="H3", choices=("H0", "H1", "H2", "H3", "H4"))
    parser.add_argument("--goal-source", choices=("context", "prompt"), default="context")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run(args.project1_root, args.task_spec, args.checkpoint, variant=args.variant, goal_source=args.goal_source)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("checkpoint", "variant", "runtime", "task_count", "protocol_valid_rate", "verified_success_rate")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
