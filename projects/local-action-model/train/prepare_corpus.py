"""Prepare a reproducible mixed corpus for local continued pretraining.

The generic slice is downloaded through Hugging Face Datasets in streaming
mode.  The protocol slice is kept separate in the manifest so a run can be
described honestly as continued pretraining plus domain adaptation rather
than as pretraining from scratch.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Iterable


def _write_rows(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            count += 1
    return count


def _load_protocol_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row.get("text"), str) or not row["text"].strip():
            raise ValueError(f"protocol row has no non-empty text: {row}")
        rows.append(row)
    return rows


def _stream_generic(dataset_id: str, config: str | None, count: int, seed: int) -> list[dict[str, Any]]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError("Install the corpus/post-training runtime first") from exc
    kwargs: dict[str, Any] = {"split": "train", "streaming": True}
    if config:
        kwargs["name"] = config
    dataset = load_dataset(dataset_id, **kwargs)
    rows: list[dict[str, Any]] = []
    for item in dataset:
        text = item.get("text") if isinstance(item, dict) else None
        if isinstance(text, str) and text.strip():
            rows.append({"text": text.strip(), "provenance": {"source": dataset_id, "synthetic": False, "split": "train"}})
        if len(rows) >= count:
            break
    random.Random(seed).shuffle(rows)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol-jsonl", required=True)
    parser.add_argument("--train-output", required=True)
    parser.add_argument("--eval-output", required=True)
    parser.add_argument("--dataset-id", default="roneneldan/TinyStories")
    parser.add_argument("--dataset-config")
    parser.add_argument("--generic-count", type=int, default=20000)
    parser.add_argument("--eval-count", type=int, default=1000)
    parser.add_argument("--protocol-repeat", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    protocol = _load_protocol_rows(Path(args.protocol_jsonl))
    if not protocol:
        raise ValueError("protocol corpus is empty")
    generic = _stream_generic(args.dataset_id, args.dataset_config, args.generic_count + args.eval_count, args.seed)
    train_generic = generic[: args.generic_count]
    eval_generic = generic[args.generic_count : args.generic_count + args.eval_count]
    protocol_rows = [
        {"text": row["text"], "provenance": {**row.get("provenance", {}), "stage": "protocol_mix"}}
        for row in protocol
        for _ in range(max(1, args.protocol_repeat))
    ]
    random.Random(args.seed).shuffle(protocol_rows)
    train_rows = train_generic + protocol_rows
    random.Random(args.seed + 1).shuffle(train_rows)
    eval_rows = eval_generic
    train_count = _write_rows(Path(args.train_output), train_rows)
    eval_count = _write_rows(Path(args.eval_output), eval_rows)
    report = {
        "schema": "continued-pretraining-corpus/v0",
        "dataset_id": args.dataset_id,
        "dataset_config": args.dataset_config,
        "train_rows": train_count,
        "eval_rows": eval_count,
        "generic_train_rows": len(train_generic),
        "protocol_train_rows": len(protocol_rows),
        "protocol_source_rows": len(protocol),
        "protocol_repeat": args.protocol_repeat,
        "seed": args.seed,
        "synthetic_protocol_warning": True,
    }
    report_path = Path(args.train_output).with_suffix(".manifest.json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
