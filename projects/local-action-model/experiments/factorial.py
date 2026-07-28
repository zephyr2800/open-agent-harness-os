"""Run the model × harness factorial with a fixed task definition.

The runner owns the experimental bookkeeping, not a claim about model quality.
Real model adapters and real harnesses can be injected through the same
interfaces. The bundled fixture models exist only to prove that all four cells
execute, that failures are recorded, and that the interaction term is computed
from cell-level measurements rather than assumed.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from action_ir.validation import validate_decision
from eval.benchmark import (
    TASKS,
    Task,
    estimate_output_tokens,
    reference_policy,
    score_decision,
    structured_field_count,
)
from model.adapter import ModelOutputError, ModelRequest, parse_decision


class ModelPolicy(Protocol):
    def decide(self, request: ModelRequest) -> dict[str, Any]: ...


@dataclass(frozen=True)
class HarnessResult:
    decision: dict[str, Any] | None
    error: str | None = None
    recovery: str | None = None


class Harness(Protocol):
    name: str

    def run(self, task: Task, model: ModelPolicy) -> HarnessResult: ...


def _request(task: Task, *, context_mode: str) -> ModelRequest:
    state = {
        "facts": [],
        "assumptions": [],
        "open_questions": [],
        "resolved_questions": [],
    }
    # Keep the baseline prompt byte-shape aligned with the SFT data. The
    # advanced harness adds context only when it actually has retrieved state.
    if context_mode != "transcript_only":
        state["context_mode"] = context_mode
        state["task_split"] = task.split
    return ModelRequest(
        task_id=task.task_id,
        goal=task.prompt,
        state=state,
        available_tools=task.available_tools,
        token_budget=task.output_token_budget,
    )


class BaselineHarness:
    name = "baseline"

    def run(self, task: Task, model: ModelPolicy) -> HarnessResult:
        try:
            return HarnessResult(model.decide(_request(task, context_mode="transcript_only")))
        except ModelOutputError as exc:
            return HarnessResult(None, error=str(exc))


def _safe_abstention(task: Task, reason: str) -> dict[str, Any]:
    return {
        "schema": "action-ir/v0",
        "task_id": task.task_id,
        "step_id": "harness-recovery-0",
        "kind": "abstain",
        "abstention": {"reason": reason, "alternatives": ["request clarification or retry with an approved output"]},
        "uncertainty": {"confidence": 0.99, "basis": "harness protocol recovery"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": ["valid model decision"], "resolved_questions": []},
        "recovery": {"strategy": "escalate", "reason": "model output failed protocol validation"},
    }


class AdvancedHarness:
    name = "advanced"

    def run(self, task: Task, model: ModelPolicy) -> HarnessResult:
        try:
            decision = model.decide(_request(task, context_mode="retrieved_tools_state_verifier"))
            return HarnessResult(decision)
        except ModelOutputError as exc:
            # This is the safe recovery path: a malformed response cannot be
            # executed, but the trajectory remains scoreable and auditable.
            prompt = task.prompt.lower()
            if "permission" in prompt:
                reason = "permission boundary is not granted; no action executed"
            elif "ambiguous" in prompt or ("team" in prompt and "channel" in prompt):
                reason = "ambiguous destination; clarification is required"
            elif "tool" in prompt or "sms" in prompt:
                reason = "requested tool is unavailable; no action executed"
            else:
                reason = f"model output invalid; {exc}"
            return HarnessResult(_safe_abstention(task, reason), recovery="safe_abstain")


class FixtureModel:
    """Deterministic plumbing fixture; not a trained model or research result."""

    def __init__(self, variant: str, tasks: tuple[Task, ...]):
        if variant not in {"generic", "specialized"}:
            raise ValueError("fixture model variant must be generic or specialized")
        self.variant = variant
        self.tasks = {task.task_id: task for task in tasks}

    def decide(self, request: ModelRequest) -> dict[str, Any]:
        task = self.tasks[request.task_id]
        if self.variant == "specialized":
            candidate = reference_policy(task)
        else:
            candidate = _generic_fixture_decision(task)
        return parse_decision(json.dumps(candidate), request)


def _generic_fixture_decision(task: Task) -> dict[str, Any]:
    """Make known, documented mistakes to exercise cell bookkeeping."""

    if task.task_id in {"write_note", "inspect_status"}:
        return reference_policy(task)
    if task.expected_kind == "act":
        candidate = reference_policy(task)
        candidate["action"]["arguments"] = dict(candidate["action"]["arguments"] or {})
        candidate["action"]["arguments"]["fixture_error"] = True
        return candidate
    if task.task_id == "verify_finish":
        candidate = reference_policy(task)
        candidate["finish"]["verified"] = False
        return candidate
    if task.task_id == "unknown_tool":
        candidate = reference_policy(task)
        candidate["kind"] = "act"
        candidate.pop("abstention", None)
        candidate["action"] = {
            "intent": "send_sms",
            "arguments": {"number": "unknown", "message": "hello"},
            "preconditions": [],
            "risk": "medium",
            "expected_effect": "sms_sent",
            "escalate_if": ["permission_denied"],
        }
        return candidate
    # Generic policies over-act on ambiguous or unauthorized requests.
    candidate = reference_policy(task)
    candidate["kind"] = "act"
    candidate.pop("abstention", None)
    candidate["action"] = {
        "intent": task.available_tools[0],
        "arguments": {},
        "preconditions": [],
        "risk": "medium",
        "expected_effect": "requested_effect",
        "escalate_if": ["permission_denied", "ambiguity"],
    }
    return candidate


def _score_cell(tasks: tuple[Task, ...], model: ModelPolicy, harness: Harness) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for task in tasks:
        result = harness.run(task, model)
        if result.decision is None:
            rows.append(
                {
                    "task_id": task.task_id,
                    "split": task.split,
                    "valid": False,
                    "success": False,
                    "errors": ["model_output_error"],
                    "detail": result.error,
                    "recovery": result.recovery,
                }
            )
            continue
        decision = result.decision
        issues = validate_decision(decision)
        success, errors = score_decision(task, decision)
        rows.append(
            {
                "task_id": task.task_id,
                "split": task.split,
                "valid": not issues,
                "success": success,
                "errors": issues or errors,
                "recovery": result.recovery,
                "estimated_output_tokens": estimate_output_tokens(decision),
                "structured_fields": structured_field_count(decision),
            }
        )
    total = len(rows)
    success_count = sum(row["success"] for row in rows)
    valid_count = sum(row["valid"] for row in rows)
    tokens = sum(row.get("estimated_output_tokens", 0) for row in rows)
    return {
        "metrics": {
            "task_count": total,
            "verified_task_success": success_count / total if total else 0.0,
            "valid_decision_rate": valid_count / total if total else 0.0,
            "invalid_action_rate": 1 - valid_count / total if total else 0.0,
            "estimated_output_tokens": tokens,
            "verified_progress_per_token": success_count / tokens if tokens else 0.0,
        },
        "tasks": rows,
    }


def interaction_term(cell_scores: Mapping[str, float]) -> float:
    """Compute D - B - C + A for A=GB, B=SB, C=GA, D=SA."""

    required = {"generic_baseline", "specialized_baseline", "generic_advanced", "specialized_advanced"}
    missing = required - cell_scores.keys()
    if missing:
        raise ValueError(f"missing factorial cells: {sorted(missing)}")
    return cell_scores["specialized_advanced"] - cell_scores["specialized_baseline"] - cell_scores["generic_advanced"] + cell_scores["generic_baseline"]


def run_factorial(tasks: tuple[Task, ...] = TASKS, *, models: Mapping[str, ModelPolicy] | None = None, harnesses: Mapping[str, Harness] | None = None) -> dict[str, Any]:
    models = models or {variant: FixtureModel(variant, tasks) for variant in ("generic", "specialized")}
    harnesses = harnesses or {"baseline": BaselineHarness(), "advanced": AdvancedHarness()}
    cells: dict[str, Any] = {}
    for model_name, model in models.items():
        for harness_name, harness in harnesses.items():
            cell_name = f"{model_name}_{harness_name}"
            cells[cell_name] = _score_cell(tasks, model, harness)
    scores = {name: result["metrics"]["verified_task_success"] for name, result in cells.items()}
    return {
        "schema": "model-harness-factorial/v0",
        "task_count": len(tasks),
        "cells": cells,
        "interaction": {
            "definition": "specialized_advanced - specialized_baseline - generic_advanced + generic_baseline",
            "verified_task_success": interaction_term(scores),
            "cell_scores": scores,
            "interpretation": "fixture wiring only; not evidence about trained models",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-spec", required=True)
    args = parser.parse_args()
    from eval.task_spec import load_tasks

    result = run_factorial(load_tasks(args.task_spec))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
