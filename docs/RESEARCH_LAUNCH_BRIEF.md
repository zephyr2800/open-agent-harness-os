# Verified Action Policies: research and launch brief

Status: active research / developer-preview candidate, 2026-07-27

## One-sentence thesis

Put probabilistic work in a compact Action IR policy, but keep authority,
execution, evidence, replay, and checkpoint promotion in a deterministic
harness; then improve the policy with verifier-backed trajectories rather than
rewarding plausible prose or unverified tool claims.

## Why this is a research question

Most agent systems blur together planning, tool execution, state mutation, and
evaluation. This project treats them as separable variables:

`policy proposes -> allowlisted executor acts -> verifier records evidence -> policy repairs/continues -> replay audits`

The measurable questions are:

1. How much verified utility can a small local policy gain from protocol-native
   SFT compared with a generic instruction model at the same deployment budget?
2. Which failures belong in weights—tool choice, exact arguments, ordering,
   abstention, evidence-grounded answers—and which belong in the harness?
3. Does verifier-backed self-improvement improve held-out utility without
   increasing unsafe actions, generic completion, or retry loops?

The intended breakthrough is not a larger chatbot score. It is a reproducible
model/harness interaction where capability, safety, and auditability improve
together on stateful tasks that are independently replayable.

## What current launches change about the thesis

