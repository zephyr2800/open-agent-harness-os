"""Externalized, versioned task specification loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Task:
    task_id: str
    prompt: str
    split: str
    available_tools: tuple[str, ...]
    expected_kind: str
    expected_tool: str | None = None
    expected_arguments: dict[str, Any] | None = None
    initial_files: dict[str, str] | None = None
    output_token_budget: int = 1800
    expected_actions: tuple[dict[str, Any], ...] = ()
    expected_tools: tuple[str, ...] = ()
    expected_files: dict[str, str] | None = None
    expected_result_contains: tuple[str, ...] = ()
    api_records: dict[str, dict[str, Any]] | None = None
    browser_pages: dict[str, dict[str, Any]] | None = None
    family: str = "unspecified"
    difficulty: str = "standard"
    adversarial: bool = False
    include_tool_outputs: bool = False


def load_tasks(path: str | Path) -> tuple[Task, ...]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if document.get("schema") != "harness-task-spec/v0" or not isinstance(document.get("tasks"), list):
        raise ValueError("task spec schema must equal harness-task-spec/v0 and contain tasks")
    result = []
    for raw in document["tasks"]:
        required = {"task_id", "prompt", "split", "available_tools", "expected_kind"}
        missing = sorted(required - raw.keys())
        if missing:
            raise ValueError(f"task is missing fields: {', '.join(missing)}")
        result.append(Task(
            task_id=raw["task_id"],
            prompt=raw["prompt"],
            split=raw["split"],
            available_tools=tuple(raw["available_tools"]),
            expected_kind=raw["expected_kind"],
            expected_tool=raw.get("expected_tool"),
            expected_arguments=raw.get("expected_arguments"),
            initial_files=raw.get("initial_files"),
            output_token_budget=raw.get("output_token_budget", 1800),
            expected_actions=tuple(raw.get("expected_actions", ())),
            expected_tools=tuple(raw.get("expected_tools", ())),
            expected_files=raw.get("expected_files"),
            expected_result_contains=tuple(str(item) for item in raw.get("expected_result_contains", ())),
            api_records=raw.get("api_records"),
            browser_pages=raw.get("browser_pages"),
            family=raw.get("family", "unspecified"),
            difficulty=raw.get("difficulty", "standard"),
            adversarial=bool(raw.get("adversarial", False)),
            include_tool_outputs=bool(raw.get("include_tool_outputs", False)),
        ))
    if len({task.task_id for task in result}) != len(result):
        raise ValueError("task ids must be unique")
    return tuple(result)
