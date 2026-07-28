"""Independent trace-level verification for the deterministic fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from benchmarks.tasks import Task, load_tasks
from traces.replay import load_jsonl


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _json_body(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def verify_trace(task: Task, variant: str, trace_jsonl: str) -> dict[str, Any]:
    trace = load_jsonl(trace_jsonl.splitlines())
    files = dict(task.initial_files or {})
    independent_verified_ids: set[str] = set()
    successful_tools: list[str] = []
    retry_attempts: dict[str, int] = {}
    pending_independent = False
    last_tool: str | None = None
    finish_evidence: list[str] = []
    finish_result = ""
    end_payload: Mapping[str, Any] | None = None
    decisions: list[Mapping[str, Any]] = []
    successful_actions: list[dict[str, Any]] = []

    for event in trace.events:
        payload = event.payload
        if event.event_type == "decision":
            if payload.get("valid") is True and isinstance(payload.get("decision"), Mapping):
                decision = payload["decision"]
                decisions.append(decision)
                if decision.get("kind") == "finish" and isinstance(decision.get("finish"), Mapping):
                    finish_evidence = [str(item) for item in decision["finish"].get("evidence", [])]
                    finish_result = str(decision["finish"].get("result", ""))
        elif event.event_type == "tool_call":
            last_tool = payload.get("tool") if isinstance(payload.get("tool"), str) else None
            pending_independent = False
            if payload.get("status") in {"verified", "unverified"} and isinstance(payload.get("output"), Mapping):
                tool = last_tool
                arguments = payload.get("arguments", {})
                output = payload["output"]
                if tool in {"write_file", "write_text"} and isinstance(arguments, Mapping) and isinstance(arguments.get("path"), str) and isinstance(arguments.get("content"), str):
                    path = arguments["path"]
                    content = arguments["content"]
                    pending_independent = output.get("path") == path and output.get("exists") is True and output.get("sha256") == _sha256(content)
                    if pending_independent:
                        files[path] = content
                elif tool in {"move_file", "move_entry"} and isinstance(arguments, Mapping):
                    source, destination = arguments.get("source"), arguments.get("destination")
                    pending_independent = isinstance(source, str) and isinstance(destination, str) and output.get("source") == source and output.get("destination") == destination and output.get("source_exists") is False and output.get("destination_exists") is True and source in files and destination not in files
                    if pending_independent:
                        files[destination] = files.pop(source)
                elif tool == "retry_operation" and isinstance(arguments, Mapping):
                    operation, attempt = arguments.get("operation"), arguments.get("attempt")
                    pending_independent = isinstance(operation, str) and isinstance(attempt, int) and output.get("operation") == operation and output.get("attempt") == attempt and output.get("status") == "recovered" and attempt >= 2
                    if isinstance(operation, str) and isinstance(attempt, int):
                        retry_attempts[operation] = attempt
                elif tool == "delete_file" and isinstance(arguments, Mapping) and isinstance(arguments.get("path"), str):
                    path = arguments["path"]
                    content = files.get(path)
                    pending_independent = content is not None and output.get("path") == path and output.get("deleted") is True and output.get("sha256") == _sha256(content)
                    if pending_independent:
                        files.pop(path, None)
                elif tool in {"api_get"} and isinstance(arguments, Mapping):
                    endpoint = arguments.get("endpoint")
                    records = task.api_records or {
                        "/health": {"service": "harness-demo", "status": "ok"},
                        "/v1/status": {"ready": True, "version": "0"},
                        "/api/v3/healthcheck": {"service": "harness-demo-v3", "status": "ok"},
                        "/metrics/v3": {"requests": 3, "status": "ready"},
                    }
                    pending_independent = isinstance(endpoint, str) and endpoint in records and output.get("endpoint") == endpoint and output.get("status_code") == 200 and output.get("body") == _json_body(records[endpoint])
                elif tool in {"browser_open"} and isinstance(arguments, Mapping):
                    url = arguments.get("url")
                    pages = task.browser_pages or {
                        "https://example.test/status": {"title": "Harness Status", "text": "All systems operational"},
                        "https://example.test/docs": {"title": "Harness Docs", "text": "Replayable local execution"},
                        "https://sandbox.test/guide-v3": {"title": "Sandbox Guide v3", "text": "Bounded verified execution"},
                        "https://docs.test/v3/overview": {"title": "Harness Overview v3", "text": "Independent replay and authority"},
                    }
                    page = pages.get(url) if isinstance(url, str) else None
                    pending_independent = bool(page and output.get("url") == url and output.get("status_code") == 200 and output.get("title") == page["title"] and output.get("text") == page["text"])
                if pending_independent:
                    successful_tools.append(tool or "")
                    successful_actions.append({"tool": tool, "arguments": dict(arguments) if isinstance(arguments, Mapping) else {}})
        elif event.event_type == "verification":
            if pending_independent and payload.get("verified") is True and isinstance(payload.get("evidence_id"), str):
                independent_verified_ids.add(payload["evidence_id"])
        elif event.event_type == "trajectory_end":
            end_payload = payload

    artifact_valid = True
    if task.task_id == "artifact-json":
        try:
            artifact_valid = json.loads(files.get("result.json", "")) == {"status": "ok", "version": 1}
        except json.JSONDecodeError:
            artifact_valid = False
    if task.expected_files is not None:
        artifact_valid = files == task.expected_files
    expected_tools = task.expected_tools
    if not expected_tools and task.expected_actions:
        expected_tools = tuple(str(item.get("tool")) for item in task.expected_actions)
    if task.expected_actions:
        expected_action_contract = True
        cursor = 0
        for expected in task.expected_actions:
            expected_tool = str(expected.get("tool"))
            expected_arguments = dict(expected.get("arguments") or {})
            match = next((index for index in range(cursor, len(successful_actions)) if successful_actions[index]["tool"] == expected_tool and successful_actions[index]["arguments"] == expected_arguments), None)
            if match is None:
                expected_action_contract = False
                break
            cursor = match + 1
    elif task.expected_tool:
        expected_action_contract = any(
            item["tool"] == task.expected_tool
            and (task.expected_arguments is None or item["arguments"] == dict(task.expected_arguments))
            for item in successful_actions
        )
    else:
        expected_action_contract = True
    if task.expected_kind == "abstain":
        independent_success = any(decision.get("kind") == "abstain" for decision in decisions) and bool(end_payload and end_payload.get("reason") == "abstain") and not successful_tools
    elif variant == "H0":
        independent_success = bool(task.expected_tool and task.expected_tool in successful_tools)
        if task.expected_tool == "retry_operation":
            independent_success = any(attempt >= 2 for attempt in retry_attempts.values())
    else:
        tools_ok = not expected_tools or all(tool in successful_tools for tool in expected_tools)
        expected_result_ok = all(marker in finish_result for marker in task.expected_result_contains)
        independent_success = bool(artifact_valid and tools_ok and expected_action_contract and expected_result_ok and end_payload and end_payload.get("reason") == "finish" and set(finish_evidence).intersection(independent_verified_ids))
    return {
        "task_id": task.task_id,
        "variant": variant,
        "trace_valid": trace.validate(require_end=True) == [],
        "independent_success": independent_success,
        "reported_success": bool(end_payload and end_payload.get("verified_success") is True),
        "independent_verified_evidence": len(independent_verified_ids),
        "expected_result_ok": all(marker in finish_result for marker in task.expected_result_contains),
        "successful_tools": successful_tools,
    }


def verify_factorial_report(report: Mapping[str, Any], task_spec: str | Path) -> dict[str, Any]:
    tasks = {task.task_id: task for task in load_tasks(task_spec)}
    rows: list[dict[str, Any]] = []
    for cell_name, cell in report.get("cells", {}).items():
        model, variant = cell_name.split("/", 1)
        for outcome in cell.get("outcomes", []):
            task = tasks[outcome["task_id"]]
            independent = verify_trace(task, variant, outcome["trace_jsonl"])
            independent["cell"] = cell_name
            independent["runtime_success"] = bool(outcome.get("verified_success"))
            independent["matches_runtime"] = independent["independent_success"] == independent["runtime_success"]
            rows.append(independent)
    total = len(rows)
    return {
        "schema": "independent-factorial-verification/v0",
        "task_cell_count": total,
        "trace_valid_rate": sum(row["trace_valid"] for row in rows) / total if total else 0.0,
        "independent_success_rate": sum(row["independent_success"] for row in rows) / total if total else 0.0,
        "runtime_independent_match_rate": sum(row["matches_runtime"] for row in rows) / total if total else 0.0,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--task-spec", default=str(Path(__file__).parent.parent / "benchmarks" / "fixtures" / "task-spec-v0.json"))
    parser.add_argument("--output", default=str(Path(__file__).parent / ".." / "experiments" / "results" / "independent-verification-v0.json"))
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    result = verify_factorial_report(report, args.task_spec)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("task_cell_count", "trace_valid_rate", "independent_success_rate", "runtime_independent_match_rate")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
