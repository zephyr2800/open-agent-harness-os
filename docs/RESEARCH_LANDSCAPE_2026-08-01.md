# Research and launch landscape — 2026-08-01

This note refreshes the research and product bar for the paired local policy
and verifier-first harness. It is a positioning and experiment-design note,
not a claim that the current checkpoint has passed the research gates.

## The field has moved toward configuration-level evaluation

- [Harness-Bench](https://arxiv.org/abs/2605.27922) measures harness effects
  across realistic workflows. This is the closest conceptual match to our
  model/policy/harness interaction hypothesis.
- [HarnessAudit-Bench](https://arxiv.org/abs/2605.14271) evaluates safety
  constraints across domains and agent configurations. It reinforces that
  authorization, auditability, and failure behavior must be measured beside
  task completion.
- [TUA-Bench](https://tuabench.ai/) and its
  [paper](https://arxiv.org/abs/2606.28480) provide a native terminal-use bar
  with execution-graded workflows. Our Action IR fixtures must remain labeled
  local proxies until a native run is completed.
- [Claw-SWE-Bench](https://arxiv.org/abs/2606.12344) treats harness behavior,
  cost, and execution outcomes as first-class axes for coding agents. It is a
  useful warning against reporting only pass rate.
- [Terminal-Bench](https://github.com/harbor-framework/terminal-bench) remains
  a practical external path for real terminal environments, including
  scientific, engineering, API, and security tasks.

The methodological consequence is direct: a high local score is useful for
failure localization, but a research result requires a fixed model-only
control, an unchanged held-out suite, independent replay, safety accounting,
and at least one native external metric.

## Product signals support the two-layer thesis

- [Thinking Machines' Inkling launch](https://thinkingmachines.ai/news/introducing-inkling/)
  makes open-weight customization a product surface. The strategic opening
  for this project is the deployable layer around customization: reproducible
  data, verifiable execution, evidence, replay, and promotion gates.
- [Thinking Machines' Tinker](https://thinkingmachines.ai/news/announcing-tinker/)
  shows that controlled post-training is becoming infrastructure. Our local
  analogue must expose rollout provenance, decomposed rewards, held-out gates,
  and failed-run artifacts rather than presenting an opaque RL score.
- [Moonshot AI's public repositories](https://github.com/MoonshotAI) and the
  current Kimi reports reinforce that large-model architecture is moving fast.
  A single RTX 5090 should therefore be positioned as a reproducible policy
  and harness laboratory, not as a fair frontier-scale pretraining baseline.

## The falsifiable research claim

> For a fixed compact policy and deployment budget, a typed verifier-first
> authority/evidence plane can convert false completion and unverified
> progress into recoverable training signals, improving held-out verified
> utility without increasing unsafe actions, replay disagreement, or cost
> beyond the stated budget.

This claim is narrower and more valuable than “the model is generally
autonomous.” It predicts a measurable interaction between policy and harness
and names the failure modes that could falsify it: long-horizon state loss,
evidence-grounding failure, retry loops, confirmation failure, injection
failure, and budget exhaustion.

## Required experiment sequence

1. Finish the frozen 9B model-only matrix and publish its complete negative
   evidence internally before reading any remediation result.
2. Run the same checkpoint with verifier-first repair as a harness ablation;
   report it separately from model learning.
3. Run retry/evidence-targeted post-training on a fixed base and evaluate on
   the same holdout plus a freshly authored disjoint suite.
4. Run the native AgentDojo or TUA-Bench adapter with the suite's own metric,
   exact source commit, runtime manifest, and per-result hashes.
5. Only if safety, replay, held-out, and external gates pass, run decomposed
   verifier-backed RL. A reward increase by itself is not a promotion result.

Every stage must retain the model-only control, family-level scores, Wilson
intervals, false-completion rate, safe-abstention rate, unsafe-attempt rate,
trace validity, replay agreement, latency, output tokens, and peak memory.

## Launch boundary

The local developer preview is the near-term product: typed Action IR,
allowlisted execution, independent evidence, replay, bounded recovery, local
HTTP/MCP surfaces, and explicit authentication/TLS boundaries. The public
repository can ship that infrastructure with claim-safe local fixtures.

Production or general autonomous-agent claims remain gated on native external
evaluation, representative usability sessions, per-tool security review,
identity and operations, licensing/provenance review, and deployment-specific
resource limits. The public launch message should be:

> We make customizable local agents verifiable: the model proposes typed
> actions, the harness controls authority and proves state transitions, and
> every promotion decision is replayable.

