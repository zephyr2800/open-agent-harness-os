"""Build preference pairs from frozen tasks and explicit hard-negative rules."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable

from eval.benchmark import Task, reference_policy


def hard_negative(task: Task, chosen: dict[str, Any]) -> tuple[dict[str, Any], str]:
    rejected = copy.deepcopy(chosen)
    if task.expected_kind == "act":
        arguments = rejected["action"]["arguments"]
        if task.expected_intent == "write_file":
            arguments["content"] = "incorrect content"
            return rejected, "wrong_argument_value"
        if task.expected_intent == "read_file":
            arguments["path"] = "missing.md"
            return rejected, "missing_artifact"
        if task.expected_intent == "move_file":
            arguments["destination"] = "archive/wrong.md"
            return rejected, "wrong_destination"
        if task.expected_intent == "retry_operation":
            arguments["attempt"] = 1
            return rejected, "insufficient_recovery"
        arguments["hard_negative"] = True
        return rejected, "extra_argument"
    if task.expected_kind == "abstain":
        rejected.pop("abstention", None)
        rejected["kind"] = "act"
        tool = next((name for name in task.available_tools if name != "abstain"), "unknown_tool")
        rejected["action"] = {
            "intent": tool,
            "arguments": {},
            "preconditions": [],
            "risk": "low",
            "expected_effect": "requested_effect",
            "escalate_if": ["permission_denied"],
        }
        return rejected, "over_action_when_abstention_required"
    rejected["finish"]["verified"] = False
    return rejected, "unverified_finish"


def build_preference_examples(tasks: Iterable[Task]) -> list[dict[str, Any]]:
    examples = []
    for task in tasks:
        chosen = reference_policy(task)
        rejected, reason = hard_negative(task, chosen)
        examples.append(
            {
                "schema": "action-preference/v0",
                "task_id": task.task_id,
                "input": {
                    "goal": task.prompt,
                    "task_id": task.task_id,
                    "state": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
                    "available_tools": list(task.available_tools),
                    "token_budget": task.output_token_budget,
                },
                "chosen": chosen,
                "rejected": rejected,
                "rejected_reason": reason,
                "provenance": {
                    "source": "deterministic_reference_policy_plus_declared_mutation",
                    "synthetic": True,
                    "independent_verifier_required": True,
                },
            }
        )
    return examples


def write_preference_jsonl(examples: Iterable[dict[str, Any]], path: str | Path) -> int:
    count = 0
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        for example in examples:
            handle.write(json.dumps(example, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            count += 1
    return count
