"""Optional causal-LM SFT entry point for `action-sft/v0` JSONL data."""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any

from model.adapter import ModelRequest
from model.transformers_backend import build_messages, load_tokenizer, serialize_chat


def load_examples(path: str | Path) -> list[dict[str, Any]]:
    examples = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    for example in examples:
        if example.get("schema") != "action-sft/v0":
            raise ValueError("every training row must use schema action-sft/v0")
        input_data = example.get("input", {})
        target = example.get("target", {})
        if input_data.get("task_id") != target.get("task_id"):
            raise ValueError("training row input.task_id must match target.task_id")
    return examples


def _texts(example: dict[str, Any]) -> tuple[str, str]:
    data = example["input"]
    request = ModelRequest(
        task_id=data["task_id"],
        goal=data["goal"],
        state=data.get("state", {}),
        available_tools=tuple(data.get("available_tools", [])),
        token_budget=int(data.get("token_budget", 256)),
    )
    messages = build_messages(request)
    target = json.dumps(example["target"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return messages, target


def tokenized_examples(tokenizer: Any, examples: list[dict[str, Any]], max_length: int) -> list[dict[str, Any]]:
    rows = []
    for example in examples:
        messages, target = _texts(example)
        prompt = serialize_chat(tokenizer, messages)
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        target_ids = tokenizer(target + (tokenizer.eos_token or ""), add_special_tokens=False)["input_ids"]
        if len(prompt_ids) + len(target_ids) > max_length:
            prompt_ids = prompt_ids[-(max_length - len(target_ids)) :]
        input_ids = prompt_ids + target_ids
        rows.append({"task_id": example["task_id"], "input_ids": input_ids, "labels": [-100] * len(prompt_ids) + target_ids})
    return rows


def _pad_batch(rows: list[dict[str, Any]], pad_token_id: int, torch: Any) -> tuple[Any, Any, Any]:
    length = max(len(row["input_ids"]) for row in rows)
    input_ids = [row["input_ids"] + [pad_token_id] * (length - len(row["input_ids"])) for row in rows]
    labels = [row["labels"] + [-100] * (length - len(row["labels"])) for row in rows]
    attention = [[1] * len(row["input_ids"]) + [0] * (length - len(row["input_ids"])) for row in rows]
    return torch.tensor(input_ids), torch.tensor(attention), torch.tensor(labels)


def run_training(
    examples: list[dict[str, Any]],
    *,
    model_id: str,
    revision: str,
    output_dir: str | Path,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    max_length: int,
    device: str,
    seed: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("Install the optional training backend with: pip install -e '.[transformers]'") from exc

    random.seed(seed)
    torch.manual_seed(seed)
    tokenizer = load_tokenizer(AutoTokenizer, model_id, revision)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    rows = tokenized_examples(tokenizer, examples, max_length)
    lengths = [len(row["input_ids"]) for row in rows]
    report: dict[str, Any] = {
        "schema": "sft-run/v0",
        "model_id": model_id,
        "revision": revision,
        "example_count": len(rows),
        "max_length": max_length,
        "min_sequence_length": min(lengths) if lengths else 0,
        "max_sequence_length": max(lengths) if lengths else 0,
        "mean_sequence_length": sum(lengths) / len(lengths) if lengths else 0.0,
        "dry_run": dry_run,
    }
    if dry_run:
        return report

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        revision=revision,
        dtype=torch.float32 if device == "cpu" else "auto",
    )
    model.to(device)
    model.train()
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    start = time.perf_counter()
    losses = []
    for epoch in range(epochs):
        order = list(range(len(rows)))
        random.Random(seed + epoch).shuffle(order)
        for offset in range(0, len(order), batch_size):
            batch_rows = [rows[index] for index in order[offset : offset + batch_size]]
            input_ids, attention_mask, labels = _pad_batch(batch_rows, tokenizer.pad_token_id, torch)
            input_ids = input_ids.to(device)
            attention_mask = attention_mask.to(device)
            labels = labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            output = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            output.loss.backward()
            optimizer.step()
            losses.append(float(output.loss.detach().cpu()))
    if device.startswith("cuda"):
        torch.cuda.synchronize(device)
        report["peak_vram_mib"] = round(torch.cuda.max_memory_allocated(device) / (1024 * 1024), 1)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_path, safe_serialization=True)
    tokenizer.save_pretrained(output_path)
    report.update({"epochs": epochs, "batch_size": batch_size, "learning_rate": learning_rate, "mean_loss": sum(losses) / len(losses) if losses else None, "train_ms": (time.perf_counter() - start) * 1000, "device": device, "training_tokens": sum(lengths) * epochs})
    (output_path / "training_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-jsonl", required=True)
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output-dir", default="work/action-model-sft")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = run_training(load_examples(args.train_jsonl), model_id=args.model_id, revision=args.revision, output_dir=args.output_dir, epochs=args.epochs, batch_size=args.batch_size, learning_rate=args.learning_rate, max_length=args.max_length, device=args.device, seed=args.seed, dry_run=args.dry_run)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
