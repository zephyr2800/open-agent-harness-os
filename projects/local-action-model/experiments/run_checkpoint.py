"""Run a pinned local checkpoint against the fixed task specification."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from eval.task_spec import load_tasks
from eval.verified import verify_decision
from model.adapter import ModelOutputError, ModelRequest
from model.transformers_backend import TransformersActionPolicy


def run_checkpoint(tasks, *, model_id: str, revision: str, max_new_tokens: int, quantization: str | None = None) -> dict[str, Any]:
    load_start = time.perf_counter()
    policy = TransformersActionPolicy(model_id=model_id, revision=revision, max_new_tokens=max_new_tokens, quantization=quantization)
    load_ms = (time.perf_counter() - load_start) * 1000
    rows = []
    for task in tasks:
        request = ModelRequest(
            task_id=task.task_id,
            goal=task.prompt,
            state={"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
            available_tools=task.available_tools,
            token_budget=task.output_token_budget,
        )
        start = time.perf_counter()
        try:
            decision = policy.decide(request)
            outcome = verify_decision(task, decision)
            row = {
                "task_id": task.task_id,
                "split": task.split,
                "valid": True,
                "success": outcome.success,
                "errors": list(outcome.errors),
                "evidence": list(outcome.evidence),
            }
        except ModelOutputError as exc:
            row = {
                "task_id": task.task_id,
                "split": task.split,
                "valid": False,
                "success": False,
                "errors": ["model_output_error", str(exc)],
                "raw_output": (policy.last_raw_text or "")[:4000],
            }
        row.update(
            {
                "wall_ms": round((time.perf_counter() - start) * 1000, 1),
                "generation_ms": round(policy.last_generation_ms or 0.0, 1),
                "input_tokens": policy.last_input_tokens,
                "output_tokens": policy.last_output_tokens,
                "peak_vram_mib": policy.last_peak_vram_mib,
            }
        )
        rows.append(row)
    total = len(rows)
    output_tokens = sum(row.get("output_tokens") or 0 for row in rows)
    return {
        "schema": "checkpoint-evaluation/v0",
        "model_id": model_id,
        "revision": revision,
        "quantization": policy.quantization,
        "load_ms": round(load_ms, 1),
        "metrics": {
            "task_count": total,
            "valid_decision_rate": sum(row["valid"] for row in rows) / total if total else 0.0,
            "verified_task_success": sum(row["success"] for row in rows) / total if total else 0.0,
            "protocol_error_rate": sum(not row["valid"] for row in rows) / total if total else 0.0,
            "output_tokens": output_tokens,
            "verified_progress_per_output_token": sum(row["success"] for row in rows) / output_tokens if output_tokens else 0.0,
            "mean_wall_ms": sum(row["wall_ms"] for row in rows) / total if total else 0.0,
            "peak_vram_mib": max((row.get("peak_vram_mib") or 0.0) for row in rows) if rows else 0.0,
        },
        "tasks": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-spec", required=True)
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--quantization", choices=("4bit", "int4", "nf4"))
    parser.add_argument("--output")
    args = parser.parse_args()
    result = run_checkpoint(load_tasks(args.task_spec), model_id=args.model_id, revision=args.revision, max_new_tokens=args.max_new_tokens, quantization=args.quantization)
    serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
