"""Provider-neutral model-facing contract.

Real backends can implement `generate` around Transformers, llama.cpp, MLX,
ExecuTorch, or a remote reference model. This module owns only request shape,
JSON decoding, and protocol checks so the evaluator remains backend-neutral.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from action_ir.validation import ActionValidationError, require_valid_decision


class ModelOutputError(ValueError):
    """Raised when a backend response cannot become a valid action decision."""


@dataclass(frozen=True)
class ModelRequest:
    task_id: str
    goal: str
    state: Mapping[str, Any]
    available_tools: tuple[str, ...]
    token_budget: int
    required_output: str = "action-ir/v0"


class ActionPolicy(Protocol):
    def decide(self, request: ModelRequest) -> dict[str, Any]: ...


def parse_decision(raw_text: str, request: ModelRequest) -> dict[str, Any]:
    """Parse one JSON response and enforce request/protocol invariants."""

    try:
        decision = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ModelOutputError(f"model output is not valid JSON: {exc.msg}") from exc
    if not isinstance(decision, dict):
        raise ModelOutputError("model output must be a JSON object")
    # Evidence binding is a bookkeeping operation, not a new capability claim:
    # when the harness has already recorded verified evidence, a model may emit
    # an otherwise valid finish with an empty evidence list. Bind only the
    # verifier-issued ids present in the request state; never invent evidence.
    if decision.get("kind") == "finish" and isinstance(decision.get("finish"), dict) and not decision["finish"].get("evidence"):
        verified = request.state.get("verified_evidence") if isinstance(request.state, Mapping) else None
        if isinstance(verified, list) and all(isinstance(item, str) and item for item in verified):
            decision["finish"] = {**decision["finish"], "evidence": list(verified)}
    try:
        require_valid_decision(decision)
    except ActionValidationError as exc:
        raise ModelOutputError(str(exc)) from exc
    if decision["schema"] != request.required_output:
        raise ModelOutputError(f"decision schema does not match request: {request.required_output}")
    if decision["task_id"] != request.task_id:
        raise ModelOutputError("decision task_id does not match request")
    if decision["kind"] == "act" and decision["action"]["intent"] not in request.available_tools:
        raise ModelOutputError("decision intent is not in the available tool surface")
    return decision


class StaticPolicy:
    """Adapter useful for fixtures, smoke tests, and evaluator baselines."""

    def __init__(self, provider: Callable[[ModelRequest], Mapping[str, Any]]):
        self._provider = provider

    def decide(self, request: ModelRequest) -> dict[str, Any]:
        decision = dict(self._provider(request))
        return parse_decision(json.dumps(decision), request)
