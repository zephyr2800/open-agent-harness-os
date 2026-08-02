# Harness systems and launch comparison - 2026-08-02

This is a primary-source positioning review for the Open Agent Harness OS and
its paired local Action IR policy. It separates observed facts from design
inferences. It is not a claim that this repository matches another system's
capability, evaluation score, scale, or deployment posture.

## Comparison matrix

| System or source | Directly observed fact | Limitation / claim boundary | Project lesson and falsifiable test |
|---|---|---|---|
| [Pi agent harness](https://github.com/earendil-works/pi) | Its public monorepo separates a multi-provider LLM API, an agent core with tool calling/state management, and a coding-agent CLI. Its README states that Pi has no built-in filesystem, process, network, or credential permission system and recommends external containerization/sandboxing. | Pi is an open runtime reference, not evidence that its operating model, security, or task score transfers to this Python harness. | The authority gate must remain a first-class runtime surface rather than an optional wrapper. Test the same policy/tool task with the gate enabled and disabled, reporting allowed, denied, and unsafe attempts. |
| [OpenAI Agents SDK update](https://openai.com/index/the-next-evolution-of-the-agents-sdk/) | The product describes controlled sandbox environments, manifest-defined workspaces, configurable memory, externalized state, snapshotting, rehydration, and isolated execution for long-running work. | This is a vendor product description and a model-native SDK, not an independent comparison with this repository or a justification for a production-security claim. | Product parity is not the research goal. Measure whether the local harness's typed authority, evidence ledger, and independent replay improve verified utility over a minimal loop under fixed budgets. |
| [AgentDojo](https://github.com/ethz-spylab/agentdojo) | It is a public benchmark for prompt-injection attacks/defenses and exposes a benchmark CLI with suite, user-task, attack, and defense selectors. The API is explicitly still under development. | A finite static benchmark is not a general security proof; a local adapter can also introduce its own implementation confounds. | Preserve AgentDojo's native runner and metric, pin its source, keep clean and direct-injection results separate, and bind adapter/checkpoint sources and logs to the result manifest. |
| [τ³-bench v1.0.1](https://github.com/sierra-research/tau2-bench) | The official `tau2` repository now spans text, voice, and knowledge-aware evaluation. Its v1.0.1 release changes banking-knowledge grading while stating that other domains are unaffected. The registered Phase A checkout is the v1.0.1 source commit `363133ada1936491fb5bcec33cd62c3518a99f65`, using the unchanged telecom/base text condition. | A six-task telecom diagnostic is not a full τ³ result, and a score across a changed task/grader version is not comparable. | Keep Phase A frozen and source-bound. If it completes, preregister any broader or knowledge-aware τ³ condition separately with exact version, selector, policy, user simulator, and environment fields. |
| [From Confident Closing to Silent Failure](https://arxiv.org/abs/2606.09863) | This 2026 preprint studies false success—an agent claims completion while environment state disagrees—across τ²-bench and AppWorld, and reports weak LLM-judge discrimination relative to state-based signals. | It is a benchmark-specific preprint, not a security certification or proof that every completion detector transfers across environments. | Keep independent replay, expected-state checks, and false-completion reporting in every local result; never upgrade a confident final answer or an LLM judge into completion evidence. |
| [AutoDojo](https://arxiv.org/abs/2606.15057) | The paper presents adaptive black-box prompt-injection optimization against a deployed defense and reports that fixed attacks can understate risk, especially for under-specified action-open tasks. | Adaptive attack success is configuration-, attacker-, and task-process-dependent. It cannot be collapsed into a static AgentDojo score. | Treat fixed native AgentDojo as Phase A and adaptive attacks as separately preregistered Phase B. Record attacker, cache hash, task bucket, utility, false refusals, unsafe execution, and each harness arm independently. |
| [TUA-Bench](https://github.com/facebookresearch/TUA-Bench) | It publishes 120 real-world execution-based terminal tasks and a reproducible runner that requires Docker or Podman, `uv`, downloaded/generated assets, and an LLM-provider account. | It is CC BY-NC and has runtime/dependency prerequisites absent on this machine; no TUA score can be implied from local proxy or tau2 results. | Use it only after an isolated runtime is available. Report its native metric and full environment rather than converting it into an Action IR score. |
| [Thinking Machines Inkling and Tinker](https://thinkingmachines.ai/news/introducing-inkling/) | Inkling is presented as an open-weights customization base and Tinker as a post-training surface; the launch describes staged SFT and large-scale RL as distinct steps. | The vendor's scale, training data, and results are not reproducible on one consumer GPU and do not validate local results. | Preserve distinct SFT, remediation, and RL gates. Publish data provenance, rollout/reward definitions, failures, and held-out measurements alongside any local customization claim. |
| [Moonshot Kimi K3](https://github.com/MoonshotAI/Kimi-K3) | The official repository/technical report documents a 2.8T-parameter, 104B-active MoE, Kimi Delta Attention, Attention Residuals, and quantization-aware MXFP4/MXFP8 deployment details. | Its reported evaluation table is vendor-reported and harness-sensitive; the system is not a direct 32 GB GPU target. | Quantization and scale are separate variables. The local 27B NF4 QLoRA track is a staged feasibility experiment, not a basis for claiming a frontier scaling law. |
| [Harness-Bench](https://arxiv.org/abs/2605.27922) | It evaluates configuration-level harness effects with shared task environments, budgets, and protocols while retaining artifacts, traces, usage records, and validator outputs. | A diagnostic benchmark does not transfer a score or an individual harness effect to this repository; it does, however, make the experimental unit explicit. | Keep model, harness, environment, task selector, source revision, decoding, and budget bound in every factorial row. Do not attribute a result to the checkpoint alone. |
| [VeRO](https://arxiv.org/abs/2602.22480) | It provides versioned agent snapshots, budget-controlled evaluation, structured execution traces, and reference procedures for agent-optimization studies. | Its target-agent benchmark is not a validation of this runtime's bounded H4 proposal loop or of a local post-training result. | A harness-evolution result must bind the editable snapshot, evaluator snapshot, budget, trace, and promotion decision. Compare proposals only on held-out tasks under matched budgets. |
| [AgentS4D](https://arxiv.org/abs/2607.27294) | It evaluates lifecycle-wide agent-runtime safety using multiple risk-entry sources, induction strategies, target harms, and post-run evidence checkpoints. | Its risk taxonomy and reported model/harness outcomes are configuration-specific; a fixed prompt-injection score is not a substitute for lifecycle safety evidence. | Treat native AgentDojo as a narrow Phase A diagnostic. Before a production-safety claim, preregister a separate lifecycle risk suite with entry path, induction, harm, and evidence checkpoint recorded per run. |
| [AsyncFC](https://arxiv.org/abs/2605.15077) | It studies dependency-aware asynchronous function calling as an execution-layer method for overlapping model decoding and tool execution without changing model weights. | Its latency results do not establish correctness or safety for arbitrary concurrent tool calls in this harness. | Any asynchronous executor branch must be an isolated H2/H3 ablation with declared read/write dependencies, deterministic replay, race checks, and the same verified-success and safety budget as the synchronous control. |

## Design consequences

1. **The runtime is the product boundary.** Tool calling alone is common;
   typed authority, independent outcome verification, evidence lineage, replay,
   and promotion gates must be observable and ablatable.
2. **Security needs two axes.** Static injection utility/security and adaptive
   attack resilience are separate measurements. Neither permits a security
   certification without a stated threat model and deployment review.
3. **The experimental unit is model plus harness plus environment.** Every
   external result must name the model, policy/harness variant, task selectors,
   decoding/budget, source revision, runtime, and native grader.
4. **Post-training is an empirical branch, not a product checkbox.** SFT,
   preference/remediation, and RL each require a frozen control, source audit,
   independent replay, and a negative-result path.
5. **Local scale has a different value proposition.** The RTX 5090 is best
   used for reproducible constrained experiments, deployment-budget Pareto
   measurements, and failure localization; it is not a proxy for frontier
   pretraining scale.
6. **Harness evolution is a versioned experiment.** A safe self-improvement
   proposal is not evidence until the editable snapshot, protected evaluator,
   trace, budget, and held-out promotion decision are all reproducible.
7. **Safety must cover the execution lifecycle.** A static injection score can
   be useful failure localization, but it cannot establish runtime safety
   across different entry paths, induced behaviors, or persisted side effects.
8. **Performance work must remain causal.** Future asynchronous tool execution
   may improve latency, but it must not be credited to a model or training
   intervention unless the synchronous control shares the same policy,
   dependencies, tasks, and verification rules.

These additions raise the follow-up evidence bar only. They do not change the
frozen clean-9B training source, promotion matrix, registered native selector,
or authorization for post-training/RL.

## Investor-safe interpretation

The market is converging on agent runtimes with tools, sandboxes, state, and
customization. The claim worth proving here is narrower: a model-agnostic,
verifier-first authority plane can make local policy specialization measurable,
replayable, and safely promotable. That claim survives only if the controlled
four-cell model-by-harness result and native external diagnostics support it.

## Required follow-through

- Complete the active clean 9B branch before changing its training source or
  starting a larger branch.
- Run registered Phase A only after promotion; do not label it an adaptive
  security result.
- Do not expand or re-rank the registered τ³ telecom/base selection while the
  clean 9B branch is live. Any broader τ³ condition needs a new preregistration
  after Phase A, not a retroactive change to its benchmark scope.
- Add a source-bound TUA run only after its isolated runtime and licensing
  boundaries have been reviewed.
- Report the factorial interaction with confidence intervals and a
  matched-budget search control before using "superadditive" language.
