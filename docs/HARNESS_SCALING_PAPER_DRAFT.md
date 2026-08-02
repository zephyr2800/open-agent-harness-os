# Harness Scaling and Model–Runtime Co-Design

## Status

Methods and preregistration draft, 2026-08-02. This is not a completed paper
or a claim that the paired model has passed an external benchmark. It records
the question, controls, evidence boundary, and publication standard before the
active clean 9B candidate is evaluated.

## Abstract

Language-model agents are executable systems, not model checkpoints in
isolation. We present Open Agent Harness OS, a local-first runtime that
separates a probabilistic Action IR policy from deterministic authority,
execution, verification, evidence, replay, and promotion surfaces. The paper
tests a falsifiable capability-placement hypothesis: for a fixed task,
environment, model budget, and decoding budget, does an advanced verifier-first
harness benefit a compact Action IR-specialized policy disproportionately more
than a generic policy? We estimate this with a preregistered 2 × 2
model–harness factorial, independent trace replay, source-bound training
provenance, and a matched-budget control for test-time search.

The current repository supplies a runnable developer-preview harness and
source-bound release evidence. It does not yet supply the empirical conditions
required for a research-breakthrough or production-model claim: a promoted
clean-split compact checkpoint, the complete four-cell real-model result,
native external diagnostics, independent training replication, and a
deployment-specific security/usability review. Negative outcomes are intended
publication results, not reasons to change a frozen evaluator.

## 1. Question and contribution

