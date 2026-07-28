"""CLI for converting a replayable trajectory JSONL file to SFT JSONL."""

from __future__ import annotations

import argparse

from action_ir.replay import load_file
from data.sft import trajectory_to_sft_examples, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="source trajectory JSONL")
    parser.add_argument("--output", required=True, help="destination SFT JSONL")
    args = parser.parse_args()
    examples = trajectory_to_sft_examples(load_file(args.input))
    count = write_jsonl(examples, args.output)
    print(f"wrote {count} SFT examples to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
