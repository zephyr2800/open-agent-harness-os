"""Lazy bridge to Project 1's optional TransformersActionPolicy."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

from protocol.ir import require_valid_decision
from .base import ModelRequest
from .repair import compile_repair


class Project1AdapterError(RuntimeError):
    """A Project 1 backend error with raw output retained for audit."""


class Project1TransformersAdapter:
    """Adapt Project 2 requests to Project 1's model-facing request contract."""

    def __init__(self, project1_root: str | Path, *, policy: Any = None, model_id: str | None = None, revision: str | None = None, goal_source: str = "context", enable_repair: bool = True, **kwargs: Any) -> None:
        self.project1_root = Path(project1_root)
        if goal_source not in {"prompt", "context"}:
            raise ValueError("goal_source must be prompt or context")
        self.goal_source = goal_source
        self.enable_repair = bool(enable_repair)
        if policy is None:
            sys.path.insert(0, str(self.project1_root))
            from model.transformers_backend import TransformersActionPolicy

            parameters = dict(kwargs)
            if model_id is not None:
                parameters["model_id"] = model_id
            if revision is not None:
                parameters["revision"] = revision
            policy = TransformersActionPolicy(**parameters)
        self.policy = policy
        self.requests: list[ModelRequest] = []

    def decide(self, request: ModelRequest) -> Mapping[str, Any]:
        self.requests.append(request)
        sys.path.insert(0, str(self.project1_root))
        from model.adapter import ModelRequest as Project1ModelRequest

        project1_request = Project1ModelRequest(
            task_id=request.task_id,
            goal=request.prompt if self.goal_source == "prompt" else request.context,
            state={
                **dict(request.state),
                "harness_step": request.step,
                "harness_variant": request.variant,
                "verified_evidence": [record.get("evidence_id") for record in request.evidence if record.get("status") == "verified"],
                "evidence_records": [dict(record) for record in request.evidence],
                "available_actions": list(request.available_actions),
            },
            available_tools=tuple(dict.fromkeys((*request.available_tools, "abstain", "finish"))),
            token_budget=int(request.budget.get("tokens", 0)),
        )
        try:
            decision = require_valid_decision(self.policy.decide(project1_request))
            verified_ids = [str(record["evidence_id"]) for record in request.evidence if record.get("status") == "verified" and isinstance(record.get("evidence_id"), str)]
            # Never trust model-supplied evidence ids. Bind only ids emitted by
            # the current verifier, and repair a premature finish/abstention
            # when a conservative next action can be compiled from the request.
            if decision.get("kind") == "finish" and self.enable_repair:
                repaired = compile_repair(request)
                if repaired is not None:
                    return require_valid_decision(repaired)
            if decision.get("kind") == "finish" and verified_ids:
                decision = {**decision, "finish": {**decision["finish"], "evidence": verified_ids, "verified": True}}
                return require_valid_decision(decision)
            if self.enable_repair and decision.get("kind") in {"finish", "abstain"} and not verified_ids:
                repaired = compile_repair(request)
                if repaired is not None and repaired.get("kind") == "act":
                    return require_valid_decision(repaired)
            return decision
        except Exception as exc:
            raw = getattr(self.policy, "last_raw_text", None)
            suffix = f"; raw_output={raw}" if raw is not None else ""
            if self.enable_repair:
                repaired = compile_repair(request)
                if repaired is not None:
                    return require_valid_decision(repaired)
            raise Project1AdapterError(f"Project 1 backend decision failed: {exc}{suffix}") from exc
