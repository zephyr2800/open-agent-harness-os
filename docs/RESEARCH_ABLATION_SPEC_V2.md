# Research ablation specification v2

Status: preregistered design for the 9B branch; no causal-cell result is
available until the train/holdout isolation gate passes.

## Claim

The testable claim is not “a structured harness makes an agent intelligent.”
It is:

> A compact typed-action policy, when coupled to an independent
> authority/evidence/replay plane and a failure-targeted self-improvement loop,
> increases independently verified utility on stateful action tasks without
> increasing unsafe actions or unverifiable completion.

This wording is intentionally narrower because [StructAgent](https://arxiv.org/abs/2607.11388)
is now a close comparison for verifier-backed state and progress checkpointing.

## Five-cell causal comparison

| Cell | Policy | Harness | Self-improvement | Purpose |
|---|---|---|---|---|
| A | Qwopus base | baseline typed runtime | none | base capability control |
| B | Action-IR QLoRA SFT | baseline typed runtime | none | policy-specialization effect |
| C | Qwopus base | verifier/evidence/replay runtime | none | harness-only effect |
| D | Action-IR QLoRA SFT | verifier/evidence/replay runtime | none | model × harness interaction |
| E | Action-IR QLoRA SFT | verifier/evidence/replay runtime | frozen-evaluator remediation/RL | self-improvement effect |

Interpretation control: Cells C and D mean the H3 advanced
context/checkpoint/recovery bundle while the scorer and verifier remain
external and common across A-D. Deterministic adapter repair is excluded from
A-D and may appear only in a separately preregistered Cell E/remediation arm.

The prior targeted 9B matrix is diagnostic only: a subsequent data-split audit
found frozen-contract overlap in its targeted curriculum. Its score cannot be
used as cell-D, held-out, or promotion evidence. The next cell-D candidate must
record a passing train/holdout audit before evaluation. Its greedy seeds are
deterministic reproducibility replicas, not stochastic samples. Cells A-C must
be run on the same task specifications,
prompt/tool contract, decoding mode, seed policy, and hardware before claiming
a causal interaction. Cell E is eligible only after its reward audit and
held-out before/after comparison pass.

## Evaluation protocol

- Active frozen local slices (promotion protocol `v2`): research-v4,
  industry-proxy-v2, and the post-freeze author holdout; greedy
  reproducibility replicas at seeds 0, 1, and 2, plus a separately reported
  `do_sample=true` stochastic audit at the same seeds. The high-affinity
  industry-proxy-v1 remains a historical diagnostic only.
- Mandatory data-isolation gate: an auditable source manifest plus a passing
  `experiments.data_split_audit` result against all seven pinned fixture
  hashes (legacy and active promotion slices, author holdout, exact-payload
  holdout, and external-bar-lite v1/v2) before any score may be described as
  held-out. The same manifest digest is required by the matrix, promotion,
  and RL gates, and its training-data fingerprints must match the merged
  checkpoint's copied training manifest.
- Disjoint diagnostics: external-bar-lite and the exact-payload holdout.
- Native reality check: pinned AgentDojo workspace cases, with clean and
  direct-injection cases reported separately.
- Primary metric: independently verified task utility.
- Safety metrics: unsafe attempts, high-risk execution, policy-denied versus
  model-avoided actions, and injection attack success.
- Integrity metrics: trace validity, runtime/replay agreement, evidence count,
  false completion, expected-result grounding, and shortcut indicators.
- Operations metrics: wall-clock latency, generated tokens, peak VRAM, and
  per-task GPU time on the RTX 5090.

Every run stores the checkpoint hash, task-spec hash, prompt/tool contract,
decoding mode and sampling parameters, seed, runtime metadata, raw trace,
independent replay result, and failure taxonomy. The evaluator and holdout
authoring code are immutable during the self-improvement loop, following the
fixed-budget discipline of
[autoresearch](https://github.com/karpathy/autoresearch).

### Factorial execution-integrity controls — preregistered 2026-08-02

The real Project 1 × Project 2 factorial must use the versioned
`multiseed-project1-harness/v1` report shape. Its H1 and H3 cells both set
`expose_contract_hints = false`: evaluator-owned expected tools and action
arguments must never be shown to the model. Both H1 and H3 set
`adapter_enable_repair = false`; their common scorer, executor, evidence
ledger, and verifier remain outside the model. H3 is the explicitly recorded
advanced context/checkpoint/recovery treatment, not a new verifier plane. The
report binds the task-spec SHA-256, model identifiers, the path and SHA-256 of
an immutable checkpoint-identity manifest for each model, sampling parameters,
per-row controls, unsafe-attempt accounting, raw trace, independent replay
result, source-tree records, a passing train/holdout audit, and the specialized
merged-checkpoint binding to that audit. This corrects the older generic
real-runner shape, which was plumbing only and cannot support a causal
H1-versus-H3 claim.

`experiments.factorial_interaction` independently replays every required row
and fails closed unless all four named cells contain exactly the same
seed × task units, carry the expected controls, use three-or-more stochastic
seeds, match the supplied task digest, agree with runtime success, and record
zero unsafe attempts. It estimates
`specialized/H3 - specialized/H1 - generic/H3 + generic/H1` with a
task-cluster percentile bootstrap that retains all seed outcomes for each
resampled task. The interval is task-sampling uncertainty for that named suite;
it is not training-replica uncertainty, a native score, or a general-capability
claim.

[Claw-SWE-Bench](https://arxiv.org/abs/2606.12344) reinforces why prompt,
workspace, runtime budget, evaluator, and cost need to be fixed across harness
comparisons. [How Many Tasks Are Enough for Agent Benchmark
Decisions?](https://arxiv.org/abs/2607.12338) reinforces why coverage and an
explicit decision rule must accompany any partial or costly evaluation. These
controls are post-gate research instrumentation only: they do not modify
promotion protocol v2, its task fixtures, the active trainer, or RL
authorization.

## Sampling and curriculum control

The active clean 9B baseline uses `uniform` sampling: all 3,232 audited rows
are seen once in a seeded permutation during its single epoch. Its stored
per-row sampling weights are therefore intentionally inactive in that run.
This distinction matters: a later result may not call itself a data-sampling
improvement merely because the same curriculum contains weights.

If the frozen baseline rejects and its error ledger localizes a failure family,
the first sampling intervention is a preregistered two-arm, full-coverage
order ablation on the exact same clean training-source hash:

| Arm | Row exposure | Ordering | Held fixed |
|---|---|---|---|
| Uniform control | Every row exactly once/epoch | seeded uniform permutation | base, tokenizer, response masking, epoch count, optimizer steps, LoRA rank, context limit, and evaluation protocol |
| Weighted-order arm | Every row exactly once/epoch | seeded Efraimidis-Spirakis weighted permutation using the committed row weights | the same factors and data hash |

The weighted arm is not replacement sampling and does not oversample rows; it
only changes when an equally exposed row is encountered. It is eligible only
as a separately named post-baseline branch, with the error slice fixed before
training and a fresh disjoint evaluation slice held outside curriculum design.
No sampling strategy is accepted because it improves a local aggregate while
regressing the worst failure family, unsafe-attempt rate, false completion, or
replay agreement.

## Promotion rules

Cell E may be called an improvement only if, on the disjoint holdout:

1. independently verified utility is higher than cell D;
2. unsafe attempts remain zero;
3. trace validity and replay agreement remain 100%;
4. false completions do not increase;
5. the effect is present in at least two of three genuinely stochastic decoding
   seeds (or independently trained replicas, explicitly labeled) or has a
   prespecified paired bootstrap interval excluding zero; and
6. the result survives one native-runtime diagnostic without changing the
   evaluator or adding a hidden guard that is absent from the baseline.

A failure is still a useful research result. It must be reported as a
  negative or neutral self-improvement result rather than silently switching
  checkpoints.

## External bar alignment

[WeaveBench](https://arxiv.org/abs/2606.09426) shows why hybrid GUI/CLI/code
workflows and trajectory-aware judging matter. [WildClawBench](https://arxiv.org/abs/2605.10912)
shows that native runtime and harness choice materially affect outcomes.
[SWE-Marathon](https://arxiv.org/abs/2606.07682) shows why multi-channel
verification and reward-hacking audits are necessary for long-horizon claims.
[General AgentBench](https://arxiv.org/abs/2602.18998) motivates measuring the
verification gap, not only the existence of a successful sampled trajectory.

The local fixtures therefore remain diagnostic. A public claim must include a
fresh native-suite result with that suite's native metric, environment,
version/commit, grader limitations, and a same-checkpoint harness ablation.
