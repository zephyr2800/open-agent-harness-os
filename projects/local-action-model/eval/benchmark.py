"""A small deterministic benchmark for protocol and action-selection regressions.

This is a harness-level smoke benchmark, not a claim of model capability. It
keeps the task definitions fixed while allowing different policies to be
compared against the same evaluator.
"""

from __future__ import annotations

import json
import math
import argparse
import copy
from dataclasses import dataclass
from typing import Any, Callable

from action_ir.codec import canonical_json
from action_ir.validation import validate_decision


@dataclass(frozen=True)
class Task:
    task_id: str
    prompt: str
    expected_kind: str
    expected_intent: str | None = None
    expected_arguments: dict[str, Any] | None = None
    required_reason_fragment: str | None = None
    split: str = "smoke"
    available_tools: tuple[str, ...] = ()
    output_token_budget: int = 256
    verified_evidence: tuple[str, ...] = ()


TASKS = (
    Task(
        task_id="write_note",
        prompt="Create notes/today.md containing exactly: checkpoint complete",
        expected_kind="act",
        expected_intent="write_file",
        expected_arguments={"path": "notes/today.md", "content": "checkpoint complete"},
        split="held_in",
        available_tools=("write_file", "abstain"),
        output_token_budget=160,
    ),
    Task(
        task_id="inspect_status",
        prompt="Read STATUS.md so the next step can be selected from current evidence.",
        expected_kind="act",
        expected_intent="read_file",
        expected_arguments={"path": "STATUS.md"},
        split="held_in",
        available_tools=("read_file", "abstain"),
        output_token_budget=128,
    ),
    Task(
        task_id="unknown_tool",
        prompt="Send an SMS using a tool that is not present in the available tool list.",
        expected_kind="abstain",
        required_reason_fragment="tool",
        split="held_out",
        available_tools=("read_file", "write_file", "abstain"),
        output_token_budget=128,
    ),
    Task(
        task_id="verify_finish",
        prompt="Report completion only after the independent verifier confirms the artifact.",
        expected_kind="finish",
        split="held_out",
        available_tools=("finish", "abstain"),
        output_token_budget=128,
    ),
)


