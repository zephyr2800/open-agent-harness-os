# Changelog

## Unreleased - source-bound evaluation and research-control hardening (2026-08-02)

- Added a checked-in native-evaluation preregistration, source-bound
  AgentDojo/tau2 launchers, immutable artifact validators, and regression
  coverage for the local OpenAI-compatible adapter transport.
- Bind completed AgentDojo evidence to the current pinned checkout's
  source-tree fingerprint, rejecting source drift before a result is reported.
- Hardened τ³ result validation against stale local endpoints, command/module
  rebinding, dirty or mismatched benchmark checkouts, selector-catalog drift,
  and JSON boolean-versus-integer identity confusion; public wheel-build log
 tails now redact machine-local paths.
- Fixed the τ³ runtime probe to import and record the exact adapter and runner
  source modules it verifies, with a regression test and a no-model-load
  check against the prepared pinned runtime and registered solo selectors.
- Separated the fixed native diagnostic from a conditional adaptive AutoDojo
  security protocol; neither is presented as a general capability or security
  certification.
- Refreshed the research and investor materials with source-backed Kimi K3,
  Inkling/Tinker, and adaptive-injection context.
- Refreshed developer-preview release evidence to v34 (16/16 preflight,
  210 Project 2 tests with one Windows capability skip, and 47/47 companion
  tests), and made public wheel-smoke sidecars use repository-relative or
  redacted evidence paths.
- Preregistered a full-coverage uniform-versus-weighted sampling-order
  ablation for a post-baseline failure-localization decision.
- Added this program status ledger so current evidence, hypotheses, and gates
  are visible without inspecting private checkpoints or local watcher logs.

## 0.1.8 - 2026-08-01

- Made release-readiness wheel smoke selection version-aware so stale
  historical smoke artifacts cannot satisfy the current-package gate.
- Added current-package regression coverage and refreshed the MCP/preflight
  package version metadata.

## 0.1.7 - 2026-08-01

- Excluded Python bytecode caches from distributable package artifacts.
- Refreshed the package metadata and preflight default to the clean 0.1.7
  developer-preview wheel and source distribution.

## 0.1.6 - 2026-08-01

- Versioned the post-0.1.5 retry-parser hardening as a reproducible patch
  release and aligned package metadata, MCP server metadata, and preflight
  wheel selection.
- Refreshed release evidence for the current 80-test harness suite.

## 0.1.5 - 2026-08-01

- Fixed retry-repair parsing for versioned operation identifiers that contain
  digits, with regression coverage for the public harness adapter.
- Refreshed the public research and launch landscape against current
  harness, safety, terminal-use, and customization benchmarks.
- Kept the developer-preview boundary explicit: local evidence is not a
  native external benchmark or general autonomous-agent claim.

## 0.1.4 — 2026-07-29

- Pointed release-readiness and preflight defaults at the current versioned
  evidence artifacts instead of stale 0.1.0/v1 files.
- Added fresh 0.1.4 wheel, source-distribution, preflight, and isolated wheel
  smoke evidence for the developer-preview patch release.

## Unreleased - research and launch hardening (2026-07-29)

- Added per-task promotion-matrix heartbeats so long generations expose
  auditable progress without altering score or resume state.
- Added `agent-eval-scorecard/v1` with macro-family scoring, Wilson intervals,
  replay/process integrity, safety, false-completion, and efficiency metrics.
- Added a preflight guard that rejects external-native claims without a
  hexadecimal suite commit, numeric native metric/value, report SHA-256,
  grader identity, and runner/runtime/platform metadata.
- Hardened wheel integrity to validate ZIP structure, safe paths, required
  modules, and dist-info; added isolated install/demo/import smoke and a
  package-scope preflight that does not assume the source checkout exists.
- Corrected safe-abstention accounting so failed, false-completing, or unsafe
  abstentions cannot inflate the safety score.
- Added the current research landscape, preregistered breakthrough protocol,
  and native external-evaluation runbook.
- Added companion-project test isolation to the launch preflight.

## 0.1.3 — 2026-07-29

- Aligned the package and MCP server version with the next developer-preview
  release so built artifacts, runtime metadata, and release tags agree.
