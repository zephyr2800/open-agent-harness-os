"""Build a stratified, paraphrase-augmented Action IR curriculum.

This is deliberately a data-policy layer over the verified v1 curriculum:
every row keeps its verifier-backed target, while the input receives a
controlled instruction perturbation and an explicit sampling stratum. The
trainer can then oversample long-horizon, structured, and safety rows without
silently changing the target contract.

The target task id is rebound to the augmented input task id. This is a
protocol invariant: copying a training example's source id into a new prompt
would teach the model to emit stale ids on unseen evaluations.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from generate_action_curriculum_v1 import build_curriculum


STYLE_PREFIXES = (
    "",
    "In a bounded local workspace, ",
    "Use only the registered capabilities and wait for verification: ",
    "Follow the exact action contract; ",
    "Work conservatively and report completion only after evidence: ",
    "Operator request: ",
)


def _stratum(row: dict[str, Any]) -> tuple[str, float]:
    target = row.get("target", {})
    kind = target.get("kind")
    action = target.get("action", {}) if isinstance(target, dict) else {}
    intent = action.get("intent") if isinstance(action, dict) else None
    state = row.get("input", {}).get("state", {})
    required = state.get("required_tools", []) if isinstance(state, dict) else []
    if kind == "abstain":
        return "safety_abstain", 2.5
    if len(required) > 1:
        return "long_horizon", 2.25
    if intent in {"api_get", "browser_open"}:
        return "external_fixture", 1.75
    if intent == "retry_operation":
        return "stateful_retry", 1.5
    if intent == "write_file" and str(action.get("arguments", {}).get("path", "")).endswith(".json"):
        return "structured_artifact", 1.75
    return "single_action", 1.0


def build_curriculum_v2() -> list[dict[str, Any]]:
    base_rows = build_curriculum()
    rows: list[dict[str, Any]] = []
    for index, base in enumerate(base_rows):
        for style_index, prefix in enumerate(STYLE_PREFIXES):
            row = copy.deepcopy(base)
            input_data = row["input"]
            input_data["goal"] = prefix + input_data["goal"]
            row["task_id"] = f"v2-{index:05d}-{style_index}"
            input_data["task_id"] = row["task_id"]
            row["target"]["task_id"] = row["task_id"]
            # Evidence ids are harness-owned outputs, not facts the policy can
            # know before execution. The runtime adapter binds an empty finish
            # evidence list to the verifier-issued ids in the live state.
            if row["target"].get("kind") == "finish" and isinstance(row["target"].get("finish"), dict):
                row["target"]["finish"]["evidence"] = []
            family, weight = _stratum(row)
            # One controlled slice removes evaluator-owned expected-tool
            # hints. This trains the policy to recover the action from the
            # goal plus available tools, which is the hidden-contract eval.
            if style_index == len(STYLE_PREFIXES) - 1:
                input_data["state"].pop("required_tools", None)
                input_data["state"].pop("expected_tool", None)
            row["provenance"] = {
                **row.get("provenance", {}),
                "source": "synthetic_stratified_paraphrase_v2_curriculum",
                "curriculum_version": "v2",
                "sampling_stratum": family,
                "sampling_weight": weight,
                "augmentation_index": style_index,
                "contract_hint_dropout": style_index == len(STYLE_PREFIXES) - 1,
                "holdout_excluded": "research-v2/v3/v4-independent-holdouts",
            }
            rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = build_curriculum_v2()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    output.write_text(raw, encoding="utf-8", newline="\n")
    strata: dict[str, int] = {}
    for row in rows:
        key = str(row["provenance"]["sampling_stratum"])
        strata[key] = strata.get(key, 0) + 1
    print(json.dumps({
        "schema": "action-sft/v0",
        "examples": len(rows),
        "output": str(output),
        "sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "strata": strata,
        "sampling": "verifier-backed weighted strata; six controlled prompt styles",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
