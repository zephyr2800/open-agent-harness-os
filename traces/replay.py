"""Offline trace validation; replay never calls tools or models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Mapping

from protocol.events import Trace, TraceFormatError


def load_jsonl(lines: Iterable[str]) -> Trace:
    events: list[Mapping[str, object]] = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TraceFormatError(f"line {line_number} is not JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise TraceFormatError(f"line {line_number} must be an object")
        events.append(value)
    return Trace.from_events(events)


def load_file(path: str | Path) -> Trace:
    with Path(path).open("r", encoding="utf-8") as handle:
        return load_jsonl(handle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace")
    args = parser.parse_args()
    trace = load_file(args.trace)
    print(json.dumps({"events": len(trace.events), "valid": not trace.validate()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
