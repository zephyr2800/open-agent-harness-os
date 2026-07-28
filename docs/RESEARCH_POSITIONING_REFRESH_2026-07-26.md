# Research positioning refresh — 2026-07-26

This note records the current external signal that changes the paired
Action-Model/Harness-OS research plan. It is a positioning and experiment
design update, not evidence for our own model scores.

## What the current field is rewarding

### 1. Customization is a product wedge, not an afterthought

Thinking Machines positions Inkling as an open-weights base for customization
and demonstrates a model writing, running, and evaluating its own fine-tuning
job. Its Tinker product exposes the training loop and makes evaluation part of
the workflow. The relevant analogy for us is not the scale of Inkling; it is
the product boundary: a useful local policy stack should make specialization,
evaluation, and rollback first-class operations.

- [Inkling announcement](https://thinkingmachines.ai/news/introducing-inkling/)
- [Tinker](https://thinkingmachines.ai/tinker/)
- [Tinker Cookbook](https://github.com/thinking-machines-lab/tinker-cookbook)

### 2. Verifiers must be grounded in the environment

Recent work on self-evolving tool-use data and verifier-backed RL combines
executable per-instance checkers with closed-loop data generation. AgentV-RL
further argues for tool-augmented, bidirectional verification because a
verifier can otherwise propagate an incorrect intermediate state. This is
consistent with our negative 7B RL result: the next experiment needs better
state/evidence verifiers and harder exploration, not simply more REINFORCE
steps.

- [Self-Evolving Synthetic Data to Verifiable-Reward RL](https://arxiv.org/abs/2601.22607)
- [AgentV-RL: Scaling Reward Modeling with Agentic Verifier](https://arxiv.org/abs/2604.16004)

### 3. Harness configuration is part of the benchmark

Kimi K3 reports long-horizon coding and knowledge-work results while explicitly
documenting different harnesses, reasoning efforts, task limits, GPU
calibration, and evaluator settings. Its public engineering description also
separates model architecture from the serving/runtime stack. This reinforces
our rule that a score without the exact harness, prompt surface, token budget,
sampling, timeout, and replay audit is not an interpretable comparison.

- [Kimi K3 technical announcement](https://www.kimi.com/ja/blog/kimi-k3)
- [Kimi Code release notes](https://www.kimi.com/code/docs/en/kimi-code/whats-new.html)

### 4. The external difficulty bar moved from tool calls to sustained execution

Toolathlon, Long-Horizon-Terminal-Bench, AgencyBench, and MCP-Atlas make the
local 16/48-task proxy useful for diagnosis but insufficient for a broad
agent claim. They cover real application state, long terminal horizons,
continuous or claim-level grading, and much larger tool surfaces. SIA is also
now a direct adjacent system because it updates both a harness and model
weights in an iterative loop. Our differentiator therefore cannot be “agents
that self-improve.” It must be the controlled interaction between a compact
typed-action policy and an independent authority/evidence/replay plane whose
evaluator, task holdout, and promotion gate are immutable to the improvement
loop.

- [Toolathlon](https://arxiv.org/abs/2510.25726)
- [Long-Horizon-Terminal-Bench](https://arxiv.org/abs/2607.08964)
- [AgencyBench](https://arxiv.org/abs/2601.11044)
- [MCP-Atlas](https://arxiv.org/abs/2602.00933)
- [SIA](https://arxiv.org/abs/2605.27276) and its
  [open implementation](https://github.com/hexo-ai/sia)

The next external evaluation should report continuous partial utility,
verified completion, unsafe/unauthorized attempts, replay agreement,
verification cost, latency, and token/tool-call budget. A single binary task
success number would hide the exact long-horizon failure mode already visible
in our 9B matrix.

### 5. Product signal: the loop itself is becoming the platform

Harness Agent DLC and Prime Intellect Lab both position build, evaluation,
training, rollout inspection, and deployment as one agent-development loop.
That validates the product direction but raises the launch bar: our product
must be legible as a governed local control plane with reproducible evidence,
not another generic agent framework. The developer preview can lead with
typed actions, authority checks, independent evidence, replay, and rollback;
public launch still requires external-suite results, provenance review,
identity/operations, and usability evidence.

- [Harness Agent DLC](https://www.harness.io/press-and-news/introducing-harness-agent-dlc)
- [Prime Intellect Lab](https://www.primeintellect.ai/blog/lab-is-open)

## What changes in our design

1. **Primary claim:** specialize a local model for verifiable state-changing
   actions while preserving a general baseline, using an independently
   replayable control plane.
2. **Core ablation:** model-only vs. verifier-backed harness vs.
   verifier-backed post-training, with the same frozen task, prompt, decoding,
   and resource configuration.
3. **Verifier design:** score state transition, exact tool arguments, evidence
   provenance, final answer grounding, safety/authority, and replay agreement
   separately; do not collapse them into a single opaque reward.
4. **Self-improvement loop:** generate candidate tasks from observed failures,
   filter them with independent checkers, hold out an author-controlled slice,
   train one controlled branch, and rerun the complete matrix. The evaluator,
   trace recorder, model identity, and promotion rules stay protected.
5. **Launch wedge:** ship the harness and local policy/evaluation workflow as
   the product. A larger checkpoint is an optional backend, not the product
   claim.

## Differentiation we must prove

The external direction is converging on scalable post-training, agentic
verifiers, and customization platforms. Our distinct, falsifiable contribution
must therefore be the measured combination of:

- typed Action IR rather than unconstrained tool text;
- evidence-grounded completion rather than self-reported success;
- independent replay and tamper-evident traces;
- safety/authority checks that remain outside the model;
- local, resource-bounded specialization on a single consumer GPU; and
- a held-out failure-generation loop that does not let the model or evaluator
  rewrite its own promotion rules.

Until the 9B matrix and external-bar diagnostic complete, this is a research
hypothesis and launch positioning—not a claim of frontier competence.

## July 26 research update: two experiments worth importing

Two newer field signals sharpen the next experiment without changing the
claim boundary:

- [ToolVerse](https://arxiv.org/abs/2607.15660) constructs executable
  environments from many MCPs, samples long-horizon tasks from tool-dependency
  graphs, and reports turn-aware relative-advantage credit assignment. For our
  harness this suggests measuring dependency depth, first-invalid-step, and
  recovery distance, then stratifying sampling by those quantities instead of
  treating every task as an interchangeable row.
- [Tinker’s SDFT discussion](https://thinkingmachines.ai/tinker/) reports
  on-policy self-distillation outperforming standard SFT on its cited skill
  learning comparison, including tool use. We should test the analogous local
  condition only after the independent verifier gate passes: generate an
  expert-context trajectory, sample the policy’s own Action IR trajectory,
  filter it with the protected verifier, and compare SFT against filtered
  self-distillation on a fresh holdout. The verifier must remain outside the
  model and the holdout must remain author-controlled.

These are experiment inputs, not borrowed performance claims. The immediate
9B matrix remains the required baseline; neither idea justifies starting RL or
claiming a breakthrough before the frozen evidence chain is complete.

## Fresh triangulation: what the current research bar implies

The latest primary work makes the experimental boundary more precise:

- [OSWorld 2.0](https://arxiv.org/abs/2606.29537) stresses long-horizon,
  stateful workflows and reports that frontier agents still fail on hidden
  state, cross-source constraints, asking instead of guessing, and skipped
  verification. Our external-bar work should therefore report state recovery,
  unsupported completion, and tool-sequence errors—not only binary task
  success.
- [Controllable and Verifiable Tool-Use Data Synthesis](https://arxiv.org/abs/2604.09813)
  supports the direction of generating trajectories with machine-checkable
  outcomes and special-case error verification. This reinforces our decision
  to expand native-tool failures, ambiguity, and recovery examples rather than
  repeat the same successful rows.
- [AgentV-RL](https://arxiv.org/abs/2604.16004) and [Tool Verification for
  Test-Time Reinforcement Learning](https://arxiv.org/abs/2603.02203) show the
  broader field moving verification into rollout selection and reward. Our
  differentiator must remain independently executable verification: the model
  cannot author its own evidence, change the evaluator, or turn a judge score
  into a trace fact.
- The open-source [Prime Intellect verifiers](https://github.com/PrimeIntellect-ai/verifiers)
  project is a useful ecosystem signal: reusable environments and verifier
  interfaces are becoming a standard post-training substrate. Our product
  wedge is the stricter local authority boundary, typed Action IR, tamper-
  evident replay, and promotion gate around that substrate.

## Falsifiable paper experiment

The primary result should be a frozen three-way comparison on the same model,
task authoring, decoding seeds, and tool schemas:

1. model-only Action IR policy;
2. Action IR SFT policy with no runtime repair;
3. the same policy behind the independent verifier/evidence/replay harness.

Report verified completion, false-completion rate, unsupported-action rate,
unsafe-attempt rate, state-dependent ordering accuracy, recovery success,
replay agreement, latency, and tokens. A positive result is credible only if
it survives the independent holdout, a renamed-tool/schema slice, at least
one external suite, and a negative-control model-only condition. The current
9B promotion matrix is the scale comparison; it is not a substitute for this
factorial.

## July 26 field refresh: reward hacking and credit assignment

Two additional primary signals sharpen the research and launch bar:

- [Reward Hacking Benchmark](https://arxiv.org/abs/2605.02964) treats shortcut
  opportunities as an explicit part of multi-step tool-use evaluation,
  including skipped verification, metadata leakage, and evaluator-relevant
  tampering. Our exact-payload failures expose a related shortcut: the policy
  emits state metadata as if it were artifact content. The next external
  diagnostic should report shortcut attempts and evaluator-integrity
  violations separately from ordinary task failure.
- [TRACE](https://arxiv.org/abs/2607.13988) argues that outcome-only rewards
  can assign the same negative credit to useful prefixes and the eventual
  invalid step. Before another RL arm, we should report first-invalid-step,
  recovery distance, and independently verified prefix utility. This does not
  justify claiming that RL will help this 5090 run; the prior 7B RL smoke
  remains neutral/negative evidence.

These signals strengthen the falsifiable product wedge: the harness must block
shortcuts even when they improve a superficial completion score, and the
research report must expose the invalid step and verified prefix rather than
collapsing every trajectory into one terminal reward.
