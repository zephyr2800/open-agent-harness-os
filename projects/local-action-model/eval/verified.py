"""Execute benchmark decisions in deterministic environments and verify effects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from action_ir.validation import validate_decision
from eval.benchmark import Task, reference_policy, score_decision
from runtime.executor import ExecutionDenied
from runtime.memory_tools import ToolExecutionError, make_memory_registry


@dataclass(frozen=True)
class VerifiedOutcome:
    task_id: str
    protocol_valid: bool
    action_executed: bool
    independently_verified: bool
    success: bool
    errors: tuple[str, ...]
    evidence: tuple[str, ...] = ()


def _initial_files(task: Task) -> dict[str, str]:
    arguments = task.expected_arguments if isinstance(task.expected_arguments, dict) else {}
    if task.expected_intent == "read_file" and isinstance(arguments.get("path"), str):
        return {arguments["path"]: "checkpoint: verified\n"}
    if task.expected_intent == "move_file" and isinstance(arguments.get("source"), str):
        return {arguments["source"]: "verified report\n"}
    if task.task_id == "inspect_status":
        return {"STATUS.md": "checkpoint: verified\n"}
    if task.task_id == "archive_report":
        return {"reports/final.md": "verified report\n"}
    return {}


def verify_decision(task: Task, decision: Any) -> VerifiedOutcome:
    issues = validate_decision(decision)
    if issues:
        return VerifiedOutcome(task.task_id, False, False, False, False, tuple(issues))
    expected_success, expected_errors = score_decision(task, decision)
    if decision.get("kind") != task.expected_kind:
        return VerifiedOutcome(
            task.task_id,
            True,
            False,
            False,
            False,
            tuple(expected_errors or ["wrong_decision_kind"]),
        )
    if task.expected_kind == "abstain":
        return VerifiedOutcome(task.task_id, True, False, True, expected_success, tuple(expected_errors), ("decision:abstain",))
    if task.expected_kind == "finish":
        finish = decision["finish"]
        evidence = tuple(finish["evidence"])
        if task.verified_evidence:
            # RL and other trajectory fixtures may bind completion only to
            # verifier-issued receipts declared by the task environment.
            independent = finish["verified"] is True and set(task.verified_evidence).issubset(evidence)
        else:
            # Preserve the original smoke-fixture contract for legacy tasks.
            independent = finish["verified"] is True and any(item.startswith("check:") for item in evidence)
        errors = [] if independent and expected_success else ["independent_finish_verification_failed", *expected_errors]
        return VerifiedOutcome(task.task_id, True, False, independent, not errors, tuple(dict.fromkeys(errors)), evidence)

    _, registry = make_memory_registry(_initial_files(task))
    try:
        result = registry.execute(decision)
    except (ExecutionDenied, ToolExecutionError) as exc:
        return VerifiedOutcome(task.task_id, True, False, False, False, (type(exc).__name__, str(exc)))
    errors = [] if expected_success and result.verified else [*expected_errors]
    if not result.verified:
        errors.append("tool_verifier_failed")
    return VerifiedOutcome(task.task_id, True, True, result.verified, not errors, tuple(dict.fromkeys(errors)), (f"tool:{result.tool}", "verifier:passed" if result.verified else "verifier:failed"))


def evaluate_verified(policy: Callable[[Task], dict[str, Any]], tasks: tuple[Task, ...]) -> dict[str, Any]:
    outcomes = [verify_decision(task, policy(task)) for task in tasks]
    total = len(outcomes)
    return {
        "metrics": {
            "task_count": total,
            "verified_task_success": sum(outcome.success for outcome in outcomes) / total if total else 0.0,
            "protocol_valid_rate": sum(outcome.protocol_valid for outcome in outcomes) / total if total else 0.0,
            "action_execution_rate": sum(outcome.action_executed for outcome in outcomes) / total if total else 0.0,
            "independent_verification_rate": sum(outcome.independently_verified for outcome in outcomes) / total if total else 0.0,
        },
        "tasks": [
            {
                "task_id": outcome.task_id,
                "protocol_valid": outcome.protocol_valid,
                "action_executed": outcome.action_executed,
                "independently_verified": outcome.independently_verified,
                "success": outcome.success,
                "errors": list(outcome.errors),
                "evidence": list(outcome.evidence),
            }
            for outcome in outcomes
        ],
    }
