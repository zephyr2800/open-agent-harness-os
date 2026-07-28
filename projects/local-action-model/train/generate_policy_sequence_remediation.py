"""Generate disjoint training rows for verified long-horizon policy recovery."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


HOLDOUT_EXCLUSION = (
    "research-v4;research-v2;industry-proxy-v1;industry-proxy-v2;"
    "external-bar-lite-v1;external-bar-lite-v2"
)


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _evidence(index: int, step: int, label: str) -> dict[str, str]:
    return {
        "claim": f"{label} completed and its outcome was independently verified",
        "evidence_id": _digest(f"policy-sequence-remediation-{index}-{step}-{label}"),
        "status": "verified",
    }


def _state(
    *,
    task_id: str,
    variant: int,
    step: int,
    artifacts: list[str],
    executed: list[str],
    evidence: list[dict[str, str]],
    state_digest: str,
) -> dict[str, Any]:
    return {
        "artifacts": artifacts,
        "assumptions": [],
        "authority": "sandbox",
        "available_actions": [
            "write_file",
            "move_file",
            "retry_operation",
            "observe",
            "abstain",
            "finish",
        ],
        "evidence_records": evidence,
        "executed_actions": executed,
        "facts": [
            "every completed tool outcome must be independently verified",
            "do not repeat an already verified action",
            "retry the named operation until the recovered attempt is verified",
            "finish only after the complete ordered sequence is evidenced",
        ],
        "harness_step": step,
        "harness_variant": f"policy-recovery-{variant % 4}",
        "open_questions": [],
        "required_tools": [
            "write_file",
            "move_file",
            "retry_operation",
            "write_file",
        ],
        "resolved_questions": [],
        "state_digest": state_digest,
        "task_id": task_id,
        "verified_evidence": [item["evidence_id"] for item in evidence],
        "verified_outcomes": [item["evidence_id"] for item in evidence],
    }


def _action_target(
    *,
    task_id: str,
    step: int,
    intent: str,
    arguments: dict[str, Any],
    risk: str = "low",
) -> dict[str, Any]:
    return {
        "action": {
            "arguments": arguments,
            "escalate_if": ["permission_denied"],
            "expected_effect": "tool output is independently verified",
            "intent": intent,
            "preconditions": [],
            "risk": risk,
        },
        "kind": "act",
        "schema": "action-ir/v0",
        "state_update": {"assumptions": [], "facts": [], "open_questions": [], "resolved_questions": []},
        "step_id": f"step-{step}",
        "task_id": task_id,
        "uncertainty": {"basis": "synthetic verified policy-recovery curriculum", "confidence": 0.98},
    }


def _finish_target(task_id: str, evidence: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "finish": {
            "evidence": [item["evidence_id"] for item in evidence],
            "result": "The independently verified ordered release sequence is complete.",
            "verified": True,
        },
        "kind": "finish",
        "schema": "action-ir/v0",
        "state_update": {"assumptions": [], "facts": [], "open_questions": [], "resolved_questions": []},
        "step_id": "step-4",
        "task_id": task_id,
        "uncertainty": {"basis": "synthetic verified policy-recovery curriculum", "confidence": 0.98},
    }


def build_rows(variants: int = 16) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant in range(variants):
        suffix = f"{variant:02d}"
        draft = f"recovery_draft_{suffix}.cfg"
        final = f"recovery_final_{suffix}.cfg"
        audit = f"recovery_audit_{suffix}.txt"
        operation = f"recovery-publish-{suffix}"
        release = f"release=verified-{suffix}-approved"
        audit_content = f"operation={operation};status=recovered"
        goal = (
            f"Prepare the bounded release: write {draft} exactly as {release}, move it to {final}, "
            f"retry {operation} until it is recovered at attempt 2, then write {audit} exactly as "
            f"{audit_content}. Do not finish early; verify every ordered step."
        )
        actions = [
            ("write_file", {"path": draft, "content": release}),
            ("move_file", {"source": draft, "destination": final}),
            ("retry_operation", {"operation": operation, "attempt": 2}),
            ("write_file", {"path": audit, "content": audit_content}),
        ]
        labels = ["write_draft", "move_final", "retry_recovered", "write_audit"]
        for step in range(5):
            task_id = f"policy-recovery-remediation-{suffix}-step-{step}"
            evidence = [_evidence(variant, index, label) for index, label in enumerate(labels[:step])]
            artifacts = [draft] if step >= 1 else []
            if step >= 2:
                artifacts = [final]
            if step >= 4:
                artifacts = [final, audit]
            executed = [name for name, _ in actions[:step]]
            state_digest = _digest(f"{task_id}|{variant}|{step}|{','.join(executed)}")
            input_record = {
                "available_tools": [
                    "write_file",
                    "move_file",
                    "retry_operation",
                    "observe",
                    "abstain",
                    "finish",
                ],
                "goal": goal,
                "state": _state(
                    task_id=task_id,
                    variant=variant,
                    step=step,
                    artifacts=artifacts,
                    executed=executed,
                    evidence=evidence,
                    state_digest=state_digest,
                ),
                "task_id": task_id,
                "token_budget": 1800,
            }
            if step < 4:
                intent, arguments = actions[step]
                target = _action_target(task_id=task_id, step=step, intent=intent, arguments=arguments, risk="medium" if intent == "retry_operation" else "low")
            else:
                target = _finish_target(task_id, evidence)
            rows.append(
                {
                    "input": input_record,
                    "provenance": {
                        "holdout_excluded": HOLDOUT_EXCLUSION,
                        "sampling_stratum": "policy_sequence_recovery",
                        "sampling_weight": 12.0,
                        "source": "synthetic_policy_sequence_recovery_v1",
                        "synthetic": True,
                        "trajectory_verified": True,
                    },
                    "schema": "action-sft/v0",
                    "target": target,
                    "task_id": task_id,
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--variants", type=int, default=16)
    args = parser.parse_args()
    rows = build_rows(args.variants)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"schema": "action-sft/v0", "examples": len(rows), "output": str(output), "synthetic": True, "sampling_stratum": "policy_sequence_recovery"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
