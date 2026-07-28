# Scale-control note — 2026-07-27

Status: interim evidence; the 9B matrix is incomplete.

## Observation

The current Qwopus3.5-9B-v3 Action IR QLoRA branch is not automatically
outperforming the earlier 7B v7 Action IR branch on the frozen local control
surface:

| Checkpoint | `research-v4` | `industry-proxy-v1` | Evaluation condition |
|---|---:|---:|---|
| 7B v7 | 120/120 (100.0%) | 39/48 (81.25%) | model-only, one recorded run |
| 9B current seed 0 | 116/120 (96.7%) | 37/48 (77.1%) | model-only, frozen matrix |
| 9B current seed 1 | 116/120 (96.7%) | 37/48 (77.1%) | model-only, frozen matrix |

Both comparisons use the same task-spec hashes:

- `research-v4`: `9c4e3a4f643c21056dd8fe5437ffe180054cf7f96ad02f572910eb298369bfda`
- `industry-proxy-v1`: `c5c0e843f2edc27cdb10b2a2b5d394d5d64373d558f072f4cb0f49001c10cb5e`

## Interpretation boundary

This is not a final claim that 7B is better than 9B. The checkpoints have
different base models, training histories, data mixtures, and recorded seed
coverage; the 9B seed-2 run is still active. The observation does establish a
necessary control: parameter scaling must be separated from Action IR data,
verifier-aware post-training, decoding, and harness effects.

## Paper consequence

The primary result should be framed as a controlled systems comparison, not a
parameter-count leaderboard. The required next comparison is:

1. same frozen evaluator and task hashes;
2. same decoding and seed protocol;
3. base versus Action IR SFT at each available scale;
4. verifier-backed remediation/RL with disjoint holdout;
5. independent replay, unsafe actions, false completion, latency, and VRAM.

Until that comparison is complete, the 9B checkpoint remains an evaluation
candidate rather than a promoted model.
