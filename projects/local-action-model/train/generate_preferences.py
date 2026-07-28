"""Generate synthetic preference pairs for protocol/hard-negative plumbing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.preferences import build_preference_examples, write_preference_jsonl
from eval.task_spec import load_tasks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-spec", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    count = write_preference_jsonl(build_preference_examples(load_tasks(args.task_spec)), args.output)
    print(json.dumps({"examples": count, "output": str(Path(args.output))}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
