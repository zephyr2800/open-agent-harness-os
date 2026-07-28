"""Build the disjoint Qwopus remediation curriculum.

The remediation deliberately combines two observed 9B failure modes: exact
payload contamination and failure to stop after independently verified work.
The source files are synthetic and are kept separate from all frozen holdouts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FORBIDDEN_MARKERS = ("research-v4", "research-v2", "industry-proxy", "external-bar")


def _read(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def build_rows(finish_path: Path, exact_path: Path, policy_path: Path | None = None) -> list[dict[str, Any]]:
    finish = _read(finish_path)
    exact = _read(exact_path)
    policy = _read(policy_path) if policy_path is not None else []
    rows = finish + exact + policy
    if not rows:
        raise ValueError("remediation curriculum is empty")
    for row in rows:
        task_id = str(row.get("task_id", ""))
        provenance = row.get("provenance") or {}
        if any(marker in task_id for marker in FORBIDDEN_MARKERS):
            raise ValueError(f"holdout marker in task id: {task_id}")
        if not provenance.get("synthetic"):
            raise ValueError(f"non-synthetic remediation row: {task_id}")
        if "sampling_weight" not in provenance:
            provenance["sampling_weight"] = 8.0 if "finish_convergence" in str(provenance.get("source")) else 10.0
        provenance["remediation_mix"] = (
            "finish_convergence_plus_exact_payload_plus_policy_sequence"
            if policy_path is not None
            else "finish_convergence_plus_exact_payload"
        )
        row["provenance"] = provenance
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finish", required=True)
    parser.add_argument("--exact", required=True)
    parser.add_argument("--policy")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = build_rows(Path(args.finish), Path(args.exact), Path(args.policy) if args.policy else None)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"schema": "action-sft/v0", "examples": len(rows), "output": str(output), "synthetic": True, "mix": "finish_convergence_plus_exact_payload_plus_policy_sequence" if args.policy else "finish_convergence_plus_exact_payload"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
