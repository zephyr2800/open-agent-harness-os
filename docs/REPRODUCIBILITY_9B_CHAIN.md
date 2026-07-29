# Qwopus3.5-9B evaluation chain

This document freezes the reproducibility boundary for the local 9B scale
experiment. The promotion matrix, v1 diagnostic, and v2 diagnostic are
separate artifacts; a diagnostic result must not be substituted for the
promotion decision.

## Checkpoint identity

- Merged checkpoint: `work/action-model-project2-qwopus35-9b-qlora-v1-merged`
- Base reference: `work/hf-models/Jackrong-Qwopus3.5-9B-v3`
- Adapter manifest SHA-256:
  `0d712d878258ef7e3e2151086a5082412afd935c0e2f6f93d3bf721f15f0f163`
- Merge manifest SHA-256:
  `3841cf528f911db45cc53b1b510d569599b1d064f1f581876a943575545af901`
- SFT: 3,972 examples, one epoch, weighted sampling, rank-64 QLoRA, NF4,
  max length 1,536, learning rate `3e-5`, 3,972 optimizer steps.
- Training manifest reports 19,812.3 MiB peak allocated VRAM and
  3,458,469 training tokens.

The manifest values are descriptive evidence for this checkpoint; they do
not establish that the checkpoint is better than the promoted 7B baseline.

## Frozen promotion matrix

Run from the Open Agent Harness OS project root only after confirming no other
GPU job is using the checkpoint:

```powershell
$py = 'python'
$root = '<workspace>'
$project1 = Join-Path $root 'outputs\local-action-model'
$project2 = Join-Path $root 'outputs\open-agent-harness-os'
$env:PYTHONPATH = "$project2;$project1;$(Join-Path $root 'work\ml-runtime-cu128');$(Join-Path $root 'work\ml-runtime-post')"
Push-Location $project2
try {
  & $py -m experiments.run_promotion_matrix `
    --project1-root $project1 `
    --checkpoint (Join-Path $root 'work\action-model-project2-qwopus35-9b-qlora-v1-merged') `
    --output experiments\results\research-project2-qwopus35-9b-promotion-greedy-v1.json `
    --task-spec benchmarks\fixtures\task-spec-research-v4.json `
    --task-spec benchmarks\fixtures\task-spec-industry-proxy-v1.json `
    --task-spec benchmarks\fixtures\task-spec-industry-proxy-v2.json `
    --seeds 0,1,2 --max-new-tokens 256 --quantization 4bit
} finally { Pop-Location }
```

The task-spec SHA-256 values are:

| Slice | SHA-256 |
|:---|:---|
| research-v4 | `9c4e3a4f643c21056dd8fe5437ffe180054cf7f96ad02f572910eb298369bfda` |
| industry-proxy-v1 | `c5c0e843f2edc27cdb10b2a2b5d394d5d64373d558f072f4cb0f49001c10cb5e` |
| industry-proxy-v2 | `eb4d071facde6b94e632d68b01caf43e3ae8f7cb456b504e52c38453304d1d6c` |

The promotion rule is machine-checked by:

```powershell
& $py -m experiments.promotion_decision `
  --matrix experiments\results\research-project2-qwopus35-9b-promotion-greedy-v1.json `
  --output experiments\results\research-project2-qwopus35-9b-promotion-decision-v1.json
```

Do not promote based on a partial matrix, a model-card score, or a diagnostic
slice. The decision requires complete frozen slices, independent replay,
valid traces, zero unsafe attempts, and no unknown task specifications.

## Diagnostics after the promotion process

The 20-task v1 diagnostic is frozen at:

`benchmarks/fixtures/task-spec-external-bar-lite-v1.json`

SHA-256:
`8d1d852b4cd181079effd7023df13655406de73ddfd6a65329ec6597adf6cae3`

The harder 32-task v2 diagnostic is frozen at:

`benchmarks/fixtures/task-spec-external-bar-lite-v2.json`

SHA-256:
`e6c2d7a34fc4317ed116ab882df1f9c6cd363aa60e9f7067329334b9491d785e`

Both diagnostics use seeds `0,1,2` and `max-new-tokens=256`. v2 additionally
records false completions, unverified actions, unknown actions, premature
finish rejections, and abstentions. Neither diagnostic is a native
TUA-Bench, OSWorld 2.0, or AgentDojo leaderboard result.

## Reporting order

1. Preserve the raw matrix and task-spec hashes.
2. Run the independent decision and replay checks.
3. Run v1 and v2 diagnostics as separate model-and-harness measurements.
4. Summarize family-level Wilson intervals and resource metrics.
5. Attempt verifier-backed RL only if frozen integrity/diagnostic evidence
   passes; keep capability promotion as a separate decision.
6. Report model-only, SFT, and verifier-backed conditions separately.

Before any RL command, authorize the run with the machine gate:

```powershell
& $py -m experiments.verified_rl_gate `
  --decision experiments\results\research-project2-qwopus35-9b-promotion-decision-v1.json `
  --external-bar-v1 experiments\results\research-project2-qwopus35-9b-external-bar-lite-v1.json `
  --external-bar-v2 experiments\results\research-project2-qwopus35-9b-external-bar-lite-v2.json `
  --checkpoint (Join-Path $root 'work\action-model-project2-qwopus35-9b-qlora-v1-merged') `
  --output experiments\results\verified-rl-gate-v2.json
```

The gate must return `passed=true`. It remains blocked until the matrix and
both diagnostics exist with valid traces, exact replay agreement, and zero
unsafe attempts. A capability rejection does not authorize promotion, but it
does not by itself prevent a controlled research RL run after those integrity
conditions pass.

After the gate passes, verify the Qwopus-compatible RL runner in dry-run mode
before allocating another GPU job. This checks tokenizer/protocol loading and
records the exact configuration without sampling or updating weights:

```powershell
$env:PYTHONPATH = "outputs\local-action-model;work\ml-runtime-cu128;work\ml-runtime-post"
python outputs\local-action-model\train\transformers_reinforce.py `
  --task-spec outputs\local-action-model\fixtures\tasks\task-spec-qwopus35-9b-rl-v1.json `
  --model-id work\action-model-project2-qwopus35-9b-qlora-v1-merged `
  --output-dir work\rl-dry-run-qwopus35-9b `
  --device cpu --dry-run --episodes 1 --max-new-tokens 64
```

The current dry-run manifest is at
`work/rl-dry-run-qwopus35-9b/rl_manifest.json`. It is compatibility evidence
only; it does not authorize RL or support an improvement claim.

