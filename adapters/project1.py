"""Adapter for any Project 1-compatible Action IR policy."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from protocol.ir import require_valid_decision
from .base import ModelRequest


class Project1ActionIRAdapter:
    """Wrap a callable policy and enforce the public Action IR v0 boundary."""

    def __init__(self, policy: Callable[[Mapping[str, Any]], Mapping[str, Any]]) -> None:
        self.policy = policy
        self.requests: list[ModelRequest] = []

    def decide(self, request: ModelRequest) -> Mapping[str, Any]:
        self.requests.append(request)
        decision = self.policy(
            {
                "task_id": request.task_id,
                "prompt": request.prompt,
                "context": request.context,
                "state": dict(request.state),
                "available_actions": list(request.available_actions),
                "evidence": [dict(item) for item in request.evidence],
                "authority": request.authority,
                "budget": dict(request.budget),
            }
        )
        return require_valid_decision(decision)
