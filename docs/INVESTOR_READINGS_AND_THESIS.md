# Investor reading brief and merged thesis

Updated 2026-07-26. This is a cram guide for the merged project: a specialized
action policy trained through verifier-backed post-training, wrapped in a
harness that executes, authorizes, verifies, replays, and mines failures for
the next training cycle.

## The 90-minute reading order

### 1. The agent loop and the failure mode

1. [Lilian Weng — LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/): the basic loop of planning, memory, tool use, and reflection.
2. [Lilian Weng — Thinking](https://lilianweng.github.io/posts/2025-05-01-thinking/): why post-training can teach models to spend compute and use external tools.
3. [Lilian Weng — Reward Hacking in Reinforcement Learning](https://lilianweng.github.io/posts/2024-11-28-reward-hacking/): the reason a model score is not the same thing as task completion.
4. [OSWorld](https://arxiv.org/abs/2404.07972), [\u03c4-bench](https://huggingface.co/papers/2406.12045), [AgentDojo](https://arxiv.org/abs/2406.13352), and [ToolSandbox](https://machinelearning.apple.com/research/toolsandbox-stateful-conversational-llm-benchmark): stateful, tool-mediated evaluation rather than static question answering.

Investor translation: agents fail at the boundary between an intention and a
verified side effect. Our harness makes that boundary an auditable product
surface.

### 2. The training recipe

1. [InstructGPT](https://arxiv.org/abs/2203.02155): supervised demonstrations followed by preference optimization and human feedback.
2. [Direct Preference Optimization](https://arxiv.org/abs/2305.18290): preference learning without a separately trained reward model.
3. [DeepSeek-R1](https://arxiv.org/abs/2501.12948): cold-start SFT plus reinforcement learning with verifiable rewards and rejection sampling.
4. [DeepSeekMath / GRPO](https://arxiv.org/abs/2402.03300): group-relative, verifier-backed policy optimization.
5. [STaR](https://arxiv.org/abs/2203.14465), [Reflexion](https://arxiv.org/abs/2303.11366), and [Self-Refine](https://arxiv.org/abs/2303.17651): self-generated traces, verbal feedback, and iterative improvement.
6. [Karpathy's nanoGPT](https://github.com/karpathy/nanoGPT), [llm.c](https://github.com/karpathy/llm.c), and [autoresearch](https://github.com/karpathy/autoresearch): the practical culture of making the training loop small, inspectable, and runnable on local hardware.

Investor translation: we are not proposing “prompting.” We are building a
specialization pipeline: continued pretraining -> protocol SFT -> preference
optimization -> verifier-backed RL -> frozen-holdout promotion.

### 3. Scaling and efficient specialization

1. [Kaplan et al. — Scaling Laws for Neural Language Models](https://arxiv.org/abs/2001.08361).
2. [Chinchilla — Training Compute-Optimal Large Language Models](https://arxiv.org/abs/2203.15556).
3. [Qwen2.5 Technical Report](https://arxiv.org/abs/2412.15115): a useful open-model baseline and model-family perspective.
4. [Kimi K2.5 — Visual Agentic Intelligence](https://arxiv.org/abs/2602.02276): multimodality, tool use, and post-training for agentic behavior.
5. [Thinking Machines Lab — Inkling](https://thinkingmachines.ai/news/introducing-inkling/) and the [Inkling model card](https://thinkingmachines.ai/model-card/inkling/): the current customization thesis—open weights, controllable thinking effort, multimodality, and a training platform. Inkling is a 975B-total/41B-active MoE, so it is a lesson in sparse scaling and customization, not a model we can run on one 5090.
6. [Towards Personalized Intelligence at Scale](https://arxiv.org/abs/2203.06668): the closest useful “Pi” architecture reading; pair it with [Inflection's Pi overview](https://inflection.ai/about) and [Pi developer documentation](https://developers.inflection.ai/docs/introduction).
7. Kimi K3: read the [current model overview](https://huggingface.co/blog/ResterChed/kimi-k3-model-overview-mxfp4-quantization-open-wei), but treat benchmark and architecture claims as provisional until Moonshot's official weights and technical report are independently available. The strategic lesson is open-weight scale plus aggressive quantization, not a claim that we can reproduce a 2.8T model locally.

Investor translation: the 5090 lets us test the scaling curve locally. Full-parameter
SFT currently fits at 0.5B-1.5B; 3B QLoRA fits comfortably, and the next useful
frontier is 7B-class QLoRA. Capacity matters, but data quality, reward design,
and evaluator independence determine whether capacity becomes capability.

### 4. Why the harness is a research contribution

1. [MCP specification](https://modelcontextprotocol.io/specification/2025-06-18/server/index): a standard tool boundary to build against.
2. [OpenAI Agents SDK](https://openai.com/index/the-next-evolution-of-the-agents-sdk/) and [AgentKit](https://openai.com/index/introducing-agentkit/): evidence that agent products are moving toward traces, tools, and evaluation as first-class surfaces.
3. [Reward Hacking Benchmark](https://arxiv.org/abs/2605.02964): directly relevant to our decision to keep the evaluator and verifier outside the policy.
4. [Agent^2 RL-Bench](https://arxiv.org/abs/2604.10547): relevant to the idea that agents can help construct and improve agentic RL workflows.
5. [When RLHF Fails](https://arxiv.org/abs/2606.03238): a useful warning about evaluator gaming, collapse, and proxy objectives.

Investor translation: the product is not merely a local model. It is a
promotion system that can answer: what did the model try, what actually
changed, who authorized it, what evidence proves it, can another process replay
the result, and should this failure become the next training example?

### Fresh launch signal: the market is converging on the same boundary

Recent primary-source launches make the positioning sharper. OpenAI's
[computer environment for the Responses API](https://openai.com/index/equip-responses-api-computer-environment/)
describes the same fundamental execution loop—model proposes, platform runs in
an isolated workspace, and the result returns as feedback—along with files,
restricted networking, and durable workflow concerns. Thinking Machines'
[Inkling launch](https://thinkingmachines.ai/news/introducing-inkling/) makes
domain customization and post-training a product surface, not merely an
internal research step. The opportunity is therefore not “agents need a loop”
by itself; that is becoming table stakes. Our research wedge is the measurable
combination of a compact protocol-specialized policy, independent outcome
verification, replayable evidence, and a promotion gate that can show where
model gains end and harness gains begin.

## The merged architecture

```text
user goal
   -> typed Action IR policy
   -> harness authority boundary
   -> bounded tool execution
   -> independent state/artifact verifier
   -> tamper-evident trace + replay
   -> failure taxonomy and hard-negative mining
   -> SFT / DPO / RLVR specialization
   -> frozen holdout promotion gate
   -> next policy checkpoint
```

The key research hypothesis is:

> Post-training specialization and harness design are coupled variables. A
> small model becomes useful when it learns a narrow, verifiable action
> language, while the harness makes truth, safety, replay, and data generation
> external to the model. The harness then becomes a bounded self-improvement
> loop, not an untrusted self-modifying agent.

The safety boundary is important: the model may propose; the harness owns
authority, execution, evidence, holdouts, and promotion. “Self-recursive” means
the system can mine its own verified failures into new training data—not that a
model can silently rewrite its weights or evaluator.

## What we can say tomorrow

- We have a working local execution product with CLI, loopback API, MCP, bounded
  tools, independent verification, tamper-evident traces, replay, and a
  developer-preview wheel.
- On the 20-task research-v3 holdout, the 3B QLoRA checkpoint reached 20/20
  protocol-valid and 16/20 verified model-only before the fixture correction;
  the corrected rerun is the authoritative result and is still being finalized.
- The 0.5B best checkpoint reached 11/20 on the same pre-correction v3 slice;
  the narrow research-v2 model-plus-repair condition reached 12/12 across
  three stochastic decodes.
- These are promising local systems results, not yet an external benchmark or
  research-breakthrough claim. The next gates are corrected expanded-holdout
  results, independent training seeds, external OSWorld/\u03c4-bench-style tasks,
  and a public security/replication review.

## The one-sentence investor pitch

We are building the post-training and execution layer for reliable local
agents: specialize a small model in a verifiable action language, then let a
security-first harness execute, prove, replay, and continuously improve those
actions without allowing the model to become its own authority.
