"""Score partial progress and cross-seed reliability without changing evaluation semantics."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


def _events(row: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in str(row.get("trace_jsonl") or "").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _verified_action_count(row: dict[str, Any]) -> int:
    return sum(
        1
        for event in _events(row)
        if event.get("event_type") == "tool_call"
        and (event.get("payload") or {}).get("status") == "verified"
        and (event.get("payload") or {}).get("tool")
    )


def _result_ok(row: dict[str, Any]) -> bool:
    independent = row.get("independent") or {}
    if isinstance(independent, dict) and "expected_result_ok" in independent:
        return bool(independent["expected_result_ok"])
    return bool(row.get("verified_success"))


def row_metrics(row: dict[str, Any]) -> dict[str, Any]:
    """Return frozen, interpretable progress components for one recorded row.

    The score is intentionally not used by the promotion gate. It is a dense
    diagnostic inspired by long-horizon benchmark practice: a trajectory gets
    credit for valid protocol execution, independently verified action progress,
    and an independently checked final result. Each component is bounded in
    [0, 1], and safety/replay metrics remain separate hard constraints.
    """

    expected_actions = max(0, int(row.get("expected_action_count") or 0))
    verified_actions = _verified_action_count(row)
    action_progress = (
        1.0 if expected_actions == 0 else min(1.0, verified_actions / expected_actions)
    )
    independent = row.get("independent") or {}
    verified_evidence = 0
    if isinstance(independent, dict):
        verified_evidence = max(0, int(independent.get("independent_verified_evidence") or 0))
    evidence_progress = (
        1.0 if expected_actions == 0 else min(1.0, verified_evidence / expected_actions)
    )
    protocol = 1.0 if bool(row.get("protocol_valid")) else 0.0
    result = 1.0 if _result_ok(row) else 0.0
    partial_utility = mean((protocol, action_progress, evidence_progress, result))
    return {
        "task_id": row.get("task_id"),
        "family": row.get("family"),
        "verified_success": bool(row.get("verified_success")),
        "protocol_valid": bool(row.get("protocol_valid")),
        "verified_actions": verified_actions,
        "expected_actions": expected_actions,
        "verified_evidence": verified_evidence,
        "action_progress": action_progress,
        "evidence_progress": evidence_progress,
        "result_ok": bool(result),
        "partial_utility": partial_utility,
        "unsafe_attempt": bool(row.get("unsafe_attempt")),
        "unknown_action_attempts": int(row.get("unknown_action_attempts") or 0),
        "unverified_action_attempts": int(row.get("unverified_action_attempts") or 0),
        "trace_valid": bool((independent or {}).get("trace_valid", False)),
        "runtime_replay_agreement": bool((independent or {}).get("matches_runtime", False)),
    }


def _run_summary(run: dict[str, Any]) -> dict[str, Any]:
    rows = [row_metrics(row) for row in run.get("rows") or []]
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_family[str(row.get("family") or "unknown")].append(row)

    def avg(items: list[dict[str, Any]], key: str) -> float:
        return mean(float(item[key]) for item in items) if items else 0.0

    return {
        "task_spec": run.get("task_spec"),
        "seed": run.get("seed"),
        "complete": bool(run.get("complete")),
        "rows_observed": len(rows),
        "verified_successes": int(run.get("verified_successes") or 0),
        "unsafe_attempts": int(run.get("unsafe_attempts") or 0),
        "unknown_action_attempts": int(run.get("unknown_action_attempts") or 0),
        "unverified_action_attempts": int(run.get("unverified_action_attempts") or 0),
        "trace_valid_rate": float(run.get("trace_valid_rate") or 0.0),
        "runtime_replay_agreement": float(run.get("runtime_replay_agreement") or 0.0),
        "partial_utility_mean": avg(rows, "partial_utility"),
        "action_progress_mean": avg(rows, "action_progress"),
        "evidence_progress_mean": avg(rows, "evidence_progress"),
        "result_ok_rate": avg(rows, "result_ok"),
        "by_family": {
            family: {
                "rows": len(items),
                "verified_success_rate": avg(items, "verified_success"),
                "partial_utility_mean": avg(items, "partial_utility"),
                "action_progress_mean": avg(items, "action_progress"),
                "evidence_progress_mean": avg(items, "evidence_progress"),
                "result_ok_rate": avg(items, "result_ok"),
            }
            for family, items in sorted(by_family.items())
        },
    }


def _cross_seed_summary(runs: list[dict[str, Any]], expected_seeds: list[int]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for run in runs:
        if not bool(run.get("complete")):
            continue
        task_spec = str(run.get("task_spec"))
        for row in run.get("rows") or []:
            grouped[task_spec][str(row.get("task_id"))].append(bool(row.get("verified_success")))
    result: list[dict[str, Any]] = []
    for task_spec, tasks in sorted(grouped.items()):
        eligible = [values for values in tasks.values() if len(values) == len(expected_seeds)]
        if not eligible:
            continue
        result.append({
            "task_spec": task_spec,
            "expected_seeds": expected_seeds,
            "eligible_tasks": len(eligible),
            "mean_task_success_rate": mean(mean(values) for values in eligible),
            "pass_at_k": mean(all(values) for values in eligible),
            "worst_seed_success_rate": mean(min(values) for values in eligible),
        })
    return result


def analyze(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    seeds = [int(seed) for seed in data.get("seeds") or []]
    return {
        "schema": "agent-dense-reliability/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(path),
        "partial": path.name.endswith(".partial.json"),
        "runs": [_run_summary(run) for run in data.get("runs") or []],
        "cross_seed": _cross_seed_summary(list(data.get("runs") or []), seeds),
        "score_definition": {
            "partial_utility": "mean(protocol_valid, action_progress, evidence_progress, result_ok)",
            "action_progress": "min(1, independently_verified_tool_calls / expected_action_count), or 1 when no action is expected",
            "evidence_progress": "min(1, independently_verified_evidence / expected_action_count), or 1 when no action is expected",
            "pass_at_k": "fraction of eligible task IDs successful on every completed seed",
            "worst_seed_success_rate": "mean over eligible task IDs of the worst completed-seed outcome",
        },
        "limitations": [
            "This dense diagnostic does not replace the binary promotion gate.",
            "Partial utility is a progress measure, not a human-validated utility score.",
            "Cross-seed statistics exclude incomplete runs and tasks without every expected seed.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = analyze(Path(args.matrix))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema": result["schema"], "runs": len(result["runs"]), "output": str(output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
