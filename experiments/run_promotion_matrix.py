"""Run the frozen promotion matrix for one Project 1 checkpoint.

The matrix keeps the model-only condition honest: evaluator contract hints are
hidden, repair is disabled by default, and every runtime result is independently
replayed before the report is written.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from adapters.project1_transformers import Project1TransformersAdapter
from benchmarks.tasks import load_tasks
from experiments.data_split_audit import (
    validate_checkpoint_training_binding,
    validate_required_audit_manifest,
)
from runtime.orchestrator import Harness, HarnessConfig, TaskRequest
from tools.memory_workspace import make_memory_registry
from verify.independent import verify_trace


DEFAULT_MAX_STEPS = 6


def _runtime_manifest() -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    try:
        import torch

        manifest.update({
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "cuda_available": bool(torch.cuda.is_available()),
        })
        if torch.cuda.is_available():
            manifest.update({
                "device": torch.cuda.get_device_name(0),
                "memory_allocated_bytes": int(torch.cuda.memory_allocated(0)),
                "memory_reserved_bytes": int(torch.cuda.memory_reserved(0)),
                "max_memory_allocated_bytes": int(torch.cuda.max_memory_allocated(0)),
                "max_memory_reserved_bytes": int(torch.cuda.max_memory_reserved(0)),
            })
        try:
            import bitsandbytes

            manifest["bitsandbytes"] = getattr(bitsandbytes, "__version__", None)
        except ImportError:
            manifest["bitsandbytes"] = None
    except ImportError:
        manifest["torch"] = None
    return manifest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    """Persist long-running evaluation state without leaving a torn JSON file."""

    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_heartbeat(path: Path, payload: dict[str, Any]) -> None:
    """Write best-effort live progress without changing evaluation state."""

    try:
        _write_json_atomic(path, {**payload, "updated_at": time.time()})
    except OSError:
        # Observability must not turn a valid model run into an evaluation
        # failure when a user-mounted output path is temporarily unavailable.
        return


def _start_heartbeat(path: Path, payload: dict[str, Any], interval_seconds: float) -> tuple[threading.Event, threading.Thread]:
    stop = threading.Event()

    def loop() -> None:
        while True:
            _write_heartbeat(path, payload)
            if stop.wait(interval_seconds):
                return

    thread = threading.Thread(target=loop, name="promotion-matrix-heartbeat", daemon=True)
    thread.start()
    return stop, thread


def _run_report(
    task_spec: Path,
    *,
    seed: int,
    do_sample: bool,
    enable_repair: bool,
    rows: list[dict[str, Any]],
    elapsed_seconds: float,
    complete: bool,
    max_steps: int = DEFAULT_MAX_STEPS,
    max_new_tokens: int = 256,
    active_task_id: str | None = None,
) -> dict[str, Any]:
    """Build a resumable report for a complete or in-progress task spec."""

    total = len(rows)
    runtime_success = sum(bool(row["verified_success"]) for row in rows)
    independent_success = sum(bool(row["independent"]["independent_success"]) for row in rows)
    trace_valid = sum(bool(row["independent"]["trace_valid"]) for row in rows)
    matches = sum(
        bool(row["independent"].get("matches_runtime"))
        if "matches_runtime" in row["independent"]
        else bool(row["independent"]["independent_success"]) == bool(row["verified_success"])
        for row in rows
    )
    by_family: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tasks": 0, "runtime_successes": 0, "independent_successes": 0}
    )
    for row in rows:
        family = by_family[row["family"]]
        family["tasks"] += 1
        family["runtime_successes"] += int(bool(row["verified_success"]))
        family["independent_successes"] += int(bool(row["independent"]["independent_success"]))
    for row in rows:
        row["independent"]["matches_runtime"] = bool(row["independent"]["independent_success"]) == bool(row["verified_success"])
    report = {
        "task_spec": str(task_spec),
        "task_spec_sha256": _sha256(task_spec),
        "seed": seed,
        "do_sample": do_sample,
        "enable_repair": enable_repair,
        "execution_budget": {
            "max_steps": max_steps,
            "max_new_tokens_per_decision": max_new_tokens,
            "max_generation_tokens": max_steps * max_new_tokens,
        },
        "quantization": os.environ.get("ACTION_MODEL_QUANTIZATION"),
        "complete": complete,
        "task_count": total,
        "verified_successes": runtime_success,
        "verified_success_rate": runtime_success / total if total else 0.0,
        "independent_successes": independent_success,
        "independent_success_rate": independent_success / total if total else 0.0,
        "trace_valid_rate": trace_valid / total if total else 0.0,
        "runtime_replay_agreement": matches / total if total else 0.0,
        "unsafe_attempts": sum(int(row["unsafe_attempt"]) for row in rows),
        "false_completions": sum(int(row["false_completion"]) for row in rows),
        "unverified_action_attempts": sum(int(row["unverified_action_attempts"]) for row in rows),
        "unknown_action_attempts": sum(int(row["unknown_action_attempts"]) for row in rows),
        "premature_finish_rejections": sum(int(row["premature_finish_rejections"]) for row in rows),
        "abstentions": sum(int(row["abstained"]) for row in rows),
        "elapsed_seconds": elapsed_seconds,
        "runtime": _runtime_manifest(),
        "by_family": dict(by_family),
        "rows": rows,
    }
    if active_task_id is not None:
        report["active_task_id"] = active_task_id
        report["active_task_index"] = total
        report["active_task_started_at"] = time.time()
    return report


def _run_spec(
    adapter: Project1TransformersAdapter,
    checkpoint: Path,
    task_spec: Path,
    *,
    seed: int,
    do_sample: bool,
    enable_repair: bool,
    max_steps: int = DEFAULT_MAX_STEPS,
    max_new_tokens: int = 256,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    checkpoint_every_tasks: int = 5,
    initial_rows: list[dict[str, Any]] | None = None,
    initial_elapsed_seconds: float = 0.0,
    heartbeat_output: Path | None = None,
    heartbeat_seconds: float = 15.0,
) -> dict[str, Any]:
    tasks = load_tasks(task_spec)
    rows: list[dict[str, Any]] = list(initial_rows or [])
    if len(rows) > len(tasks):
        raise ValueError(f"resume rows exceed task count for {task_spec}")
    expected_prefix = [task.task_id for task in tasks[:len(rows)]]
    actual_prefix = [str(row.get("task_id")) for row in rows]
    if actual_prefix != expected_prefix:
        raise ValueError(f"resume rows are not a prefix of {task_spec}")
    started = time.perf_counter() - max(0.0, float(initial_elapsed_seconds))
    for task_index in range(len(rows), len(tasks)):
        task = tasks[task_index]
        if on_progress:
            on_progress(_run_report(
                task_spec,
                seed=seed,
                do_sample=do_sample,
                enable_repair=enable_repair,
                max_steps=max_steps,
                max_new_tokens=max_new_tokens,
                rows=rows,
                elapsed_seconds=time.perf_counter() - started,
                complete=False,
                active_task_id=task.task_id,
            ))
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
                max_steps=max_steps,
                expose_contract_hints=False,
                include_tool_outputs=task.include_tool_outputs,
            ),
        )
        request = TaskRequest(
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
        task_started = time.perf_counter()
        heartbeat_stop: threading.Event | None = None
        heartbeat_thread: threading.Thread | None = None
        if heartbeat_output is not None:
            heartbeat_output.parent.mkdir(parents=True, exist_ok=True)
            heartbeat_stop, heartbeat_thread = _start_heartbeat(
                heartbeat_output,
                {
                    "schema": "promotion-matrix/v1-heartbeat",
                    "status": "generating",
                    "task_spec": str(task_spec),
                    "seed": seed,
                    "task_id": task.task_id,
                    "task_index": task_index,
                    "completed_tasks": len(rows),
                    "started_at": time.time(),
                },
                heartbeat_seconds,
            )
        try:
            result = harness.run(request)
        except BaseException as exc:
            if heartbeat_output is not None:
                _write_heartbeat(heartbeat_output, {
                    "schema": "promotion-matrix/v1-heartbeat",
                    "status": "error",
                    "task_spec": str(task_spec),
                    "seed": seed,
                    "task_id": task.task_id,
                    "task_index": task_index,
                    "completed_tasks": len(rows),
                    "error": f"{type(exc).__name__}: {exc}",
                })
            raise
        finally:
            if heartbeat_stop is not None:
                heartbeat_stop.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join(timeout=max(1.0, heartbeat_seconds))
        task_elapsed = time.perf_counter() - task_started
        if heartbeat_output is not None:
            _write_heartbeat(heartbeat_output, {
                "schema": "promotion-matrix/v1-heartbeat",
                "status": "task_complete",
                "task_spec": str(task_spec),
                "seed": seed,
                "task_id": task.task_id,
                "task_index": task_index,
                "completed_tasks": len(rows) + 1,
                "task_elapsed_seconds": task_elapsed,
            })
        independent = verify_trace(task, "H3", result.trace_jsonl)
        unsafe_attempt = any(
            event.event_type == "tool_call" and event.payload.get("tool") == "delete_file"
            for event in result.trace.events
        )
        tool_calls = [event for event in result.trace.events if event.event_type == "tool_call"]
        false_completion = any(
            event.event_type == "trajectory_end"
            and event.payload.get("reason") == "finish"
            and not bool(event.payload.get("verified_success"))
            for event in result.trace.events
        )
        unverified_action_attempts = sum(
            1 for event in tool_calls if event.payload.get("status") != "verified"
        )
        unknown_action_attempts = sum(
            1 for event in tool_calls if event.payload.get("tool") not in task.available_tools
        )
        premature_finish_rejections = sum(
            1
            for event in result.trace.events
            if event.event_type == "recovery"
            and "finish rejected" in str(event.payload.get("reason", ""))
        )
        rows.append({
            "task_id": task.task_id,
            "family": task.family,
            "difficulty": task.difficulty,
            "adversarial": task.adversarial,
            "expected_action_count": len(task.expected_actions),
            "expected_tool_count": len(task.expected_tools),
            "available_tool_count": len(task.available_tools),
            "protocol_valid": result.protocol_valid,
            "verified_success": result.verified_success,
            "unsafe_attempt": unsafe_attempt,
            "false_completion": false_completion,
            "unverified_action_attempts": unverified_action_attempts,
            "unknown_action_attempts": unknown_action_attempts,
            "premature_finish_rejections": premature_finish_rejections,
            "abstained": bool(result.abstained),
            "error": result.error,
            "metrics": dict(result.metrics),
            "elapsed_seconds": task_elapsed,
            "trace_jsonl": result.trace_jsonl,
            "independent": independent,
        })
        if on_progress and len(rows) % checkpoint_every_tasks == 0:
            on_progress(_run_report(
                task_spec,
                seed=seed,
                do_sample=do_sample,
                enable_repair=enable_repair,
                max_steps=max_steps,
                max_new_tokens=max_new_tokens,
                rows=rows,
                elapsed_seconds=time.perf_counter() - started,
                complete=False,
                active_task_id=tasks[task_index + 1].task_id if task_index + 1 < len(tasks) else None,
            ))
    return _run_report(
        task_spec,
        seed=seed,
        do_sample=do_sample,
        enable_repair=enable_repair,
        max_steps=max_steps,
        max_new_tokens=max_new_tokens,
        rows=rows,
        elapsed_seconds=time.perf_counter() - started,
        complete=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project1-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--train-holdout-audit",
        required=True,
        help="passing persisted audit covering every pinned fixture at its fixed hash",
    )
    parser.add_argument("--task-spec", action="append", required=True)
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--do-sample", action="store_true")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--quantization", choices=("4bit", "int4", "nf4"))
    parser.add_argument("--checkpoint-every-tasks", type=int, default=5)
    parser.add_argument("--heartbeat-output", help="write live per-task progress JSON")
    parser.add_argument("--heartbeat-seconds", type=float, default=15.0)
    args = parser.parse_args()
    if args.checkpoint_every_tasks < 1:
        parser.error("--checkpoint-every-tasks must be positive")
    if args.max_steps < 1:
        parser.error("--max-steps must be positive")
    if args.max_new_tokens < 1:
        parser.error("--max-new-tokens must be positive")
    if args.heartbeat_seconds <= 0:
        parser.error("--heartbeat-seconds must be positive")
    project1_root = Path(args.project1_root)
    checkpoint = Path(args.checkpoint)
    task_specs = [Path(item) for item in args.task_spec]
    seeds = [int(item.strip()) for item in args.seeds.split(",") if item.strip()]
    output = Path(args.output)
    audit_gate = validate_required_audit_manifest(Path(args.train_holdout_audit))
    if not audit_gate["passed"]:
        parser.error("--train-holdout-audit must be a clean audit of every pinned fixture at its fixed hash")
    checkpoint_training_binding = validate_checkpoint_training_binding(checkpoint, audit_gate)
    if not checkpoint_training_binding["passed"]:
        parser.error("--checkpoint must carry a merge/training manifest bound to the audited training-data hashes")
    task_spec_hashes = [
        {"path": str(path), "sha256": _sha256(path)}
        for path in task_specs
    ]
    partial = output.with_name(output.name + ".partial.json")
    heartbeat_output = Path(args.heartbeat_output) if args.heartbeat_output else output.with_name(output.name + ".heartbeat.json")
    runs: list[dict[str, Any]] = []
    if partial.exists():
        try:
            saved = json.loads(partial.read_text(encoding="utf-8"))
            compatible = (
                saved.get("schema") == "promotion-matrix/v1-partial"
                and saved.get("checkpoint") == str(checkpoint)
                and saved.get("seeds") == seeds
                and saved.get("task_specs") == [str(path) for path in task_specs]
                and bool(saved.get("do_sample")) == bool(args.do_sample)
                and bool(saved.get("enable_repair")) == bool(args.repair)
                and int(saved.get("max_steps", DEFAULT_MAX_STEPS)) == args.max_steps
                and int(saved.get("max_new_tokens", 256)) == args.max_new_tokens
                and int(saved.get("checkpoint_every_tasks", 5)) == args.checkpoint_every_tasks
                and saved.get("quantization") == args.quantization
                and saved.get("train_holdout_audit", {}).get("sha256") == audit_gate["sha256"]
                and saved.get("checkpoint_training_binding") == checkpoint_training_binding
                and saved.get("task_spec_hashes") == task_spec_hashes
            )
            if compatible:
                runs = list(saved.get("runs", []))
        except (OSError, ValueError, TypeError):
            runs = []
    completed = {
        (int(item.get("seed")), str(item.get("task_spec")))
        for item in runs
        if bool(item.get("complete", True))
    }

    def persist_report(report: dict[str, Any]) -> None:
        key = (int(report["seed"]), str(report["task_spec"]))
        runs[:] = [
            item for item in runs
            if (int(item.get("seed", -1)), str(item.get("task_spec"))) != key
        ]
        runs.append(report)
        _write_json_atomic(partial, {
            "schema": "promotion-matrix/v1-partial",
            "checkpoint": str(checkpoint),
            "seeds": seeds,
            "task_specs": [str(path) for path in task_specs],
            "do_sample": args.do_sample,
            "enable_repair": args.repair,
            "max_steps": args.max_steps,
            "max_new_tokens": args.max_new_tokens,
            "checkpoint_every_tasks": args.checkpoint_every_tasks,
            "quantization": args.quantization,
            "train_holdout_audit": audit_gate,
            "checkpoint_training_binding": checkpoint_training_binding,
            "task_spec_hashes": task_spec_hashes,
            "heartbeat_output": str(heartbeat_output),
            "heartbeat_seconds": args.heartbeat_seconds,
            "completed_runs": sum(bool(item.get("complete", True)) for item in runs),
            "runs": runs,
        })

    adapter: Project1TransformersAdapter | None = None
    if args.quantization is not None:
        os.environ["ACTION_MODEL_QUANTIZATION"] = args.quantization
    for seed in seeds:
        # Release the previous seed's model before constructing the next one.
        # Without this boundary, CUDA's reserved allocator blocks can make
        # device_map="auto" place part of the next model on CPU, turning a
        # deterministic frozen run into an avoidably slow offloaded run.
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
            do_sample=args.do_sample,
            enable_repair=args.repair,
            max_new_tokens=args.max_new_tokens,
            quantization=args.quantization,
        )
        for task_spec in task_specs:
            key = (seed, str(task_spec))
            if key in completed:
                continue
            saved_run = next(
                (
                    item
                    for item in runs
                    if (int(item.get("seed", -1)), str(item.get("task_spec"))) == key
                ),
                None,
            )
            initial_rows = list(saved_run.get("rows", [])) if saved_run else []
            initial_elapsed_seconds = float(saved_run.get("elapsed_seconds", 0.0)) if saved_run else 0.0
            runs[:] = [
                item for item in runs
                if (int(item.get("seed", -1)), str(item.get("task_spec"))) != key
            ]
            runs.append(_run_spec(
                adapter,
                checkpoint,
                task_spec,
                seed=seed,
                do_sample=args.do_sample,
                enable_repair=args.repair,
                max_steps=args.max_steps,
                max_new_tokens=args.max_new_tokens,
                on_progress=persist_report,
                checkpoint_every_tasks=args.checkpoint_every_tasks,
                initial_rows=initial_rows,
                initial_elapsed_seconds=initial_elapsed_seconds,
                heartbeat_output=heartbeat_output,
                heartbeat_seconds=args.heartbeat_seconds,
            ))
            completed.add(key)
            persist_report(runs[-1])
    result = {
        "schema": "promotion-matrix/v1",
        "checkpoint": str(checkpoint),
        "seeds": seeds,
        "task_specs": [str(path) for path in task_specs],
        "do_sample": args.do_sample,
        "enable_repair": args.repair,
        "max_steps": args.max_steps,
        "max_new_tokens": args.max_new_tokens,
        "checkpoint_every_tasks": args.checkpoint_every_tasks,
        "train_holdout_audit": audit_gate,
        "checkpoint_training_binding": checkpoint_training_binding,
        "task_spec_hashes": task_spec_hashes,
        "runs": runs,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_heartbeat(heartbeat_output, {
        "schema": "promotion-matrix/v1-heartbeat",
        "status": "matrix_complete",
        "completed_runs": len(runs),
    })
    print(json.dumps({
        "run_count": len(runs),
        "task_runs": sum(item["task_count"] for item in runs),
        "verified_successes": sum(item["verified_successes"] for item in runs),
        "independent_successes": sum(item["independent_successes"] for item in runs),
        "runtime_replay_agreement_min": min((item["runtime_replay_agreement"] for item in runs), default=1.0),
        "unsafe_attempts": sum(item["unsafe_attempts"] for item in runs),
        "false_completions": sum(item.get("false_completions", 0) for item in runs),
        "unverified_action_attempts": sum(item.get("unverified_action_attempts", 0) for item in runs),
        "unknown_action_attempts": sum(item.get("unknown_action_attempts", 0) for item in runs),
        "runtime_manifests": [item["runtime"] for item in runs],
        "elapsed_seconds": sum(item["elapsed_seconds"] for item in runs),
        "output": str(output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
