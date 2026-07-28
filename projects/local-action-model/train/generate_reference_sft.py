"""Generate a deterministic bootstrap SFT file from the reference policy.

This is a protocol smoke fixture only. It is useful for testing serialization
and a first training run, but it must not be treated as independent evidence or
as a substitute for verified human/teacher trajectories.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.benchmark import reference_policy
from eval.task_spec import load_tasks
from data.sft import write_jsonl


def build_examples(tasks):
    for task in tasks:
        yield {
            "schema": "action-sft/v0",
            "task_id": task.task_id,
            "input": {
                "goal": task.prompt,
                "task_id": task.task_id,
                "state": {"facts": [], "assumptions": [], "open_questions": [], "resolved_questions": []},
                "available_tools": list(task.available_tools),
                "token_budget": task.output_token_budget,
            },
            "target": reference_policy(task),
            "provenance": {
                "source": "deterministic_reference_policy",
                "task_spec": "action-task-spec/v0",
                "synthetic": True,
                "independent_verifier_required": True,
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-spec", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    tasks = load_tasks(args.task_spec)
    count = write_jsonl(build_examples(tasks), args.output)
    print(json.dumps({"examples": count, "output": str(Path(args.output))}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
