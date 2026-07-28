"""Select remediation strata from a completed frozen matrix.

This is deliberately a data-selection helper, not an evaluator.  It reads
failure observations from a completed matrix and selects only provenance-tagged
synthetic remediation rows whose stratum matches an observed failure family.
The evaluator and all holdout task specifications remain immutable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STRATA_BY_CATEGORY = {
    "finish_evidence_failure": "verified_finish_convergence",
    "exact_payload_contamination": "exact_payload_fidelity",
    "repeated_verified_action": "policy_sequence_recovery",
    "step_budget_exhaustion": "policy_sequence_recovery",
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row {line_number} is not an object")
            rows.append(value)
    return rows


def _observed_categories(matrix: dict[str, Any]) -> set[str]:
    categories: set[str] = set()
    for run in matrix.get("runs", []):
        for row in run.get("rows", []):
            if bool(row.get("verified_success")):
                continue
            error = str(row.get("error", "")).lower()
            task_id = str(row.get("task_id", "")).lower()
            family = str(row.get("family", "")).lower()
            if bool(row.get("false_completion")) or "finish" in error or "finish" in task_id:
                categories.add("finish_evidence_failure")
            if "payload" in error or "exact" in family or "write" in task_id:
                categories.add("exact_payload_contamination")
            if "repeat" in error or "budget" in error or int(row.get("expected_action_count", 0)) > 1:
                categories.add("repeated_verified_action")
                categories.add("step_budget_exhaustion")
    return categories


def select_rows(matrix: dict[str, Any], source_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    categories = _observed_categories(matrix)
    strata = {STRATA_BY_CATEGORY[item] for item in categories if item in STRATA_BY_CATEGORY}
    frozen_ids = {
        str(row.get("task_id"))
        for run in matrix.get("runs", [])
        for row in run.get("rows", [])
        if row.get("task_id")
    }
    selected = [
        row
        for row in source_rows
        if str(row.get("provenance", {}).get("sampling_stratum")) in strata
        and str(row.get("task_id")) not in frozen_ids
    ]
    manifest = {
        "schema": "failure-target-selection/v1",
        "observed_categories": sorted(categories),
        "selected_strata": sorted(strata),
        "source_rows": len(source_rows),
        "selected_rows": len(selected),
        "frozen_task_ids_excluded": len(frozen_ids),
        "evaluator_mutation": False,
    }
    return selected, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    source_rows = _load_jsonl(args.source)
    selected, manifest = select_rows(matrix, source_rows)
    if not selected:
        raise SystemExit("no remediation rows match observed failure families")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
