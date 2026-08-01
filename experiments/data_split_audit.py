"""Fail closed when an SFT corpus contains frozen evaluation contracts.

The check is intentionally lexical and conservative: if a held-out task ID,
action argument, expected file, endpoint, browser page, or response marker
appears in a training row, the corpus is not independent of that fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


_GENERIC_VALUES = frozenset(
    {
        "abstain",
        "api_get",
        "browser_open",
        "delete_file",
        "finish",
        "move_file",
        "observe",
        "retry_operation",
        "write_file",
    }
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _add_markers(markers: set[tuple[str, str]], task_id: str, kind: str, value: Any) -> None:
    for text in _strings(value):
        normalized = text.strip()
        if len(normalized) >= 8 and normalized not in _GENERIC_VALUES:
            markers.add((kind, normalized))


def _task_markers(task: dict[str, Any]) -> set[tuple[str, str]]:
    task_id = str(task.get("task_id") or task.get("id") or "<unknown>")
    markers: set[tuple[str, str]] = set()
    _add_markers(markers, task_id, "task_id", task_id)
    _add_markers(markers, task_id, "prompt", task.get("prompt"))
    _add_markers(markers, task_id, "expected_arguments", task.get("expected_arguments", {}))
    for action in task.get("expected_actions", []):
        _add_markers(markers, task_id, "expected_action_arguments", action.get("arguments", {}))
    _add_markers(markers, task_id, "expected_files", task.get("expected_files", {}))
    _add_markers(markers, task_id, "api_records", task.get("api_records", {}))
    _add_markers(markers, task_id, "browser_pages", task.get("browser_pages", {}))
    _add_markers(markers, task_id, "expected_result_contains", task.get("expected_result_contains", []))
    return markers


def audit(train_jsonl: list[Path], task_specs: list[Path]) -> dict[str, Any]:
    """Return an immutable, JSON-serializable summary of train/holdout overlap."""

    train_text = "\n".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for path in train_jsonl
        for row in _read_jsonl(path)
    )
    fixtures: list[dict[str, Any]] = []
    marker_sources: dict[tuple[str, str], set[str]] = {}
    for path in task_specs:
        document = json.loads(path.read_text(encoding="utf-8"))
        tasks = document.get("tasks", []) if isinstance(document, dict) else document
        fixtures.append({"path": str(path), "sha256": _sha256(path), "tasks": len(tasks)})
        for task in tasks:
            task_id = str(task.get("task_id") or task.get("id") or "<unknown>")
            for marker in _task_markers(task):
                marker_sources.setdefault(marker, set()).add(task_id)

    overlaps = [
        {
            "kind": kind,
            "value": value,
            "task_ids": sorted(marker_sources[(kind, value)]),
        }
        for kind, value in sorted(marker_sources)
        if value in train_text
    ]
    return {
        "schema": "train-holdout-audit/v1",
        "passed": not overlaps,
        "train": [
            {"path": str(path), "sha256": _sha256(path), "rows": len(_read_jsonl(path))}
            for path in train_jsonl
        ],
        "fixtures": fixtures,
        "marker_count": len(marker_sources),
        "overlap_count": len(overlaps),
        "overlaps": overlaps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-jsonl", action="append", type=Path, required=True)
    parser.add_argument("--task-spec", action="append", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--fail-on-overlap", action="store_true")
    args = parser.parse_args()

    report = audit(args.train_jsonl, args.task_spec)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.manifest is not None:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 2 if args.fail_on_overlap and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
