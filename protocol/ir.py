"""Dependency-free validation for the Project 1 Action IR v0 contract."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

SCHEMA = "action-ir/v0"
DECISION_KINDS = {"act", "observe", "abstain", "finish"}
RISK_LEVELS = {"low", "medium", "high", "critical"}
RECOVERY_STRATEGIES = {"retry", "repair", "substitute", "clarify", "escalate", "stop"}


class ActionValidationError(ValueError):
    def __init__(self, issues: Iterable[str]):
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues))


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _object(value: Any, path: str, issues: list[str]) -> bool:
    if not isinstance(value, Mapping):
        issues.append(f"{path} must be an object")
        return False
    return True


def _strings(value: Any, path: str, issues: list[str]) -> None:
    if not isinstance(value, list) or not all(_nonempty(item) for item in value):
        issues.append(f"{path} must be a list of non-empty strings")


def validate_decision(document: Any) -> list[str]:
    """Return structural Action IR issues; unknown extension fields are allowed."""

    issues: list[str] = []
    if not _object(document, "decision", issues):
        return issues
    if document.get("schema") != SCHEMA:
        issues.append(f"schema must equal {SCHEMA!r}")
    for field in ("task_id", "step_id", "kind"):
        if not _nonempty(document.get(field)):
            issues.append(f"{field} must be a non-empty string")
    kind = document.get("kind")
    if kind not in DECISION_KINDS:
        issues.append(f"kind must be one of {sorted(DECISION_KINDS)}")
    uncertainty = document.get("uncertainty")
    if _object(uncertainty, "uncertainty", issues):
        confidence = uncertainty.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            issues.append("uncertainty.confidence must be a number between 0 and 1")
        if not _nonempty(uncertainty.get("basis")):
            issues.append("uncertainty.basis must be a non-empty string")
    state_update = document.get("state_update")
    if _object(state_update, "state_update", issues):
        for field in ("facts", "assumptions", "open_questions", "resolved_questions"):
            _strings(state_update.get(field), f"state_update.{field}", issues)
    recovery = document.get("recovery")
    if recovery is not None and _object(recovery, "recovery", issues):
        if recovery.get("strategy") not in RECOVERY_STRATEGIES:
            issues.append(f"recovery.strategy must be one of {sorted(RECOVERY_STRATEGIES)}")
        if not _nonempty(recovery.get("reason")):
            issues.append("recovery.reason must be a non-empty string")
    if kind == "act":
        action = document.get("action")
        if _object(action, "action", issues):
            if not _nonempty(action.get("intent")):
                issues.append("action.intent must be a non-empty string")
            if not isinstance(action.get("arguments"), Mapping):
                issues.append("action.arguments must be an object")
            _strings(action.get("preconditions"), "action.preconditions", issues)
            if action.get("risk") not in RISK_LEVELS:
                issues.append(f"action.risk must be one of {sorted(RISK_LEVELS)}")
            if not _nonempty(action.get("expected_effect")):
                issues.append("action.expected_effect must be a non-empty string")
            _strings(action.get("escalate_if"), "action.escalate_if", issues)
        for forbidden in ("observation", "abstention", "finish"):
            if forbidden in document:
                issues.append(f"{forbidden} is not allowed for kind=act")
    elif kind == "observe":
        observation = document.get("observation")
        if _object(observation, "observation", issues):
            if not _nonempty(observation.get("request")):
                issues.append("observation.request must be a non-empty string")
            if not isinstance(observation.get("max_items"), int) or isinstance(observation.get("max_items"), bool) or observation["max_items"] < 1:
                issues.append("observation.max_items must be a positive integer")
        if "action" in document:
            issues.append("action is not allowed for kind=observe")
    elif kind == "abstain":
        abstention = document.get("abstention")
        if _object(abstention, "abstention", issues):
            if not _nonempty(abstention.get("reason")):
                issues.append("abstention.reason must be a non-empty string")
            _strings(abstention.get("alternatives"), "abstention.alternatives", issues)
        if "action" in document:
            issues.append("action is not allowed for kind=abstain")
    elif kind == "finish":
        finish = document.get("finish")
        if _object(finish, "finish", issues):
            if not _nonempty(finish.get("result")):
                issues.append("finish.result must be a non-empty string")
            _strings(finish.get("evidence"), "finish.evidence", issues)
            if finish.get("verified") is not True:
                issues.append("finish.verified must be true")
        if "action" in document:
            issues.append("action is not allowed for kind=finish")
    return issues


def require_valid_decision(document: Any) -> dict[str, Any]:
    issues = validate_decision(document)
    if issues:
        raise ActionValidationError(issues)
    return dict(document)
