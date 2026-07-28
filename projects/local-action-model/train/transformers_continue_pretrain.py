"""Checkpointed causal-LM continued pretraining on JSONL text rows.

This is intentionally a small, inspectable trainer: packed causal-LM blocks,
BF16 on CUDA, gradient accumulation, periodic checkpoints, resume support,
and a held-out loss.  It is suitable for a single local GPU and does not claim
to be from-scratch pretraining when initialized from a released checkpoint.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path
from typing import Any


def load_text_rows(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"row has no non-empty text: {row}")
        rows.append(row)
    if not rows:
        raise ValueError(f"no rows found in {path}")
    return rows


def _pack(tokenizer: Any, rows: list[dict[str, Any]], block_size: int) -> list[list[int]]:
    ids: list[int] = []
    eos = tokenizer.eos_token_id
    for row in rows:
        item = tokenizer(row["text"], add_special_tokens=True)["input_ids"]
        ids.extend(item)
        if eos is not None and (not item or item[-1] != eos):
            ids.append(eos)
    usable = len(ids) - (len(ids) % block_size)
    return [ids[offset : offset + block_size] for offset in range(0, usable, block_size)]


def _evaluate(model: Any, blocks: list[list[int]], *, device: str, torch: Any, batch_size: int, pad_id: int) -> float | None:
    if not blocks:
        return None
    model.eval()
    losses: list[float] = []
    with torch.no_grad():
        for offset in range(0, len(blocks), batch_size):
            batch = blocks[offset : offset + batch_size]
            input_ids = torch.tensor(batch, dtype=torch.long, device=device)
            attention = torch.ones_like(input_ids)
            output = model(input_ids=input_ids, attention_mask=attention, labels=input_ids)
            losses.append(float(output.loss.detach().float().cpu()))
    model.train()
    return sum(losses) / len(losses) if losses else None


def run_training(
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    *,
    model_id: str,
    revision: str,
    output_dir: str | Path,
    resume_from: str | Path | None,
    max_steps: int,
    batch_size: int,
    gradient_accumulation: int,
    learning_rate: float,
    warmup_steps: int,
    block_size: int,
    save_every: int,
    eval_every: int,
    device: str,
    seed: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("Install the Transformers training runtime") from exc
    random.seed(seed)
    torch.manual_seed(seed)
    source = str(resume_from) if resume_from else model_id
    source_revision = "main" if resume_from else revision
    tokenizer = AutoTokenizer.from_pretrained(source, revision=source_revision)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    train_blocks = _pack(tokenizer, train_rows, block_size)
    eval_blocks = _pack(tokenizer, eval_rows, block_size)
    report: dict[str, Any] = {
        "schema": "continued-pretraining-run/v1",
        "base_model_id": model_id,
        "base_revision": revision,
        "source_checkpoint": str(resume_from) if resume_from else None,
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "train_blocks": len(train_blocks),
        "eval_blocks": len(eval_blocks),
        "block_size": block_size,
        "max_steps": max_steps,
        "batch_size": batch_size,
        "gradient_accumulation": gradient_accumulation,
        "learning_rate": learning_rate,
        "warmup_steps": warmup_steps,
        "seed": seed,
        "device": device,
        "dtype": "bfloat16" if device.startswith("cuda") else "float32",
        "dry_run": dry_run,
        "synthetic_protocol_warning": True,
    }
    if dry_run:
        report["train_tokens"] = len(train_blocks) * block_size
        report["eval_tokens"] = len(eval_blocks) * block_size
        return report
    if not train_blocks:
        raise ValueError("training corpus produced no complete blocks")
    dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
    model = AutoModelForCausalLM.from_pretrained(source, revision=source_revision, dtype=dtype)
    model.to(device)
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, betas=(0.9, 0.95), weight_decay=0.1)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    start_step = 0
    token_count = 0
    if resume_from and (Path(resume_from) / "optimizer.pt").exists():
        optimizer.load_state_dict(torch.load(Path(resume_from) / "optimizer.pt", map_location=device, weights_only=False))
        state_path = Path(resume_from) / "trainer_state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            start_step = int(state.get("step", 0))
            token_count = int(state.get("tokens", 0))
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(device)
    history: list[dict[str, Any]] = []
    losses: list[float] = []
    global_step = start_step
    started = time.perf_counter()
    epoch = 0
    while global_step < max_steps:
        order = list(range(len(train_blocks)))
        random.Random(seed + epoch).shuffle(order)
        epoch += 1
        for offset in range(0, len(order), batch_size):
            if global_step >= max_steps:
                break
            micro = [train_blocks[index] for index in order[offset : offset + batch_size]]
            input_ids = torch.tensor(micro, dtype=torch.long, device=device)
            attention = torch.ones_like(input_ids)
            output = model(input_ids=input_ids, attention_mask=attention, labels=input_ids)
            loss = output.loss / gradient_accumulation
            loss.backward()
            if ((offset // batch_size) + 1) % gradient_accumulation == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                warmup_scale = min(1.0, (global_step + 1) / max(1, warmup_steps))
                for group in optimizer.param_groups:
                    group["lr"] = learning_rate * warmup_scale
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                global_step += 1
                loss_value = float(output.loss.detach().float().cpu())
                losses.append(loss_value)
                token_count += int(attention.sum().item())
                record = {"step": global_step, "loss": loss_value, "tokens": token_count}
                if global_step % eval_every == 0 or global_step == max_steps:
                    record["eval_loss"] = _evaluate(model, eval_blocks, device=device, torch=torch, batch_size=batch_size, pad_id=tokenizer.pad_token_id)
                history.append(record)
                if global_step % save_every == 0 or global_step == max_steps:
                    model.save_pretrained(output_path, safe_serialization=True)
                    tokenizer.save_pretrained(output_path)
                    torch.save(optimizer.state_dict(), output_path / "optimizer.pt")
                    (output_path / "trainer_state.json").write_text(json.dumps({"step": global_step, "tokens": token_count}, indent=2) + "\n", encoding="utf-8")
                    report["latest_checkpoint_step"] = global_step
                    report["history"] = history[-20:]
                    (output_path / "training_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if device.startswith("cuda"):
        torch.cuda.synchronize(device)
        report["peak_vram_mib"] = round(torch.cuda.max_memory_allocated(device) / (1024 * 1024), 1)
    report.update({
        "steps_completed": global_step,
        "training_tokens": token_count,
        "mean_loss": sum(losses) / len(losses) if losses else None,
        "final_eval_loss": history[-1].get("eval_loss") if history else None,
        "train_ms": (time.perf_counter() - started) * 1000,
        "history": history,
        "output_dir": str(output_path),
    })
    model.save_pretrained(output_path, safe_serialization=True)
    tokenizer.save_pretrained(output_path)
    torch.save(optimizer.state_dict(), output_path / "optimizer.pt")
    (output_path / "trainer_state.json").write_text(json.dumps({"step": global_step, "tokens": token_count}, indent=2) + "\n", encoding="utf-8")
    (output_path / "training_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-jsonl", required=True)
    parser.add_argument("--eval-jsonl", required=True)
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--resume-from")
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--warmup-steps", type=int, default=50)
    parser.add_argument("--block-size", type=int, default=512)
    parser.add_argument("--save-every", type=int, default=100)
    parser.add_argument("--eval-every", type=int, default=100)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run_training(load_text_rows(args.train_jsonl), load_text_rows(args.eval_jsonl), model_id=args.model_id, revision=args.revision, output_dir=args.output_dir, resume_from=args.resume_from, max_steps=args.max_steps, batch_size=args.batch_size, gradient_accumulation=args.gradient_accumulation, learning_rate=args.learning_rate, warmup_steps=args.warmup_steps, block_size=args.block_size, save_every=args.save_every, eval_every=args.eval_every, device=args.device, seed=args.seed, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
