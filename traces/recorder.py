"""Trace capture with redaction before persistence."""

from __future__ import annotations

import re
from typing import Any, Mapping

from protocol.events import Trace


SECRET_PATTERN = re.compile(r"(?i)(token|api[_-]?key|secret|password)(\s*[:=]\s*)([^\s,}]+)")


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value)
    if isinstance(value, Mapping):
        return {str(key): redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    return value


class TraceRecorder:
    def __init__(self, task_id: str) -> None:
        self.trace = Trace(task_id)

    def record(self, event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.trace.append(event_type, redact(dict(payload))).as_dict()

    def jsonl(self) -> str:
        return self.trace.to_jsonl()
