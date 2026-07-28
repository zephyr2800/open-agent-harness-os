"""Merge a PEFT LoRA adapter into its base checkpoint for standalone eval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("Install the PEFT runtime first") from exc
    base = AutoModelForCausalLM.from_pretrained(args.base_model, revision="main", dtype="auto")
    model = PeftModel.from_pretrained(base, args.adapter)
    merged = model.merge_and_unload()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(output, safe_serialization=True)
    AutoTokenizer.from_pretrained(args.adapter).save_pretrained(output)
    manifest = {
        "schema": "merged-peft-checkpoint/v0",
        "base_model": args.base_model,
        "adapter": args.adapter,
        "output_dir": str(output),
        "merge": "peft.merge_and_unload",
    }
    (output / "merge_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
