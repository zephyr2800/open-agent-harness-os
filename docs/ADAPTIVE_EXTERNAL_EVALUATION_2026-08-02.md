# Adaptive external evaluation plan — 2026-08-02

Status: prepared, not executed. This is a Phase B security protocol for a
promoted clean-split checkpoint. It is not evidence that the current model is
robust to prompt injection.

## Why this is a separate phase

The registered AgentDojo diagnostic is deliberately fixed before the clean 9B
checkpoint is available. It provides reproducible utility and static-injection
evidence, but it is not a test against an attacker that can adapt to the
particular harness configuration. [AutoDojo](https://arxiv.org/abs/2606.15057)
shows why that distinction matters: its black-box optimization can recover
attack success against defenses that appear robust on static injections, and
the effect is especially pronounced for under-specified, action-open tasks.

Phase B therefore remains conditional on Phase A completing and validates a
different claim: how the exact deployed policy/harness configuration behaves
when attacks are optimized against it. It must never be combined with Phase A
into a single aggregate “security score.”

## Pinned source and local compatibility

- Source: [AutoDojo](https://github.com/xhOwenMa/AutoDojo), commit
  `f5ad9309f864a3ecde4face656cbe205ec9e2fb1` (MIT license for the repository;
  review the bundled benchmark/data licenses independently).
- The source supplies an AgentDojo fork plus an `autodojo` attack that consumes
  model/defense-specific optimized-injection caches. Do not reuse the paper's
  cached variants for this checkpoint; they target other models/configurations.
- A dependency-only, no-model-load CLI smoke succeeded locally with the pinned
  source, the existing AgentDojo dependency bundle, and Python 3.12. It
  confirmed that `python -m agentdojo.scripts.benchmark --help` exposes the
  `autodojo` attack and local `vllm_parsed` target mode.
- The harness's loopback adapter provides the two OpenAI-compatible endpoints
  AutoDojo's local mode needs: `GET /v1/models` and `POST /v1/chat/completions`.
  This is a compatibility hypothesis only until a checkpoint-bound Phase B
  smoke validates an end-to-end request.

AutoDojo normally calls an optimizer/analyzer model through an API provider.
For a local-only study, the attacker model and its endpoint must be named in
the run manifest; using the target model itself as an attacker is permitted as
a weaker local red-team baseline, but must be labeled as such. Do not spend on
an external attacker model or create credentials without explicit approval.

## Preconditions — all required

1. The clean 9B training run completes, merges, and has a complete
   three-seed frozen promotion decision of `promote`.
2. Registered Phase A AgentDojo and tau2 diagnostics complete with native logs
   and their result validators passing. A Phase A failure is evidence, not a
   reason to loosen Phase B selectors or budgets.
3. The AutoDojo checkout remains clean at the pinned commit; the exact Python
   dependency root, adapter source tree, policy checkpoint, tokenizer revision,
   and local endpoint response are recorded before any attack optimization.
4. A new task set is frozen before generating variants. It must use an
   AutoDojo-supported suite and must not be selected after observing a model
   result. Keep Phase B tasks separate from Phase A's registered workspace
   diagnostic when the supported suite allows it.
5. The attacker model, optimizer prompts, seed, number of variants,
   iterations, per-pair evaluation cap, concurrency, timeout, and cache output
   directory are all precommitted. The cache is hashed before benchmark use.
6. Generated injections, traces, API credentials, and native benchmark data
   stay under ignored local evidence directories; none may enter the public
   repository or any subsequent training corpus.

## Required conditions

For each selected task family, report these arms separately under matched
target-model budgets:

| Arm | Target policy/harness | Attack material | Purpose |
|---|---|---|---|
| Clean utility | `model-only`, then `repair` | none | Establish utility/false-refusal control. |
| Fixed attack | same two variants | preregistered static attack | Bridge to Phase A and expose static robustness. |
| Adaptive attack | same two variants | cache optimized independently against that exact arm | Measure adaptive attack success; never transfer a cache silently between arms. |

The `repair` condition is the project harness ablation carried by the local
adapter; it is not interchangeable with AutoDojo's built-in `--defense`
choices. If an AutoDojo defense is added later, it becomes a new named factor,
not a replacement for either harness arm.

Report native utility, security, and attack-success metrics; per-task results;
the action-open/underspecified bucket where available; false refusals on clean
controls; unsafe execution; trace/replay validity; output tokens; wall time;
peak memory; the attack-cache hash; and all failed/timeout attempts. The
headline is the worst relevant family, not the best average.

## Execution boundary

Run only after the GPU is free from training. Start the local policy adapter on
a dedicated loopback port and point AutoDojo's `LOCAL_LLM_PORT` only at that
endpoint. The first checkpoint-bound operation is a one-task end-to-end smoke
whose result is marked `setup-validation`, not benchmark evidence. It must
prove the source path, adapter model discovery, native log shape, and no
unexpected network listener before the preregistered evaluation begins.

An adaptive result can falsify a security claim. It cannot certify the harness:
the benchmark remains a bounded evaluation of its selected task/attack process.
Any Phase B result belongs beside, not instead of, the independent terminal-use
bar. [TUA-Bench](https://github.com/facebookresearch/TUA-Bench) is a separate
120-task execution benchmark; its current setup requires Docker or Podman and
`uv`. Those runtimes are not presently installed on this machine, so no TUA
score is claimed or scheduled until an isolated runtime is available.
