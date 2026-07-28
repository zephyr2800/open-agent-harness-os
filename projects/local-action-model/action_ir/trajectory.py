"""Minimal replayable trajectory contract for Action IR v0."""

from __future__ import annotations

from typing import Any

from .codec import sha256_digest


EVENT_TYPES = {
    "decision_request",
    "decision",
    "tool_call",
    "observation",
    "verification",
    "checkpoint",
    "trajectory_end",
}


def validate_trajectory(events: Any) -> list[str]:
    """Validate event order and lineage without executing any side effects."""

    issues: list[str] = []
    if not isinstance(events, list) or not events:
        return ["trajectory must be a non-empty list"]
    expected_sequence = 0
    task_id = None
    for index, event in enumerate(events):
        path = f"trajectory[{index}]"
        if not isinstance(event, dict):
            issues.append(f"{path} must be an object")
            continue
        if event.get("sequence") != expected_sequence:
            issues.append(f"{path}.sequence must equal {expected_sequence}")
        expected_sequence += 1
        if event.get("event_type") not in EVENT_TYPES:
            issues.append(f"{path}.event_type must be one of {sorted(EVENT_TYPES)}")
        current_task = event.get("task_id")
        if not isinstance(current_task, str) or not current_task:
            issues.append(f"{path}.task_id must be a non-empty string")
        elif task_id is None:
            task_id = current_task
        elif current_task != task_id:
            issues.append(f"{path}.task_id must match the first event")
        if "payload" not in event or not isinstance(event["payload"], dict):
            issues.append(f"{path}.payload must be an object")
        if index > 0 and event.get("parent_digest") != sha256_digest(events[index - 1]):
            issues.append(f"{path}.parent_digest does not match the previous event")
    if events[-1].get("event_type") != "trajectory_end":
        issues.append("trajectory must end with trajectory_end")
    return issues


def append_event(events: list[dict[str, Any]], task_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Append a lineage-linked event and return the event."""

    event: dict[str, Any] = {
        "event_type": event_type,
        "task_id": task_id,
        "sequence": len(events),
        "payload": payload,
    }
    if events:
        event["parent_digest"] = sha256_digest(events[-1])
    events.append(event)
    return event
