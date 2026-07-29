"""Classify observed agent failures without changing evaluator semantics."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _events(row: dict[str, Any]) -> list[dict[str, Any]]:
    raw = row.get("trace_jsonl") or ""
    events: list[dict[str, Any]] = []
    for line in str(raw).splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _categories(row: dict[str, Any]) -> list[str]:
    categories: set[str] = set()
    error = str(row.get("error") or "").lower()
    events = _events(row)
    for event in events:
        if event.get("event_type") != "tool_call":
            continue
        payload = event.get("payload") or {}
        arguments = payload.get("arguments") or {}
        content = str(arguments.get("content") or "")
        if "STATE_DIGEST:" in content or "state_digest:" in content:
            categories.add("exact_payload_contamination")
    finish_has_independent_evidence = any(
        event.get("event_type") == "verification"
        and bool((event.get("payload") or {}).get("independent_evidence"))
        for event in events
    )
    finish_result_mismatch = any(
        event.get("event_type") == "verification"
        and (event.get("payload") or {}).get("expected_result") is False
        for event in events
    )
    if "finish lacked independent verified evidence" in error and not finish_has_independent_evidence:
        categories.add("finish_evidence_failure")
    if finish_has_independent_evidence and finish_result_mismatch:
        categories.add("finish_result_mismatch")
    if "step budget exhausted" in error:
        categories.add("step_budget_exhaustion")
    serialized = json.dumps(events, ensure_ascii=False).lower()
    if int(row.get("unverified_action_attempts") or 0) > 0 or "unverified action" in error or "unverified_action_attempt" in serialized:
        categories.add("unverified_action")
    if row.get("unsafe_attempt"):
        categories.add("unsafe_attempt")

    verified_tools: list[str] = []
    repeated_after_verification = False
    for event in events:
        if event.get("event_type") == "tool_call":
            payload = event.get("payload") or {}
            if payload.get("status") == "verified" and payload.get("tool"):
                verified_tools.append(str(payload["tool"]))
        if event.get("event_type") == "decision":
            decision = (event.get("payload") or {}).get("decision") or {}
            action = decision.get("action") or {}
            intent = action.get("intent")
            if intent and verified_tools and str(intent) == verified_tools[-1] and decision.get("kind") == "act":
                repeated_after_verification = True
    if repeated_after_verification:
        categories.add("repeated_verified_action")
    return sorted(categories)


def analyze(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    runs: list[dict[str, Any]] = []
    for run in data.get("runs", []):
        counts: Counter[str] = Counter()
        rows = list(run.get("rows") or [])
        for row in rows:
            for category in _categories(row):
                counts[category] += 1
        runs.append({
            "task_spec": run.get("task_spec"),
            "seed": run.get("seed"),
            "complete": bool(run.get("complete")),
            "task_count": run.get("task_count"),
            "rows_observed": len(rows),
            "verified_successes": run.get("verified_successes"),
            "unsafe_attempts": run.get("unsafe_attempts"),
            "failure_categories": dict(sorted(counts.items())),
        })
    return {
        "schema": "agent-failure-taxonomy/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(path),
        "partial": path.name.endswith(".partial.json"),
        "runs": runs,
        "limitations": ["Categories are diagnostic labels over recorded traces, not causal proof", "A row may have more than one category", "Native external-suite failure taxonomies remain separate"],
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
