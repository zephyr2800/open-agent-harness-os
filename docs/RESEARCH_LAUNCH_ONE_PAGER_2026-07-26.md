# Verified local action systems — research and launch one-pager

## The one-sentence thesis

Small local action models become materially more useful when the harness owns
authority, evidence, recovery, and replay—and when post-training is promoted
only from independently verified outcomes.

This is a systems claim, not a claim that a 9B model is a frontier general
agent.

## Why now

The current market and research direction validates the problem while raising
the bar:

- Thinking Machines' [Inkling release](https://thinkingmachines.ai/news/introducing-inkling/)
  makes customization and self-fine-tuning a visible product surface, and its
  [Tinker platform](https://thinkingmachines.ai/tinker/) treats model
  customization as an interactive workflow.
- [OSWorld 2.0](https://arxiv.org/abs/2606.29537) emphasizes long-horizon
  workflows, hidden state, cross-source constraints, and skipped verification;
  these are exactly the failure modes our harder v2 diagnostic targets.
- [AgentV-RL](https://arxiv.org/abs/2604.16004) demonstrates the field's move
  toward agentic verifiers and reward models. Our distinction is that the
  execution verifier is independent of the model and the trace is replayable.
- [ToolVerse](https://arxiv.org/abs/2607.15660) reinforces the importance of
  dependency-aware long-horizon task generation and turn-level credit
  assignment. [Tinker](https://thinkingmachines.ai/tinker/) also highlights
  on-policy self-distillation as a promising alternative to plain SFT for
  accumulating tool-use skills. We treat both as follow-up hypotheses, not as
  evidence for our current checkpoint.

## What exists today

### Research system

- Qwen/Qwopus3.5-9B-v3 Action IR QLoRA branch trained on the RTX 5090.
- Frozen 9B promotion matrix across hidden and industry-proxy slices, three
  seeds, independent replay, safety checks, and resource instrumentation.
- The frozen matrix includes a 120-task research-v4 slice, a 48-task
  industry-proxy-v1 slice, and a 16-task evidence-grounding/confirmation v2
  slice per seed.
- Machine-readable pre-RL gate; RL cannot start on an incomplete or failed
  promotion chain.

### Live evidence snapshot — 2026-07-27

The 9B matrix is still in progress at 507/552 task-runs: 450 verified
successes, 28 false completions, zero unsafe attempts, and 100% trace validity
and runtime/replay agreement. The current diagnostic finding is a replicated
termination-control failure, not a promotion claim; downstream RL and public
model-release decisions remain gated.

### Product system

- Local-first CLI, HTTP, and MCP surfaces.
- Typed Action IR, authority/risk policy, independent tool verifiers,
  evidence-grounded completion, bounded recovery, and tamper-evident replay.
- Loopback default, bearer-plus-TLS non-loopback gate, tenant trace isolation,
  authenticated rate limiting, security policy, Apache-2.0 package metadata,
  clean-wheel smoke, and the historical 12/12 preview preflight checks.

## The falsifiable breakthrough experiment

Use the same checkpoint, task authoring, schemas, seeds, and decoding budget
for three conditions:

1. model-only Action IR policy;
2. Action IR SFT without runtime repair;
3. the same policy behind independent verification, evidence, recovery, and
   replay.

Report verified completion, false completion, unsafe attempts, unsupported
actions, state-dependent ordering, recovery success, replay agreement,
latency, and tokens. The result becomes paper-grade only when it survives a
freshly authored holdout and at least one native external suite.

## Launch language

Say:

> “We are building a local, verifiable action-policy stack: small models can
> specialize cheaply, while the harness independently decides whether actions
> were authorized, executed, evidenced, and replayable.”

Do not say yet:

- “The 9B branch beats the 7B baseline.”
- “We are generally capable on computer use.”
- “RL improved the model.”
- “Production-ready autonomous agent.”

Those claims remain gated on the frozen 9B result, adversarial diagnostics,
external benchmark evidence, and production security/provenance review.

## Near-term launch sequence

1. Finish and audit the 9B matrix.
2. Run v1 and adversarial v2 diagnostics; publish family-level intervals and
   resource/replay metrics.
3. Run the machine pre-RL gate; only then attempt verifier-backed RL with a
   held-out control.
4. Release the local developer preview with the clean wheel, reproducibility
   chain, security boundary, and explicit limitations.
5. Complete external benchmark, usability, identity/operations, licensing,
   and deployment-security review before calling it a public launch.
