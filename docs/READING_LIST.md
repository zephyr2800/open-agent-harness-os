# Reading list for the verified-agent project

This is the shortest path to being able to explain the project technically,
compare it with current launches, and defend the claim boundaries.

## Read first: the project thesis

1. [Lilian Weng — LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/)
   — planning, memory, tools, and why natural-language interfaces are fragile.
2. [Lilian Weng — Harness Engineering for Self-Improvement](https://lilianweng.github.io/posts/2026-07-04-harness/)
   — workflow design, evaluation, permission controls, persistent state, and
   joint optimization of harness and model.
3. [ReAct](https://arxiv.org/abs/2210.03629) and [Toolformer](https://arxiv.org/abs/2302.04761)
   — the foundational action/observation and learned-API-use patterns.

## Read next: action models and small-model specialization

4. [xLAM](https://arxiv.org/abs/2409.03215) — normalized action data and
   action-model scaling.
5. [TinyAgent](https://arxiv.org/abs/2409.00608) — small/edge function-calling
   systems and deployment-aware evaluation.
6. [Hammer](https://arxiv.org/abs/2410.04587) — irrelevance detection,
   function masking, and the importance of learning when not to call.
7. [Agent Distillation](https://arxiv.org/abs/2505.17612) — transferring
   executable behavior into smaller agents.
8. [Thinking Machines Tinker](https://thinkingmachines.ai/news/announcing-tinker/)
   and [Inkling](https://thinkingmachines.ai/news/introducing-inkling/) —
   customization and post-training as a product surface.

## Read for the evaluation/security bar

9. [ToolSandbox](https://arxiv.org/abs/2408.04682) — state dependencies,
   canonicalization, and insufficient information.
10. [AgentDojo](https://agentdojo.spylab.ai/) — indirect prompt injection and
    utility/security tradeoffs.
11. [τ-Knowledge](https://taubench.com/blog/tau-knowledge.html) — messy
    knowledge bases, policy retrieval, and evidence-grounded action.
12. [AppWorld-UL](https://arxiv.org/abs/2607.20536) — clarification,
    confirmation, infeasibility, and user-in-the-loop behavior.
13. [OSWorld](https://arxiv.org/abs/2404.07972) / [OSWorld 2.0](https://osworld-v1.xlang.ai/)
    — real desktop execution rather than toy API traces.
14. [MELON](https://proceedings.mlr.press/v267/zhu25z.html) — a research
    reference for defending against indirect prompt injection while retaining
    utility.
14a. [AutoDojo](https://arxiv.org/abs/2606.15057) — why a defense that looks
    robust to fixed injections can fail under adaptive black-box attacks,
    especially on under-specified action-open tasks. Read this before treating
    any static AgentDojo score as a security result.

## Read for the current launch landscape

15. [OpenAI Computer-Using Agent](https://openai.com/index/computer-using-agent/)
    — universal computer action, RL, safety, and benchmark reality.
16. [OpenAI computer environment for the Responses API](https://openai.com/index/equip-responses-api-computer-environment/)
    — the model-proposes/platform-executes loop, isolated workspaces,
    restricted networking, durable state, and production harness lessons.
    Pair it with the [Agents SDK harness update](https://openai.com/index/the-next-evolution-of-the-agents-sdk/)
    for tracing, approvals, and orchestration.
17. [Kimi K2: Open Agentic Intelligence](https://arxiv.org/abs/2507.20534),
    [Kimi K2.5](https://arxiv.org/abs/2602.02276), and [Kimi Linear](https://github.com/MoonshotAI/Kimi-Linear)
    — sparse scaling, multimodality, agentic post-training, and hybrid
    attention.

## Newly added frontier comparison papers

18. [StructAgent](https://arxiv.org/abs/2607.11388) - the closest current
    comparison for verifier-backed state, progress checkpointing, and
    evidence-grounded completion; read it to sharpen our novelty boundary.
19. [WeaveBench](https://arxiv.org/abs/2606.09426) - hybrid GUI/CLI/code
    workflows and trajectory-aware judging; read it before making a general
    computer-use claim.
20. [WildClawBench](https://arxiv.org/abs/2605.10912) - native-runtime,
    human-authored long-horizon tasks and harness-dependent performance.
21. [SWE-Marathon](https://arxiv.org/abs/2606.07682) - multi-channel
    verification, ultra-long horizons, and explicit reward-hacking audits.
22. [General AgentBench](https://arxiv.org/abs/2602.18998) - context ceilings
    and the verification gap in sequential and parallel test-time scaling.
23. [Toolathlon](https://arxiv.org/abs/2510.25726) - 32 applications, 604
    tools, and 108 execution-verified long-horizon tasks; use it to calibrate
    how far our local proxy is from real software state diversity.
24. [Long-Horizon-Terminal-Bench](https://arxiv.org/abs/2607.08964) - 46
    terminal tasks with graded subtasks across software, science, and
    multimodal workflows; this is the most direct next external bar for our
    terminal-first Action IR.
25. [AgencyBench](https://arxiv.org/abs/2601.11044) - 138 tasks requiring
    roughly 90 tool calls, 1M tokens, and hours of execution with sandboxed
    rubric evaluation; read it before making any self-evolving-agent claim.
26. [MCP-Atlas](https://arxiv.org/abs/2602.00933) - 1,000 natural-language
    tasks over 36 real MCP servers and 220 tools, with claim-level scoring;
    useful for measuring tool discovery and cross-server generalization.
27. [SIA: Self Improving AI with Harness & Weight Updates](https://arxiv.org/abs/2605.27276)
    and its [open implementation](https://github.com/hexo-ai/sia) - the
    closest adjacent self-improvement system; compare its mutable loop with
    our immutable evaluator and independent promotion gate.
28. [Harness Agent DLC](https://www.harness.io/press-and-news/introducing-harness-agent-dlc)
    and [Prime Intellect Lab](https://www.primeintellect.ai/blog/lab-is-open)
    - current product signals that build/evaluate/train/deploy loops are
    becoming a platform category, not merely research tooling.

## Fresh 2026 comparison points

29. [Thinking Machines — Inkling](https://thinkingmachines.ai/news/introducing-inkling/)
    and its [model card](https://thinkingmachines.ai/model-card/inkling/) - a
    975B-total/41B-active MoE open-weights release with a 12B-active smaller
    preview, multimodal inputs, long context, and a self-fine-tuning demo.
    The lesson for us is to separate a customizable policy-training surface
    from the independent authority and promotion plane.
30. [$\pi$-Bench](https://arxiv.org/abs/2605.14678) - 100 multi-turn tasks
    across five personas with hidden intents, inter-task dependencies, and
    cross-session continuity. Add persistence, user burden, and proactive
    intent metrics before calling the harness self-evolving.
31. [Thinking Machines — Interaction Models](https://thinkingmachines.ai/blog/interaction-models/)
    - native multimodal interaction using 200 ms micro-turns. Treat this as a
    reminder that launch readiness includes responsiveness and interruption
    behavior, not just end-state correctness.
32. [PBT-Bench](https://arxiv.org/abs/2605.15229) - property-based testing
    over real Python libraries with model-specific failure gaps. Use its
    invariant-discovery framing to add adversarial, stateful tool contracts to
    our failure-mining curriculum.

## The investor explanation after reading

The market is moving toward models that can act, but the difficult product
problem is making action reliable, permissioned, observable, and customizable.
Our thesis is that a compact policy can propose typed actions while a
model-agnostic harness owns authority, execution, evidence, replay, and model
promotion. The research claim is only valid if it survives held-out tasks,
independent replay, adversarial content, ambiguity, and an external suite.

## 90-minute cram order

Skim items 29–32 for the current customization, persistence, proactivity, and
hard-evaluator launch context.

Read 1–2, then 4–6, then 9–13, then 15–18, then 23–27. For each paper,
write down:

- what the model controls;
- what the environment/harness controls;
- how success is verified;
- what the benchmark does not measure;
- which failure mode maps to our v2 holdout or promotion gate.
