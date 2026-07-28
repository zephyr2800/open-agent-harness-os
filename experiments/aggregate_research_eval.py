"""Aggregate checkpoint runs without hiding task-family failures."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable


def _wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) / total) + (z * z / (4 * total * total))) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _slice(rows: Iterable[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get(key, "unspecified")), []).append(row)
    result: dict[str, dict[str, Any]] = {}
    for name, group in sorted(groups.items()):
        total = len(group)
        successes = sum(bool(row.get("verified_success")) for row in group)
        valid = sum(bool(row.get("protocol_valid")) for row in group)
        low, high = _wilson(successes, total)
        result[name] = {
            "count": total,
            "successes": successes,
            "success_rate": successes / total if total else 0.0,
            "protocol_valid_rate": valid / total if total else 0.0,
            "wilson_95_low": low,
            "wilson_95_high": high,
        }
    return result


def aggregate(reports: list[dict[str, Any]]) -> dict[str, Any]:
    all_rows: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    for report in reports:
        rows = list(report.get("rows", []))
        all_rows.extend(rows)
        total = len(rows)
        successes = sum(bool(row.get("verified_success")) for row in rows)
        valid = sum(bool(row.get("protocol_valid")) for row in rows)
        cells.append({
            "checkpoint": report.get("checkpoint"),
            "seed": report.get("seed"),
            "do_sample": bool(report.get("do_sample")),
            "task_spec_sha256": report.get("task_spec_sha256"),
            "task_count": total,
            "verified_successes": successes,
            "verified_success_rate": successes / total if total else 0.0,
            "protocol_valid_rate": valid / total if total else 0.0,
        })
    total = len(all_rows)
    successes = sum(bool(row.get("verified_success")) for row in all_rows)
    valid = sum(bool(row.get("protocol_valid")) for row in all_rows)
    adversarial = [row for row in all_rows if row.get("adversarial")]
    safety_passes = sum(bool(row.get("verified_success")) and bool(row.get("abstained")) for row in adversarial)
    unsafe_attempts = sum(bool(row.get("unsafe_attempt")) for row in all_rows)
    return {
        "schema": "project2-research-eval-aggregate/v1",
        "run_count": len(reports),
        "task_runs": total,
        "verified_successes": successes,
        "verified_success_rate": successes / total if total else 0.0,
        "protocol_valid_rate": valid / total if total else 0.0,
        "adversarial_task_runs": len(adversarial),
        "adversarial_safe_abstain_rate": safety_passes / len(adversarial) if adversarial else 0.0,
        "unsafe_attempts": unsafe_attempts,
        "unsafe_attempt_rate": unsafe_attempts / total if total else 0.0,
        "cells": cells,
        "by_family": _slice(all_rows, "family"),
        "by_difficulty": _slice(all_rows, "difficulty"),
        "by_adversarial": _slice(all_rows, "adversarial"),
    }


def to_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Project 2 Research Evaluation Aggregate",
        "",
        f"- Runs: **{result['run_count']}**; task-runs: **{result['task_runs']}**",
        f"- Verified success: **{result['verified_successes']}/{result['task_runs']}** ({result['verified_success_rate']:.1%})",
        f"- Protocol-valid rate: **{result['protocol_valid_rate']:.1%}**",
        f"- Adversarial safe-abstain rate: **{result['adversarial_safe_abstain_rate']:.1%}** over {result['adversarial_task_runs']} runs",
        f"- Unsafe high-risk attempts observed: **{result['unsafe_attempts']}** ({result['unsafe_attempt_rate']:.1%} of task-runs)",
        "",
        "## Per-run cells",
        "",
        "| Seed | Sampling | Tasks | Success | Protocol | Holdout hash |",
        "|---:|:---:|---:|---:|---:|:---|",
    ]
    for cell in result["cells"]:
        lines.append(f"| {cell['seed']} | {'sample' if cell['do_sample'] else 'greedy'} | {cell['task_count']} | {cell['verified_success_rate']:.1%} | {cell['protocol_valid_rate']:.1%} | `{str(cell['task_spec_sha256'])[:12]}` |")
    lines.extend(["", "## By task family", "", "| Family | N | Success | 95% Wilson interval |", "|:---|---:|---:|:---|"])
    for family, cell in result["by_family"].items():
        lines.append(f"| {family} | {cell['count']} | {cell['success_rate']:.1%} | {cell['wilson_95_low']:.1%}–{cell['wilson_95_high']:.1%} |")
    lines.extend(["", "## Interpretation", "", "The family slices and confidence intervals are the decision surface. A single aggregate score is not a launch gate: safety abstention, long-horizon completion, and independent replay agreement must be checked separately.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown-output")
    args = parser.parse_args()
    reports = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.reports]
    result = aggregate(reports)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_output:
        markdown = Path(args.markdown_output)
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(to_markdown(result), encoding="utf-8", newline="\n")
    print(json.dumps({key: result[key] for key in ("run_count", "task_runs", "verified_success_rate", "protocol_valid_rate", "adversarial_safe_abstain_rate", "unsafe_attempt_rate")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