The core question is whether useful agent capability can be placed partly in a
runtime rather than entirely in model weights. The harness owns tool schemas,
authority, state retention, verification, checkpoints, and recovery; the model
owns bounded probabilistic action selection, abstention, and response to
verified feedback. This follows the interface-design insight of
[SWE-agent](https://arxiv.org/abs/2405.15793), but treats each runtime feature
as an observable experimental factor rather than hidden prompt glue.

The intended contributions are:

1. An open typed Action IR plus model-agnostic execution, authority, evidence,
   trace, and replay runtime.
2. A fail-closed evaluation protocol that treats verifier evidence and replay
   as execution boundaries, not model self-reports.
3. A source-bound four-cell model–harness factorial with an estimable
   interaction term and explicit limits on its interpretation.
4. A bounded harness-evolution/post-training interface that protects the
   evaluator, permission boundary, model identity, and held-out tasks.

These are system and methodology contributions. The paper must not claim that
small models generally outperform larger ones, that the harness is secure in
all deployments, or that a local fixture score is an external benchmark score.

## 2. Related work and positioning

[ReAct](https://arxiv.org/abs/2210.03629) established action/observation loops;
[Agentless](https://arxiv.org/abs/2407.01489) showed why deterministic
baselines must survive; and [TinyAgent](https://arxiv.org/abs/2409.00608) and
[xLAM](https://arxiv.org/abs/2409.03215) motivate compact function/action
policies. Recent [Harness-Bench](https://arxiv.org/abs/2605.27922) makes the
experimental unit explicit: performance should be attributed to a
model–harness configuration under common task conditions, not to the model
alone. [VeRO](https://arxiv.org/abs/2602.22480) motivates versioned,
budget-controlled studies of agent evolution. [AgentS4D](https://arxiv.org/abs/2607.27294)
reinforces that successful completion is not sufficient evidence of runtime
safety across the execution lifecycle.

Our distinction is a local, verifier-first control plane paired with a
pre-registered interaction experiment. The release artifact makes promotion
and failure evidence inspectable; the empirical contribution remains pending
the measured factorial and external diagnostics.

## 3. System

The public runtime exposes a stable Action IR with `act`, `observe`, `abstain`,
and `finish` decisions. Registered tools carry schemas, preconditions, risk,
authority, side-effect, and verifier metadata. The runtime compiles bounded
state and evidence into each decision request; the policy gate decides whether
a proposed action may execute; independent verifiers and the trace recorder
establish what happened. H4 may propose changes only to bounded editable
middleware surfaces. It cannot rewrite evaluators, traces, authorization,
promotion policy, hidden tasks, or model identity.

The public package currently demonstrates this boundary through local CLI,
loopback HTTP, and MCP interfaces. Fresh v36 evidence records 16/16
developer-preview checks, 214 Project 2 tests (213 passed and one Windows
symlink-capability skip), and 47/47 companion-project tests. This is
reproducibility/product-control evidence, not a model-capability result.

## 4. Preregistered evaluation

For generic model \(M_g\), specialized compact model \(M_s\), deterministic
baseline harness \(H_1\), and co-designed context/checkpoint/recovery harness
\(H_3\), the primary interaction is:

\[
\Delta_{MH}=U(M_s,H_3)-U(M_s,H_1)-U(M_g,H_3)+U(M_g,H_1).
\]

All four cells use the same task specification, task-owned environment data,
model/output budgets, decoding settings, independent verifier, and replay
logic. H1 and H3 both hide evaluator-owned contract hints and disable
deterministic adapter repair; H3 is the advanced runtime treatment, not a
different evaluator. A separate matched-budget task-level retry/search arm is
required before attributing an improvement to reusable harness behavior.

Each completed result must bind model identities, checkpoint manifests,
training/holdout audit, task digest, source-tree digests, generation settings,
and all task × seed rows. The interaction analyzer rejects missing cells,
duplicate units, non-stochastic decoding, unsafe actions, invalid traces,
replay disagreement, repair leakage, or missing provenance before estimating a
task-cluster bootstrap interval. The interval is task-sampling uncertainty for
the named suite only; it is not a confidence interval over training replicas
or a general-agent capability claim.

## 5. Evidence status

The historical 9B Qwopus matrix recorded 483/552 independently verified local
successes with zero unsafe attempts and complete trace/replay checks, but was
rejected because the training-source isolation was not auditable. It is useful
failure-localization context and is not a promotion or paper result.

The clean 9B QLoRA candidate binds 3,232 audited training rows to a frozen
three-seed promotion protocol. Audited SFT and merged-checkpoint handoff are
complete; the promotion matrix was intentionally paused at 96 of 480 task-seed
attempts. Its partial output is preserved as non-decisional evidence and does
not authorize any downstream evaluation or training. A resumption requires
explicit operator direction and must preserve the frozen protocol, then produce
a separate decision artifact. Only a `promote` decision authorizes the
pre-registered native AgentDojo/tau2 diagnostics. It does not authorize RL by
itself.

## 6. Outcomes and publication criteria

A credible empirical paper result requires all of the following:

- complete matched four-cell rows across at least three stochastic seeds;
- independent replay and zero unsafe attempts for every reported unit;
- a disjoint author-held-out suite and native external diagnostic reported
  with its own grader and metric;
- family-level success, false-completion, abstention, recovery, tokens,
  latency, memory, energy (where measured), and cost reporting;
- an independent training replica where practical; and
- a matched-budget search control and an explicit negative-result path.

If the interaction is zero, negative, or confined to one local family, that is
the correct result. The paper will then separate a reproducible harness/product
contribution from an unsupported model–runtime synergy claim.

## 7. Threats to validity

Local synthetic and proxy tasks can overstate generalization, especially when
tool schemas or contracts are too predictable. Static injection tests are not
a lifecycle security certification. A three-seed decoding sweep does not
replace independent training replication. Whole-GPU energy sampling is not a
per-process or wall-socket measurement. Qwopus model-card labeling does not
replace a complete redistribution/provenance review. These limitations are
publication constraints, not footnotes.

## 8. Reproduction package and claim boundary

The repository distributes Apache-2.0 harness source, synthetic fixtures,
tests, documentation, and public reproducibility records. It intentionally
excludes local checkpoints, raw curricula, private traces, native benchmark
assets, and credentials. The public statement is therefore:

> We provide a local developer-preview harness that makes typed agent actions,
> authority decisions, verified state transitions, replay, and model-promotion
> evidence inspectable. The general model–harness claim is under evaluation.
