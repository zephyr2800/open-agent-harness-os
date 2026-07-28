"""Versioned, append-only events with cryptographic parent lineage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .digest import sha256_digest

EVENT_TYPES = {
    "decision_request",
    "decision",
    "policy_decision",
    "tool_call",
    "observation",
    "verification",
    "recovery",
    "checkpoint",
    "proposal",
    "promotion",
    "trajectory_end",
}


class TraceFormatError(ValueError):
    pass


@dataclass(frozen=True)
class TraceEvent:
    event_type: str
    task_id: str
    sequence: int
    payload: dict[str, Any]
    parent_digest: str | None = None

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema": "harness-event/v0",
            "event_type": self.event_type,
            "task_id": self.task_id,
            "sequence": self.sequence,
            "payload": self.payload,
        }
        if self.parent_digest is not None:
            value["parent_digest"] = self.parent_digest
        return value


class Trace:
    """In-memory trace that can be serialized without executing any tools."""

    def __init__(self, task_id: str):
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("task_id must be non-empty")
        self.task_id = task_id
        self._events: list[TraceEvent] = []

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

    def append(self, event_type: str, payload: Mapping[str, Any]) -> TraceEvent:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event_type: {event_type}")
        previous = self._events[-1].as_dict() if self._events else None
        event = TraceEvent(
            event_type=event_type,
            task_id=self.task_id,
            sequence=len(self._events),
            payload=dict(payload),
            parent_digest=sha256_digest(previous) if previous is not None else None,
        )
        self._events.append(event)
        return event

    def as_dicts(self) -> list[dict[str, Any]]:
        return [event.as_dict() for event in self._events]

    def validate(self, require_end: bool = False) -> list[str]:
        issues: list[str] = []
        previous: dict[str, Any] | None = None
        for index, event in enumerate(self._events):
            value = event.as_dict()
            if value.get("schema") != "harness-event/v0":
                issues.append(f"event[{index}].schema is invalid")
            if event.sequence != index:
                issues.append(f"event[{index}].sequence must equal {index}")
            if event.task_id != self.task_id:
                issues.append(f"event[{index}].task_id does not match trace")
            if previous is None and event.parent_digest is not None:
                issues.append(f"event[{index}].parent_digest must be absent for the first event")
            if previous is not None and event.parent_digest != sha256_digest(previous):
                issues.append(f"event[{index}].parent_digest is invalid")
            previous = value
        if require_end and (not self._events or self._events[-1].event_type != "trajectory_end"):
            issues.append("trace must end with trajectory_end")
        return issues

    def to_jsonl(self) -> str:
        issues = self.validate()
        if issues:
            raise TraceFormatError("; ".join(issues))
        return "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in self.as_dicts())

    @classmethod
    def from_events(cls, events: Iterable[Mapping[str, Any]]) -> "Trace":
        values = [dict(item) for item in events]
        if not values:
            raise TraceFormatError("trace must contain at least one event")
        task_id = values[0].get("task_id")
        trace = cls(task_id)
        for value in values:
            if value.get("schema") != "harness-event/v0":
                raise TraceFormatError("event schema must equal 'harness-event/v0'")
            if value.get("event_type") not in EVENT_TYPES:
                raise TraceFormatError(f"unknown event_type: {value.get('event_type')}")
            if not isinstance(value.get("payload"), Mapping):
                raise TraceFormatError("event payload must be an object")
            trace._events.append(
                TraceEvent(
                    event_type=value["event_type"],
                    task_id=value.get("task_id", ""),
                    sequence=value.get("sequence", -1),
                    payload=dict(value.get("payload", {})),
                    parent_digest=value.get("parent_digest"),
                )
            )
        issues = trace.validate()
        if issues:
            raise TraceFormatError("; ".join(issues))
        return trace
