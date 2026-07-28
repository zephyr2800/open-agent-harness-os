"""Verifier-backed reward shaping for environment-grounded RL experiments."""

from __future__ import annotations

from typing import Any

from eval.verified import verify_decision


def reward_decision(task: Any, decision: Any) -> dict[str, Any]:
    """Return a decomposed, bounded reward for one model decision.

    The verifier outcome remains authoritative. Reward shaping is deliberately
    small and transparent so an RL trainer cannot turn an unverified effect or
    unsafe call into a positive score through a proxy.
    """

    outcome = verify_decision(task, decision)
    if not outcome.protocol_valid:
        reward = -1.0
        reason = "invalid_protocol"
    elif outcome.success:
        reward = 1.0
        reason = "verified_task_success"
    elif not outcome.action_executed and "wrong_decision_kind" in outcome.errors:
        reward = -0.5
        reason = "wrong_decision_kind"
    elif not outcome.independently_verified:
        reward = -0.75
        reason = "independent_verification_failed"
    else:
        reward = -0.25
        reason = "task_not_completed"
    return {
        "task_id": task.task_id,
        "reward": reward,
        "reason": reason,
        "protocol_valid": outcome.protocol_valid,
        "action_executed": outcome.action_executed,
        "independently_verified": outcome.independently_verified,
        "success": outcome.success,
        "errors": list(outcome.errors),
        "evidence": list(outcome.evidence),
    }
