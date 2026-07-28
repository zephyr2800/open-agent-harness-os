"""Merge a PEFT adapter into a pinned base checkpoint for inference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base = AutoModelForCausalLM.from_pretrained(args.base_model, revision=args.revision, dtype=torch.bfloat16, device_map={"": 0})
    merged = PeftModel.from_pretrained(base, args.adapter).merge_and_unload()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(output, safe_serialization=True)
    AutoTokenizer.from_pretrained(args.adapter).save_pretrained(output)
    (output / "merge_manifest.json").write_text(json.dumps({
        "schema": "merged-lora-checkpoint/v1",
        "base_model": args.base_model,
        "revision": args.revision,
        "adapter": str(Path(args.adapter).resolve()),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "base_model": args.base_model, "adapter": args.adapter}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
