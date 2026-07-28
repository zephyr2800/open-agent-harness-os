"""Deterministic model×harness factorial with independent trace evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from adapters.base import ModelRequest
from benchmarks.evaluate import Evaluation, evaluate_tasks
from benchmarks.tasks import Task, load_tasks


def _decision(task_id: str, step: int, kind: str, *, intent: str | None = None, arguments: Mapping[str, Any] | None = None, evidence: list[str] | None = None, reason: str = "deterministic policy", risk: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema": "action-ir/v0",
        "task_id": task_id,
        "step_id": f"step-{step}",
        "kind": kind,
        "uncertainty": {"confidence": 0.95 if kind in {"act", "finish"} else 0.7, "basis": reason},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
    }
    if kind == "act":
        action_risk = "high" if intent == "delete_file" else ("medium" if intent in {"move_file", "move_entry"} else "low")
        value["action"] = {"intent": intent, "arguments": dict(arguments or {}), "preconditions": [], "risk": risk or action_risk, "expected_effect": "tool output is independently verified", "escalate_if": ["tool result is unverified"]}
    elif kind == "finish":
        value["finish"] = {"result": "task completed", "evidence": list(evidence or []), "verified": True}
    elif kind == "abstain":
        value["abstention"] = {"reason": reason, "alternatives": ["request a permitted tool"]}
    return value


class FactorialPolicy:
    def __init__(self, task: Task, model_name: str, variant: str) -> None:
        self.task = task
        self.model_name = model_name
        self.variant = variant

    def decide(self, request: ModelRequest) -> Mapping[str, Any]:
        task_id = self.task.task_id
        if self.model_name == "generic" and self.variant == "H0":
            # Control condition: a generic model emits an unconstrained plan.
            return {"plan": "write the file"}
        if task_id == "unknown-tool":
            if self.model_name == "specialized":
                return _decision(task_id, request.step, "abstain", reason="requested tool is outside the available action surface")
            return _decision(task_id, request.step, "act", intent="network_delete", arguments={}, reason="generic model follows prompt without checking registry")
        if task_id == "permission-sensitive-delete":
            if self.model_name == "specialized":
                return _decision(task_id, request.step, "abstain", reason="high-risk deletion requires explicit user authorization")
            return _decision(task_id, request.step, "act", intent="delete_file", arguments={"path": "temporary.txt"}, risk="high", reason="generic model follows the requested operation")
        if task_id == "recover-operation":
            if request.step == 0:
                return _decision(task_id, request.step, "act", intent="retry_operation", arguments={"operation": "export", "attempt": 1})
            recovery_tuned = self.variant == "H2" or (self.variant in {"H3", "H4"} and self.model_name == "specialized")
            if recovery_tuned and (not request.evidence or request.evidence[-1].get("status") != "verified"):
                return _decision(task_id, request.step, "act", intent="retry_operation", arguments={"operation": "export", "attempt": 2}, reason="use verifier feedback to repair")
            evidence = [str(request.evidence[-1]["evidence_id"])] if request.evidence and request.evidence[-1].get("status") == "verified" else []
            return _decision(task_id, request.step, "finish", evidence=evidence, reason="finish only with evidence")
        if task_id == "long-horizon-archive":
            if request.step == 0:
                first = self.task.expected_actions[0]
                return _decision(task_id, request.step, "act", intent=str(first["tool"]), arguments=first["arguments"])
            if request.step == 1:
                second = self.task.expected_actions[1]
                return _decision(task_id, request.step, "act", intent=str(second["tool"]), arguments=second["arguments"])
            evidence = [str(request.evidence[-1]["evidence_id"])] if request.evidence and request.evidence[-1].get("status") == "verified" else []
            return _decision(task_id, request.step, "finish", evidence=evidence)
        if task_id in {"write-config", "renamed-write", "renamed-write-tool", "artifact-json", "api-health", "browser-status"}:
            if request.step == 0:
                return _decision(task_id, request.step, "act", intent=self.task.expected_tool or "write_file", arguments=self.task.expected_arguments)
            evidence = [str(request.evidence[-1]["evidence_id"])] if request.evidence and request.evidence[-1].get("status") == "verified" else []
            return _decision(task_id, request.step, "finish", evidence=evidence)
        if task_id in {"rename-config", "renamed-move", "renamed-move-tool"}:
            if request.step == 0:
                return _decision(task_id, request.step, "act", intent=self.task.expected_tool or "move_file", arguments=self.task.expected_arguments)
            evidence = [str(request.evidence[-1]["evidence_id"])] if request.evidence and request.evidence[-1].get("status") == "verified" else []
            return _decision(task_id, request.step, "finish", evidence=evidence)
        return _decision(task_id, request.step, "abstain", reason="no policy branch")


def run_factorial(task_path: str | Path) -> dict[str, Any]:
    tasks = load_tasks(task_path)
    cells: dict[str, dict[str, Any]] = {}
    evaluations: dict[tuple[str, str], Evaluation] = {}
    for model_name in ("generic", "specialized"):
        for variant in ("H0", "H1", "H2", "H3", "H4"):
            evaluation = evaluate_tasks(tasks, model_factory=lambda task, current_variant, model_name=model_name: FactorialPolicy(task, model_name, current_variant), variant=variant, model_name=model_name)
            evaluations[(model_name, variant)] = evaluation
            cells[f"{model_name}/{variant}"] = evaluation.as_dict()
    interaction_by_variant: dict[str, float] = {}
    for variant in ("H1", "H2", "H3", "H4"):
        interaction_by_variant[variant] = (
            evaluations[("specialized", variant)].summary()["verified_success_rate"]
            - evaluations[("specialized", "H1")].summary()["verified_success_rate"]
            - evaluations[("generic", variant)].summary()["verified_success_rate"]
            + evaluations[("generic", "H1")].summary()["verified_success_rate"]
        )
    raw = Path(task_path).read_bytes()
    return {"schema": "harness-factorial/v0", "task_spec_sha256": hashlib.sha256(raw).hexdigest(), "cells": cells, "interaction_vs_H1": interaction_by_variant}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-spec", default=str(Path(__file__).parent.parent / "benchmarks" / "fixtures" / "task-spec-v0.json"))
    parser.add_argument("--output", default=str(Path(__file__).parent / "results" / "factorial-v0.json"))
    args = parser.parse_args()
    report = run_factorial(args.task_spec)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "interaction_vs_H1": report["interaction_vs_H1"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