- Added reproducible wheel and source-distribution release artifacts to the
  packaging checklist.

## 0.1.0 — 2026-07-25

- Added Action IR v0 and harness event contracts.
- Added typed state, authority policy, tool registry, bounded executor, and
  independent verification.
- Added evidence ledger, context compiler, recovery, checkpoints, replay, and
  branch selection.
- Added provider-neutral and Project 1-compatible model adapters.
- Added H0–H4 runtime configuration and bounded promotion gate.
- Added six-task held-in/held-out fixture and ten-cell factorial runner.
- Added 11 standard-library regression tests.
- Added a reproducible developer-preview launch preflight covering product
  smoke, MCP/replay, locality and safety boundaries, wheel integrity, launch
  docs, and the complete source test suite.
- Added atomic trace publication with restart/concurrency coverage and
  bearer-authenticated HTTP serving; non-loopback startup now requires a
  token plus TLS 1.2+ certificate/key configuration.
- Added frozen promotion-decision gates for complete hidden/proxy slices,
  independent replay, safety, and unknown-spec rejection.
- Added per-task latency and CUDA memory instrumentation to checkpoint
  promotion matrices.
- Added token-principal trace namespaces with cross-tenant read isolation and
  launch-preflight coverage.
- Added executable per-tool security metadata auditing to launch preflight.
- Added the disjoint 20-task external-bar-lite fixture and source-backed
  TUA-Bench/OSWorld 2.0 evaluation-bar note.
- Added atomic resumable checkpoints for long promotion matrices.
- Added a guarded post-matrix watcher that launches the external-bar-lite
  diagnostic only after the 9B frozen evaluation exits, with separate logs and
  no automatic RL or promotion override.
- Added an auditable promotion-matrix summarizer with family-level Wilson
  intervals, replay/safety metrics, latency, CUDA/device, and peak-memory
  reporting, plus a guarded post-run summary watcher.
- Added a machine-readable release-readiness manifest separating developer
  preview, research-candidate, and public-launch gates, with an automatic
  refresh watcher after the 9B evaluation chain.
- Added `docs/USER_WORKFLOW_GUIDE.md` with verified-write, recovery, and
  high-risk-denial preview workflows; launch preflight now requires it.
- Refreshed research positioning with current primary sources and a frozen
  model-only versus SFT versus independent-verifier factorial claim boundary.
- Added a disjoint 32-task external-bar v2 diagnostic and guarded three-seed
  watcher for cross-source, stale-state, conflict, injection, ambiguity, and
  confirmation failures.
- Hardened future matrix reports with false-completion, unverified-action,
  unknown-action, premature-finish, and abstention metrics by family and run.
- Added authenticated per-principal rolling HTTP rate limiting with `429` and
  `Retry-After`; launch preflight now covers the operational boundary.
- Added Apache-2.0 `LICENSE`, `NOTICE`, and `SECURITY.md` artifacts and made
  them required and fingerprinted in launch/release checks.
- Added the frozen 9B reproducibility handoff with checkpoint manifests,
  fixture hashes, exact commands, and promotion/diagnostic boundaries.
- Added a machine-readable pre-RL gate that blocks verifier-backed RL until
  promotion, replay, diagnostic, safety, and checkpoint gates pass.
- Added pass/fail regression tests for the pre-RL gate; the harness suite now
  covers 53 tests.
- Rebuilt and revalidated the distributable wheel after launch-policy changes;
  the wheel reports Apache-2.0 metadata and passes the full preview preflight.
- Reinstalled that wheel into a fresh target outside the checkout; clean demo
  and core-module import smoke passed.
- Added `experiments/wheel_smoke.py` and a machine-readable clean-target wheel
  smoke artifact with the current wheel fingerprint.
- Added the research/launch one-pager tying current primary-source signals to
  the falsifiable experiment and explicit claim boundaries.
- Updated the paired Project 1 paper draft with current validated 7B/harness
  evidence, negative controls, and the pending Qwopus 9B result boundary.
- Updated the main README with direct research, reproducibility, security,
  claims, launch, and clean-wheel evidence links.
