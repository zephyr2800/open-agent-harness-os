# Research and launch landscape - 2026-07-29

This note updates the project's positioning against the current agent
research and product bar. The central conclusion is that the interesting unit
is not a model score in isolation: it is a model-harness-environment
configuration with observable actions, state, evidence, safety outcomes, and
cost.

The current local result is summarized in
[`RESEARCH_MATRIX_9B_2026-07-29.md`](RESEARCH_MATRIX_9B_2026-07-29.md): the
9B frozen matrix is complete and replay-valid but correctly rejected for
promotion because its failures concentrate in long-horizon control and
evidence-grounded finalization.

## Papers and evaluation systems that set the bar

- [Harness-Bench](https://arxiv.org/abs/2605.27922) evaluates 106 sandboxed
  tasks across 5,194 trajectories and reports completion, process quality,
  efficiency, and failure behavior at the model-harness level. This directly
  supports the project's configuration-level hypothesis.
- [TUA-Bench](https://arxiv.org/abs/2606.28480) contains 120 real terminal
  tasks across five families, including document, email, web, scientific, and
  engineering workflows. It reports native execution-based grading, not a
  synthetic action-contract score. This is the closest current external bar
  for a terminal-use launch claim.
- [General Agent Evaluation / Exgentic](https://arxiv.org/abs/2602.22953)
  and the [Open Agent Leaderboard](https://www.exgentic.ai/) treat the agent
  scaffold, environment, trajectory, and cost as first-class experimental
  variables. The project should adopt the same reproducibility discipline.
- [HAL](https://hal.cs.princeton.edu/about) provides cost-controlled,
  cross-benchmark evaluation with standardized traces and token accounting.
  The missing piece in our current local reports is a similarly portable
  scorecard across configurations.
- [ToolSandbox](https://arxiv.org/abs/2408.04682) stresses stateful tools,
  implicit dependencies, conversational user simulation, canonicalization,
  and insufficient-information handling. Our proxy covers some of these, but
  the native benchmark remains external evidence.
- [AgentDojo](https://arxiv.org/abs/2406.13352) evaluates prompt injection in
  dynamic environments with 97 tasks and 629 security test cases. The
  project's authority/evidence separation is relevant, but a local proxy or a
  single task is not AgentDojo certification.
- [OpenEnv in practice](https://huggingface.co/blog/openenv-turing) uses a
  reset/step/action/observation contract and MCP connectivity to evaluate
  stateful environments closer to real systems. This is a useful integration
  shape for the next benchmark adapter.
- [Large Language Model Post-Training: A Unified View](https://arxiv.org/abs/2604.07941)
  frames SFT, preference optimization, RL, verifiers, and distillation as
  support expansion, policy reshaping, and behavioral consolidation. It
  supports our stage order: teach the Action IR contract first, then use
  on-policy verifier-backed training only after the baseline is measurable.
- [RLFactory](https://arxiv.org/abs/2509.06980) is a useful engineering
  reference for multi-turn tool-use RL. It reinforces that environment
  throughput, rollout validity, and reward design are part of the research
  result rather than implementation detail.

## Product launches and open infrastructure signals

- [Microsoft Agent Framework Harness](https://devblogs.microsoft.com/agent-framework/the-microsoft-agent-framework-harness-is-now-released/)
  ships file memory, skills, tool approval, and OpenTelemetry. The product
  bar is therefore not merely a loop around a model; it includes durable
  state, approval boundaries, and observability.
- [Microsoft ASSERT and Agent Control Specification](https://devblogs.microsoft.com/foundry/build-2026-open-trust-stack-ai-agents/)
  make policy-driven evaluation and portable control a public ecosystem
  direction. Our scorecard and typed authority plane should be positioned as
  a compatible research implementation, not as a replacement for a standard.
- [Google Gemini 3.5 Flash computer use](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-computer-use-gemini-3-5-flash/)
  explicitly advertises confirmation for sensitive actions and automatic
  stopping on detected indirect prompt injection. That makes confirmation and
  injection behavior launch metrics, not optional safety prose.
- [OpenAI Computer-Using Agent](https://openai.com/index/computer-using-agent/)
  reports native OSWorld, WebArena, and WebVoyager numbers using a universal
  screen/mouse/keyboard interface. A local Action IR score must not be
  compared to those numbers without running the native suite and metric.
- [Thinking Machines Tinker](https://tinker-docs.thinkingmachines.ai/) exposes
  researcher-controlled post-training loops while hiding distributed systems
  complexity. The local analogue is a reproducible verifier environment and
  explicit rollout/reward manifests; an RL result without those artifacts is
  not reproducible research.
- [Thinking Machines Inkling](https://thinkingmachines.ai/news/introducing-inkling/)
  is the current open-weights/customization launch signal: sparse scaling,
  controllable effort, multimodality, and a self-fine-tuning demonstration.
  It strengthens the case for separating a customizable policy from an
  independent control/evidence plane.
- [Moonshot's Kimi K3 technical report](https://arxiv.org/abs/2607.24653)
  and [official repository](https://github.com/MoonshotAI/Kimi-K3) provide a
  current open-weight frontier reference. Its scale and architecture are a
  market signal, not a fair single-5090 baseline; compare local systems on
  verified utility, latency, and cost instead.
- [Pi mono](https://github.com/earendil-works/pi-mono) is a useful current
  reference for a minimal, stateful, provider-neutral agent runtime. It is
  adjacent infrastructure, not evidence for model capability; our research
  contribution is the verifier/evidence/promotion layer around the policy.
- [Hugging Face agent evaluation guidance](https://huggingface.co/blog/is-it-agentic-enough)
  and [Community Evals](https://huggingface.co/blog/eee-community-evals)
  emphasize running real tools, repeated trials, trajectory evidence, and
  standardized result metadata. This is the right eventual publication path
  for model and harness cards.

## What is actually novel enough to test

The defensible research hypothesis is:

> A typed, verifier-first authority and evidence plane can improve the
> reliability of a compact tool-use policy by converting unverified progress
> and false completion into recoverable training signals, while preserving
> safety and replayability across task and tool perturbations.

This is stronger than “the model got 100% on a local fixture” and narrower
than “we built a generally capable agent.” It predicts a measurable
model-by-harness interaction and makes concrete failure modes falsifiable:
long-horizon state loss, evidence-grounding failure, confirmation failure,
prompt injection, false completion, and budget exhaustion.

## Required next evidence

1. Publish the complete 9B frozen scorecard and failure taxonomy: all three
   seeds are now present, replay-valid, and zero-unsafe, but the promotion gate
   rejects the failed long-horizon and evidence-grounded slices.
2. Run a disjoint author-held-out suite with macro-family scoring, Wilson
   intervals, unsafe-attempt rate, false-completion rate, trace validity,
   replay agreement, latency, and output-token cost.
3. Run at least one native external suite, starting with AgentDojo or
   TUA-Bench, and report its native metric, commit, environment, and harness
   configuration. A local proxy remains explicitly labeled local.
4. Compare the same model under model-only, verifier-first repair, and
   verifier-backed post-training conditions. Keep evaluator, holdout, and
   replay code outside the learned policy.
5. Only after the complete pre-RL baseline is frozen, run verifier-backed RL
   with decomposed rewards for valid Action IR, verified state transition,
   evidence-grounded finalization, safe abstention, and efficiency. A reward
   improvement is not a capability promotion until it survives the held-out
   and external gates.
6. Ship the product as a local developer preview with explicit loopback,
   token/TLS, trace-isolation, and tool-security boundaries. Production
   multi-tenant launch still requires identity lifecycle, operations,
   usability, licensing, and security review.

## Claim control

The repository may currently claim a verifiable local harness and local
fixture/proxy results. It may not yet claim general terminal or computer-use
capability, superiority to frontier agents, production safety for arbitrary
tools/content, or verifier-backed RL improvement. The new scorecard rejects
an `external_native` label unless the native suite metric/value, suite commit,
native report hash, grader identity, and runner/runtime/platform metadata are
present.
