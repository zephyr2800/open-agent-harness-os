"""Smoke-test the public Project 1 Action IR adapter against its reference policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from adapters.project1 import Project1ActionIRAdapter
from adapters.base import ModelRequest
from runtime.orchestrator import Harness, HarnessConfig, TaskRequest
from tools.memory_workspace import make_memory_registry


def _project1_root() -> Path:
    return Path(__file__).resolve().parents[1] / "projects" / "local-action-model"


class ReferenceSequencer:
    """Bridge the Project 1 fixture policy to the harness request mapping.

    The reference policy is deliberately stateless. For act tasks this bridge
    emits a finish only after the harness supplies verified evidence; that
    makes the integration smoke test exercise the real public feedback path,
    while `verify_finish` remains a negative strict-evidence control.
    """

    def __init__(self, project1_root: Path) -> None:
        sys.path.insert(0, str(project1_root))
        from eval.benchmark import TASKS, reference_policy

        self.tasks = {task.task_id: task for task in TASKS}
        self.reference_policy = reference_policy

    def __call__(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        task = self.tasks[request["task_id"]]
        if task.expected_kind == "act" and request.get("evidence"):
            evidence_id = request["evidence"][-1]["evidence_id"]
            return {
                "schema": "action-ir/v0",
                "task_id": task.task_id,
                "step_id": "step-finish",
                "kind": "finish",
                "uncertainty": {"confidence": 0.9, "basis": "harness verifier feedback"},
                "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
                "finish": {"result": "The verifier confirmed completion.", "evidence": [evidence_id], "verified": True},
            }
        return self.reference_policy(task)


def run(project1_root: Path | None = None) -> dict[str, Any]:
    bridge = ReferenceSequencer(project1_root or _project1_root())
    rows: list[dict[str, Any]] = []
    for task in bridge.tasks.values():
        initial_files = {"STATUS.md": "checkpoint: verified\n"} if task.task_id == "inspect_status" else {}
        _, registry = make_memory_registry(initial_files)
        model = Project1ActionIRAdapter(bridge)
        harness = Harness(model, registry, config=HarnessConfig(variant="H1", max_steps=3))
        request = TaskRequest(task.task_id, task.prompt, task.available_tools, task.output_token_budget, task.expected_kind, task.expected_intent, task.expected_arguments, task.split)
        result = harness.run(request)
        verified_events = [event for event in result.trace.events if event.event_type == "verification" and event.payload.get("verified") is True]
        rows.append({
            "task_id": task.task_id,
            "split": task.split,
            "protocol_valid": result.protocol_valid,
            "verified_success": result.verified_success,
            "abstained": result.abstained,
            "verified_tool_events": len(verified_events),
            "trace_events": len(result.trace.events),
            "trace_valid": result.trace.validate() == [],
            "error": result.error,
        })
    total = len(rows)
    return {
        "schema": "project1-harness-integration/v0",
        "project1_root": str(project1_root or _project1_root()),
        "task_count": total,
        "protocol_valid_rate": sum(row["protocol_valid"] for row in rows) / total if total else 0.0,
        "verified_success_rate": sum(row["verified_success"] for row in rows) / total if total else 0.0,
        "trace_valid_rate": sum(row["trace_valid"] for row in rows) / total if total else 0.0,
        "tasks": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project1-root", type=Path)
    parser.add_argument("--output", default=str(Path(__file__).parent / "results" / "project1-integration-v0.json"))
    args = parser.parse_args()
    report = run(args.project1_root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("task_count", "protocol_valid_rate", "verified_success_rate", "trace_valid_rate")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
