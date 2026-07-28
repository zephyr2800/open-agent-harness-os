"""Run the real checkpoint-backed model x harness factorial.

Unlike ``experiments.factorial``, this runner loads two local checkpoints and
evaluates them through the same baseline/advanced harness interfaces. The
stateful evaluator remains the source of truth for execution and independent
verification. A real result is still a smoke experiment until the task suite
is enlarged and the specialized data is independently sourced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

from eval.task_spec import load_tasks
from eval.verified import verify_decision
from model.adapter import ModelOutputError, ModelRequest
from model.transformers_backend import TransformersActionPolicy
from .factorial import AdvancedHarness, BaselineHarness, Harness


class CheckpointPolicy:
    """Expose a real Transformers policy through the factorial model interface."""

    def __init__(self, model_id: str, revision: str, *, max_new_tokens: int) -> None:
        self.model_id = model_id
        self.revision = revision
        load_start = time.perf_counter()
        self.backend = TransformersActionPolicy(
            model_id=model_id,
            revision=revision,
            max_new_tokens=max_new_tokens,
        )
        self.load_ms = (time.perf_counter() - load_start) * 1000

    def decide(self, request: ModelRequest) -> dict[str, Any]:
        return self.backend.decide(request)


def _request(task: Any, *, context_mode: str) -> ModelRequest:
    return ModelRequest(
        task_id=task.task_id,
        goal=task.prompt,
        state={
            "facts": [],
            "assumptions": [],
            "open_questions": [],
            "resolved_questions": [],
            "context_mode": context_mode,
            "task_split": task.split,
        },
        available_tools=task.available_tools,
        token_budget=task.output_token_budget,
    )


def _run_cell(tasks: tuple[Any, ...], policy: CheckpointPolicy, harness: Harness) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    backend = getattr(policy, "backend", None)
    for task in tasks:
        request = _request(task, context_mode="retrieved_tools_state_verifier" if harness.name == "advanced" else "transcript_only")
        start = time.perf_counter()
        try:
            # Use the same request the harness would use, but keep the harness
            # responsible for deciding whether malformed output is recoverable.
            result = harness.run(task, policy)
            if result.decision is None:
                rows.append(
                    {
                        "task_id": task.task_id,
                        "split": task.split,
                        "protocol_valid": False,
                        "action_executed": False,
                        "independently_verified": False,
                        "success": False,
                        "errors": [result.error or "model_output_error"],
                        "recovery": result.recovery,
                    }
                )
            else:
                outcome = verify_decision(task, result.decision)
                rows.append(
                    {
                        "task_id": task.task_id,
                        "split": task.split,
                        "protocol_valid": outcome.protocol_valid,
                        "action_executed": outcome.action_executed,
                        "independently_verified": outcome.independently_verified,
                        "success": outcome.success,
                        "errors": list(outcome.errors),
                        "evidence": list(outcome.evidence),
                        "recovery": result.recovery,
                    }
                )
        except ModelOutputError as exc:
            rows.append(
                {
                    "task_id": task.task_id,
                    "split": task.split,
                    "protocol_valid": False,
                    "action_executed": False,
                    "independently_verified": False,
                    "success": False,
                    "errors": ["model_output_error", str(exc)],
                    "recovery": None,
                }
            )
        row = rows[-1]
        row.update(
            {
                "wall_ms": round((time.perf_counter() - start) * 1000, 1),
                "generation_ms": round(getattr(backend, "last_generation_ms", None) or 0.0, 1),
                "input_tokens": getattr(backend, "last_input_tokens", None),
                "output_tokens": getattr(backend, "last_output_tokens", None),
                "peak_vram_mib": getattr(backend, "last_peak_vram_mib", None),
                "raw_output": (getattr(backend, "last_raw_text", None) or "")[:4000],
            }
        )
    total = len(rows)
    abstention_tasks = {task.task_id for task in tasks if task.expected_kind == "abstain"}
    output_tokens = sum(row.get("output_tokens") or 0 for row in rows)
    return {
        "metrics": {
            "task_count": total,
            "protocol_valid_rate": sum(row["protocol_valid"] for row in rows) / total if total else 0.0,
            "verified_task_success": sum(row["success"] for row in rows) / total if total else 0.0,
            "correct_abstention_rate": sum(row["success"] for row in rows if row["task_id"] in abstention_tasks) / len(abstention_tasks) if abstention_tasks else 0.0,
            "action_execution_rate": sum(row["action_executed"] for row in rows) / total if total else 0.0,
            "independent_verification_rate": sum(row["independently_verified"] for row in rows) / total if total else 0.0,
            "output_tokens": output_tokens,
            "mean_wall_ms": sum(row["wall_ms"] for row in rows) / total if total else 0.0,
            "mean_generation_ms": sum(row["generation_ms"] for row in rows) / total if total else 0.0,
            "peak_vram_mib": max((row.get("peak_vram_mib") or 0.0) for row in rows) if rows else 0.0,
        },
        "tasks": rows,
    }


def _interaction(scores: dict[str, float]) -> float:
    return scores["specialized_advanced"] - scores["specialized_baseline"] - scores["generic_advanced"] + scores["generic_baseline"]


def run_checkpoint_factorial(
    tasks: tuple[Any, ...],
    *,
    generic_model_id: str,
    generic_revision: str,
    specialized_model_id: str,
    specialized_revision: str,
    max_new_tokens: int,
    task_spec_path: str | None = None,
    task_spec_digest: str | None = None,
    runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    models = {
        "generic": CheckpointPolicy(generic_model_id, generic_revision, max_new_tokens=max_new_tokens),
        "specialized": CheckpointPolicy(specialized_model_id, specialized_revision, max_new_tokens=max_new_tokens),
    }
    harnesses = {"baseline": BaselineHarness(), "advanced": AdvancedHarness()}
    cells: dict[str, Any] = {}
    for model_name, model in models.items():
        for harness_name, harness in harnesses.items():
            cells[f"{model_name}_{harness_name}"] = _run_cell(tasks, model, harness)
    scores = {name: cell["metrics"]["verified_task_success"] for name, cell in cells.items()}
    return {
        "schema": "checkpoint-model-harness-factorial/v0",
        "task_spec": "action-task-spec/v0",
        "task_spec_path": task_spec_path,
        "task_spec_sha256": task_spec_digest,
        "task_count": len(tasks),
        "runtime": runtime or {},
        "generation": {"do_sample": False, "max_new_tokens": max_new_tokens, "seed": 0},
        "models": {
            "generic": {"model_id": generic_model_id, "revision": generic_revision, "load_ms": models["generic"].load_ms},
            "specialized": {"model_id": specialized_model_id, "revision": specialized_revision, "load_ms": models["specialized"].load_ms},
        },
        "cells": cells,
        "interaction": {
            "definition": "specialized_advanced - specialized_baseline - generic_advanced + generic_baseline",
            "verified_task_success": _interaction(scores),
            "cell_scores": scores,
        },
        "limitations": [
            "The task specification is a small smoke suite, not a deployment benchmark.",
            "The specialized checkpoint may be trained on synthetic fixture data and must not be treated as independent evidence.",
            "The advanced harness currently changes context and performs safe-abstain recovery; it does not yet add a larger external adapter surface.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-spec", required=True)
    parser.add_argument("--generic-model-id", required=True)
    parser.add_argument("--generic-revision", required=True)
    parser.add_argument("--specialized-model-id", required=True)
    parser.add_argument("--specialized-revision", default="main")
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    task_spec_digest = hashlib.sha256(Path(args.task_spec).read_bytes()).hexdigest()
    runtime: dict[str, Any] = {"python": sys.version.split()[0]}
    try:
        import torch
        import transformers

        runtime.update({"torch": torch.__version__, "transformers": transformers.__version__, "cuda": torch.version.cuda, "cuda_available": bool(torch.cuda.is_available())})
        if torch.cuda.is_available():
            runtime.update({"device": torch.cuda.get_device_name(0), "compute_capability": list(torch.cuda.get_device_capability(0)), "bf16_supported": bool(torch.cuda.is_bf16_supported())})
    except ImportError:
        runtime["optional_backend"] = "unavailable"
    result = run_checkpoint_factorial(
        load_tasks(args.task_spec),
        generic_model_id=args.generic_model_id,
        generic_revision=args.generic_revision,
        specialized_model_id=args.specialized_model_id,
        specialized_revision=args.specialized_revision,
        max_new_tokens=args.max_new_tokens,
        task_spec_path=args.task_spec,
        task_spec_digest=task_spec_digest,
        runtime=runtime,
    )
    serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
