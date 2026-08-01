"""Run a matched-budget task-level search control.

This is a deliberately explicit control for harness-evolution studies.  It
spends the same total step and generation budgets as one model-only episode,
splits that budget across independent model-only attempts, and lets an
immutable verifier choose the best recorded attempt.  It is an evaluation
baseline, not a production harness and not evidence of general autonomy.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from adapters.project1_transformers import Project1TransformersAdapter
from benchmarks.tasks import Task, load_tasks
from experiments.run_promotion_matrix import _runtime_manifest, _sha256, _write_json_atomic
from runtime.orchestrator import Harness, HarnessConfig, TaskRequest
from tools.memory_workspace import make_memory_registry
from verify.independent import verify_trace


def matched_budget(*, attempts: int, max_steps: int, max_new_tokens: int) -> dict[str, int]:
    """Return per-attempt caps that never exceed the total control budget."""

    if attempts < 1:
        raise ValueError("attempts must be positive")
    if max_steps < attempts:
        raise ValueError("max_steps must be at least attempts")
    if max_new_tokens < attempts:
        raise ValueError("max_new_tokens must be at least attempts")
    return {
        "attempts": attempts,
        "total_max_steps": max_steps,
        "total_max_new_tokens": max_new_tokens,
        "max_steps_per_attempt": max_steps // attempts,
        "max_new_tokens_per_attempt": max_new_tokens // attempts,
    }


def _request(task: Task) -> TaskRequest:
    return TaskRequest(
        task.task_id,
        task.prompt,
        task.available_tools,
        task.output_token_budget,
        task.expected_kind,
        task.expected_tool,
        task.expected_arguments,
        task.split,
        task.expected_tools,
        task.expected_actions,
        task.expected_files,
        task.expected_result_contains,
    )


def _attempt_row(task: Task, result: Any, independent: dict[str, Any], attempt: int) -> dict[str, Any]:
    tool_calls = [event for event in result.trace.events if event.event_type == "tool_call"]
    unsafe_attempt = any(
        event.payload.get("tool") == "delete_file" for event in tool_calls
    )
    false_completion = any(
        event.event_type == "trajectory_end"
        and event.payload.get("reason") == "finish"
        and not bool(event.payload.get("verified_success"))
        for event in result.trace.events
    )
    return {
        "attempt": attempt,
        "protocol_valid": result.protocol_valid,
        "verified_success": result.verified_success,
        "independent_success": bool(independent["independent_success"]),
        "trace_valid": bool(independent["trace_valid"]),
        "unsafe_attempt": unsafe_attempt,
        "false_completion": false_completion,
        "unverified_action_attempts": sum(
            1 for event in tool_calls if event.payload.get("status") != "verified"
        ),
        "unknown_action_attempts": sum(
            1 for event in tool_calls if event.payload.get("tool") not in task.available_tools
        ),
        "elapsed_seconds": result.metrics.get("tool_time_ms", 0.0),
        "metrics": dict(result.metrics),
        "trace_jsonl": result.trace_jsonl,
        "independent": independent,
        "error": result.error,
    }


def _run_task(
    adapter: Project1TransformersAdapter,
    checkpoint: Path,
    task: Task,
    *,
    budget: dict[str, int],
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for attempt in range(budget["attempts"]):
        _, registry = make_memory_registry(
            task.initial_files,
            api_records=task.api_records,
            browser_pages=task.browser_pages,
        )
        harness = Harness(
            adapter,
            registry,
            config=HarnessConfig(
                variant="H3",
                model_name=str(checkpoint),
                max_steps=budget["max_steps_per_attempt"],
                expose_contract_hints=False,
                include_tool_outputs=task.include_tool_outputs,
            ),
        )
        result = harness.run(_request(task))
        independent = verify_trace(task, "H3", result.trace_jsonl)
        attempts.append(_attempt_row(task, result, independent, attempt))

    # This selection is intentionally verifier-owned.  It makes the baseline
    # a generous test-time-search control while keeping the selector immutable
    # and visible in the report.
    selected = next(
        (item for item in attempts if item["independent_success"]),
        attempts[0],
    )
    return {
        "task_id": task.task_id,
        "family": task.family,
        "difficulty": task.difficulty,
        "adversarial": task.adversarial,
        "selected_attempt": selected["attempt"],
        "selected_independent_success": selected["independent_success"],
        "selected_verified_success": selected["verified_success"],
        "attempt_count": len(attempts),
        "attempts": attempts,
        "unsafe_attempts": sum(int(item["unsafe_attempt"]) for item in attempts),
        "false_completions": sum(int(item["false_completion"]) for item in attempts),
        "unverified_action_attempts": sum(item["unverified_action_attempts"] for item in attempts),
        "unknown_action_attempts": sum(item["unknown_action_attempts"] for item in attempts),
    }


def _run_report(
    task_spec: Path,
    *,
    seed: int,
    checkpoint: Path,
    budget: dict[str, int],
    rows: list[dict[str, Any]],
    complete: bool,
    active_task_id: str | None = None,
) -> dict[str, Any]:
    selected_successes = sum(int(row["selected_independent_success"]) for row in rows)
    attempts = sum(int(row["attempt_count"]) for row in rows)
    report: dict[str, Any] = {
        "schema": "task-search-control/v1-partial" if not complete else "task-search-control/v1",
        "task_spec": str(task_spec),
        "task_spec_sha256": _sha256(task_spec),
        "checkpoint": str(checkpoint),
        "seed": seed,
        "search_selector": "immutable_independent_verifier_first_success",
        "budget": budget,
        "matched_budget": attempts <= len(rows) * budget["attempts"] and all(
            budget["max_steps_per_attempt"] * budget["attempts"] <= budget["total_max_steps"]
            and budget["max_new_tokens_per_attempt"] * budget["attempts"] <= budget["total_max_new_tokens"]
            for _ in (0,)
        ),
        "complete": complete,
        "task_count": len(rows),
        "search_attempts": attempts,
        "selected_independent_successes": selected_successes,
        "selected_independent_success_rate": selected_successes / len(rows) if rows else 0.0,
        "unsafe_attempts": sum(row["unsafe_attempts"] for row in rows),
        "false_completions": sum(row["false_completions"] for row in rows),
        "unverified_action_attempts": sum(row["unverified_action_attempts"] for row in rows),
        "unknown_action_attempts": sum(row["unknown_action_attempts"] for row in rows),
        "runtime": _runtime_manifest(),
        "limitations": [
            "verifier-selected search is an intentionally generous test-time-search control",
            "the selector is not available to a deployed agent",
            "native external evaluation remains required",
        ],
        "rows": rows,
    }
    if active_task_id is not None:
        report["active_task_id"] = active_task_id
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project1-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--task-spec", action="append", required=True)
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--quantization", choices=("4bit", "int4", "nf4"))
    parser.add_argument("--checkpoint-every-tasks", type=int, default=5)
    args = parser.parse_args()
    if args.checkpoint_every_tasks < 1:
        parser.error("--checkpoint-every-tasks must be positive")
    project1_root = Path(args.project1_root)
    checkpoint = Path(args.checkpoint)
    task_specs = [Path(item) for item in args.task_spec]
    seeds = [int(item.strip()) for item in args.seeds.split(",") if item.strip()]
    budget = matched_budget(
        attempts=args.attempts,
        max_steps=args.max_steps,
        max_new_tokens=args.max_new_tokens,
    )
    output = Path(args.output)
    partial = output.with_name(output.name + ".partial.json")
    runs: list[dict[str, Any]] = []
    if partial.exists():
        try:
            saved = json.loads(partial.read_text(encoding="utf-8"))
            compatible = (
                saved.get("schema") == "task-search-control/v1-partial"
                and saved.get("checkpoint") == str(checkpoint)
                and saved.get("seeds") == seeds
                and saved.get("task_specs") == [str(path) for path in task_specs]
                and saved.get("budget") == budget
                and saved.get("quantization") == args.quantization
            )
            if compatible:
                runs = list(saved.get("runs", []))
        except (OSError, ValueError, TypeError):
            runs = []
    completed = {
        (int(item.get("seed")), str(item.get("task_spec")))
        for item in runs
        if bool(item.get("complete"))
    }

    def persist(run: dict[str, Any]) -> None:
        key = (int(run["seed"]), str(run["task_spec"]))
        runs[:] = [
            item for item in runs
            if (int(item.get("seed", -1)), str(item.get("task_spec"))) != key
        ]
        runs.append(run)
        _write_json_atomic(partial, {
            "schema": "task-search-control/v1-partial",
            "checkpoint": str(checkpoint),
            "seeds": seeds,
            "task_specs": [str(path) for path in task_specs],
            "budget": budget,
            "quantization": args.quantization,
            "runs": runs,
        })

    adapter: Project1TransformersAdapter | None = None
    if args.quantization is not None:
        os.environ["ACTION_MODEL_QUANTIZATION"] = args.quantization
    for seed in seeds:
        if adapter is not None:
            del adapter
            adapter = None
            gc.collect()
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
        adapter = Project1TransformersAdapter(
            project1_root,
            model_id=str(checkpoint),
            revision="main",
            seed=seed,
            do_sample=True,
            enable_repair=False,
            max_new_tokens=budget["max_new_tokens_per_attempt"],
            quantization=args.quantization,
        )
        for task_spec in task_specs:
            key = (seed, str(task_spec))
            if key in completed:
                continue
            tasks = load_tasks(task_spec)
            saved = next(
                (item for item in runs if (int(item.get("seed", -1)), str(item.get("task_spec"))) == key),
                None,
            )
            rows = list(saved.get("rows", [])) if saved else []
            if len(rows) > len(tasks):
                raise ValueError(f"resume rows exceed task count for {task_spec}")
            for task_index in range(len(rows), len(tasks)):
                row = _run_task(adapter, checkpoint, tasks[task_index], budget=budget)
                rows.append(row)
                if len(rows) % args.checkpoint_every_tasks == 0:
                    persist(_run_report(task_spec, seed=seed, checkpoint=checkpoint, budget=budget, rows=rows, complete=False, active_task_id=tasks[task_index].task_id))
            final = _run_report(task_spec, seed=seed, checkpoint=checkpoint, budget=budget, rows=rows, complete=True)
            persist(final)
            completed.add(key)

    result = {
        "schema": "task-search-control/v1",
        "checkpoint": str(checkpoint),
        "seeds": seeds,
        "task_specs": [str(path) for path in task_specs],
        "attempts": args.attempts,
        "max_steps": args.max_steps,
        "max_new_tokens": args.max_new_tokens,
        "budget": budget,
        "quantization": args.quantization,
        "runs": runs,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "run_count": len(runs),
        "task_runs": sum(item["task_count"] for item in runs),
        "search_attempts": sum(item["search_attempts"] for item in runs),
        "selected_independent_successes": sum(item["selected_independent_successes"] for item in runs),
        "unsafe_attempts": sum(item["unsafe_attempts"] for item in runs),
        "output": str(output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
