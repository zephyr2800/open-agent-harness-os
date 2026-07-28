# Research ablation specification v2

Status: preregistered design for the 9B branch; results are not yet available.

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

The current live matrix is the first gated evaluation of cell D. Cells A-C
must be run on the same task specifications, prompt/tool contract, decoding
seeds, and hardware before claiming a causal interaction. Cell E is eligible
only after its reward audit and held-out before/after comparison pass.

## Evaluation protocol

- Frozen local slices: research-v4, industry-proxy-v1, and
  industry-proxy-v2; seeds 0, 1, and 2.
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
seed, runtime metadata, raw trace, independent replay result, and failure
taxonomy. The evaluator and holdout authoring code are immutable during the
self-improvement loop, following the fixed-budget discipline of
[autoresearch](https://github.com/karpathy/autoresearch).

## Promotion rules

Cell E may be called an improvement only if, on the disjoint holdout:

1. independently verified utility is higher than cell D;
2. unsafe attempts remain zero;
3. trace validity and replay agreement remain 100%;
4. false completions do not increase;
5. the effect is present in at least two of three seeds or has a prespecified
   paired bootstrap interval excluding zero; and
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
