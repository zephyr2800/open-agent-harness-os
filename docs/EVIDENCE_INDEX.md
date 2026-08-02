# Evidence index

`docs/RESEARCH_LAUNCH_BRIEF.md` is the current investor/reviewer-facing
summary of the thesis, evidence tiers, external benchmark bar, and developer
preview versus public-launch gates. It intentionally distinguishes completed
local evidence from pending generalization claims.

`docs/DENSE_RELIABILITY_PROTOCOL.md` defines the non-promoting partial-credit,
pass-at-k, and worst-seed diagnostics. The implementation is
`experiments/analyze_dense_reliability.py`; these metrics explain progress and
variance without weakening the strict promotion gate.

`docs/READING_LIST.md` is the current 90-minute technical cram list, including
Lilian Wengâ€™s harness/self-improvement posts, action-model papers, security and
stateful-agent benchmarks, and current model/harness launches.

`docs/EXTERNAL_BAR_UPDATE_2026-07-26.md` records the newly checked TUA-Bench
and OSWorld 2.0 bar and translates their failure modes into the next local
evaluation gate.

`docs/RESEARCH_LAUNCH_UPDATE_2026-07-27.md` records the current primary-source
review, the falsifiable systems claim, the Kimi/Inkling/autoresearch signals,
and the execution order from the live 9B gate to external evaluation and
public-launch readiness.

`docs/RESEARCH_LAUNCH_UPDATE_2026-08-01.md` refreshes the external bar with
TUA-Bench, OSWorld 2.0, OpenComputer, current verifier-grounded research,
Inkling/Tinker, Kimi K3, and the current claim-safe launch consequences.

`docs/SCALE_CONTROL_NOTE_2026-07-27.md` records the interim same-task-hash
7B-versus-9B comparison and the parameter-scaling caveats; it is evidence for
the ablation design, not a final model leaderboard result.

`docs/REMEDIATION_DATA_AUDIT_2026-07-27.md` records the corrected schema and
zero frozen-task-ID-overlap audit for the queued remediation curricula. It
explicitly separates data-contract validity from evidence of improvement.

`docs/PROVENANCE_REVIEW.md` now records the external Qwopus model-page and
fine-tuning-repository review. The visible Apache-2.0 labels do not substitute
for human clearance of upstream weights, training sources, traces, or intended
commercial redistribution.

`docs/PRODUCT_LAUNCH_PLAN.md` now separates a potential public harness-only /
bring-your-own-model distribution from the private Qwopus research bundle, so
model provenance is not silently conflated with the Apache-licensed harness.

`docs/PUBLIC_HARNESS_PACKAGE_AUDIT_2026-07-27.md` records the wheel-content
audit and hash for that public-track boundary; the wheel contains no Qwopus
weights, model binaries, or training fixtures.

`docs/RESEARCH_REPORT.md` and `docs/RESEARCH_MATRIX_9B_2026-07-29.md` record the
completed historical 9B frozen-matrix result and explicitly separate it from promotion,
external-benchmark, RL, and generalized-capability claims. The committed
sanitized result is
`experiments/results/research-project2-qwopus35-9b-promotion-summary-v1.json`.
Raw replay traces, the merged checkpoint, and the machine-readable promotion
decision remain private research artifacts and are not bundled in this public
repository.

The 2026-07-27 literature refresh adds StructAgent, WeaveBench,
WildClawBench, SWE-Marathon, General AgentBench, Toolathlon,
Long-Horizon-Terminal-Bench, AgencyBench, MCP-Atlas, and SIA as explicit
comparison points. Their common lesson is that verifier-backed state,
native-runtime evaluation, long-horizon partial credit, and anti-reward-
hacking checks are now baseline expectations; the remaining differentiator
under test is compact policy specialization coupled to an immutable,
evidence-driven self-improvement loop. The refresh also records Harness Agent
DLC and Prime Intellect Lab as product signals for an integrated
build/evaluate/train/deploy category.

The latest primary-source refresh adds Thinking Machines' Inkling release,
its interaction-model direction, Ï€-Bench, and PBT-Bench. These sharpen the
next external bar around customization, persistent cross-session state,
proactive intent, invariant discovery, responsiveness, and model-specific
failure coverage; none are treated as local benchmark results.

`docs/RESEARCH_ABLATION_SPEC_V2.md` freezes the five-cell causal comparison,
metrics, held-out protocol, and promotion rules for that differentiator.

The public repository includes the diagnostic fixture and analysis code, but
not private watcher scripts, partial outputs, model checkpoints, raw traces, or
RL results. Those artifacts are intentionally excluded from the public release
until provenance, licensing, and reproducibility review are complete.

