"""Convert verified trajectory pairs into a stable JSONL SFT format."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from action_ir.trajectory import validate_trajectory


class SFTFormatError(ValueError):
    """Raised when a trajectory cannot produce a supervised example."""


def trajectory_to_sft_examples(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues = validate_trajectory(events)
    if issues:
        raise SFTFormatError("; ".join(issues))
    examples: list[dict[str, Any]] = []
    pending_request: dict[str, Any] | None = None
    for event in events:
        if event["event_type"] == "decision_request":
            pending_request = event["payload"]
        elif event["event_type"] == "decision":
            if pending_request is None:
                raise SFTFormatError("decision event has no preceding decision_request")
            payload = event["payload"]
            target = payload.get("decision", payload)
            if not isinstance(target, dict):
                raise SFTFormatError("decision payload must contain an object target")
            examples.append(
                {
                    "schema": "action-sft/v0",
                    "task_id": event["task_id"],
                    "input": pending_request,
                    "target": target,
                    "source_sequence": event["sequence"],
                }
            )
            pending_request = None
    return examples


def write_jsonl(examples: Iterable[dict[str, Any]], path: str | Path) -> int:
    count = 0
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        for example in examples:
            handle.write(json.dumps(example, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            count += 1
    return count
