"""Create a provenance-labeled domain-adaptive corpus for Action IR mid-training."""

from __future__ import annotations

import json
from typing import Any, Iterable

from eval.benchmark import Task, reference_policy


SCHEMA = "action-midtrain/v0"


def _protocol_text() -> str:
    return (
        "Action IR v0 requires schema action-ir/v0, task_id, step_id, kind, "
        "uncertainty, and state_update. Kinds are act, observe, abstain, and finish. "
        "A finish decision requires independent evidence and verified=true. "
        "A model proposes a decision; the harness authorizes, executes, and verifies it."
    )


def build_midtrain_examples(tasks: Iterable[Task]) -> list[dict[str, Any]]:
    """Build small domain-adaptive rows from the frozen fixture.

    These rows are intentionally synthetic. They teach the model the local
    protocol vocabulary and envelope; they do not establish generalization.
    """

    examples: list[dict[str, Any]] = []
    for task in tasks:
        decision = reference_policy(task)
        context = {
            "task_id": task.task_id,
            "goal": task.prompt,
            "available_tools": list(task.available_tools),
            "expected_kind": task.expected_kind,
        }
        examples.append(
            {
                "schema": SCHEMA,
                "task_id": task.task_id,
                "text": _protocol_text(),
                "provenance": {"source": "protocol_spec", "synthetic": True, "split": "train"},
            }
        )
        examples.append(
            {
                "schema": SCHEMA,
                "task_id": task.task_id,
                "text": "Context: " + json.dumps(context, sort_keys=True, separators=(",", ":")) + "\nValid decision: " + json.dumps(decision, sort_keys=True, separators=(",", ":")),
                "provenance": {
                    "source": "deterministic_reference_policy",
                    "synthetic": True,
                    "split": task.split,
                    "task_spec": "action-task-spec/v0",
                },
            }
        )
    return examples


def write_midtrain_jsonl(examples: Iterable[dict[str, Any]], path: str) -> int:
    count = 0
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for example in examples:
            handle.write(json.dumps(example, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            count += 1
    return count
