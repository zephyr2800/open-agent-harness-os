"""Summarize a promotion-matrix JSON into auditable research tables."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable


def _wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt((p * (1.0 - p) / total) + (z * z / (4.0 * total * total))) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _percentile(values: Iterable[float], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def _row_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    successes = sum(bool(row.get("verified_success")) for row in rows)
    protocol_valid = sum(bool(row.get("protocol_valid")) for row in rows)
    independent_successes = sum(
        bool((row.get("independent") or {}).get("independent_success")) for row in rows
    )
    trace_valid = sum(bool((row.get("independent") or {}).get("trace_valid")) for row in rows)
    agreements = sum(
        bool((row.get("independent") or {}).get("matches_runtime"))
        if "matches_runtime" in (row.get("independent") or {})
        else bool((row.get("independent") or {}).get("independent_success")) == bool(row.get("verified_success"))
        for row in rows
    )
    unsafe = sum(bool(row.get("unsafe_attempt")) for row in rows)
    false_completions = sum(bool(row.get("false_completion")) for row in rows)
    unverified_actions = sum(int(row.get("unverified_action_attempts", 0) or 0) for row in rows)
    unknown_actions = sum(int(row.get("unknown_action_attempts", 0) or 0) for row in rows)
    premature_finish_rejections = sum(int(row.get("premature_finish_rejections", 0) or 0) for row in rows)
    abstentions = sum(bool(row.get("abstained")) for row in rows)
    low, high = _wilson(successes, total)
    return {
        "tasks": total,
        "verified_successes": successes,
        "verified_success_rate": successes / total if total else 0.0,
        "wilson_95_low": low,
        "wilson_95_high": high,
        "protocol_valid_rate": protocol_valid / total if total else 0.0,
        "independent_success_rate": independent_successes / total if total else 0.0,
        "trace_valid_rate": trace_valid / total if total else 0.0,
        "runtime_replay_agreement": agreements / total if total else 0.0,
        "unsafe_attempts": unsafe,
        "false_completions": false_completions,
        "false_completion_rate": false_completions / total if total else 0.0,
        "unverified_action_attempts": unverified_actions,
        "unknown_action_attempts": unknown_actions,
        "premature_finish_rejections": premature_finish_rejections,
        "abstentions": abstentions,
    }


def summarize(matrix: dict[str, Any]) -> dict[str, Any]:
    runs = list(matrix.get("runs", []))
    rows: list[dict[str, Any]] = []
    run_summaries: list[dict[str, Any]] = []
    all_latencies: list[float] = []
    max_allocated = 0
    max_reserved = 0
    runtimes: list[dict[str, Any]] = []

    for run in runs:
        run_rows = list(run.get("rows", []))
        task_spec = str(run.get("task_spec", ""))
        seed = run.get("seed")
        for row in run_rows:
            enriched = dict(row)
            enriched["task_spec"] = task_spec
            enriched["seed"] = seed
            rows.append(enriched)
            if isinstance(row.get("elapsed_seconds"), (int, float)):
                all_latencies.append(float(row["elapsed_seconds"]))
        metrics = _row_metrics(run_rows)
        runtime = dict(run.get("runtime") or {})
        max_allocated = max(max_allocated, int(runtime.get("max_memory_allocated_bytes", 0) or 0))
        max_reserved = max(max_reserved, int(runtime.get("max_memory_reserved_bytes", 0) or 0))
        runtimes.append(runtime)
        run_summaries.append({
            "task_spec": task_spec,
            "seed": seed,
            "do_sample": bool(run.get("do_sample")),
            "task_spec_sha256": run.get("task_spec_sha256"),
            "elapsed_seconds": float(run.get("elapsed_seconds", 0.0) or 0.0),
            "resource": runtime,
            **metrics,
        })

    def grouped(key: str) -> dict[str, dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            groups.setdefault(str(row.get(key, "unspecified")), []).append(row)
        return {name: _row_metrics(group) for name, group in sorted(groups.items())}

    overall = _row_metrics(rows)
    devices = sorted({str(runtime.get("device")) for runtime in runtimes if runtime.get("device")})
    cuda_versions = sorted({str(runtime.get("cuda")) for runtime in runtimes if runtime.get("cuda")})
    return {
        "schema": "project2-matrix-summary/v1",
        "matrix_schema": matrix.get("schema"),
        "checkpoint": matrix.get("checkpoint"),
        "seeds": matrix.get("seeds", []),
        "task_specs": matrix.get("task_specs", []),
        "max_new_tokens": matrix.get("max_new_tokens"),
        "run_count": len(runs),
        "overall": overall,
        "runs": run_summaries,
        "by_task_spec": grouped("task_spec"),
        "by_family": grouped("family"),
        "by_difficulty": grouped("difficulty"),
        "resource": {
            "devices": devices,
            "cuda_versions": cuda_versions,
            "max_memory_allocated_bytes": max_allocated,
            "max_memory_reserved_bytes": max_reserved,
            "total_matrix_seconds": sum(item["elapsed_seconds"] for item in run_summaries),
            "task_latency_seconds_p50": _percentile(all_latencies, 0.50),
            "task_latency_seconds_p95": _percentile(all_latencies, 0.95),
            "task_latency_seconds_max": max(all_latencies, default=0.0),
        },
    }


def _pct(value: float) -> str:
    return f"{value:.1%}"


def to_markdown(summary: dict[str, Any], title: str = "Promotion Matrix Summary") -> str:
    overall = summary["overall"]
    resource = summary["resource"]
    lines = [
        f"# {title}",
        "",
        f"- Checkpoint: `{summary.get('checkpoint')}`",
        f"- Runs: **{summary['run_count']}**; task-runs: **{overall['tasks']}**",
        f"- Verified success: **{overall['verified_successes']}/{overall['tasks']}** ({_pct(overall['verified_success_rate'])}); 95% Wilson interval **{_pct(overall['wilson_95_low'])}–{_pct(overall['wilson_95_high'])}**",
        f"- Protocol-valid: **{_pct(overall['protocol_valid_rate'])}**; independent success: **{_pct(overall['independent_success_rate'])}**",
        f"- Replay agreement: **{_pct(overall['runtime_replay_agreement'])}**; trace-valid: **{_pct(overall['trace_valid_rate'])}**; unsafe attempts: **{overall['unsafe_attempts']}**",
        f"- False completions: **{overall['false_completions']}** ({_pct(overall['false_completion_rate'])}); unverified/unknown actions: **{overall['unverified_action_attempts']}/{overall['unknown_action_attempts']}**; premature finish rejections: **{overall['premature_finish_rejections']}**; abstentions: **{overall['abstentions']}**",
        "",
        "## Run cells",
        "",
        "| Seed | Task spec | Tasks | Success | Replay | Unsafe | Seconds | Peak reserved MiB |",
        "|---:|:---|---:|---:|---:|---:|---:|---:|",
    ]
    for run in summary["runs"]:
        peak = int(run["resource"].get("max_memory_reserved_bytes", 0) or 0) / (1024 * 1024)
        lines.append(
            f"| {run['seed']} | `{Path(run['task_spec']).name}` | {run['tasks']} | {_pct(run['verified_success_rate'])} | {_pct(run['runtime_replay_agreement'])} | {run['unsafe_attempts']} | {run['elapsed_seconds']:.1f} | {peak:.0f} |"
        )
    lines.extend([
        "",
        "## By family",
        "",
        "| Family | N | Success | 95% Wilson interval | Protocol | Replay | False finish | Unsafe |",
        "|:---|---:|---:|:---|---:|---:|---:|---:|",
    ])
    for family, metrics in summary["by_family"].items():
        lines.append(
            f"| {family} | {metrics['tasks']} | {_pct(metrics['verified_success_rate'])} | {_pct(metrics['wilson_95_low'])}–{_pct(metrics['wilson_95_high'])} | {_pct(metrics['protocol_valid_rate'])} | {_pct(metrics['runtime_replay_agreement'])} | {metrics['false_completions']} | {metrics['unsafe_attempts']} |"
        )
    lines.extend([
        "",
        "## Resource report",
        "",
        f"- Devices: {', '.join(resource['devices']) or 'not recorded'}",
        f"- CUDA versions: {', '.join(resource['cuda_versions']) or 'not recorded'}",
        f"- Maximum allocated/reserved memory: {resource['max_memory_allocated_bytes'] / (1024 * 1024):.0f}/{resource['max_memory_reserved_bytes'] / (1024 * 1024):.0f} MiB",
        f"- Task latency p50/p95/max: {resource['task_latency_seconds_p50']:.3f}/{resource['task_latency_seconds_p95']:.3f}/{resource['task_latency_seconds_max']:.3f} seconds",
        f"- Matrix wall-time sum: {resource['total_matrix_seconds'] / 3600:.2f} hours",
        "",
        "These are model-and-harness measurements for the named task specifications; they are not external benchmark scores.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown-output")
    args = parser.parse_args()
    matrix = json.loads(Path(args.matrix).read_text(encoding="utf-8"))
    summary = summarize(matrix)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_output:
        markdown = Path(args.markdown_output)
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(to_markdown(summary), encoding="utf-8", newline="\n")
    print(json.dumps({
        "run_count": summary["run_count"],
        "task_runs": summary["overall"]["tasks"],
        "verified_success_rate": summary["overall"]["verified_success_rate"],
        "runtime_replay_agreement": summary["overall"]["runtime_replay_agreement"],
        "unsafe_attempts": summary["overall"]["unsafe_attempts"],
        "false_completions": summary["overall"]["false_completions"],
        "unverified_action_attempts": summary["overall"]["unverified_action_attempts"],
        "unknown_action_attempts": summary["overall"]["unknown_action_attempts"],
        "output": str(output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
