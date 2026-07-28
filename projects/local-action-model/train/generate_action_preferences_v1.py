"""Create synthetic hard-negative preferences from Action IR curriculum rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _envelope(row: dict[str, Any], kind: str) -> dict[str, Any]:
    data = row["input"]
    result: dict[str, Any] = {
        "schema": "action-ir/v0",
        "task_id": data["task_id"],
        "step_id": f"step-{data.get('state', {}).get('harness_step', 0)}",
        "kind": kind,
        "uncertainty": {"confidence": 0.1, "basis": "synthetic hard negative"},
        "state_update": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
    }
    if kind == "finish":
        result["finish"] = {"result": "premature completion", "evidence": [], "verified": True}
    else:
        result["abstention"] = {"reason": "synthetic hard negative", "alternatives": ["continue with the permitted action"]}
    return result


def build_preferences(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preferences: list[dict[str, Any]] = []
    for row in rows:
        target = row.get("target", {})
        kind = target.get("kind")
        if kind not in {"act", "finish", "abstain"}:
            continue
        if kind == "act":
            rejected = _envelope(row, "finish")
            reason = "premature finish without verifier evidence"
        elif kind == "finish":
            rejected = _envelope(row, "abstain")
            reason = "unnecessary abstention after independent evidence"
        else:
            rejected = _envelope(row, "finish")
            reason = "unsafe completion without approved capability or authorization"
        preferences.append({
            "schema": "action-preference/v0",
            "task_id": row["task_id"],
            "input": row["input"],
            "chosen": target,
            "rejected": rejected,
            "rejected_reason": reason,
            "provenance": {"source": "synthetic_curriculum_hard_negative", "synthetic": True, "holdout_excluded": "research-v2-independent-holdout"},
        })
    return preferences


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.input).read_text(encoding="utf-8").splitlines() if line.strip()]
    preferences = build_preferences(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in preferences:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"schema": "action-preference/v0", "examples": len(preferences), "output": str(output), "synthetic": True, "holdout_excluded": "research-v2-independent-holdout"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
