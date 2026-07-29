"""Run Project 1's optional Transformers checkpoint through this harness."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from adapters.project1_transformers import Project1TransformersAdapter
from benchmarks.tasks import load_tasks
from runtime.orchestrator import Harness, HarnessConfig, TaskRequest
from tools.memory_workspace import make_memory_registry


def _runtime_manifest() -> dict[str, object]:
    manifest: dict[str, object] = {"python": platform.python_version(), "platform": platform.platform()}
    try:
        import torch

        manifest.update({"torch": torch.__version__, "cuda": torch.version.cuda, "cuda_available": bool(torch.cuda.is_available())})
        if torch.cuda.is_available():
            manifest.update({"device": torch.cuda.get_device_name(0), "compute_capability": list(torch.cuda.get_device_capability(0)), "bf16_supported": bool(torch.cuda.is_bf16_supported())})
    except ImportError:
        manifest["torch"] = None
    try:
        import transformers

        manifest["transformers"] = transformers.__version__
    except ImportError:
        manifest["transformers"] = None
    try:
        import bitsandbytes

        manifest["bitsandbytes"] = bitsandbytes.__version__
    except (ImportError, AttributeError):
        manifest["bitsandbytes"] = None
    return manifest


def run(project1_root: str | Path, task_spec: str | Path, *, model_id: str | None = None, revision: str | None = None, seed: int = 0, do_sample: bool = False, goal_source: str = "context", quantization: str | None = None) -> dict:
    adapter = Project1TransformersAdapter(project1_root, model_id=model_id, revision=revision, seed=seed, do_sample=do_sample, goal_source=goal_source, quantization=quantization)
    rows = []
    for task in load_tasks(task_spec):
        _, registry = make_memory_registry(task.initial_files)
        harness = Harness(adapter, registry, config=HarnessConfig(variant="H3", model_name=model_id or "project1-transformers", max_steps=6))
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
        rows.append({"task_id": task.task_id, "split": task.split, "protocol_valid": result.protocol_valid, "verified_success": result.verified_success, "error": result.error, "metrics": dict(result.metrics), "trace_jsonl": result.trace_jsonl})
    total = len(rows)
    return {"schema": "project1-transformers-harness-run/v0", "model_id": model_id, "revision": revision, "quantization": getattr(adapter.policy, "quantization", quantization), "seed": seed, "do_sample": do_sample, "runtime": _runtime_manifest(), "task_count": total, "protocol_valid_rate": sum(row["protocol_valid"] for row in rows) / total if total else 0.0, "verified_success_rate": sum(row["verified_success"] for row in rows) / total if total else 0.0, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project1-root", required=True)
    parser.add_argument("--task-spec", default=str(Path(__file__).parent.parent / "benchmarks" / "fixtures" / "task-spec-v0.json"))
    parser.add_argument("--model-id")
    parser.add_argument("--revision")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--do-sample", action="store_true")
    parser.add_argument("--goal-source", choices=("context", "prompt"), default="context")
    parser.add_argument("--quantization", choices=("4bit", "int4", "nf4"))
    parser.add_argument("--output", default=str(Path(__file__).parent / "results" / "project1-transformers-h3-v0.json"))
    args = parser.parse_args()
    report = run(args.project1_root, args.task_spec, model_id=args.model_id, revision=args.revision, seed=args.seed, do_sample=args.do_sample, goal_source=args.goal_source, quantization=args.quantization)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("model_id", "revision", "runtime", "task_count", "protocol_valid_rate", "verified_success_rate")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
