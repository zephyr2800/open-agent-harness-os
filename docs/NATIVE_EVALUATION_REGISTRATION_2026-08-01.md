# Native external evaluation registration — 2026-08-01

[`benchmarks/fixtures/native-external-registration-v1.json`](../benchmarks/fixtures/native-external-registration-v1.json)
is the precommitted external-diagnostic protocol for the active clean 9B SFT
checkpoint. It was committed before that checkpoint completed or was evaluated.
The native launchers require this file for `--execute`; they record its path,
SHA-256, registration ID, selected condition, and bound training-source
fingerprints in every run manifest.

## Fixed scope

- Checkpoint scope: only the 3,232-row clean SFT mixture with SHA-256
  `d226a3246cd646ce1b1e7d1350d665749f4a986ec854d4314a885e12702d5ed6`,
  after its complete, zero-overlap train/holdout audit and merged-checkpoint
  binding pass.
- Variants: evaluate `model-only` first, then the matched-budget `repair`
  ablation. No sampling, seed changes, or token-budget changes are permitted.
- AgentDojo: clean workspace utility on five unobserved user tasks, then a
  three-injection `direct` condition with five user tasks (15 pairs plus three
  native injection controls). The task ranks use deterministic SHA-256 labels
  and exclude every task ID present in the historical local native-log
  inventory before registration.
- tau2: the six-task, two-per-family telecom/base solo diagnostic under the
  pinned `tau2` commit, official grader, loopback policy endpoint, one trial,
  30 steps, 10 errors, and a 256-token response cap.

The registration is intentionally a compact diagnostic, not a claim that the
model achieves a full-suite score. A valid result still requires the native
result validator, intact benchmark source tree, native output records, and the
claim boundaries in `docs/CLAIMS_AND_EVIDENCE_MATRIX.md`.

## Execution boundary

Use the same registration path with either launcher:

```powershell
--registration benchmarks/fixtures/native-external-registration-v1.json
```

The launcher rejects any changed source commit, checkpoint training source,
task selector/order, policy seed, decoding setting, quantization, budget, or
variant. A dry plan can be inspected without this flag, but a live external
run cannot start without it.
