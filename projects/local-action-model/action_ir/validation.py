"""Validation for Action IR v0.

The validator is deliberately dependency-free so the protocol can run on a
local Python install, in a mobile client, or behind another language binding.
It checks shape and safety invariants; it does not decide whether an action is
authorized or whether it actually succeeded.
"""

from __future__ import annotations

from typing import Any, Iterable


SCHEMA = "action-ir/v0"
DECISION_KINDS = {"act", "observe", "abstain", "finish"}
RISK_LEVELS = {"low", "medium", "high", "critical"}
RECOVERY_STRATEGIES = {"retry", "repair", "substitute", "clarify", "escalate", "stop"}


class ActionValidationError(ValueError):
    """Raised when a model output cannot be accepted as Action IR v0."""

    def __init__(self, issues: Iterable[str]):
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues))


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_string_list(value: Any, path: str, issues: list[str]) -> None:
    if not isinstance(value, list) or not all(_is_nonempty_string(item) for item in value):
        issues.append(f"{path} must be a list of non-empty strings")


def _check_object(value: Any, path: str, issues: list[str]) -> bool:
    if not isinstance(value, dict):
        issues.append(f"{path} must be an object")
        return False
    return True


def validate_decision(document: Any) -> list[str]:
    """Return all validation issues for an Action IR decision.

    An empty list means the decision is structurally valid. Unknown extension
    fields are allowed so protocol-compatible implementations can add metadata
    without changing the required core contract.
    """

    issues: list[str] = []
    if not _check_object(document, "decision", issues):
        return issues

    if document.get("schema") != SCHEMA:
        issues.append(f"schema must equal {SCHEMA!r}")
    for field in ("task_id", "step_id", "kind"):
        if not _is_nonempty_string(document.get(field)):
            issues.append(f"{field} must be a non-empty string")

    kind = document.get("kind")
    if not isinstance(kind, str) or kind not in DECISION_KINDS:
        issues.append(f"kind must be one of {sorted(DECISION_KINDS)}")

    uncertainty = document.get("uncertainty")
    if _check_object(uncertainty, "uncertainty", issues):
        confidence = uncertainty.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            issues.append("uncertainty.confidence must be a number between 0 and 1")
        if not _is_nonempty_string(uncertainty.get("basis")):
            issues.append("uncertainty.basis must be a non-empty string")

    state_update = document.get("state_update")
    if _check_object(state_update, "state_update", issues):
        for field in ("facts", "assumptions", "open_questions", "resolved_questions"):
            _check_string_list(state_update.get(field), f"state_update.{field}", issues)

    recovery = document.get("recovery")
    if recovery is not None and _check_object(recovery, "recovery", issues):
        strategy = recovery.get("strategy")
        if not isinstance(strategy, str) or strategy not in RECOVERY_STRATEGIES:
            issues.append(f"recovery.strategy must be one of {sorted(RECOVERY_STRATEGIES)}")
        if not _is_nonempty_string(recovery.get("reason")):
            issues.append("recovery.reason must be a non-empty string")

    if kind == "act":
        action = document.get("action")
        if _check_object(action, "action", issues):
            if not _is_nonempty_string(action.get("intent")):
                issues.append("action.intent must be a non-empty string")
            if not isinstance(action.get("arguments"), dict):
                issues.append("action.arguments must be an object")
            _check_string_list(action.get("preconditions"), "action.preconditions", issues)
            risk = action.get("risk")
            if not isinstance(risk, str) or risk not in RISK_LEVELS:
                issues.append(f"action.risk must be one of {sorted(RISK_LEVELS)}")
            if not _is_nonempty_string(action.get("expected_effect")):
                issues.append("action.expected_effect must be a non-empty string")
            _check_string_list(action.get("escalate_if"), "action.escalate_if", issues)
        for forbidden in ("observation", "abstention", "finish"):
            if forbidden in document:
                issues.append(f"{forbidden} is not allowed for kind=act")
    elif kind == "observe":
        observation = document.get("observation")
        if _check_object(observation, "observation", issues):
            if not _is_nonempty_string(observation.get("request")):
                issues.append("observation.request must be a non-empty string")
            max_items = observation.get("max_items")
            if not isinstance(max_items, int) or isinstance(max_items, bool) or max_items < 1:
                issues.append("observation.max_items must be a positive integer")
        if "action" in document:
            issues.append("action is not allowed for kind=observe")
    elif kind == "abstain":
        abstention = document.get("abstention")
        if _check_object(abstention, "abstention", issues):
            if not _is_nonempty_string(abstention.get("reason")):
                issues.append("abstention.reason must be a non-empty string")
            _check_string_list(abstention.get("alternatives"), "abstention.alternatives", issues)
        if "action" in document:
            issues.append("action is not allowed for kind=abstain")
    elif kind == "finish":
        finish = document.get("finish")
        if _check_object(finish, "finish", issues):
            if not _is_nonempty_string(finish.get("result")):
                issues.append("finish.result must be a non-empty string")
            _check_string_list(finish.get("evidence"), "finish.evidence", issues)
            if finish.get("verified") is not True:
                issues.append("finish.verified must be true")
        if "action" in document:
            issues.append("action is not allowed for kind=finish")

    return issues


def require_valid_decision(document: Any) -> dict[str, Any]:
    """Validate and return a decision, raising a useful error on failure."""

    issues = validate_decision(document)
    if issues:
        raise ActionValidationError(issues)
    return document
