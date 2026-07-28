"""Provider-neutral model boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class ModelRequest:
    task_id: str
    prompt: str
    context: str
    state: Mapping[str, Any]
    available_actions: tuple[str, ...]
    evidence: tuple[Mapping[str, Any], ...]
    authority: str
    budget: Mapping[str, int]
    variant: str
    step: int
    available_tools: tuple[str, ...] = ()


class ModelAdapter(Protocol):
    def decide(self, request: ModelRequest) -> Mapping[str, Any]: ...


class ScriptedModel:
    """Deterministic model for protocol, ablation, and replay tests."""

    def __init__(self, decisions: list[Mapping[str, Any]], *, repeat_last: bool = False) -> None:
        self.decisions = [dict(item) for item in decisions]
        self.repeat_last = repeat_last
        self.requests: list[ModelRequest] = []

    def decide(self, request: ModelRequest) -> Mapping[str, Any]:
        self.requests.append(request)
        if self.decisions:
            return self.decisions.pop(0)
        if self.repeat_last and self.requests:
            return self.requests[-1].state.get("last_decision", {"kind": "abstain"})
        return {"schema": "action-ir/v0", "task_id": request.task_id, "step_id": f"step-{request.step}", "kind": "abstain", "uncertainty": {"confidence": 0.0, "basis": "script exhausted"}, "state_update": {"facts": [], "assumptions": [], "open_questions": ["script exhausted"], "resolved_questions": []}, "abstention": {"reason": "script exhausted", "alternatives": ["request a new model decision"]}}
