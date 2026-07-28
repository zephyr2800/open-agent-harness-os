"""Safe local service wrapper around the harness runtime."""

from __future__ import annotations

from typing import Any, Mapping

from adapters.base import ModelRequest
from runtime.orchestrator import Harness, HarnessConfig, TaskRequest
from tools.memory_workspace import make_memory_registry
from .storage import TraceStore


def _decision(task_id: str, step: int, kind: str, *, intent: str | None = None, arguments: Mapping[str, Any] | None = None, evidence: list[str] | None = None, risk: str = "low", reason: str = "local service policy") -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": "action-ir/v0",
        "task_id": task_id,
        "step_id": f"step-{step}",
        "kind": kind,
        "uncertainty": {"confidence": 0.99 if kind in {"act", "finish"} else 0.8, "basis": reason},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
    }
    if kind == "act":
        value["action"] = {"intent": intent, "arguments": dict(arguments or {}), "preconditions": [], "risk": risk, "expected_effect": "independent tool verification", "escalate_if": ["tool result is unverified"]}
    elif kind == "finish":
        value["finish"] = {"result": "task completed", "evidence": list(evidence or []), "verified": True}
    else:
        value["abstention"] = {"reason": reason, "alternatives": ["request an explicitly permitted action"]}
    return value


class ActionThenFinishModel:
    """Small product policy used for the offline demo and API smoke path."""

    def __init__(self, tool: str, arguments: Mapping[str, Any], risk: str):
        self.tool = tool
        self.arguments = dict(arguments)
        self.risk = risk
        self.requests: list[ModelRequest] = []

    def decide(self, request: ModelRequest) -> Mapping[str, Any]:
        self.requests.append(request)
        if request.step == 0:
            if self.tool not in request.available_actions:
                return _decision(request.task_id, request.step, "abstain", reason="requested tool is not available")
            return _decision(request.task_id, request.step, "act", intent=self.tool, arguments=self.arguments, risk=self.risk)
        evidence = [str(request.evidence[-1]["evidence_id"])] if request.evidence and request.evidence[-1].get("status") == "verified" else []
        if evidence:
            return _decision(request.task_id, request.step, "finish", evidence=evidence)
        return _decision(request.task_id, request.step, "abstain", reason="action was not independently verified")


def run_action(task_id: str, prompt: str, tool: str, arguments: Mapping[str, Any], *, variant: str = "H1", adapter: Any = None, model_name: str = "local-service-policy", initial_files: Mapping[str, str] | None = None, max_steps: int = 4, timeout_seconds: float = 5.0, token_budget: int = 1800, trace_dir: str | None = None) -> dict[str, Any]:
    if not isinstance(task_id, str) or not task_id or len(task_id) > 256:
        raise ValueError("task_id must be 1–256 characters")
    if not isinstance(prompt, str) or not prompt or len(prompt.encode("utf-8")) > 64_000:
        raise ValueError("prompt must be non-empty and at most 64 KB")
    if not 1 <= max_steps <= 8:
        raise ValueError("max_steps must be between 1 and 8")
    if not 0.1 <= timeout_seconds <= 30.0:
        raise ValueError("timeout_seconds must be between 0.1 and 30")
    if not 64 <= token_budget <= 10_000:
        raise ValueError("token_budget must be between 64 and 10,000")
    if len(str(arguments).encode("utf-8")) > 256_000:
        raise ValueError("arguments exceed 256 KB")
    if initial_files is not None and sum(len(str(key).encode("utf-8")) + len(str(value).encode("utf-8")) for key, value in initial_files.items()) > 1_000_000:
        raise ValueError("initial_files exceed 1 MB")
    workspace, registry = make_memory_registry(initial_files)
    del workspace
    spec = registry.get(tool)
    risk = spec.risk if spec is not None else "low"
    model = adapter or ActionThenFinishModel(tool, arguments, risk)
    harness = Harness(model, registry, config=HarnessConfig(variant=variant, model_name=model_name, max_steps=max_steps, timeout_seconds=timeout_seconds, token_budget=token_budget))
    result = harness.run(TaskRequest(task_id, prompt, (tool,), token_budget, "finish", tool, arguments, "product", (tool,)))
    response = {
        "schema": "harness-run-result/v1",
        "task_id": result.task_id,
        "variant": result.variant,
        "protocol_valid": result.protocol_valid,
        "verified_success": result.verified_success,
        "abstained": result.abstained,
        "steps": result.steps,
        "metrics": dict(result.metrics),
        "error": result.error,
        "trace_jsonl": result.trace_jsonl,
    }
    if trace_dir is not None:
        response["trace_retention"] = TraceStore(trace_dir).save(result.trace_jsonl)
    return response
