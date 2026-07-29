# Quantized serving smoke test — 2026-07-29

This is a one-request, real-GPU serving diagnostic for the opt-in 4-bit path.
It is evidence that the loader and generation path work on the local target
machine; it is not a capability benchmark, an external evaluation score, or a
production-readiness claim.

## Result

| Field | Measurement |
| --- | --- |
| Checkpoint | Local merged Qwopus 3.5 9B action-policy checkpoint |
| Device | NVIDIA GeForce RTX 5090 |
| PyTorch | 2.11.0+cu128 |
| Transformers | 5.14.1 |
| bitsandbytes | 0.50.0 |
| Quantization | `4bit-nf4` |
| Compute dtype | `bfloat16` |
| Load time | 11,595 ms |
| Generation time | 34,529 ms |
| Input/output tokens | 469 / 108 |
| Peak VRAM | 7,450.9 MiB |
| Decision | valid `act` for `get_current_day` |

The model produced a parseable Action IR decision with the expected tool
intent. The run used greedy decoding, JSON-completion stopping, and a
128-token generation cap.

## Reproduction

Install the optional Transformers extra, then run:

```powershell
python -m experiments.quantized_smoke `
  --project1-root ..\local-action-model `
  --checkpoint C:\path\to\local-checkpoint `
  --output experiments/results/quantized-serving-smoke-v1.json
```

The checkpoint path above is intentionally a placeholder because the measured
checkpoint is a local derived artifact. The diagnostic records the exact model
identifier supplied at runtime and keeps this evidence separate from the
public benchmark and promotion gates.

## Interpretation boundary

This establishes serving viability and a reproducible memory/timing baseline.
It does not establish broad task success, injection robustness, long-horizon
reliability, RL improvement, or readiness for public model promotion. Those
claims require the frozen matrix plus disjoint external evaluation and
independent provenance review.
