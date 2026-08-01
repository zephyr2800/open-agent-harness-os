"""Merge a PEFT adapter into a pinned base checkpoint for inference."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _normalise_training_data(value: object) -> list[dict[str, object]] | None:
    items = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
    if not items:
        return None
    records: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            return None
        if not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str) or type(item.get("rows")) is not int:
            return None
        records.append({"path": item["path"], "sha256": item["sha256"], "rows": item["rows"]})
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    adapter = Path(args.adapter).resolve()
    training_manifest_path = adapter / "training_manifest.json"
    if not training_manifest_path.is_file():
        parser.error("--adapter must contain training_manifest.json with training-data provenance")
    try:
        training_manifest_bytes = training_manifest_path.read_bytes()
        training_manifest = json.loads(training_manifest_bytes)
    except (OSError, ValueError):
        parser.error("adapter training_manifest.json is not valid JSON")
    training_data = _normalise_training_data(training_manifest.get("training_data") if isinstance(training_manifest, dict) else None)
    if training_data is None:
        parser.error("adapter training_manifest.json is missing auditable training_data")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base = AutoModelForCausalLM.from_pretrained(args.base_model, revision=args.revision, dtype=torch.bfloat16, device_map={"": 0})
    merged = PeftModel.from_pretrained(base, args.adapter).merge_and_unload()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(output, safe_serialization=True)
    AutoTokenizer.from_pretrained(adapter).save_pretrained(output)
    (output / "training_manifest.json").write_bytes(training_manifest_bytes)
    (output / "merge_manifest.json").write_text(json.dumps({
        "schema": "merged-lora-checkpoint/v2",
        "base_model": args.base_model,
        "revision": args.revision,
        "adapter": str(adapter),
        "training_manifest": "training_manifest.json",
        "training_manifest_sha256": hashlib.sha256(training_manifest_bytes).hexdigest(),
        "training_data": training_data,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "base_model": args.base_model, "adapter": args.adapter}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
