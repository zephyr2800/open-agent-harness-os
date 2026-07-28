"""Verifier-backed on-policy REINFORCE for the local Action IR policy.

This is a deliberately small RL loop for a single GPU.  Samples are drawn
from the current model, scored by the independent task verifier, and the
policy gradient is computed from the sampled completion's log probability.
The verifier reward is the only positive path; malformed or unverified output
receives a bounded negative reward.  The 4-bit QLoRA path keeps the experiment
inside a single 32 GB GPU and saves an adapter that can be merged separately.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any

from eval.reward import reward_decision
from eval.task_spec import load_tasks
from model.adapter import ModelOutputError, ModelRequest, parse_decision
from model.transformers_backend import build_messages, load_tokenizer, serialize_chat


def _extract_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _request(task: Any) -> ModelRequest:
    verified_evidence = list(getattr(task, "verified_evidence", ()))
    return ModelRequest(
        task_id=task.task_id,
        goal=task.prompt,
        state={
            "facts": [],
            "assumptions": [],
            "open_questions": [],
            "resolved_questions": [],
            "verified_evidence": verified_evidence,
        },
        available_tools=task.available_tools,
        token_budget=task.output_token_budget,
    )


def _greedy_eval(model: Any, tokenizer: Any, tasks: tuple[Any, ...], *, device: str, torch: Any, max_new_tokens: int) -> dict[str, Any]:
    model.eval()
    rows = []
    with torch.no_grad():
        for task in tasks:
            request = _request(task)
            prompt = serialize_chat(tokenizer, build_messages(request))
            inputs = tokenizer([prompt], return_tensors="pt").to(device)
            model.config.use_cache = True
            generated = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
            model.config.use_cache = False
            raw = tokenizer.decode(generated[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
            try:
                decision = parse_decision(_extract_json(raw), request)
                reward = reward_decision(task, decision)
                row = {"task_id": task.task_id, **reward, "raw_output": raw[:2000]}
            except ModelOutputError as exc:
                row = {"task_id": task.task_id, "reward": -1.0, "reason": "invalid_protocol", "success": False, "protocol_valid": False, "errors": [str(exc)], "raw_output": raw[:2000]}
            rows.append(row)
    return {"task_count": len(rows), "mean_reward": sum(row["reward"] for row in rows) / len(rows) if rows else 0.0, "success_rate": sum(bool(row.get("success")) for row in rows) / len(rows) if rows else 0.0, "rows": rows}


def run_rl(
    tasks: tuple[Any, ...],
    *,
    model_id: str,
    revision: str,
    output_dir: str | Path,
    episodes: int,
    learning_rate: float,
    temperature: float,
    top_p: float,
    max_new_tokens: int,
    device: str,
    seed: int,
    save_every: int,
    quantization: str = "4bit",
    lora_r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    dry_run: bool = False,
) -> dict[str, Any]:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as exc:
        raise RuntimeError("Install the Transformers training runtime") from exc
    if quantization not in {"none", "4bit"}:
        raise ValueError("quantization must be none or 4bit")
    if quantization == "4bit":
        try:
            from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        except ImportError as exc:
            raise RuntimeError("Install post-training extras including peft and bitsandbytes") from exc
    random.seed(seed)
    torch.manual_seed(seed)
    source_revision = "main" if Path(model_id).exists() else revision
    tokenizer = load_tokenizer(AutoTokenizer, model_id, source_revision)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    report: dict[str, Any] = {
        "schema": "reinforce-run/v1",
        "model_id": model_id,
        "revision": source_revision,
        "task_count": len(tasks),
        "episodes": episodes,
        "learning_rate": learning_rate,
        "temperature": temperature,
        "top_p": top_p,
        "max_new_tokens": max_new_tokens,
        "device": device,
        "dtype": "bfloat16" if device.startswith("cuda") else "float32",
        "seed": seed,
        "quantization": quantization,
        "lora_r": lora_r,
        "lora_alpha": lora_alpha,
        "lora_dropout": lora_dropout,
        "dry_run": dry_run,
        "synthetic_reward_warning": True,
        "algorithm": "on-policy REINFORCE with exponential moving-average baseline",
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if dry_run:
        report["dry_run_ready"] = True
        (output / "rl_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return report
    dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
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
        revision=source_revision,
        dtype=dtype,
        device_map={"": 0} if device.startswith("cuda") else None,
        quantization_config=quant_config,
    )
    if quantization == "none":
        model.to(device)
    else:
        model = prepare_model_for_kbit_training(model)
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
        trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
        report["trainable_parameters"] = trainable
        report["total_parameters"] = sum(parameter.numel() for parameter in model.parameters())
    model.config.use_cache = False
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=learning_rate,
        betas=(0.9, 0.95),
        weight_decay=0.0,
    )
    before = _greedy_eval(model, tokenizer, tasks, device=device, torch=torch, max_new_tokens=max_new_tokens)
    baseline = 0.0
    baseline_decay = 0.9
    trajectories: list[dict[str, Any]] = []
    episode_reports: list[dict[str, Any]] = []
    started = time.perf_counter()
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(device)
    for episode in range(episodes):
        order = list(tasks)
        random.Random(seed + episode).shuffle(order)
        loss_count = 0
        optimizer.zero_grad(set_to_none=True)
        rewards: list[float] = []
        valid = 0
        successes = 0
        for task in order:
            request = _request(task)
            prompt = serialize_chat(tokenizer, build_messages(request))
            inputs = tokenizer([prompt], return_tensors="pt").to(device)
            model.eval()
            with torch.no_grad():
                model.config.use_cache = True
                sampled = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=temperature,
                    top_p=top_p,
                    pad_token_id=tokenizer.eos_token_id,
                )
                model.config.use_cache = False
            prompt_len = int(inputs["input_ids"].shape[-1])
            completion = sampled[0, prompt_len:]
            raw = tokenizer.decode(completion, skip_special_tokens=True)
            try:
                decision = parse_decision(_extract_json(raw), request)
                reward_data = reward_decision(task, decision)
                reward = float(reward_data["reward"])
                valid += int(bool(reward_data["protocol_valid"]))
                successes += int(bool(reward_data["success"]))
                reason = reward_data["reason"]
            except ModelOutputError as exc:
                reward = -1.0
                reason = "invalid_protocol"
                reward_data = {"protocol_valid": False, "success": False, "errors": [str(exc)]}
            rewards.append(reward)
            advantage = reward - baseline
            baseline = baseline_decay * baseline + (1 - baseline_decay) * reward
            if completion.numel() > 0:
                model.train()
                full = sampled[:, :]
                output_logits = model(input_ids=full, attention_mask=torch.ones_like(full)).logits
                predicted = output_logits[:, prompt_len - 1 : full.shape[-1] - 1, :]
                log_probs = torch.log_softmax(predicted.float(), dim=-1)
                token_logp = log_probs.gather(2, completion.view(1, -1, 1)).squeeze(-1).mean()
                (-float(advantage) * token_logp / max(1, len(order))).backward()
                loss_count += 1
            trajectories.append({"episode": episode + 1, "task_id": task.task_id, "reward": reward, "reason": reason, "protocol_valid": bool(reward_data.get("protocol_valid")), "success": bool(reward_data.get("success")), "raw_output": raw[:2000]})
        if loss_count:
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        episode_report = {"episode": episode + 1, "mean_reward": sum(rewards) / len(rewards) if rewards else 0.0, "valid_rate": valid / len(order) if order else 0.0, "success_rate": successes / len(order) if order else 0.0, "baseline": baseline}
        episode_reports.append(episode_report)
        if (episode + 1) % save_every == 0 or episode + 1 == episodes:
            model.save_pretrained(output, safe_serialization=True)
            tokenizer.save_pretrained(output)
            (output / "rl_trajectories.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in trajectories), encoding="utf-8")
            report["episodes_completed"] = episode + 1
            report["episode_reports"] = episode_reports
            (output / "rl_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    after = _greedy_eval(model, tokenizer, tasks, device=device, torch=torch, max_new_tokens=max_new_tokens)
    if device.startswith("cuda"):
        torch.cuda.synchronize(device)
        report["peak_vram_mib"] = round(torch.cuda.max_memory_allocated(device) / (1024 * 1024), 1)
    report.update({"before_greedy": before, "after_greedy": after, "episode_reports": episode_reports, "episodes_completed": episodes, "trajectory_count": len(trajectories), "train_ms": (time.perf_counter() - started) * 1000, "output_dir": str(output)})
    model.save_pretrained(output, safe_serialization=True)
    tokenizer.save_pretrained(output)
    (output / "rl_trajectories.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in trajectories), encoding="utf-8")
    (output / "rl_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-spec", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--episodes", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=5e-7)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--save-every", type=int, default=8)
    parser.add_argument("--quantization", choices=("none", "4bit"), default="4bit")
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run_rl(
        tuple(load_tasks(args.task_spec)),
        model_id=args.model_id,
        revision=args.revision,
        output_dir=args.output_dir,
        episodes=args.episodes,
        learning_rate=args.learning_rate,
        temperature=args.temperature,
        top_p=args.top_p,
        max_new_tokens=args.max_new_tokens,
        device=args.device,
        seed=args.seed,
        save_every=args.save_every,
        quantization=args.quantization,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
