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

1. The live 9B matrix remains a scale and failure-localization experiment;
   it cannot be promoted from local proxy scores alone.
2. The policy-sequence, finish-DPO, and retry-repair interventions are the
   correct next causal test because the observed failures are repeated actions,
   premature completion, and missing evidence—not ordinary tool selection.
3. A breakthrough claim requires a disjoint author-held-out suite, three
   decoding seeds, a matched-budget search control, independent replay, zero
   unsafe attempts, and at least one native external-suite result.
4. The public product should remain a local developer preview until identity,
   operations, usability, provenance, and native external evaluation are
   complete. The public repository must not imply that local 100% slices are
   general agent competence.

The current state is therefore strategically coherent but scientifically
unfinished: the harness/product boundary is launchable as a developer preview,
while the research breakthrough is still an empirical gate awaiting the frozen
matrix and post-training ablations.
