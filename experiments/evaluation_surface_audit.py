"""Describe static task-spec structure without exposing task contents.

This is deliberately a structural audit, not a model evaluation.  It reports
the action horizon, tool-choice surface, evidence exposure, and task metadata
encoded in one or more versioned task specifications.  It neither runs a
policy nor changes any promotion or verifier-backed-RL decision rule.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from benchmarks.tasks import Task, load_tasks
from experiments.data_split_audit import task_spec_sha256


def _string_distribution(values: Iterable[str]) -> dict[str, int]:
    counter = Counter(values)
    return {key: counter[key] for key in sorted(counter)}


def _integer_distribution(values: Iterable[int]) -> dict[str, int]:
    counter = Counter(values)
    return {str(key): counter[key] for key in sorted(counter)}


def _boolean_distribution(values: Iterable[bool]) -> dict[str, int]:
    counter = Counter(bool(value) for value in values)
    return {"false": counter[False], "true": counter[True]}


def _reference_tools(task: Task) -> tuple[str, ...]:
    """Return the tool types required by the task's reference contract."""

    if task.expected_actions:
        result: list[str] = []
        for action in task.expected_actions:
            tool = action.get("tool") if isinstance(action, dict) else None
            if not isinstance(tool, str) or not tool:
                raise ValueError(f"{task.task_id} has an expected action without a tool")
            result.append(tool)
        return tuple(result)
    if task.expected_tool is None:
        return ()
    if not isinstance(task.expected_tool, str) or not task.expected_tool:
        raise ValueError(f"{task.task_id} has an invalid expected_tool")
    return (task.expected_tool,)


def _minimum_contract_actions(task: Task) -> int:
    """Count required actions while preserving legacy single-action contracts."""

    if task.expected_actions:
        return len(task.expected_actions)
    return 1 if task.expected_tool is not None else 0


def _source_summary(tasks: Sequence[Task]) -> dict[str, Any]:
    if not tasks:
        raise ValueError("task specification must contain at least one task")

    reference_tools = [_reference_tools(task) for task in tasks]
    available_tools = [set(task.available_tools) for task in tasks]
    expected_distinct_tools = [set(tools) for tools in reference_tools]
    finish_indices = [index for index, task in enumerate(tasks) if task.expected_kind == "finish"]
    finish_extra_tools = [
        available_tools[index] - expected_distinct_tools[index]
        for index in finish_indices
    ]
    reference_tools_allowed = all(
        expected.issubset(available)
        for expected, available in zip(expected_distinct_tools, available_tools)
    )
    minimum_actions = [_minimum_contract_actions(task) for task in tasks]
    trajectory_actions = [len(task.expected_actions) for task in tasks]
    legacy_contracts = [
        not task.expected_actions and task.expected_tool is not None
        for task in tasks
    ]
    tool_outputs = [bool(task.include_tool_outputs) for task in tasks]
    grounded_state = [bool(task.api_records or task.browser_pages) for task in tasks]
    final_content_checks = [
        bool(task.expected_files or task.expected_result_contains)
        for task in tasks
    ]
    finish_contracts_present = all(
        minimum_actions[index] > 0
        for index in finish_indices
    )
    structural_counts = {
        "finish_tasks": len(finish_indices),
        "abstain_tasks": sum(task.expected_kind == "abstain" for task in tasks),
        "finish_tasks_with_available_but_unexpected_tool": sum(
            bool(extra) for extra in finish_extra_tools
        ),
        "finish_tasks_without_available_but_unexpected_tool": sum(
            not extra for extra in finish_extra_tools
        ),
        "tasks_with_grounded_api_or_browser_state": sum(grounded_state),
        "tasks_with_tool_outputs_visible_to_policy": sum(tool_outputs),
        "tasks_with_final_content_check": sum(final_content_checks),
        "legacy_single_action_contracts": sum(legacy_contracts),
        "max_minimum_contract_actions": max(minimum_actions, default=0),
        "max_explicit_trajectory_actions": max(trajectory_actions, default=0),
    }
    warnings: list[str] = []
    if finish_indices and structural_counts["finish_tasks_with_available_but_unexpected_tool"] == 0:
        warnings.append(
            "Every finish task exposes only reference-contract tool types; this surface does not isolate distractor-tool selection."
        )
    maximum_actions = structural_counts["max_minimum_contract_actions"]
    if finish_indices and maximum_actions <= 3:
        warnings.append(
            f"No finish-task contract requires more than {maximum_actions} action(s)."
        )
    legacy_count = structural_counts["legacy_single_action_contracts"]
    if legacy_count:
        warnings.append(
            f"{legacy_count} task(s) use legacy expected_tool contracts and have no explicit expected_actions sequence."
        )
    if structural_counts["tasks_with_tool_outputs_visible_to_policy"] < len(tasks):
        warnings.append(
            "Not every task exposes structured tool output to the policy; aggregate scores mix direct and evidence-grounded task surfaces."
        )
    return {
        "task_count": len(tasks),
        "structural_counts": structural_counts,
        "distributions": {
            "expected_kind": _string_distribution(task.expected_kind for task in tasks),
            "family": _string_distribution(task.family for task in tasks),
            "difficulty": _string_distribution(task.difficulty for task in tasks),
            "minimum_contract_actions": _integer_distribution(minimum_actions),
            "explicit_trajectory_actions": _integer_distribution(trajectory_actions),
            "available_tool_count": _integer_distribution(len(tools) for tools in available_tools),
            "reference_distinct_tool_count": _integer_distribution(len(tools) for tools in expected_distinct_tools),
            "available_minus_reference_distinct_tool_count": _integer_distribution(
                len(available) - len(expected)
                for available, expected in zip(available_tools, expected_distinct_tools)
            ),
            "tool_outputs_visible_to_policy": _boolean_distribution(tool_outputs),
            "grounded_api_or_browser_state": _boolean_distribution(grounded_state),
            "adversarial": _boolean_distribution(task.adversarial for task in tasks),
            "legacy_single_action_contract": _boolean_distribution(legacy_contracts),
            "final_content_check": _boolean_distribution(final_content_checks),
        },
        "assertions": {
            "reference_tools_are_available": reference_tools_allowed,
            "finish_tasks_have_action_contracts": finish_contracts_present,
        },
        "warnings": warnings,
        "passed": reference_tools_allowed and finish_contracts_present,
    }


