# Research and launch update - 2026-08-01

This note refreshes the external bar after the 9B scale-branch evaluation was
started. It is a positioning and protocol update, not a new capability claim.

## External bar

- [TUA-Bench](https://arxiv.org/abs/2606.28480) evaluates 120 real terminal
  workflows across documents, email, web, scientific, and engineering tasks.
  Its strongest reported configuration reaches 65.8% overall. The lesson for
  this project is to report native execution, task-family failures, and cost,
  not only Action IR validity.
- [OSWorld 2.0](https://arxiv.org/abs/2606.29537) contains 108 long-horizon
  workflows with realistic cross-source and implicit-state dependencies. Even
  a frontier configuration reaches only 20.6% binary completion at 500 steps,
  with 54.8% partial credit. This directly validates our focus on state,
  evidence, clarification, and finalization failures.
- [OpenComputer](https://arxiv.org/abs/2605.19769) is a useful adjacent
  systems reference: it combines verifiable software worlds, app-specific
  state verifiers, execution-grounded verifier improvement, and auditable
  partial-credit trajectories. Our claimed contribution must therefore be the
  compact-policy / independent-authority / promotion interaction, not merely
  the existence of a verifier.
- [Evidence-Grounded Verified Agentic Reasoning](https://arxiv.org/abs/2607.12650)
  and [Self-Modifying Lean Proof Agents](https://arxiv.org/abs/2607.17352)
  reinforce the same experimental requirement: self-improvement counts only
  when an external verifier accepts the result on a disjoint holdout.

## Product and model signals

- [Thinking Machines' Inkling](https://thinkingmachines.ai/news/introducing-inkling/)
  and [Tinker](https://thinkingmachines.ai/tinker/) make open-weight
  customization and researcher-controlled post-training a product surface.
  Our local policy-training pipeline is directionally aligned, but its value
  depends on publishing the data provenance, rollout budget, verifier, and
  held-out result together.
- [Moonshot's official Kimi K3 repository](https://github.com/MoonshotAI/Kimi-K3)
  describes a 2.8T-parameter, 104B-active MoE with Kimi Delta Attention,
  Attention Residuals, native vision, and a 1M-token context window. This is a
  scale and systems signal, not a fair RTX 5090 comparison. It strengthens our
  decision to optimize verified utility, resource cost, and replayability
  rather than chase a raw parameter leaderboard.
- [OpenAI's Agents SDK update](https://openai.com/index/the-next-evolution-of-the-agents-sdk/)
  makes sandbox execution, snapshotting, and rehydration part of the expected
  agent platform. The launch implication is that isolation, recovery,
  observability, and authority boundaries must be first-class product
  surfaces.

## Consequences for this project

1. Two 9B results must remain distinct and context-only in public claims: the
   completed historical frozen promotion matrix is summarized as 483/552
   independently verified with promotion rejected, but its source-corpus split
   is not auditably recorded. A later targeted curriculum was found to overlap
   with frozen proxy contracts, so its matrix was stopped at a saved 441-row
   partial and remains diagnostic only. Neither result can be promoted from
   local proxy scores alone.
2. The policy-sequence, finish-DPO, and retry-repair interventions are the
   correct next causal test because the observed failures are repeated actions,
   premature completion, and missing evidence—not ordinary tool selection.
3. A breakthrough claim requires a disjoint author-held-out suite, three
   genuinely stochastic decoding seeds (not greedy replicas), a matched-budget
   search control, independent replay, zero unsafe attempts, and at least one
   native external-suite result.
4. The public product should remain a local developer preview until identity,
   operations, usability, provenance, and native external evaluation are
   complete. The public repository must not imply that local 100% slices are
   general agent competence.

The current state is therefore strategically coherent but scientifically
unfinished: the harness/product boundary is launchable as a developer preview,
while the research breakthrough is still an empirical gate awaiting a
clean-split candidate, stochastic audit, post-training ablations, and native
external evaluation. This is separate from the diagnostic historical matrices
summarized above.

## August 2 protocol update: fixed external evaluation is necessary but not sufficient

The checked-in
[`native-external-registration-v1.json`](../benchmarks/fixtures/native-external-registration-v1.json)
now freezes the first external diagnostic before the active clean 9B checkpoint
can be evaluated. It binds the clean SFT source fingerprint, benchmark commits,
deterministic decoding, 256-token response limit, and matched `model-only` /
`repair` order. The executable launchers record the registration hash and the
result validators reject an altered registration file.

- AgentDojo is frozen to five previously unobserved workspace user tasks for
  the clean condition, then those same users crossed with three direct
  injections (15 pairs plus three native injection controls).
- The local tau2 condition is frozen to six valid telecom/base solo tasks,
  stratified as two tasks from each of three task families at one trial, 30
  steps, and 10 errors.

This improves falsifiability by preventing task/budget substitution after a
checkpoint is available. It does not turn the small diagnostic into a complete
benchmark score or an adaptive-security result. In particular,
[AutoDojo](https://arxiv.org/abs/2606.15057) reports that adaptive black-box
injections can defeat defenses that appear robust to static injections. The
fixed AgentDojo result therefore remains the reproducible Phase A gate; an
adaptive red-team Phase B must be separately preregistered, use a held-out
attack process, preserve the same utility measurement, and report attack
success alongside false refusals. No current result supports a security
certification.

The concrete conditional Phase B protocol, including the pinned AutoDojo
source, local-endpoint compatibility boundary, cache provenance, matched
model-only/repair arms, and public-data exclusion rule, is recorded in
[`ADAPTIVE_EXTERNAL_EVALUATION_2026-08-02.md`](ADAPTIVE_EXTERNAL_EVALUATION_2026-08-02.md).
