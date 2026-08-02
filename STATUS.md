# Status

Updated: 2026-08-02

## Program state

Project 2 is a runnable local developer-preview harness and an active research
prototype. It is **not** a public-production agent service or a completed
research-breakthrough result. The paired Project 1 clean 9B Action IR SFT
candidate is still training; no new checkpoint has passed the frozen promotion
gate, native external diagnostic, or verifier-backed RL gate.

## Facts

- The public harness provides typed Action IR, H0-H4 variants, authority
  gates, registered tools, deterministic verification, an evidence ledger,
  replayable JSONL traces, checkpoint/recovery machinery, loopback HTTP, and
  MCP stdio surfaces.
- The current Project 2 regression suite has 210 tests total (209 passed; one
  Windows symlink-capability skip), and fresh release preflight v34 is 16/16.
  These are developer-preview regression controls, not an external capability
  score.
- A historical 9B matrix completed at 483/552 independently verified local
  successes with zero unsafe attempts and complete trace/replay checks, but it
  was rejected and remains context-only because its training-source isolation
  was not auditable.
- The active clean 9B branch binds 3,232 audited training rows to a frozen
  promotion protocol with genuinely stochastic decoding seeds, source-tree
  records, independent replay, safety accounting, and a decision artifact.
- The active local v2 promotion surface is structurally bounded: every
  `finish` task offers only reference-contract tool types, and no finish
  contract exceeds three required actions. The tracked evaluation-surface
  audit is a complexity floor and does not weaken or change the frozen gate.
- A separate post-freeze 36-task action-surface stress diagnostic is registered
  for after promotion. Its completion tasks require five ordered actions with
  valid distractor tools under the fixed six-step budget; it is local,
  diagnostic-only, and does not alter v2 promotion or RL authorization.
- The public corpus-quality audit binds that same 3,232-row source hash and
  reports zero exact duplicate rows or inputs, 7 provenance sources, and 15
  sampling strata without exposing examples. It is a data-integrity control,
  not evidence of held-out model generalization.
- The first native external diagnostic is preregistered before checkpoint
  evaluation: source-pinned AgentDojo clean/direct-injection cases and a
  source-pinned tau3-bench v1.0.1 telecom/base solo diagnostic (using the
  upstream `tau2` CLI). The launchers preserve native artifacts and the
  validators fail closed on selector, source, policy, or artifact drift.
- The next post-gate model×harness factorial has an isolated execution-control
  upgrade: H1 and H3 both hide evaluator-owned contract hints and disable
  deterministic adapter repair; H3 is explicitly the advanced
  context/checkpoint/recovery treatment. A separate analysis tool will reject
  incomplete, mismatched, unreplayable, unsafe, non-stochastic, or
  source/data-unbound four-cell reports before calculating a task-cluster
  interaction interval. This is prepared instrumentation, not a checkpoint
  result or a change to promotion v2.
- Future checkpoint, native, and factorial runs can preserve a raw sampled
  whole-GPU-energy sidecar (`gpu-energy/v1`). No energy value is claimed for
  the live clean 9B training job; the sampler cannot retroactively observe it
  and is not a per-process or wall-socket meter.
- Adaptive AutoDojo evaluation is a separate conditional Phase B protocol.
  It has not run, generated attack data is excluded from training/public
  artifacts, and no current result is a security certification.

## Inferences

- The harness is ready to be inspected and exercised as a bounded local
  developer preview.
- The research claim is still empirical: local fixture scores and a source
  bound native diagnostic alone cannot establish broad agent capability,
  robust security, or model-harness superadditivity.
- The next valid intervention depends on the frozen clean-candidate evidence.
  A failed gate is useful failure localization, not justification to loosen the
  evaluator or start RL.

## Hypotheses under test

1. A specialized Action IR policy and verifier-first harness can improve
   independently verified utility on stateful tasks without increasing unsafe
   actions, false completion, or replay disagreement.
2. Any model-harness interaction must be demonstrated with the four-cell
   factorial and a matched-budget search control, not inferred from a single
   checkpoint score.
3. If failure localization supports it, a full-coverage weighted-order
   curriculum can improve the error family without silently oversampling data
   or regressing the worst safety/replay slice.

## Next gates

1. Finish the clean 9B SFT and validate its manifest and train/holdout audit.
2. Run the frozen three-seed promotion matrix and publish either its promotion
   decision or its rejection evidence.
3. If promoted, run the registered native AgentDojo and tau3-bench diagnostics,
   then validate their native artifacts before describing any external result.
4. Only then choose a failure-targeted remediation, the preregistered
   sampling-order ablation, verifier-backed RL, or the separate 27B NF4 QLoRA
   feasibility smoke; preserve the same held-out and safety gates. The 27B
   branch must use audited clean data and cannot substitute for a failed 9B
   evaluation.
5. Complete the real model-by-harness factorial, deployment measurements,
   licensing/provenance review, usability evidence, and public-launch controls
   before claiming a completed paper result or production readiness.

## Pointers

- `docs/RESEARCH_LAUNCH_BRIEF.md` -- thesis, evidence tiers, and claim limits.
- `docs/RESEARCH_ABLATION_SPEC_V2.md` -- controlled model/harness and sampling
  ablations.
- `docs/CORPUS_QUALITY_AUDIT.md` -- raw-content-free corpus integrity audit.
- `docs/EVALUATION_SURFACE_AUDIT.md` -- reproducible limits of the local task
  surface; not a model score.
- `docs/ACTION_SURFACE_STRESS_V1.md` -- post-freeze five-step local stress
  diagnostic and replay-validation procedure.
- `docs/NATIVE_EVALUATION_REGISTRATION_2026-08-01.md` -- Phase A external
  diagnostic.
- `docs/ADAPTIVE_EXTERNAL_EVALUATION_2026-08-02.md` -- conditional Phase B.
- `docs/PUBLIC_RELEASE_CHECKLIST.md` -- developer-preview/public-release
  boundaries.
