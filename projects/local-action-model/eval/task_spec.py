"""Versioned JSON task-spec loading for reproducible benchmark splits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .benchmark import Task


class TaskSpecError(ValueError):
    """Raised when a task specification is malformed."""


def task_from_mapping(mapping: dict[str, Any]) -> Task:
    required = {"task_id", "prompt", "expected_kind", "split", "available_tools", "output_token_budget"}
    missing = sorted(required - mapping.keys())
    if missing:
        raise TaskSpecError(f"task is missing fields: {', '.join(missing)}")
    if not isinstance(mapping["available_tools"], list) or not all(isinstance(tool, str) and tool for tool in mapping["available_tools"]):
        raise TaskSpecError(f"available_tools must be a list of non-empty strings for {mapping.get('task_id')}")
    verified_evidence = mapping.get("verified_evidence", [])
    if not isinstance(verified_evidence, list) or not all(isinstance(item, str) and item for item in verified_evidence):
        raise TaskSpecError(f"verified_evidence must be a list of non-empty strings for {mapping.get('task_id')}")
    return Task(
        task_id=mapping["task_id"],
        prompt=mapping["prompt"],
        expected_kind=mapping["expected_kind"],
        expected_intent=mapping.get("expected_intent"),
        expected_arguments=mapping.get("expected_arguments"),
        required_reason_fragment=mapping.get("required_reason_fragment"),
        split=mapping["split"],
        available_tools=tuple(mapping["available_tools"]),
        output_token_budget=mapping["output_token_budget"],
        verified_evidence=tuple(verified_evidence),
    )


def load_tasks(path: str | Path) -> tuple[Task, ...]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict) or document.get("schema") != "action-task-spec/v0":
        raise TaskSpecError("task spec schema must equal 'action-task-spec/v0'")
    raw_tasks = document.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise TaskSpecError("task spec must contain a non-empty tasks list")
    tasks = tuple(task_from_mapping(item) for item in raw_tasks if isinstance(item, dict))
    if len(tasks) != len(raw_tasks):
        raise TaskSpecError("every task must be an object")
    ids = [task.task_id for task in tasks]
    if len(ids) != len(set(ids)):
        raise TaskSpecError("task_id values must be unique")
    return tasks


def task_to_mapping(task: Task) -> dict[str, Any]:
    result: dict[str, Any] = {
        "task_id": task.task_id,
        "prompt": task.prompt,
        "expected_kind": task.expected_kind,
        "split": task.split,
        "available_tools": list(task.available_tools),
        "output_token_budget": task.output_token_budget,
    }
    if task.expected_intent is not None:
        result["expected_intent"] = task.expected_intent
    if task.expected_arguments is not None:
        result["expected_arguments"] = task.expected_arguments
    if task.required_reason_fragment is not None:
        result["required_reason_fragment"] = task.required_reason_fragment
    if task.verified_evidence:
        result["verified_evidence"] = list(task.verified_evidence)
    return result