`docs/CLAIMS_AND_EVIDENCE_MATRIX.md` is the claim-control sheet: it maps every
investor/research statement to authoritative artifacts and labels pending or
unsupported claims explicitly.

The disjoint 20-task bridge fixture is
`benchmarks/fixtures/task-spec-external-bar-lite-v1.json`; it is validated by
the task loader and has SHA-256
`8d1d852b4cd181079effd7023df13655406de73ddfd6a65329ec6597adf6cae3`.

An outside reviewer can reproduce the public harness checks and fixture-level
evaluations from the project root. The private 9B checkpoint result is
summarized here but cannot be independently rerun from this repository alone.

## Core audit

```powershell
$py = 'python'
& $py -m unittest discover -s tests -v
& $py -m compileall -q .
```

Current result: 95 Project 2 tests pass. The latest delta includes the
external-adapter and evidence/replay regressions.

## Independent research fixture

```powershell
& $py -m experiments.factorial --task-spec benchmarks/fixtures/task-spec-research-v1.json --output experiments/results/research-factorial-v1.json
& $py -m verify.independent experiments/results/research-factorial-v1.json --task-spec benchmarks/fixtures/task-spec-research-v1.json --output experiments/results/research-independent-v1.json
```

Current result: 110 traces, 1.0 trace-valid, 1.0 runtime/verifier agreement,
and fixture-only H3/H4 interaction `+0.090909`.

## Real-model evidence

- `experiments/results/research-project2-qwopus35-9b-promotion-summary-v1.json`:
  public sanitized aggregate of the completed historical 9B frozen matrix: 483/552 verified,
  zero unsafe attempts, and rejected promotion.
- `docs/QUANTIZED_SERVING_SMOKE_2026-07-29.md`: one-request RTX 5090
  4-bit-serving diagnostic with measured memory and timing.

The raw checkpoint, replay traces, and private decision artifacts are not
distributed here. The public evidence supports a developer-preview harness and
failure localization, not a breakthrough, external benchmark, or production
model claim.

## Product evidence

- `python -m app.cli demo` succeeds with a verified trace;
- `python -m app.cli replay <trace>` validates the trace offline;
- loopback API smoke test passes `/health`, `/tools`, and `/run`;
- high-risk delete is denied by default;
- wheel build plus clean extracted-package demo succeeds.
- `experiments/results/product-smoke-v0.json` covers six workflows with 1.0
  protocol validity, 0.833333 verified-success rate, and a deliberate safety
  denial for high-risk delete.
- `experiments/results/launch-preflight-v19.json` is the current local developer-
  preview gate: product smoke, MCP contract/replay, locality, high-risk
  safety, persistence, HTTP bearer authentication, token-principal trace
  isolation, non-loopback TLS gating, per-tool security metadata, wheel
  integrity, extracted-wheel install smoke, launch-document presence, and all
  the 170-test source suite passed at artifact creation. It builds from a
  clean source copy, binds the complete wheel archive, modules, and console
  scripts to a fresh source-derived reference, and rejects Python bytecode
  caches. It
  records the 0.1.8 source-package fingerprint and wheel-manifest hash in
  `docs/PUBLIC_RELEASE_CHECKLIST.md`.

See `PRODUCT.md` and `docs/PRODUCT_LAUNCH_PLAN.md` for the developer-preview
boundary and remaining public-launch gates.

## Research-bar refresh â€” 2026-07-26

