# Literature and architecture review

This review is a working research record for Project 1. “Fact” means a claim
directly stated in the linked primary source. “Inference” is our interpretation
for this project. “Hypothesis” is an unvalidated claim that must be tested on
the frozen task and tool splits.

## 1. ReAct — reasoning/action interleaving

Source: [Yao et al., ReAct](https://arxiv.org/abs/2210.03629)

- Problem: language models need to reason about a task while taking actions in external environments.
- Architecture: interleaved reasoning traces and task-specific actions in an environment loop.
- Data/objective: prompting and few-shot trajectories across QA, fact verification, ALFWorld, and WebShop; the source reports interactive outcomes and comparisons with reasoning/action baselines.
- Inference strategy: the model alternates internal reasoning and environment actions, then incorporates observations.
- Contribution: connects planning, state tracking, exception handling, and evidence gathering in one trajectory format.
- Limitation/inference: the method leaves much of authority, state persistence, and verification to the surrounding environment; free-form traces are not a stable typed protocol.
- Lesson: preserve compact state and observations externally, while training the small model on action/recovery decisions rather than requiring it to narrate all reasoning.
- Experiment: compare prose trajectory, raw JSON, and Action IR v0 under identical tools; measure valid actions, verified progress, and tokens per state transition.

## 2. Toolformer — self-supervised API use

Source: [Schick et al., Toolformer](https://arxiv.org/abs/2302.04761)

- Problem: language models struggle with simple factual lookup and arithmetic while external APIs can perform those operations.
- Architecture: a language model trained to decide which API to call, when to call it, which arguments to pass, and how to incorporate the result.
- Data/objective: self-supervised API-call insertion and filtering using a small number of demonstrations per API, optimized through language-model prediction.
- Inference strategy: API calls are inserted into text generation and their results are consumed by later prediction.
- Contribution: shows a route to tool-use learning without manually labeling every trajectory.
- Limitation/inference: next-token utility is not the same as verified task utility, and the paper’s APIs do not establish permission, rollback, or artifact verification.
- Lesson: use API-call synthesis only as a data source; filter trajectories through independent verifiers and retain abstention/error labels.
- Experiment: compare teacher-generated synthetic traces before and after verifier filtering, measuring held-out tool schemas, invalid actions, and reward-hacking cases.

## 3. TinyAgent — function calling at the edge

Source: [Erdogan et al., TinyAgent](https://arxiv.org/abs/2409.00608)

- Problem: deploy task-specific function-calling agents on edge devices despite large-model cost and prompt length.
- Architecture: task-specific small language models, with tool retrieval and quantization for efficient deployment; the paper reports TinyAgent-1.1B and 7B systems.
- Data/objective: curated function-calling data and fine-tuning through an LLMCompiler-based pipeline.
- Inference strategy: retrieve a smaller relevant tool set, then run a quantized local model.
- Contribution: makes tool retrieval, edge quantization, and installable local deployment part of the agent design rather than afterthoughts.
- Limitation/inference: a driving application and its tool distribution do not establish broad robustness to unseen schemas, misleading tools, or permission-sensitive actions.
- Lesson: tool retrieval and deployment budgets belong in the benchmark cell, not only in implementation notes.
- Experiment: all-tools versus retrieved-tools ablation under fixed model weights; measure prompt tokens, valid actions, unseen-tool performance, latency, memory, and energy.

## 4. xLAM — normalized large action models

Source: [Zhang et al., xLAM](https://arxiv.org/abs/2409.03215)

- Problem: open agent systems lack high-quality action data and standard protocols for tool use.
- Architecture: a family of dense and mixture-of-experts action models ranging from 1B to 8×22B parameters.
- Data/objective: scalable data unification, augmentation, and synthesis across tool-use sources, with a normalized action representation.
- Inference strategy: structured function calling evaluated on agent ability benchmarks.
- Contribution: treats action modeling and data normalization as a distinct model family rather than a side effect of chat tuning.
- Limitation/inference: benchmark performance can reflect data scale, tool coverage, and representation choices; the source does not by itself isolate harness gains from model gains.
- Lesson: version Action IR and provenance independently from model weights, and run model × harness factorial controls.
- Experiment: train same-size generic and action-specialized policies on identical task/tool splits, then measure the interaction term under baseline and advanced harnesses.

## 5. Hammer — irrelevance detection and function masking

Source: [Lin et al., Hammer](https://arxiv.org/abs/2410.04587)

- Problem: function-calling models can be misled by function names and call irrelevant tools.
- Architecture: on-device function-calling models with function masking and irrelevance-augmented training data.
- Data/objective: additional examples where the correct function is absent, teaching no-call behavior and robustness to misleading names.
- Inference strategy: mask or constrain candidate functions during generation.
- Contribution: makes “do not call” a first-class function-calling capability and treats naming robustness as an evaluation axis.
- Limitation/inference: name masking and absent-function tests do not fully cover state-dependent permission, destructive effects, or recovery after a tool has already failed.
- Lesson: include abstain, renamed-tool, irrelevant-tool, missing-capability, and permission cases in the action benchmark.
- Experiment: no-call augmentation and function masking ablation under renamed tools; report abstention precision/recall, invalid-action rate, and verified safety.

## 6. Agent Distillation — transferring tool-using behavior

Source: [Kang et al., Agent Distillation](https://arxiv.org/abs/2505.17612)

- Problem: chain-of-thought distillation alone can leave small models hallucinating when tasks require rare facts, retrieval, or exact computation.
- Architecture: small agents trained from teacher trajectories with retrieval and code tools; the source studies 0.5B, 1.5B, and 3B students.
- Data/objective: first-thought prefixes for teacher trajectories and self-consistent action generation for test-time robustness.
- Inference strategy: use external retrieval/code tools and multiple action candidates where appropriate.
- Contribution: transfers executable task-solving behavior rather than only verbal reasoning traces.
- Limitation/inference: the evaluated task families are reasoning-centric; transfer to permissioned local workflows and typed state protocols remains open.
- Lesson: distill verified action/observation/recovery trajectories and keep prose optional or external.
- Experiment: compare SFT, rejection sampling, self-consistent action candidates, and verifier-gated distillation on held-out tools and partial observations.

## 7. SWE-agent — interface design as a model variable

Source: [Yang et al., SWE-agent](https://arxiv.org/abs/2405.15793)

- Problem: language models need interfaces designed for their abilities when operating software environments.
- Architecture: a custom agent-computer interface for editing files, navigating repositories, and running tests.
- Data/objective: interactive software-engineering tasks evaluated on SWE-bench and HumanEvalFix.
- Inference strategy: iterative model actions through a task-specific interface with execution feedback.
- Contribution: demonstrates that the model–computer interface is a causal design object, not merely prompt glue.
- Limitation/inference: software repair and its interface may not generalize to calendar, browser, device, or stateful personal workflows.
- Lesson: treat harness quality as an independent variable and expose interface decisions in traces.
- Experiment: same model and tasks under transcript-only, typed deterministic, and co-designed harnesses; ablate context, tool descriptions, verification, and recovery one component at a time.

## 8. Agentless — the simple baseline must survive

Source: [Xia et al., Agentless](https://arxiv.org/abs/2407.01489)

- Problem: complex autonomous software agents may add cost and failure modes beyond what a deterministic pipeline needs.
- Architecture: a three-phase localization, repair, and patch-validation pipeline without model-controlled future actions.
- Data/objective: software-repair evaluation on SWE-bench Lite and a filtered SWE-bench Lite-S analysis.
- Inference strategy: fixed phases and validation rather than open-ended tool planning.
- Contribution: establishes a strong, interpretable baseline and warns against assuming agentic complexity is automatically useful.
- Limitation/inference: a fixed software-repair pipeline is not a universal baseline for open-ended local agents.
- Lesson: include minimal deterministic and semi-agentic controls, and report when a proposed action model is worse than a simpler workflow.
- Experiment: compare H0 minimal loop, deterministic verifier pipeline, and model-controlled recovery at equal token/call budgets.

## 9. Granite function calling — multi-task decomposition

Source: [Abdelaziz et al., Granite-20B-FunctionCalling](https://arxiv.org/abs/2407.00121)

- Problem: function calling comprises several distinct sub-capabilities rather than one monolithic skill.
- Architecture: a function-calling model trained with multi-task learning.
- Data/objective: nested calls, chaining, parallel functions, name detection, parameter extraction, next-best function, and response generation.
- Inference strategy: structured tool-call generation evaluated across multiple out-of-domain datasets.
- Contribution: supplies a capability decomposition useful for action-model ablations.
- Limitation/inference: the 20B scale and benchmark setting do not establish what can be externalized to a harness for a 0.5B local policy.
- Lesson: keep tool selection, argument validity, recovery, abstention, and stopping as separate metrics and training labels.
- Experiment: train/measure each capability head or data slice separately, then test compositional multi-step tasks and unseen tools.

## 10. Emerging irrelevance and abstention evidence

Sources: [Hammer](https://arxiv.org/abs/2410.04587), [SABEval](https://arxiv.org/abs/2604.11322), and [AgentAbstain](https://arxiv.org/abs/2607.10059)

- Fact: these works treat irrelevant tools, structural matching bias, and should-abstain paired tasks as distinct failure modes.
- Inference: a benchmark that only scores successful calls will overestimate safe utility and miss the cost of confident over-action.
- Hypothesis: explicit abstention labels plus harness-side authority gates will improve safety and verified utility per call, especially for small models.
- Experiment: paired should-act/should-abstain tasks, renamed tools, absent tools, ambiguous destinations, permission failures, and post-error stopping; report calibrated abstention, unnecessary calls, recovery, and verified outcomes.

## Architecture implications for Project 1

The literature supports a narrow first prototype rather than a new foundation model:

1. Start from a mature 0.5B–3B checkpoint and specialize the policy.
2. Make tool retrieval, authority, state persistence, verification, and rollback external and deterministic.
3. Train typed actions, abstention, recovery, and stopping with verified trajectories.
4. Freeze task/tool schemas before training and perturb names/interfaces at evaluation time.
5. Compare against simple deterministic pipelines and generic checkpoints.
6. Measure verified utility per token, second, joule, memory, and dollar—not raw function-call accuracy alone.

These are design implications, not results. The current zero-shot checkpoint
result (0/8 valid Action IR decisions) is consistent with the need for
specialization, but it does not establish that specialization will succeed.

## 11. Stateful and user-in-the-loop evaluation

Sources: [ToolSandbox](https://arxiv.org/abs/2408.04682),
[τ-Knowledge](https://taubench.com/blog/tau-knowledge.html), and
[AppWorld-UL](https://arxiv.org/abs/2607.20536).

- Fact: these benchmarks move beyond single-turn function calling toward
  implicit state dependencies, messy knowledge/policy retrieval, insufficient
  information, clarification, confirmation, and infeasible requests.
- Inference: a model can execute the correct tool and still fail the user by
  answering generically, acting on missing information, or skipping a needed
  confirmation.
- Lesson: score the evidence-grounded final answer and boundary behavior, not
  only the action trace. Project 2 now implements this through the v2 proxy and
  `expected_result_contains` checks shared by runtime and replay.
- Experiment: compare Action IR SFT, verifier-first repair, and preference/RL
  on disjoint policy documents and user-interaction tasks.

## 12. Computer-use launches and the harness layer

Sources: [OpenAI Computer-Using Agent](https://openai.com/index/computer-using-agent/)
and [the Agents SDK harness update](https://openai.com/index/the-next-evolution-of-the-agents-sdk/).

- Fact: frontier launches increasingly package models with sandboxes,
  observability, isolated subagents, confirmation prompts, and computer-use
  interfaces; even strong computer-use systems report substantial residual
  failure on real desktop benchmarks.
- Inference: the surrounding control plane is a durable product surface even
  when the underlying model changes. Safety, replay, state ownership, and
  evidence provenance should not be learned implicitly by the policy.
- Lesson: Project 2 should remain model-agnostic and expose the same Action IR
  contract for local dense models, remote frontier models, and future MoE
  computer-use policies.

## 13. Customization as the product surface

Sources: [Thinking Machines Tinker](https://thinkingmachines.ai/news/announcing-tinker/)
and [Inkling](https://thinkingmachines.ai/news/introducing-inkling/).

- Fact: Tinker exposes model fine-tuning controls through an API, while Inkling
  is released as open weights intended for customization.
- Inference: the durable product may be the reproducible customization and
  evaluation loop, not a single frozen model checkpoint.
- Lesson: every Project 1 run should emit a dataset hash, training manifest,
  adapter/merged artifacts, evaluator hash, replay report, and promotion
  decision. Project 2 should make those artifacts operationally inspectable.
- Experiment: measure whether verifier-filtered trajectories and held-out
  promotion gates produce better task-specific models than raw fine-tuning,
  while keeping the same base model and compute budget.

## 14. Open sparse/agentic model direction

Sources: [Kimi K2: Open Agentic Intelligence](https://arxiv.org/abs/2507.20534),
[Kimi K2.5](https://arxiv.org/abs/2602.02276), and
[Kimi Linear](https://github.com/MoonshotAI/Kimi-Linear), and the
[official Kimi K3 repository and technical report](https://github.com/MoonshotAI/Kimi-K3).

- Fact: Moonshot’s public work explores large sparse models, multimodal/agentic
  post-training, and hybrid linear/global attention to improve long-context
  efficiency.
- Update: the official K3 repository now includes weights and a technical
  report describing a 2.8T-total, 104B-active MoE with Kimi Delta Attention,
  Attention Residuals, and MXFP4/MXFP8 quantization-aware training.
- Inference: parameter count and active parameters are separate scaling axes;
  our 9B QLoRA branch is a useful local dense comparison, while the harness
  should be evaluated independently of architecture.
- Caveat: K3's report and weights do not make it a comparable local baseline,
  and its evaluation table remains vendor-reported and harness-sensitive.
  Do not turn its scale or benchmark claims into a claim about this 32 GB
  local-policy program.
- Experiment: compare verified utility per active parameter, memory, latency,
  and replayable success—not headline total parameters alone.
