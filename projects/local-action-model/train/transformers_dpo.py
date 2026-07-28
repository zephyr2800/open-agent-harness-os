"""Optional DPO/LoRA post-training path for verifier-backed preferences.

The dry-run path is dependency-light and validates the prompt/chosen/rejected
contract. The actual trainer is intentionally optional because TRL/PEFT versions
are fast-moving; the command fails with an actionable install message when the
extras are absent.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from model.adapter import ModelRequest
from model.transformers_backend import build_messages


def load_examples(path: str | Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if row.get("schema") != "action-preference/v0":
            raise ValueError("every row must use action-preference/v0")
        for field in ("input", "chosen", "rejected", "rejected_reason"):
            if field not in row:
                raise ValueError(f"preference row is missing {field}")
    return rows


def format_examples(rows: list[dict[str, Any]], tokenizer: Any = None) -> list[dict[str, str]]:
    formatted = []
    for row in rows:
        data = row["input"]
        request = ModelRequest(
            task_id=data["task_id"],
            goal=data["goal"],
            state=data.get("state", {}),
            available_tools=tuple(data.get("available_tools", [])),
            token_budget=int(data.get("token_budget", 256)),
        )
        messages = build_messages(request)
        if tokenizer is None:
            prompt = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        else:
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        formatted.append(
            {
                "task_id": row["task_id"],
                "prompt": prompt,
                "chosen": json.dumps(row["chosen"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                "rejected": json.dumps(row["rejected"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                "rejected_reason": row["rejected_reason"],
            }
        )
    return formatted


def run_dpo(rows: list[dict[str, Any]], *, model_id: str, revision: str, output_dir: str, dry_run: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "dpo-run/v0",
        "model_id": model_id,
        "revision": revision,
        "example_count": len(rows),
        "rejection_reasons": sorted({row["rejected_reason"] for row in rows}),
        "dry_run": dry_run,
        "synthetic_data_warning": any(row.get("provenance", {}).get("synthetic") for row in rows),
    }
    if dry_run:
        return report
    try:
        from datasets import Dataset
        from peft import LoraConfig
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import DPOConfig, DPOTrainer
    except ImportError as exc:
        raise RuntimeError("Install post-training extras with: pip install '.[post-training]'") from exc
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    formatted = format_examples(rows, tokenizer)
    model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision, dtype="auto")
    dataset = Dataset.from_list(formatted)
    trainer = DPOTrainer(
        model=model,
        args=DPOConfig(output_dir=output_dir, num_train_epochs=1, per_device_train_batch_size=1, report_to=[]),
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=LoraConfig(task_type="CAUSAL_LM", r=16, lora_alpha=32, lora_dropout=0.05, target_modules="all-linear"),
    )
    trainer.train()
    trainer.save_model(output_dir)
    report["output_dir"] = output_dir
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preferences", required=True)
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output-dir", default="work/action-model-dpo")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_dpo(load_examples(args.preferences), model_id=args.model_id, revision=args.revision, output_dir=args.output_dir, dry_run=args.dry_run), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
