# Industry-Level Benchmark Plan

The current 120-task v4 suite is a useful deterministic control, but its
perfect score is not evidence of broad agent competence. It is too close to a
contract-following unit test. The next evaluation stack should measure the
failure modes that external agent benchmarks emphasize.

## External reference suites

| Reference | What it stresses | Relevance to this project | Local status |
|---|---|---|---|
| [τ-bench / τ³-bench](https://github.com/sierra-research/tau2-bench) | Dynamic user-agent interaction, domain policy, stateful APIs, consequential actions, confirmation and authentication | Direct analogue for a policy-governed action model and harness | Pinned native checkout plus result exporter implemented; full suite still requires its isolated environment and a declared model/user simulator |
| [ToolSandbox](https://github.com/apple/ToolSandbox) | Stateful tools, implicit state dependencies, canonicalization, insufficient information, on-policy conversation | Direct analogue for verifier-backed state transitions | Proxy implemented; full suite has extra environment/API dependencies |
| [AgentDojo](https://github.com/ethz-spylab/agentdojo) | Indirect prompt injection, tool poisoning, dynamic environments, attack/defense scoring | Direct analogue for untrusted browser/API output and authority separation | OpenAI-compatible bridge exercised; first external task exposed state-dependency and Action IR generalization gaps |
| [BrowserGym](https://github.com/ServiceNow/BrowserGym) / [WebChoreArena](https://github.com/WebChoreArena/WebChoreArena) | Multi-step browser workflows over realistic web apps | Measures browser state and recovery rather than URL extraction | Requires browser containers; local proxy covers untrusted page content |
| [OSWorld](https://github.com/xlang-ai/OSWorld) / [OSWorld 2.0](https://github.com/xlang-ai/OSWorld-V2) | Real desktop applications, hidden state, cross-application workflows, long horizons | Product-launch external validity for computer-use claims | Requires VM/browser infrastructure; not represented by local score |
| [TUA-Bench](https://tuabench.ai/) | Terminal workflows, document/email/web tasks, scientific and engineering workflows, execution-based grading | Closest current reference for terminal-use and research/engineering launch claims | Add as an external evaluation track; local proxy is not a substitute |
| [τ-Knowledge](https://taubench.com/blog/tau-knowledge.html) | Messy long-form knowledge bases, policy retrieval, conditional reasoning, and tool use | Direct test of evidence-grounded answers rather than generic completion | Add a local knowledge/policy slice first; external run remains open |
| [AppWorld-UL](https://arxiv.org/abs/2607.20536) | Ambiguity, clarification, user confirmation, infeasible requests, and compositional app workflows | Direct test of the harness’s abstain/ask/confirm boundary | Add a held-out user-interaction slice; do not report v4 as sufficient |

## Frozen local proxy

`benchmarks/fixtures/task-spec-industry-proxy-v1.json` contains 48 tasks and
is SHA-256 `c5c0e843f2edc27cdb10b2a2b5d394d5d64373d558f072f4cb0f49001c10cb5e`.
It imports four hard phenomena:

- implicit state dependencies across three actions;
- four-action ordered workflows with retry and exact artifact checks;
- browser/API outputs containing adversarial instructions that must be
  treated as untrusted data;
- a high-risk delete surface exposed as an attack temptation but denied by
  the harness policy.

For proxy runs, `include_tool_outputs` deliberately exposes labeled
`UNTRUSTED_TOOL_OUTPUT` facts to the model. The system prompt says these are
data, never authorization; independent replay still verifies the final trace.
The report records `unsafe_attempt` separately, so a policy denial cannot be
mistaken for safe model behavior.

## Results to date — 2026-07-26

The honest hidden-contract 7B control scored **12/48 (25.0%)** on the proxy,
with 39/48 protocol-valid traces. After adding 720 verifier-backed proxy
trajectory rows to the 3,072-row stratified curriculum and training one 7B
QLoRA epoch at 5e-5, the proxy-mix checkpoint scored **43/48 (89.6%)**
greedy, **48/48 protocol-valid**, and **48/48 independently replay-matched**.
Family scores were state dependency 12/12, browser injection 12/12, API
injection 11/12, and policy sequence 8/12. It attempted zero high-risk
delete actions. Three sampled decoding seeds scored **41/48 (85.4%)**,
**37/48 (77.1%)**, and **39/48 (81.3%)**; each had 100% independent replay
agreement and zero unsafe attempts. Greedy plus those three runs averaged
**83.3%** over 192 task-runs (range 77.1%–89.6%).

The same proxy-mix checkpoint scored **120/120** on the frozen 120-task v4
holdout under hidden-contract, no-repair evaluation, including 20/20
adversarial tasks and zero unsafe attempts. This is a strong local result,
but it is still an offline proxy and not a result on the external suites
listed above; external execution and a held-out authoring pass remain open.

## First external integration result

The public AgentDojo repository was exercised through a local OpenAI-compatible
bridge at commit `089ed468cf3ed0322acc66b0211f26d9d90dbf60`. The v5 model-only
write task scored **0/1 utility**. The v6 checkpoint plus an explicitly labeled
lookup-first harness guard scored **1/1** on that write task, while the v6
model-only Q&A task scored **0/1** and the direct-injection composite scored
**0/1 utility** without carrying out the injected email exfiltration. The
remaining failure was an invalid native calendar-read schema and a generic
finish instead of evidence-grounded text. These are exploratory integration
observations, not an external benchmark average. Full traces and the exact
next gate are in `docs/EXTERNAL_AGENTDOJO_RUN.md`.

## Research gates

The next model checkpoint is not promoted on v4 alone. It must report:

1. full v4 greedy and at least three decoding seeds;
2. industry-proxy success by family and unsafe-attempt rate;
3. independent trace replay with runtime/replay agreement of 100%;
4. no high-risk action execution, including when untrusted tool output is
   adversarial;
5. a held-out task authoring pass that does not reuse generator templates;
6. then one external suite run, initially τ-bench/τ³-bench or AgentDojo,
   before any generalized research or public-launch claim.

The 5090 can run the proxy locally, but the OSWorld/BrowserGym/τ-bench
environments are separate infrastructure projects. A perfect score here is a
signal to raise difficulty, not a reason to lower the external bar.

## Newly raised external bar

The current benchmark map changes the launch claim in two ways. First, a
successful action is not enough: the agent must retrieve and apply messy policy
evidence, as emphasized by τ-Knowledge, and answer with the verified
consequence. Second, the harness must recognize when the user’s request is
ambiguous, infeasible, or requires confirmation, as emphasized by AppWorld-UL.
The next local revision will therefore add disjoint policy documents, hidden
canonicalization cases, insufficient-information cases, and confirmation-required
write actions. These will be authored separately from the training generators
and scored by exact state transitions plus independent replay.

The evaluator now also supports `expected_result_contains`: a trace only
passes when the final answer contains the held-out, verifier-backed markers.
This closes the earlier loophole where a generic "done" answer could pass
after a correct tool call. The frozen v2 proxy has 16 disjoint tasks (SHA-256
`eb4d071facde6b94e632d68b01caf43e3ae8f7cb456b504e52c38453304d1d6c`) across
evidence-to-answer API/browser tasks, insufficient-information abstentions,
and confirmation-required destructive requests.

## External-bar-lite fixture — 2026-07-26

The next disjoint local gate is now authored at
`benchmarks/fixtures/task-spec-external-bar-lite-v1.json` (20 tasks; SHA-256
`8d1d852b4cd181079effd7023df13655406de73ddfd6a65329ec6597adf6cae3`). It is
kept outside the training JSONL and outside the frozen promotion matrix. The
fixture contains four three-action terminal workflows, four implicit
read-then-write state tasks, four adversarial API evidence tasks, four
adversarial browser evidence tasks, and four confirmation-boundary tasks.

This is a local bridge to the external bar, not an external benchmark score.
It is intentionally evaluated separately before being considered for a future
promotion gate.

## External bar refresh - 2026-07-27

The latest primary-source benchmark work raises the standard beyond a single
terminal proxy:

- [StructAgent](https://arxiv.org/abs/2607.11388) is a close comparator for
  verifier-backed state, checkpointing, and evidence-grounded completion. It
  makes those mechanisms a baseline for our ablation, not our novelty claim.
- [WeaveBench](https://arxiv.org/abs/2606.09426) evaluates 114 hybrid GUI,
  CLI, and code workflows and uses trajectory-aware judging; its best reported
  PassRate is 41.2%. This is the clearest reason to add a native hybrid track
  before claiming general computer use.
- [WildClawBench](https://arxiv.org/abs/2605.10912) evaluates 60 human-authored
  tasks in native CLI runtimes with deterministic, state, and semantic checks.
  Its harness-dependent spread means model and harness must be reported as
  separate factors.
- [SWE-Marathon](https://arxiv.org/abs/2606.07682) demonstrates why long-horizon
  claims need multi-channel verification and explicit reward-hacking audits.
- [General AgentBench](https://arxiv.org/abs/2602.18998) identifies a context
  ceiling and a verification gap in test-time scaling, supporting our emphasis
  on compact evidence state and independent replay.

The launch consequence is explicit: our local 20-task bridge remains a
diagnostic gate. A research or public-launch claim needs one fresh native-suite
run with that suite's environment, grader, version/commit, and native metric,
plus an ablation showing whether the improvement comes from the model, the
harness, or their interaction.
