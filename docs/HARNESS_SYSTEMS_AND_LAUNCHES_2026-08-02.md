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
| [AutoDojo](https://arxiv.org/abs/2606.15057) | The paper presents adaptive black-box prompt-injection optimization against a deployed defense and reports that fixed attacks can understate risk, especially for under-specified action-open tasks. | Adaptive attack success is configuration-, attacker-, and task-process-dependent. It cannot be collapsed into a static AgentDojo score. | Treat fixed native AgentDojo as Phase A and adaptive attacks as separately preregistered Phase B. Record attacker, cache hash, task bucket, utility, false refusals, unsafe execution, and each harness arm independently. |
| [TUA-Bench](https://github.com/facebookresearch/TUA-Bench) | It publishes 120 real-world execution-based terminal tasks and a reproducible runner that requires Docker or Podman, `uv`, downloaded/generated assets, and an LLM-provider account. | It is CC BY-NC and has runtime/dependency prerequisites absent on this machine; no TUA score can be implied from local proxy or tau2 results. | Use it only after an isolated runtime is available. Report its native metric and full environment rather than converting it into an Action IR score. |
| [Thinking Machines Inkling and Tinker](https://thinkingmachines.ai/news/introducing-inkling/) | Inkling is presented as an open-weights customization base and Tinker as a post-training surface; the launch describes staged SFT and large-scale RL as distinct steps. | The vendor's scale, training data, and results are not reproducible on one consumer GPU and do not validate local results. | Preserve distinct SFT, remediation, and RL gates. Publish data provenance, rollout/reward definitions, failures, and held-out measurements alongside any local customization claim. |
| [Moonshot Kimi K3](https://github.com/MoonshotAI/Kimi-K3) | The official repository/technical report documents a 2.8T-parameter, 104B-active MoE, Kimi Delta Attention, Attention Residuals, and quantization-aware MXFP4/MXFP8 deployment details. | Its reported evaluation table is vendor-reported and harness-sensitive; the system is not a direct 32 GB GPU target. | Quantization and scale are separate variables. The local 27B NF4 QLoRA track is a staged feasibility experiment, not a basis for claiming a frontier scaling law. |

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
- Add a source-bound TUA run only after its isolated runtime and licensing
  boundaries have been reviewed.
- Report the factorial interaction with confidence intervals and a
  matched-budget search control before using "superadditive" language.