def reference_policy(task: Task) -> dict[str, Any]:
    base = {
        "schema": "action-ir/v0",
        "task_id": task.task_id,
        "step_id": "step-0",
        "uncertainty": {"confidence": 0.98, "basis": "deterministic benchmark fixture"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
    }
    if task.expected_kind == "act":
        base.update(
            kind="act",
            action={
                "intent": task.expected_intent,
                "arguments": copy.deepcopy(task.expected_arguments),
                "preconditions": [],
                "risk": "medium" if task.expected_intent == "move_file" else "low",
                "expected_effect": "requested_observation_or_artifact",
                "escalate_if": ["permission_denied"],
            },
        )
    elif task.expected_kind == "abstain":
        fragment = task.required_reason_fragment or "tool"
        base.update(kind="abstain", abstention={"reason": f"request is {fragment}; approved capability is unavailable", "alternatives": ["ask the user for clarification or an approved capability"]})
    else:
        base.update(kind="finish", finish={"result": "The verifier confirmed completion.", "evidence": ["check:fixture_verifier_ok"], "verified": True})
    return base


def score_decision(task: Task, decision: Any) -> tuple[bool, list[str]]:
    issues = validate_decision(decision)
    if issues:
        return False, ["invalid_decision"]
    if decision.get("task_id") != task.task_id:
        return False, ["wrong_task_id"]
    if decision.get("kind") != task.expected_kind:
        return False, ["wrong_decision_kind"]
    if task.expected_kind == "act":
        action = decision["action"]
        if action.get("intent") not in task.available_tools:
            return False, ["intent_not_in_available_tools"]
        if action.get("intent") != task.expected_intent:
            return False, ["wrong_intent"]
        if action.get("arguments") != task.expected_arguments:
            return False, ["wrong_arguments"]
    elif task.expected_kind == "abstain":
        reason = decision["abstention"]["reason"].lower()
        if task.required_reason_fragment and task.required_reason_fragment not in reason:
            return False, ["abstention_reason_not_informative"]
    return True, []


def estimate_output_tokens(decision: Any) -> int:
    """Use a stable proxy until a tokenizer-backed model is under test."""

    return max(1, math.ceil(len(canonical_json(decision).encode("utf-8")) / 4))


def structured_field_count(decision: Any) -> int:
    """Count non-empty protocol structures as a transparent density proxy."""

    count = sum(field in decision for field in ("task_id", "step_id", "kind", "uncertainty", "state_update"))
    kind = decision.get("kind")
    if kind == "act":
        count += sum(field in decision.get("action", {}) for field in ("intent", "arguments", "preconditions", "risk", "expected_effect", "escalate_if"))
    elif kind == "abstain":
        count += sum(field in decision.get("abstention", {}) for field in ("reason", "alternatives"))
    elif kind == "finish":
        count += sum(field in decision.get("finish", {}) for field in ("result", "evidence", "verified"))
    return count


def evaluate(policy: Callable[[Task], dict[str, Any]], tasks: tuple[Task, ...] = TASKS) -> dict[str, Any]:
    rows = []
    for task in tasks:
        decision = policy(task)
        valid = not validate_decision(decision)
        success, errors = score_decision(task, decision)
        output_tokens = estimate_output_tokens(decision)
        rows.append(
            {
                "task_id": task.task_id,
                "split": task.split,
                "available_tools": list(task.available_tools),
                "valid": valid,
                "success": success,
                "errors": errors,
                "estimated_output_tokens": output_tokens,
                "useful_state_transitions": int(success),
                "successful_actions": int(success and decision.get("kind") == "act"),
                "structured_fields": structured_field_count(decision),
            }
        )
    total = len(rows)
    success_count = sum(row["success"] for row in rows)
    valid_count = sum(row["valid"] for row in rows)
    estimated_tokens = sum(row["estimated_output_tokens"] for row in rows)
    useful_transitions = sum(row["useful_state_transitions"] for row in rows)
    successful_actions = sum(row["successful_actions"] for row in rows)
    structured_fields = sum(row["structured_fields"] for row in rows)
    abstention_tasks = [row for row, task in zip(rows, tasks) if task.expected_kind == "abstain"]
    correct_abstentions = sum(row["success"] for row in abstention_tasks)
    return {
        "tasks": rows,
        "metrics": {
            "task_count": total,
            "verified_task_success": success_count / total if total else 0.0,
            "valid_decision_rate": valid_count / total if total else 0.0,
            "invalid_action_rate": 1 - valid_count / total if total else 0.0,
            "correct_abstention_rate": correct_abstentions / len(abstention_tasks) if abstention_tasks else 0.0,
            "estimated_output_tokens": estimated_tokens,
            "useful_state_transitions_per_token": useful_transitions / estimated_tokens if estimated_tokens else 0.0,
            "successful_actions_per_token": successful_actions / estimated_tokens if estimated_tokens else 0.0,
            "verified_progress_per_token": success_count / estimated_tokens if estimated_tokens else 0.0,
            "structured_information_density": structured_fields / estimated_tokens if estimated_tokens else 0.0,
        },
    }


def run_reference_benchmark() -> dict[str, Any]:
    return evaluate(reference_policy)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-spec", help="versioned JSON task spec; defaults to the four-task smoke fixture")
    parser.add_argument("--split", choices=("held_in", "held_out", "smoke"), help="evaluate only one declared split")
    args = parser.parse_args()
    tasks = TASKS
    if args.task_spec:
        from eval.task_spec import load_tasks

        tasks = load_tasks(args.task_spec)
    if args.split:
        tasks = tuple(task for task in tasks if task.split == args.split)
    print(json.dumps(evaluate(reference_policy, tasks=tasks), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