def audit(
    sources: Iterable[Path],
    *,
    source_labels: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return a content-free structural report for versioned task specs."""

    paths = [Path(path) for path in sources]
    if not paths:
        raise ValueError("at least one task specification is required")
    labels = list(source_labels or ())
    if labels and len(labels) != len(paths):
        raise ValueError("source_labels must be omitted or contain one label per task specification")

    source_reports: list[dict[str, Any]] = []
    all_tasks: list[Task] = []
    for index, path in enumerate(paths):
        tasks = list(load_tasks(path))
        source_reports.append({
            "source": labels[index] if labels else str(path),
            "sha256": task_spec_sha256(path),
            "sha256_normalization": "LF newline-normalized to match promotion fixture binding",
            "summary": _source_summary(tasks),
        })
        all_tasks.extend(tasks)
    aggregate = _source_summary(all_tasks)
    return {
        "schema": "evaluation-surface-audit/v1",
        "raw_examples_included": False,
        "scope": "Static task-spec metadata and reference-contract structure only; this is not a model score or a semantic difficulty measurement.",
        "limitations": [
            "It cannot establish model capability, semantic novelty, real-world environment fidelity, or native-benchmark performance.",
            "It does not inspect prompts, task IDs, state values, expected arguments, or reference outputs.",
            "It does not alter a task specification, evaluator, promotion decision, training run, or verifier-backed-RL gate.",
        ],
        "sources": source_reports,
        "aggregate": aggregate,
        "passed": all(source["summary"]["passed"] for source in source_reports),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-spec", action="append", required=True)
    parser.add_argument("--source-label", action="append", help="portable label to publish instead of a local path")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        report = audit(
            [Path(item) for item in args.task_spec],
            source_labels=args.source_label,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({
        "passed": report["passed"],
        "sources": len(report["sources"]),
        "output": str(output),
    }, indent=2, sort_keys=True))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
