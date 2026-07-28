"""Independent replay audit for real-model harness reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from traces.replay import load_jsonl


def verify_real_report(report: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for row in report.get("rows", []):
        trace = load_jsonl(str(row.get("trace_jsonl", "")).splitlines())
        issues = trace.validate(require_end=True)
        rows.append({
            "model": row.get("model"),
            "variant": row.get("variant"),
            "seed": row.get("seed"),
            "task_id": row.get("task_id"),
            "trace_valid": not issues,
            "issues": issues,
            "reported_protocol_valid": bool(row.get("protocol_valid")),
            "reported_success": bool(row.get("verified_success")),
        })
    total = len(rows)
    return {
        "schema": "independent-real-report-verification/v0",
        "row_count": total,
        "trace_valid_rate": sum(row["trace_valid"] for row in rows) / total if total else 0.0,
        "reported_protocol_valid_rate": sum(row["reported_protocol_valid"] for row in rows) / total if total else 0.0,
        "reported_success_rate": sum(row["reported_success"] for row in rows) / total if total else 0.0,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    result = verify_real_report(report)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("row_count", "trace_valid_rate", "reported_protocol_valid_rate", "reported_success_rate")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