The current positioning refresh adds primary references on long-horizon hidden
state and verification failures ([OSWorld 2.0](https://arxiv.org/abs/2606.29537)),
machine-checkable tool-use data synthesis ([Controllable and Verifiable
Tool-Use Data Synthesis](https://arxiv.org/abs/2604.09813)), verifier-driven RL
([AgentV-RL](https://arxiv.org/abs/2604.16004)), test-time tool verification
([Tool Verification for Test-Time Reinforcement Learning](https://arxiv.org/abs/2603.02203)),
and reusable verifier environments ([Prime Intellect verifiers](https://github.com/PrimeIntellect-ai/verifiers)).
The required next paper ablation is model-only versus Action IR SFT versus
independent verifier/evidence/replay under a frozen holdout and external
suite; the 9B matrix is a scale gate, not that factorial.

`docs/REPRODUCIBILITY_9B_CHAIN.md` freezes the Qwopus3.5-9B checkpoint
manifests, task-spec hashes, exact matrix command, promotion decision command,
diagnostic order, and the rule that diagnostics cannot substitute for a
promotion or external-benchmark result.

`docs/PROVENANCE_REVIEW.md` is the launch handoff for model, dataset, trace,
dependency, benchmark, and redistribution review. It records the engineering
inventory without treating local Apache-2.0 metadata as clearance for upstream
weights or data.

## Current strict checkpoint ablation

- `experiments/results/research-project2-ablation-v1.json` is the aggregate
  report for the corrected model-only versus verifier-first repair ablation.
- `experiments/results/research-project2-sft-v2-model-only-v2.json`: v1 model
  only, 4/11 verified.
- `experiments/results/research-project2-sft-v2-repair-v3.json`: v1 model plus
  repair, 11/11 verified.
- `experiments/results/research-project2-sft-v2-independent-holdout-model-only-v1.json`:
  independent v2 model only, 5/12 verified.
- `experiments/results/research-project2-sft-v2-independent-holdout-repair-v2.json`:
  independent v2 model plus repair, 12/12 verified.
- The four adjacent `*-independent.json` reports independently replay every
  trace; all have 1.0 trace validity and 1.0 runtime/replay agreement.
- `experiments/results/research-project2-stochastic-replication-v1.json`
  records sampled seeds 0, 1, and 2 on the independent holdout; all 36
  traces replay successfully. This is one-checkpoint stochastic stability,
  not independent training replication.
- `benchmarks/fixtures/task-spec-research-v2.json` is the independent holdout
  spec; its SHA-256 is
  `d5794508c7d3b17554e9efba44f7fb56f7e0bb62861e25c14f03d59348346fcd`.

## Launch smoke

- `python -m app.cli demo` and `python -m app.cli replay` both pass.
- The live MCP stdio server passes `initialize`, `tools/list`, and a verified
  `harness_run`; it advertises MCP protocol `2025-06-18` and has no network
  listener.
- Fresh recorded result: `experiments/results/mcp-stdio-smoke-v1.json`.

## Active research expansion

- `benchmarks/fixtures/task-spec-research-v4.json`: frozen 120-task,
  12-family holdout; SHA-256
  `9c4e3a4f643c21056dd8fe5437ffe180054cf7f96ad02f572910eb298369bfda`.
- `experiments/project2_checkpoint_run.py`: records family, difficulty, and
  adversarial labels in every row and instantiates task-owned API/browser
  fixtures.
- `experiments/aggregate_research_eval.py`: aggregates full runs with family
  slices and 95% Wilson intervals; use it after each greedy or sampled seed.
- `../local-action-model/work/action-harness-sft-v5-stratified-hidden.jsonl`: 3,072
  verifier-backed training rows with six controlled prompt styles.
- `../local-action-model/train/transformers_lora_sft.py`: reproducible
  uniform/weighted epoch sampler with sampled-row accounting.

These are evaluation/data-method artifacts. The v4 model score is intentionally
not listed until the complete checkpoint run and independent replay report are
available.

## Corrected v4 control

- `experiments/results/research-project2-7b-qlora-v1-research-v4-model-only.json`:
  hinted control, 120/120; retained only as an evaluator-ablation result.
- `experiments/results/research-project2-7b-qlora-v1-research-v4-hidden-model-only.json`:
  honest model-only control, 80/120 verified and 118/120 protocol-valid.
- `experiments/results/research-project2-7b-qlora-v1-research-v4-hidden-model-only-independent.json`:
  120/120 valid traces and 120/120 runtime/replay agreement.
- `experiments/results/research-project2-7b-qlora-v1-research-v4-hidden-aggregate.md`:
  per-family slices and confidence intervals.
- `benchmarks/fixtures/task-spec-industry-proxy-v1.json`: 48-task offline
  proxy for stateful tool use and indirect injection; SHA-256
  `c5c0e843f2edc27cdb10b2a2b5d394d5d64373d558f072f4cb0f49001c10cb5e`.
- `docs/INDUSTRY_BENCHMARK_PLAN.md`: external-suite mapping and promotion
  gates for Ï„Â³-bench, ToolSandbox, AgentDojo, BrowserGym, and OSWorld.

## Proxy-mix checkpoint evidence

- `../local-action-model/work/action-harness-sft-v6-proxy-mix.jsonl`: 3,792
  rows combining the corrected 3,072-row curriculum with 720 verifier-backed
  industry-proxy trajectories; SHA-256
  `ca481e498e22ebe9e1c81d199e32899c7968e91b18c121c35c0764a62b82e95f`.
- `experiments/results/research-project2-7b-qlora-v5-proxy-mix-industry-proxy-v1-model-only.json`:
  43/48 greedy, 100% protocol-valid, zero unsafe attempts.
- `experiments/results/research-project2-7b-qlora-v5-proxy-mix-industry-proxy-v1-model-only-independent.json`:
  100% trace validity and runtime/replay agreement.
- `experiments/results/research-project2-7b-qlora-v5-proxy-mix-industry-proxy-v1-sample-seed1.json`:
  sampled seed 1, 41/48 verified and 45/48 protocol-valid.
- `experiments/results/research-project2-7b-qlora-v5-proxy-mix-industry-proxy-v1-sample-seed2.json`:
  sampled seed 2, 37/48 verified and 48/48 protocol-valid.
- `experiments/results/research-project2-7b-qlora-v5-proxy-mix-industry-proxy-v1-sample-seed3.json`:
  sampled seed 3, 39/48 verified and 48/48 protocol-valid.
- The adjacent `*-sample-seed1-independent.json`,
  `*-sample-seed2-independent.json`, and `*-sample-seed3-independent.json`
  files each report 100% trace validity and runtime/replay agreement.
- `experiments/results/research-project2-7b-qlora-v5-proxy-mix-industry-proxy-v1-four-run-aggregate.md`:
  greedy plus three sampled runs, 160/192 verified (83.3%) and zero unsafe
  attempts.
- `experiments/results/research-project2-7b-qlora-v5-proxy-mix-research-v4-model-only.json`:
  120/120 verified and protocol-valid on the hidden-contract v4 holdout.
- `experiments/results/research-project2-7b-qlora-v5-proxy-mix-research-v4-model-only-independent.json`:
  100% trace validity and runtime/replay agreement.

## Native-tool v6 checkpoint evidence

- `../local-action-model/work/action-native-tool-curriculum-v1.jsonl`: 180
  held-out-safe AgentDojo-like native-tool rows; SHA-256
  `69b080913023e8c60ca049640767ba3534f6447ce450adaea7f64c7273f8117a`.
- `../local-action-model/work/action-harness-sft-v7-native-tool.jsonl`: 3,972
  rows including the v5 curriculum and native-tool rows; SHA-256
  `aaf2c0ea03f1f2e1a8e7936be1402c983a0c1e55947eed514d065837db17a522`.
- `experiments/results/research-project2-7b-qlora-v6-native-tool-research-v4-model-only.json`:
  120/120 verified and protocol-valid on frozen v4.
- `experiments/results/research-project2-7b-qlora-v6-native-tool-industry-proxy-v1-model-only.json`:
  48/48 verified and protocol-valid on the local industry proxy, with zero
  unsafe attempts across state, policy, browser-injection, and API-injection
  slices.
- The adjacent v6 independent reports show 100% trace validity and runtime /
  independent-replay agreement.

## Verifier-backed RL ablation

- `../local-action-model/train/transformers_reinforce.py` now supports a
  4-bit NF4/BF16 QLoRA REINFORCE path with verifier-only reward, an EMA
  baseline, and cache-safe sampling.
- `../work/action-model-project2-7b-post-rl-qlora-v1/rl_manifest.json`: 16
  sampled trajectories from the v5 7B checkpoint, 40,370,176 trainable LoRA
  parameters, and 9,041.3 MiB peak VRAM. Before and after greedy reward were
  both `-0.78125`, with 0/8 smoke-task successes; this is a neutral/negative
  calibration result, not a promoted checkpoint.
- `experiments/results/research-project2-7b-post-rl-qlora-v1-research-v3-model-only.json`:
  20/20 verified and protocol-valid on the hidden-contract research-v3
  holdout with repair disabled.
- `experiments/results/research-project2-7b-post-rl-qlora-v1-research-v3-model-only-independent.json`:
  100% trace validity, independent success, and runtime/replay agreement.

## External benchmark integration

- `docs/EXTERNAL_AGENTDOJO_RUN.md`: exploratory AgentDojo integration report;
  includes the pinned source commit, v5 baseline, v6 guard ablation, exact
  clean/injection outcomes, raw trace paths, and next promotion gate.
- `../work/external/agentdojo_adapter_server.py`: local OpenAI-compatible
  Action IR bridge; it retains raw model decisions and labels tool results as
  untrusted context, never verified harness evidence.
- The v5 clean external task scored 0/1 utility because the policy skipped
  required information retrieval. The v6 lookup-first guard raised the
  corresponding write task to 1/1, but the v6 model-only clean Q&A task still
  scored 0/1 and the direct-injection composite scored 0/1 utility while not
  carrying out the injection. These are ablations, not an external-suite
  average or a launch claim.

## Qwopus3.5-9B external reference

- `docs/QWOPUS35_REFERENCE.md`: review of the Qwopus3.5-9B-v3 model card,
  linked fine-tuning repository, 26-page PDF guide, and the proposed 9B
  comparison/adapter/RL gates.
- Local metadata and tokenizer snapshot:
  `../work/hf-models/Jackrong-Qwopus3.5-9B-v3-meta`.
- Full four-shard checkpoint is available at
  `../work/hf-models/Jackrong-Qwopus3.5-9B-v3` (~19.3 GB).
- BF16 load and 4-bit QLoRA architecture smoke passed; the smoke adapter is
  `../work/qwopus35-9b-action-smoke`.
- The Qwopus-compatible verifier-backed REINFORCE entry point passes a
  tokenizer/model dry-run on the disjoint 24-task Action IR specification; this checks
  post-training compatibility but is not an RL improvement result.
- The full rank-64 Action IR SFT branch is running separately under
  `../work/action-model-project2-qwopus35-9b-qlora-v1`; it is not promoted
  until hidden, independent-replay, industry-proxy, and AgentDojo gates pass.

## External-gap revision result

- `../local-action-model/work/action-harness-sft-v8-external-gap-repeated.jsonl`:
  4,512-row revision with the held-out-safe external-gap curriculum repeated
  5x; SHA-256 `ba89ab3ab4da016d64a739e2649181a0a22df55540fb47273dfb8a46608dc937`.
- `experiments/results/research-project2-7b-qlora-v7-external-gap-research-v4-model-only.json`:
  120/120 verified and protocol-valid, but this does not prove generalization.
- `experiments/results/research-project2-7b-qlora-v7-external-gap-industry-proxy-v1-model-only.json`:
  39/48 verified, 100% protocol-valid, zero unsafe; the policy-sequence slice
  fell to 3/12. v6 remains the promoted 7B checkpoint.
- AgentDojo bridge artifacts under `../work/external/agentdojo-runs/` show the
  v7 model still fails clean user task 17 and regresses the exact calendar
  slots on user task 18. These are diagnostic runs, not a benchmark average.

## Evidence-grounded benchmark hardening

- `benchmarks/fixtures/task-spec-industry-proxy-v2.json`: 16-task disjoint
  holdout for evidence-to-answer, insufficient information, and confirmation
  boundaries; SHA-256
  `eb4d071facde6b94e632d68b01caf43e3ae8f7cb456b504e52c38453304d1d6c`.
- `benchmarks/generate_industry_proxy_v2.py`: reproducible generator with
  fresh markers and no training-row reuse.
- `experiments/run_promotion_matrix.py`: one-command greedy/sampled matrix
  runner that hides contract hints, reuses one loaded checkpoint, and records
  runtime plus independent replay outcomes for every task.
- `experiments/holdout_novelty_audit.py`: identifier-normalized lexical
  template-affinity screen. It binds its report to the exact training-source
  and task-spec hashes, but is explicitly not a semantic-novelty claim.
- `experiments/promotion_decision.py`: separate frozen promotion gate that
  requires all three slices, all recorded runs, independent replay agreement,
  zero unsafe attempts, no unknown task specifications, and a bound passing
  template-affinity report.
- The harness now checks `expected_result_contains` in addition to tool
  execution, independent evidence, action ordering, and artifact state. This
  prevents generic final answers from receiving a verified-success score.
- `verify/independent.py` applies the same expected-result check during replay,
  keeping runtime and independent success semantics aligned.
- The current project test suite is 115/115 after evaluator hardening, dense-reliability,
  atomic concurrent
  trace-retention coverage, and HTTP bearer-auth coverage.
- Current wheel/preflight artifact: `work/package-dist-0.1.8-final/open_agent_harness_os-0.1.8-py3-none-any.whl`,
  SHA-256 is recorded in `docs/PUBLIC_RELEASE_CHECKLIST.md`;
  it contains the explicit non-loopback authentication-plus-TLS gate.
- `experiments/launch_preflight.py` provides the reproducible source-checkout
  command `python -m experiments.launch_preflight --with-tests --output
  experiments/results/launch-preflight-local.json`; the artifact
  explicitly records 12 concurrent writes, 12 valid traces after a fresh
  store restart, and is scoped to the local developer preview; it does not
  claim public authentication, multi-user isolation, or external-benchmark
  readiness.

## Research positioning refresh â€” 2026-07-26

`docs/RESEARCH_POSITIONING_REFRESH_2026-07-26.md` records the primary-source
comparison to current customization, verifier-RL, and long-horizon agent
launches. It converts those observations into the next falsifiable ablation:
model-only vs. verifier-backed harness vs. verifier-backed post-training under
a frozen evaluation and replay contract.

