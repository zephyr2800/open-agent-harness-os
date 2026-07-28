"""Independently replay and audit a Project 2 checkpoint-run report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.tasks import load_tasks
from verify.independent import verify_trace


def verify(report_path: str | Path, task_spec: str | Path) -> dict:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    tasks = {task.task_id: task for task in load_tasks(task_spec)}
    rows = []
    for row in report.get("rows", []):
        task = tasks[row["task_id"]]
        independent = verify_trace(task, report.get("variant", "H3"), row["trace_jsonl"])
        independent["runtime_success"] = bool(row.get("verified_success"))
        independent["matches_runtime"] = independent["independent_success"] == independent["runtime_success"]
        rows.append(independent)
    total = len(rows)
    return {
        "schema": "independent-checkpoint-run-verification/v1",
        "source_report": str(report_path),
        "task_spec": str(task_spec),
        "task_count": total,
        "trace_valid_rate": sum(row["trace_valid"] for row in rows) / total if total else 0.0,
        "independent_success_rate": sum(row["independent_success"] for row in rows) / total if total else 0.0,
        "runtime_independent_match_rate": sum(row["matches_runtime"] for row in rows) / total if total else 0.0,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--task-spec", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = verify(args.report, args.task_spec)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("task_count", "trace_valid_rate", "independent_success_rate", "runtime_independent_match_rate")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