The market is validating the harness layer as a product category. OpenAI’s
Agents SDK update describes model-native harnesses, sandbox execution, isolated
subagents, and long-horizon work; its computer-use work reports that even a
frontier computer-use model remains far from reliable on OSWorld. This makes
verification, confirmation, isolation, and replay product requirements rather
than academic extras. ([Agents SDK](https://openai.com/index/the-next-evolution-of-the-agents-sdk/),
[Computer-Using Agent](https://openai.com/index/computer-using-agent/))

Moonshot’s open model work reinforces a complementary scaling direction:
mixture-of-experts plus hybrid/linear attention and agent-oriented execution,
as documented for Kimi K2/K2.5 and Kimi Linear. The July 2026 K3 launch is a
useful market signal, but until an official technical report and reproducible
weights/evals are available, we treat third-party parameter and architecture
claims as unverified—not as a benchmark target. ([Kimi K2.5 paper](https://arxiv.org/abs/2602.02276),
[Moonshot research organization](https://github.com/MoonshotAI))

Our strategic position is therefore the layer frontier model launches do not
remove: a local, model-agnostic control plane that can constrain a small model,
frontier API model, or future MoE model with the same authority and evidence
contract.

The more precise current-market read is that “model proposes, platform
executes in an isolated workspace, and verified feedback returns” is becoming
table stakes. OpenAI's [computer environment for the Responses API](https://openai.com/index/equip-responses-api-computer-environment/)
and Thinking Machines' [Inkling launch](https://thinkingmachines.ai/news/introducing-inkling/)
both reinforce that direction. Our differentiating research claim therefore
cannot be harness existence alone; it must be the measured interaction between
a compact protocol-specialized policy, independent verification, replayable
evidence, and checkpoint promotion.

Thinking Machines’ Tinker and Inkling add a second market signal: model
customization itself is becoming the product, with training control exposed as
an API and open weights designed to be adapted. That strengthens our two-layer
position: Project 1 is the customizable local policy, while Project 2 is the
portable control/evidence plane that makes customized models deployable. The
technical lesson is to preserve reproducible data, eval, and promotion
artifacts as first-class product outputs. ([Tinker](https://thinkingmachines.ai/news/announcing-tinker/),
[Inkling](https://thinkingmachines.ai/news/introducing-inkling/))

The current benchmark bar also moves beyond one-shot completion: [π-Bench](https://arxiv.org/abs/2605.14678)
separates proactivity from completion across persistent multi-turn workflows,
while [PBT-Bench](https://arxiv.org/abs/2605.15229) exposes model-specific
invariant-discovery gaps. Our next external track should therefore report
persistence, proactive intent, partial utility, and failure families rather
than one aggregate success number.

## Evidence currently in hand

| Artifact | Result | Interpretation |
|---|---:|---|
| 7B v6 hidden v4 holdout | 120/120 verified and protocol-valid | Strong local control; not broad generalization |
| 7B v6 industry proxy v1 | 48/48 verified, zero unsafe attempts | Stronger state/injection proxy result; still offline |
| 7B v7 external-gap revision | 39/48; policy sequence 3/12 | Not promoted; repeated narrow data caused regression |
| 7B verifier-backed RL smoke | neutral reward before/after | Undirected RL is not a valid improvement strategy |
| Project 2 test suite | 104/104 passing | Harness/evaluator regression control |
| Qwopus3.5-9B rank-64 QLoRA | Historical SFT, merge, and 9-run matrix complete on RTX 5090 | 483/552 independently verified (87.5%), zero unsafe attempts, perfect trace/replay checks; context only because source-corpus isolation was not recorded |

Data-isolation addendum: the later targeted 9B curriculum was found to overlap
with frozen proxy contracts and its matrix was stopped at a 441-row saved
partial, so it is diagnostic only. The older 483/552 matrix remains context-
only as well: its original SFT manifest does not record an auditable source-
corpus split. Neither result supports a held-out-performance, causal,
breakthrough, or promotion claim.

The Qwopus-compatible verifier-backed REINFORCE path also passes a local
dry-run on the disjoint 24-task Action IR specification after sharing the same
thinking-disabled chat serializer as SFT and inference. This validates the RL
entry point, not an RL improvement claim. The rank-64 adapter and merged
checkpoint now exist; the frozen matrix is complete but rejected, so RL waits
for a failure-targeted remediation ablation and fresh external evidence.

The promotion runner records per-task latency and peak CUDA allocation for
each frozen checkpoint matrix. The 9B report therefore includes a real local
deployment-cost measurement rather than pass rate alone.

Promotion is now a separate machine-readable gate in
`experiments/promotion_decision.py`: it rejects missing slices, unknown task
specifications, any failed task, unsafe attempt, invalid trace, or runtime /
independent-replay disagreement. A checkpoint cannot enter RL on aggregate
score alone.

The new v2 holdout adds 16 disjoint cases for evidence-to-answer content,
insufficient information, and confirmation-required destructive requests. A
generic final response no longer passes merely because a preceding tool call
was correct.

## External research bar

- [ToolSandbox](https://machinelearning.apple.com/research/toolsandbox-stateful-conversational-llm-benchmark): stateful tools, implicit dependencies, canonicalization, and insufficient information.
- [AgentDojo](https://agentdojo.spylab.ai/): indirect prompt injection and utility/security tradeoffs.
- [τ-Knowledge](https://taubench.com/blog/tau-knowledge.html): messy knowledge bases, procedural policy, retrieval, and action.
- [AppWorld-UL](https://arxiv.org/abs/2607.20536): ambiguity, clarification, confirmation, infeasible requests, and user interaction.
- [OSWorld 2.0](https://osworld-v1.xlang.ai/): execution-based computer-use validity beyond in-memory fixtures.

Our local suites are diagnostic proxies, not substitutes for these external
benchmarks. The next credible paper result requires a held-out authoring pass
and at least one external suite run.

The current external-bar update is recorded in
`docs/EXTERNAL_BAR_UPDATE_2026-07-26.md`. In particular, TUA-Bench provides a
direct terminal-use comparison point, while OSWorld 2.0 shows that long-horizon
computer use remains difficult even for frontier systems. These results make
hidden state, delayed evidence, clarification, final-answer verification, and
resource cost first-class metrics for our next checkpoint.

## Model strategy

The current promotion baseline is Qwen2.5-7B v6, not because it is the
largest model, but because it has the strongest completed end-to-end evidence.
The controlled scale branch is:

`Qwopus3.5-9B-v3 -> response-only Action IR SFT -> hidden/replay/proxy gates -> verifier-backed preference/RL`

The Qwopus model card and fine-tuning guide motivate SFT, data normalization,
response masking, QA, and staged post-training. They do not independently
establish action-policy RL, so our claims remain tied to our own manifests and
replays. ([model card](https://huggingface.co/Jackrong/Qwopus3.5-9B-v3),
[training guide](https://github.com/R6410418/Jackrong-llm-finetuning-guide))

## Launch decision

### Developer preview: conditionally ready

The local product surface has a CLI, loopback HTTP API, MCP stdio server,
typed Action IR, allowlisted tools, default high-risk denial, independent
verification, bounded budgets, and replayable JSONL traces. The 95-test suite,
offline demo, replay smoke, explicit concurrent-retention preflight, and
bearer-authentication plus tenant-isolation checks support a technically
capable local preview.
Non-loopback serving now requires both bearer authentication and TLS 1.2+;
plain HTTP remains available only for explicit loopback development.

### Public launch: not yet ready

Remaining gates are full multi-user identity/operations, real-model latency and resource
reports, usability sessions across representative workflows,
security review of each enabled tool, licensing/provenance audit, and at least
one external benchmark result. No public “autonomous agent” claim should ship
before these are closed.

## Promotion gates

A checkpoint can replace v6 only if it has:

1. hidden v4 success plus three genuinely stochastic decoding seeds (or
   independently trained replicas, explicitly labeled);
2. v2 evidence-grounded result checks;
3. family-level industry proxy scores and zero unsafe attempts;
4. 100% independent trace validity and runtime/replay agreement;
5. no high-risk state mutation under injected untrusted content;
6. held-out tasks authored independently from training generators; and
7. one external AgentDojo, τ-bench/τ³-bench, ToolSandbox, or equivalent run.

## Investor-safe framing

“We are building the control plane and local policy stack for verifiable
computer action. The model proposes typed actions; the harness proves what
happened, blocks unauthorized mutation, and produces replayable evidence. Our
early result is not that a small model is generally intelligent—it is that
specialization plus deterministic verification can make local agents
measurably more reliable and auditable. We are now testing whether that result
survives harder evidence, ambiguity, injection, and external benchmarks.”
