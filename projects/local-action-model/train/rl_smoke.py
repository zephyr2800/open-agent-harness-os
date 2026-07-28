"""Calibrate the verifier-backed reward used by a future local RL run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.preferences import hard_negative
from eval.benchmark import reference_policy
from eval.reward import reward_decision
from eval.task_spec import load_tasks


def build_reward_smoke(tasks):
    rows = []
    for task in tasks:
        chosen = reference_policy(task)
        rejected, rejection_reason = hard_negative(task, chosen)
        chosen_reward = reward_decision(task, chosen)
        rejected_reward = reward_decision(task, rejected)
        rows.append(
            {
                "task_id": task.task_id,
                "chosen": chosen_reward,
                "rejected": rejected_reward,
                "rejected_reason": rejection_reason,
                "provenance": {"synthetic": True, "source": "deterministic_reference_policy_plus_mutation"},
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-spec", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    tasks = load_tasks(args.task_spec)
    rows = build_reward_smoke(tasks)
    result = {
        "schema": "rl-reward-smoke/v0",
        "task_count": len(rows),
        "mean_chosen_reward": sum(row["chosen"]["reward"] for row in rows) / len(rows) if rows else 0.0,
        "mean_rejected_reward": sum(row["rejected"]["reward"] for row in rows) / len(rows) if rows else 0.0,
        "chosen_beats_rejected": sum(row["chosen"]["reward"] > row["rejected"]["reward"] for row in rows),
        "rows": rows,
        "limitations": ["synthetic oracle and mutation data; reward calibration only, not an RL result"],
    }
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
