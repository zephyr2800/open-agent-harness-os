# Qwopus3.5-27B feasibility track

This is the maximum-scale branch to attempt on the single RTX 5090 after the
9B evaluation chain completes. It is a feasibility experiment, not a claim
that a larger checkpoint will improve the action policy.

## Configuration

- 4-bit NF4 base weights with BF16 compute;
- QLoRA rank 16 first, then rank 32 only if the rank-16 smoke is stable;
- activation/gradient checkpointing enabled;
- micro-batch size 1 and gradient accumulation 8;
- maximum sequence length 1,024 for the first memory probe;
- eight optimizer steps for the smoke, then one controlled epoch only after
  memory and loss checks pass;
- same Action IR curriculum, hidden holdout, independent replay, and safety
  evaluator as the 7B/9B branches.

## Staged run

Run only when no other GPU process is active and the model's license/provenance
has been reviewed:

```powershell
$py = 'python'
$env:PYTHONPATH = '<workspace>\work\ml-runtime-cu128;<workspace>\work\ml-runtime-post'
& $py -m train.transformers_lora_sft `
  --train-jsonl work\action-harness-sft-v5-stratified-hidden.jsonl `
  --model-id <local-qwopus35-27b-path> --revision main `
  --output-dir work\action-model-project2-qwopus35-27b-feasibility-r16 `
  --quantization 4bit --lora-r 16 --lora-alpha 32 `
  --max-length 1024 --batch-size 1 --gradient-checkpointing `
  --gradient-accumulation-steps 8 --max-steps 8 --progress-every 1
```

## Acceptance gates

The smoke is usable only if it has finite loss, no CUDA OOM, complete row
coverage, stable checkpoint writes, and peak allocated VRAM below the machine
budget with headroom for evaluation. A lower training loss alone is not a
promotion signal. Any candidate must run the same frozen holdouts and
independent replay used for 9B, with family-level failures and resource
metrics, before a larger-model claim is made.

The branch is intentionally not auto-started: the 9B promotion and external
diagnostic chain has priority on the single GPU, and a larger model cannot
retroactively rescue a failed evaluation protocol.


