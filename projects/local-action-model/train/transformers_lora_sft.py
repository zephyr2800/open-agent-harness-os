"""LoRA/QLoRA SFT for scaling action policies beyond full-finetune VRAM."""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any

from train.transformers_sft import _pad_batch, load_examples, tokenized_examples


def _sampling_weight(row: dict[str, Any]) -> float:
    provenance = row.get("provenance", {})
    try:
        value = float(provenance.get("sampling_weight", 1.0))
    except (TypeError, ValueError):
        value = 1.0
    return max(0.1, value)


def _sample_order(rows: list[dict[str, Any]], *, seed: int, epoch: int, strategy: str) -> list[int]:
    population = list(range(len(rows)))
    if strategy == "uniform" or not population:
        random.Random(seed + epoch).shuffle(population)
        return population
    if strategy != "weighted":
        raise ValueError("sampling_strategy must be uniform or weighted")
    sampler = random.Random(seed + (epoch * 1009))
    # Weighted random.choices can silently omit a large fraction of a small
    # curriculum. Use an Efraimidis-Spirakis weighted permutation instead:
    # every row is seen exactly once per epoch, while higher-weight strata are
    # scheduled earlier and therefore receive more optimizer attention before
    # later rows overwrite the short-horizon behavior.
    keyed = [(sampler.random() ** (1.0 / _sampling_weight(row)), index) for index, row in enumerate(rows)]
    keyed.sort(reverse=True)
    return [index for _, index in keyed]


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
    quantization: str,
    lora_r: int,
    lora_alpha: int,
    lora_dropout: float,
    sampling_strategy: str = "uniform",
    gradient_checkpointing: bool = False,
    gradient_accumulation_steps: int = 1,
    dry_run: bool = False,
    max_steps: int | None = None,
    progress_every: int = 50,
) -> dict[str, Any]:
    try:
        import torch
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as exc:
        raise RuntimeError("Install post-training extras including peft and bitsandbytes") from exc

    if quantization not in {"none", "4bit"}:
        raise ValueError("quantization must be none or 4bit")
    if progress_every < 0:
        raise ValueError("progress_every must be non-negative")
    if gradient_accumulation_steps < 1:
        raise ValueError("gradient_accumulation_steps must be positive")
    random.seed(seed)
    torch.manual_seed(seed)
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    rows = tokenized_examples(tokenizer, examples, max_length)
    lengths = [len(row["input_ids"]) for row in rows]
    report: dict[str, Any] = {
        "schema": "lora-sft-run/v0",
        "model_id": model_id,
        "revision": revision,
        "example_count": len(rows),
        "max_length": max_length,
        "min_sequence_length": min(lengths) if lengths else 0,
        "max_sequence_length": max(lengths) if lengths else 0,
        "mean_sequence_length": sum(lengths) / len(lengths) if lengths else 0.0,
        "quantization": quantization,
        "lora_r": lora_r,
        "lora_alpha": lora_alpha,
        "lora_dropout": lora_dropout,
        "sampling_strategy": sampling_strategy,
        "gradient_checkpointing": gradient_checkpointing,
        "gradient_accumulation_steps": gradient_accumulation_steps,
        "dry_run": dry_run,
        "max_steps": max_steps,
        "progress_every": progress_every,
    }
    if dry_run:
        return report

    quant_config = None
    if quantization == "4bit":
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        revision=revision,
        dtype=torch.bfloat16,
        device_map={"": 0} if device.startswith("cuda") else None,
        quantization_config=quant_config,
    )
    if quantization == "4bit":
        model = prepare_model_for_kbit_training(model)
    model.config.use_cache = False
    if gradient_checkpointing:
        try:
            model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        except TypeError:
            # Older Transformers releases do not accept the kwargs mapping.
            model.gradient_checkpointing_enable()
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
    model = get_peft_model(
        model,
        LoraConfig(
            task_type="CAUSAL_LM",
            r=lora_r,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            target_modules="all-linear",
        ),
    )
    model.print_trainable_parameters()
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    total = sum(parameter.numel() for parameter in model.parameters())
    report.update({"trainable_parameters": trainable, "total_parameters": total})
    model.train()
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(device)
    optimizer = torch.optim.AdamW((parameter for parameter in model.parameters() if parameter.requires_grad), lr=learning_rate)
    start = time.perf_counter()
    output_path = Path(output_dir)
    progress_path = output_path / "training_progress.json"
    if not dry_run:
        output_path.mkdir(parents=True, exist_ok=True)
        progress_path.write_text(json.dumps({
            "schema": "lora-sft-progress/v0",
            "status": "started",
            "optimizer_steps": 0,
            "example_count": len(rows),
            "started_unix": time.time(),
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    losses: list[float] = []
    sampled_unique: list[int] = []
    steps = 0
    micro_steps = 0
    optimizer.zero_grad(set_to_none=True)
    for epoch in range(epochs):
        order = _sample_order(examples, seed=seed, epoch=epoch, strategy=sampling_strategy)
        sampled_unique.append(len(set(order)))
        for offset in range(0, len(order), batch_size):
            batch_rows = [rows[index] for index in order[offset : offset + batch_size]]
            input_ids, attention_mask, labels = _pad_batch(batch_rows, tokenizer.pad_token_id, torch)
            input_ids = input_ids.to(device)
            attention_mask = attention_mask.to(device)
            labels = labels.to(device)
            output = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            output.loss.div(gradient_accumulation_steps).backward()
            micro_steps += 1
            losses.append(float(output.loss.detach().cpu()))
            is_last_batch = offset + batch_size >= len(order)
            if micro_steps % gradient_accumulation_steps == 0 or is_last_batch:
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                steps += 1
            if progress_every and (steps % progress_every == 0 or (max_steps is not None and steps >= max_steps)):
                progress_path.write_text(json.dumps({
                    "schema": "lora-sft-progress/v0",
                    "status": "running",
                    "optimizer_steps": steps,
                    "epoch": epoch,
                    "last_loss": losses[-1],
                    "elapsed_ms": (time.perf_counter() - start) * 1000,
                    "example_count": len(rows),
                }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if max_steps is not None and steps >= max_steps:
                break
        if max_steps is not None and steps >= max_steps:
            break
    if device.startswith("cuda"):
        torch.cuda.synchronize(device)
        report["peak_vram_mib"] = round(torch.cuda.max_memory_allocated(device) / (1024 * 1024), 1)
    model.save_pretrained(output_path, safe_serialization=True)
    tokenizer.save_pretrained(output_path)
    report.update({
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "mean_loss": sum(losses) / len(losses) if losses else None,
        "train_ms": (time.perf_counter() - start) * 1000,
        "device": device,
        "training_tokens": sum(lengths) * epochs,
        "sampled_unique_rows_per_epoch": sampled_unique,
        "optimizer_steps": steps,
    })
    (output_path / "training_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    progress_path.write_text(json.dumps({
        "schema": "lora-sft-progress/v0",
        "status": "completed",
        "optimizer_steps": steps,
        "last_loss": losses[-1] if losses else None,
        "elapsed_ms": report["train_ms"],
        "example_count": len(rows),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-jsonl", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output-dir", default="work/action-model-lora-sft")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-length", type=int, default=1536)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--quantization", choices=("none", "4bit"), default="4bit")
    parser.add_argument("--lora-r", type=int, default=32)
    parser.add_argument("--lora-alpha", type=int, default=64)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--sampling-strategy", choices=("uniform", "weighted"), default="uniform")
    parser.add_argument("--gradient-checkpointing", action="store_true", help="trade activation recomputation for lower VRAM use")
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1, help="micro-batches per optimizer step")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--progress-every", type=int, default=50, help="write a sidecar progress manifest every N optimizer steps; 0 disables it")
    args = parser.parse_args()
    report = run_training(
        load_examples(args.train_jsonl),
        model_id=args.model_id,
        revision=args.revision,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_length=args.max_length,
        device=args.device,
        seed=args.seed,
        quantization=args.quantization,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        sampling_strategy=args.sampling_strategy,
        gradient_checkpointing=args.gradient_checkpointing,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        dry_run=args.dry_run,
        max_steps=args.max_steps,
        progress_every=args.progress_every,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
