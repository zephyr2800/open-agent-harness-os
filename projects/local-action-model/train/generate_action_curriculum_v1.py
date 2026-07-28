"""Generate a larger synthetic Action IR curriculum without using holdout v2.

The curriculum expands parameter and wording diversity over the v1 task
families. It deliberately excludes every path, operation, and endpoint used by
the independent research-v2 holdout. This is training data, not evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PREFIXES = (
    "",
    "In a bounded local workspace, ",
    "Use only the registered tools and wait for independent verification: ",
    "Work conservatively and report completion only after verification: ",
)


def _state(
    tools: list[str],
    step: int,
    *,
    executed: list[str] | None = None,
    verified: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    artifacts: list[str] | None = None,
    expected_tool: str | None = None,
    required_tools: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "facts": [],
        "assumptions": [],
        "open_questions": [],
        "resolved_questions": [],
        "executed_actions": list(executed or []),
        "verified_outcomes": list(verified or []),
        "artifacts": list(artifacts or []),
        "authority": "sandbox",
        "harness_step": step,
        "harness_variant": "H3",
        # These fields are evaluator-owned at runtime. Keeping them in the
        # training distribution prevents a prompt-shape shift at inference.
        "required_tools": list(required_tools or []),
        "expected_tool": expected_tool,
        "verified_evidence": list(verified or []),
        "evidence_records": list(evidence or []),
        "available_actions": list(dict.fromkeys([*tools, "observe", "abstain", "finish"])),
    }


def _envelope(task_id: str, step: int, kind: str, state: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "action-ir/v0",
        "task_id": task_id,
        "step_id": f"step-{step}",
        "kind": kind,
        "uncertainty": {"confidence": 0.98 if kind != "abstain" else 0.95, "basis": "synthetic verifier-backed curriculum"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
    }
    if kind == "finish":
        result["finish"] = {"result": "The independently verified task is complete.", "evidence": list(state["verified_evidence"]), "verified": True}
    elif kind == "abstain":
        result["abstention"] = {"reason": "the requested capability or authorization is unavailable", "alternatives": ["ask for clarification or an approved capability"]}
    return result


def _act(task_id: str, step: int, state: dict[str, Any], tool: str, arguments: dict[str, Any], risk: str = "low") -> dict[str, Any]:
    result = _envelope(task_id, step, "act", state)
    result["action"] = {"intent": tool, "arguments": arguments, "preconditions": [], "risk": risk, "expected_effect": "tool output is independently verified", "escalate_if": ["permission_denied"]}
    return result


def _evidence(task_id: str, step: int, tool: str) -> tuple[str, dict[str, Any]]:
    evidence_id = "sha256:" + hashlib.sha256(f"curriculum:{task_id}:{step}".encode()).hexdigest()
    return evidence_id, {"evidence_id": evidence_id, "status": "verified", "claim": f"{tool} execution completed"}


def _row(task_id: str, prompt: str, tools: list[str], step: int, state: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    input_data = {"task_id": task_id, "goal": prompt, "state": state, "available_tools": list(dict.fromkeys([*tools, "abstain", "finish"])), "token_budget": 1800}
    return {"schema": "action-sft/v0", "task_id": task_id, "input": input_data, "target": target, "provenance": {"source": "synthetic_parameterized_v1_curriculum", "synthetic": True, "holdout_excluded": "research-v2-independent-holdout"}}


def _single(rows: list[dict[str, Any]], task_id: str, prompt: str, tool: str, arguments: dict[str, Any], *, risk: str = "low") -> None:
    tools = [tool]
    for prefix in PREFIXES:
        text = prefix + prompt
        start = _state(tools, 0, expected_tool=tool)
        rows.append(_row(task_id, text, tools, 0, start, _act(task_id, 0, start, tool, arguments, risk)))
        evidence_id, evidence = _evidence(task_id, 0, tool)
        finish_state = _state(tools, 1, executed=[tool], verified=[evidence_id], evidence=[evidence], artifacts=[str(arguments["path"])] if "path" in arguments else [], expected_tool=tool)
        rows.append(_row(task_id, text, tools, 1, finish_state, _envelope(task_id, 1, "finish", finish_state)))


def _abstain(rows: list[dict[str, Any]], task_id: str, prompt: str, tool: str) -> None:
    for prefix in PREFIXES:
        state = _state([tool], 0)
        rows.append(_row(task_id, prefix + prompt, [tool], 0, state, _envelope(task_id, 0, "abstain", state)))


def _long_horizon(rows: list[dict[str, Any]], task_id: str, source: str, destination: str, content: str) -> None:
    prompt = f"Create {source} containing exactly {content}, then move it to {destination} and finish only after the final artifact is verified."
    tools = ["write_text", "move_entry"]
    for prefix in PREFIXES:
        text = prefix + prompt
        first_state = _state(tools, 0, required_tools=tools)
        first = _act(task_id, 0, first_state, "write_text", {"path": source, "content": content})
        rows.append(_row(task_id, text, tools, 0, first_state, first))
        e0, r0 = _evidence(task_id, 0, "write_text")
        second_state = _state(tools, 1, executed=["write_text"], verified=[e0], evidence=[r0], artifacts=[source], required_tools=tools)
        second = _act(task_id, 1, second_state, "move_entry", {"source": source, "destination": destination}, "medium")
        rows.append(_row(task_id, text, tools, 1, second_state, second))
        e1, r1 = _evidence(task_id, 1, "move_entry")
        finish_state = _state(tools, 2, executed=["write_text", "move_entry"], verified=[e1], evidence=[r1], artifacts=[destination], required_tools=tools)
        rows.append(_row(task_id, text, tools, 2, finish_state, _envelope(task_id, 2, "finish", finish_state)))


def build_curriculum() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (path, content) in enumerate((("prefs.cfg", "mode=offline"), ("journal.txt", "hello-world"), ("cache.ini", "enabled=true"), ("profile.toml", "active=yes"), ("ledger.md", "approved"), ("summary.txt", "done"), ("draft2.json", '{"ok":true}'), ("report2.cfg", "ready=1"))):
        _single(rows, f"curriculum-write-{index}", f"Write {path} with the exact content {content}.", "write_file", {"path": path, "content": content})
    for index, (path, content) in enumerate((("memo2.txt", "hello"), ("notes2.md", "payload"), ("queue2.txt", "ready"), ("scratch2.ini", "on"), ("brief2.txt", "complete"), ("draft3.cfg", "v1"))):
        _single(rows, f"curriculum-text-{index}", f"Persist {path} with the exact content {content} through the renamed text tool.", "write_text", {"path": path, "content": content})
    for index, (source, destination) in enumerate((("inbox2.md", "done2.md"), ("source2.log", "archive2.log"), ("raw2.csv", "clean2.csv"), ("draft4.txt", "final4.txt"), ("old2.cfg", "new2.cfg"), ("input2.json", "output2.json"))):
        _single(rows, f"curriculum-move-{index}", f"Move {source} to {destination}.", "move_file", {"source": source, "destination": destination}, risk="medium")
    for index, operation in enumerate(("export", "index", "compile", "publish", "sync2", "backup", "refresh", "validate")):
        _single(rows, f"curriculum-retry-{index}", f"Retry the flaky {operation} operation until it is verified.", "retry_operation", {"operation": operation, "attempt": 2})
    for index, (path, content) in enumerate((("artifact2.json", '{"status":"ok","version":2}'), ("manifest2.json", '{"ready":true}'), ("record2.json", '{"count":1}'), ("state2.json", '{"state":"clean"}'))):
        _single(rows, f"curriculum-json-{index}", f"Write {path} containing exactly the valid JSON object {content}.", "write_file", {"path": path, "content": content})
    for index in range(6):
        _abstain(rows, f"curriculum-unknown-{index}", f"Use the unavailable local_capability_{index} tool.", f"local_capability_{index}")
    for index in range(6):
        _abstain(rows, f"curriculum-delete-{index}", f"Delete protected{index}.txt only if the high-risk operation has explicit authorization.", "delete_file")
    for index, (source, destination, content) in enumerate((("draft5.txt", "archive5.txt", "payload"), ("queue3.md", "stored3.md", "item"), ("work3.cfg", "done3.cfg", "ready"), ("plan2.txt", "archive6.txt", "notes"))):
        _long_horizon(rows, f"curriculum-long-{index}", source, destination, content)
    for index in range(10):
        _single(rows, f"curriculum-api-{index}", "Read the /health endpoint and finish only after the response is independently verified.", "api_get", {"endpoint": "/health"})
        _single(rows, f"curriculum-browser-{index}", "Open https://example.test/status and finish only after the page is independently verified.", "browser_open", {"url": "https://example.test/status"})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = build_curriculum()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"schema": "action-sft/v0", "examples": len(rows), "output": str(output), "synthetic": True, "holdout_excluded": "research-v2-independent-holdout"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
