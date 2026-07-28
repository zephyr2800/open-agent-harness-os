"""Bounded recovery decisions; no unbounded self-modification."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryAction:
    strategy: str
    reason: str
    next_step: int


class RecoveryManager:
    def __init__(self, *, max_retries: int = 2, max_branches: int = 3) -> None:
        self.max_retries = max_retries
        self.max_branches = max_branches

    def classify(self, *, error: str, attempts: int, verified: bool) -> RecoveryAction:
        if verified:
            return RecoveryAction("stop", "operation already verified", attempts)
        lowered = error.lower()
        if "permission" in lowered or "approval" in lowered:
            return RecoveryAction("escalate", error, attempts)
        if "does not exist" in lowered or "missing" in lowered:
            return RecoveryAction("repair", error, attempts)
        if attempts < self.max_retries:
            return RecoveryAction("retry", error, attempts + 1)
        return RecoveryAction("stop", f"retry budget exhausted: {error}", attempts)
