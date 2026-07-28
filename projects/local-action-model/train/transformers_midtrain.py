"""Optional causal-LM domain-adaptive mid-training for action-domain text."""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any


def load_examples(path: str | Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if row.get("schema") != "action-midtrain/v0" or not isinstance(row.get("text"), str) or not row["text"].strip():
            raise ValueError("every row must use action-midtrain/v0 and contain non-empty text")
    return rows


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
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    encoded = []
    for row in examples:
        ids = tokenizer(row["text"] + (tokenizer.eos_token or ""), add_special_tokens=True)["input_ids"][:max_length]
        encoded.append(ids)
    report: dict[str, Any] = {
        "schema": "midtrain-run/v0",
        "model_id": model_id,
        "revision": revision,
        "example_count": len(encoded),
        "max_length": max_length,
        "min_sequence_length": min((len(row) for row in encoded), default=0),
        "max_sequence_length": max((len(row) for row in encoded), default=0),
        "mean_sequence_length": sum(len(row) for row in encoded) / len(encoded) if encoded else 0.0,
        "dry_run": dry_run,
        "synthetic_data_warning": True,
    }
    if dry_run:
        return report

    model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision, dtype=torch.float32 if device == "cpu" else "auto")
    model.to(device)
    model.train()
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    start = time.perf_counter()
    losses: list[float] = []
    total_tokens = 0
    for epoch in range(epochs):
        order = list(range(len(encoded)))
        random.Random(seed + epoch).shuffle(order)
        for offset in range(0, len(order), batch_size):
            batch = [encoded[index] for index in order[offset : offset + batch_size]]
            length = max(len(row) for row in batch)
            input_ids = torch.tensor([row + [tokenizer.pad_token_id] * (length - len(row)) for row in batch], device=device)
            attention = (input_ids != tokenizer.pad_token_id).long()
            labels = input_ids.clone()
            labels[attention == 0] = -100
            optimizer.zero_grad(set_to_none=True)
            output = model(input_ids=input_ids, attention_mask=attention, labels=labels)
            output.loss.backward()
            optimizer.step()
            losses.append(float(output.loss.detach().cpu()))
            total_tokens += int(attention.sum().item())
    if device.startswith("cuda"):
        torch.cuda.synchronize(device)
        report["peak_vram_mib"] = round(torch.cuda.max_memory_allocated(device) / (1024 * 1024), 1)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_path, safe_serialization=True)
    tokenizer.save_pretrained(output_path)
    report.update(
        {
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "mean_loss": sum(losses) / len(losses) if losses else None,
            "train_ms": (time.perf_counter() - start) * 1000,
            "device": device,
            "training_tokens": total_tokens,
        }
    )
    (output_path / "training_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-jsonl", required=True)
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output-dir", default="work/action-model-midtrain")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = run_training(load_examples(args.train_jsonl), model_id=args.model_id, revision=args.revision, output_dir=args.output_dir, epochs=args.epochs, batch_size=args.batch_size, learning_rate=args.learning_rate, max_length=args.max_length, device=args.device, seed=args.seed, dry_run=args.dry_run)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
