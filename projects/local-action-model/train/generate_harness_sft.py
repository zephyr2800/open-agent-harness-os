"""Generate Action IR supervision from a versioned harness task specification.

The output is explicitly synthetic reference-policy data. It is useful for
teaching the model the Project 2 act/verify/finish contract, but must not be
presented as independent generalization evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load(path: str | Path) -> list[dict[str, Any]]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("schema") != "harness-task-spec/v0":
        raise ValueError("expected harness-task-spec/v0")
    return list(document["tasks"])


def _state(*, tools: list[str], step: int, executed: list[str] | None = None, verified: list[str] | None = None, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "facts": [],
        "assumptions": [],
        "open_questions": [],
        "resolved_questions": [],
        "executed_actions": list(executed or []),
        "verified_outcomes": list(verified or []),
        "artifacts": [],
        "authority": "sandbox",
        "harness_step": step,
        "harness_variant": "H3",
        "verified_evidence": list(verified or []),
        "evidence_records": list(evidence or []),
        "available_actions": list(dict.fromkeys([*tools, "observe", "abstain", "finish"])),
    }


def _decision(task_id: str, step: int, kind: str, *, state: dict[str, Any], action: dict[str, Any] | None = None, reason: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "action-ir/v0",
        "task_id": task_id,
        "step_id": f"step-{step}",
        "kind": kind,
        "uncertainty": {"confidence": 0.98 if kind != "abstain" else 0.95, "basis": "synthetic harness reference policy"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
    }
    if kind == "act":
        result["action"] = action
    elif kind == "abstain":
        result["abstention"] = {"reason": reason or "approved capability or authorization is unavailable", "alternatives": ["ask the user for clarification or an approved capability"]}
    else:
        result["finish"] = {"result": "The independently verified artifact is complete.", "evidence": list(state["verified_evidence"]), "verified": True}
    return result


def _action(task: dict[str, Any], *, attempt: int = 1) -> dict[str, Any] | None:
    tool = task.get("expected_tool")
    arguments = task.get("expected_arguments")
    actions = task.get("expected_actions") or []
    if actions:
        action = actions[0]
        return {"intent": action["tool"], "arguments": dict(action["arguments"]), "preconditions": [], "risk": "low", "expected_effect": "tool output is independently verified", "escalate_if": ["permission_denied"]}
    if not tool:
        return None
    if tool == "retry_operation" and not arguments:
        arguments = {"operation": "export", "attempt": attempt}
    return {"intent": tool, "arguments": dict(arguments or {}), "preconditions": [], "risk": "high" if tool == "delete_file" else ("medium" if tool in {"move_file", "move_entry"} else "low"), "expected_effect": "tool output is independently verified", "escalate_if": ["permission_denied"]}


def build_rows(tasks: list[dict[str, Any]], repeat: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in tasks:
        if task.get("split") != "held_in" and task.get("split") != "held_out":
            continue
        task_id = task["task_id"]
        tools = list(task.get("available_tools", []))
        model_tools = list(dict.fromkeys([*tools, "abstain", "finish"]))
        variants = [task["prompt"]] + [f"In a bounded, verifier-backed workspace: {task['prompt']}" for _ in range(max(0, repeat - 1))]
        for prompt in variants:
            base_input = {
                "task_id": task_id,
                "goal": prompt,
                "state": _state(tools=model_tools, step=0),
                "available_tools": model_tools,
                "token_budget": task.get("output_token_budget", 1800),
            }
            if task.get("expected_kind") == "abstain":
                target = _decision(task_id, 0, "abstain", state=base_input["state"], reason="the requested operation is unavailable or requires explicit authorization")
                rows.append({"schema": "action-sft/v0", "task_id": task_id, "input": base_input, "target": target, "provenance": {"source": "harness_reference_policy", "synthetic": True, "task_spec": "harness-task-spec/v0"}})
                continue
            first = _action(task)
            if first is None:
                continue
            rows.append({"schema": "action-sft/v0", "task_id": task_id, "input": base_input, "target": _decision(task_id, 0, "act", state=base_input["state"], action=first), "provenance": {"source": "harness_reference_policy", "synthetic": True, "task_spec": "harness-task-spec/v0"}})
            executed = [first["intent"]]
            evidence_id = "sha256:" + hashlib.sha256((task_id + ":step-0").encode()).hexdigest()
            evidence = [{"evidence_id": evidence_id, "status": "verified", "claim": f"{first['intent']} execution completed"}]
            if task.get("expected_actions") and len(task["expected_actions"]) > 1:
                second = dict(task["expected_actions"][1])
                second_action = {"intent": second["tool"], "arguments": dict(second["arguments"]), "preconditions": [], "risk": "medium" if second["tool"] == "move_entry" else "low", "expected_effect": "tool output is independently verified", "escalate_if": ["permission_denied"]}
                state = _state(tools=model_tools, step=1, executed=executed, verified=[evidence_id], evidence=evidence)
                rows.append({"schema": "action-sft/v0", "task_id": task_id, "input": {**base_input, "state": state}, "target": _decision(task_id, 1, "act", state=state, action=second_action), "provenance": {"source": "harness_reference_policy", "synthetic": True, "task_spec": "harness-task-spec/v0"}})
                executed.append(second_action["intent"])
                evidence_id = "sha256:" + hashlib.sha256((task_id + ":step-1").encode()).hexdigest()
                evidence.append({"evidence_id": evidence_id, "status": "verified", "claim": f"{second_action['intent']} execution completed"})
            elif task_id == "recover-operation":
                state = _state(tools=model_tools, step=1, executed=executed, evidence=evidence)
                retry = _action(task, attempt=2)
                rows.append({"schema": "action-sft/v0", "task_id": task_id, "input": {**base_input, "state": state}, "target": _decision(task_id, 1, "act", state=state, action=retry), "provenance": {"source": "harness_reference_policy", "synthetic": True, "task_spec": "harness-task-spec/v0"}})
                executed.append("retry_operation")
                evidence_id = "sha256:" + hashlib.sha256((task_id + ":step-1").encode()).hexdigest()
                evidence = [{"evidence_id": evidence_id, "status": "verified", "claim": "retry_operation execution completed"}]
            finish_state = _state(tools=model_tools, step=2, executed=executed, verified=[evidence_id], evidence=evidence)
            rows.append({"schema": "action-sft/v0", "task_id": task_id, "input": {**base_input, "state": finish_state}, "target": _decision(task_id, 2, "finish", state=finish_state), "provenance": {"source": "harness_reference_policy", "synthetic": True, "task_spec": "harness-task-spec/v0"}})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-spec", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repeat", type=int, default=8)
    args = parser.parse_args()
    rows = build_rows(_load(args.task_spec), args.repeat)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"schema": "action-sft/v0", "examples": len(rows), "output": str(output), "synthetic": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
