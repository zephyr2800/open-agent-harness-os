"""Generate held-out-safe supervision for stopping after verified completion.

This curriculum targets a specific failure mode: the policy has completed and
received independent evidence for every required action, but repeats an old
tool instead of emitting one ``finish`` decision. The task IDs, payloads, and
state digests are synthetic and disjoint from every frozen evaluation suite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCENARIOS = (
    ("handoff", ("write_file", "move_file", "retry_operation", "write_file"), ("handoff_draft.txt", "handoff_final.txt", "handoff_audit.txt")),
    ("release", ("write_file", "move_file", "retry_operation", "write_file"), ("release_draft.cfg", "release_final.cfg", "release_audit.txt")),
    ("report", ("read_file", "write_file", "move_file", "write_file"), ("report_source.md", "report_draft.md", "report_final.md", "report_audit.txt")),
    ("dataset", ("read_file", "write_file", "retry_operation", "write_file"), ("dataset_schema.json", "dataset_manifest.json", "dataset_audit.txt")),
    ("migration", ("write_file", "move_file", "write_file", "write_file"), ("migration_plan.md", "migration_final.md", "migration_audit.txt")),
    ("checkpoint", ("read_file", "write_file", "retry_operation", "write_file"), ("checkpoint_source.txt", "checkpoint_note.txt", "checkpoint_audit.txt")),
)


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _row(index: int, scenario: tuple[str, tuple[str, ...], tuple[str, ...]], horizon: int, style: int) -> dict[str, Any]:
    name, tools, paths = scenario
    task_id = f"finish-convergence-v1-{index:04d}-h{horizon}-s{style}"
    executed = [tools[i % len(tools)] for i in range(horizon)]
    evidence = [_digest(f"finish-convergence:{task_id}:step:{i}") for i in range(horizon)]
    records = [
        {"claim": f"{tool} completed and its outcome was independently verified", "evidence_id": evidence[i], "status": "verified"}
        for i, tool in enumerate(executed)
    ]
    artifacts = [paths[i % len(paths)] for i in range(horizon)]
    variant = ("H1", "H2", "H3", "H4")[style % 4]
    state = {
        "artifacts": artifacts,
        "assumptions": [],
        "authority": "sandbox",
        "available_actions": list(dict.fromkeys([*tools, "observe", "abstain", "finish"])),
        "evidence_records": records,
        "executed_actions": executed,
        "facts": [
            "every required tool outcome is independently verified",
            "the requested state transition is complete",
            "state_digest is verifier metadata and is not artifact content",
            "do not repeat an already verified action",
        ],
        "harness_step": horizon,
        "harness_variant": variant,
        "open_questions": [],
        "required_tools": list(dict.fromkeys(tools)),
        "resolved_questions": [],
        "state_digest": _digest(f"runtime-state:{task_id}:{horizon}"),
        "task_id": task_id,
        "verified_evidence": evidence,
        "verified_outcomes": evidence,
    }
    prompt_styles = (
        f"Complete the {name} workflow and stop immediately after independent verification.",
        f"Finish the bounded {name} operation. All required actions below are already verified; do not repeat a tool.",
        f"The {name} artifact is complete. Emit exactly one verified finish decision rather than another action.",
        f"In the verifier-backed workspace, acknowledge completion of the {name} workflow and terminate cleanly.",
    )
    goal = prompt_styles[style % len(prompt_styles)]
    target = {
        "schema": "action-ir/v0",
        "task_id": task_id,
        "step_id": f"step-{horizon}",
        "kind": "finish",
        "finish": {"evidence": evidence, "result": "The independently verified task is complete.", "verified": True},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
        "uncertainty": {"basis": "synthetic finish-convergence reference policy", "confidence": 0.99},
    }
    return {
        "schema": "action-sft/v0",
        "task_id": task_id,
        "input": {"task_id": task_id, "goal": goal, "state": state, "available_tools": state["available_actions"], "token_budget": 1800},
        "target": target,
        "provenance": {
            "source": "synthetic_finish_convergence_v1",
            "synthetic": True,
            "trajectory_verified": True,
            "sampling_stratum": "verified_finish_convergence",
            "sampling_weight": 8.0,
            "holdout_excluded": "research-v4;research-v2;industry-proxy-v1;industry-proxy-v2;external-bar-lite-v1;external-bar-lite-v2",
        },
    }


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    index = 0
    for scenario in SCENARIOS:
        for horizon in range(2, 9):
            for style in range(8):
                rows.append(_row(index, scenario, horizon, style))
                index += 1
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = build_rows()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"schema": "action-sft/v0", "examples": len(rows), "output": str(output), "synthetic": True, "sampling_stratum": "verified_finish_convergence"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
