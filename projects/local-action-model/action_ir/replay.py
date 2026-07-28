"""Load and validate JSONL trajectories without executing tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .trajectory import validate_trajectory


class ReplayFormatError(ValueError):
    """Raised when a JSONL trace is malformed or fails lineage checks."""


def load_jsonl(lines: Iterable[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReplayFormatError(f"line {line_number} is not valid JSON: {exc.msg}") from exc
        if not isinstance(event, dict):
            raise ReplayFormatError(f"line {line_number} must contain a JSON object")
        events.append(event)
    issues = validate_trajectory(events)
    if issues:
        raise ReplayFormatError("; ".join(issues))
    return events


def load_file(path: str | Path) -> list[dict[str, Any]]:
    """Read a UTF-8 JSONL trace and validate it before returning events."""

    with Path(path).open("r", encoding="utf-8") as handle:
        return load_jsonl(handle)
