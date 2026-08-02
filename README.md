# Open Agent Harness OS

[![CI](https://github.com/zephyr2800/open-agent-harness-os/actions/workflows/ci.yml/badge.svg)](https://github.com/zephyr2800/open-agent-harness-os/actions/workflows/ci.yml)

Open-source, local-first infrastructure for verifiable tool-use agents.

The project separates a probabilistic action policy from the deterministic
control plane that authorizes actions, executes tools, records evidence,
replays traces, enforces safety boundaries, and decides whether a task is
actually complete.

## What is included

- Typed Action IR and protocol validation
- Allowlisted execution with explicit risk and confirmation boundaries
- Independent evidence and replay verification
- Bounded recovery and tamper-evident trace lineage
- Local CLI, HTTP, and MCP surfaces
- Reproducible benchmark generators, task fixtures, tests, and research docs
- Claim-safe model-harness scorecards with macro-family, safety, replay, and
  efficiency metrics
- The companion local-action-model source under `projects/local-action-model/`

## Current evidence

The local developer-preview harness passes its documented product checks:

- Project 2 tests: 214 total (213 passed; one Windows symlink-capability test skipped; including dense-reliability, source-bound wheel integrity, scorecard, promotion-protocol, native-result-validator, energy-measurement, corpus-quality-audit, action-surface-stress, public-evidence-path, wheel-license-notice, and HTTP security-boundary checks)
- Project 1 tests: 47/47
- Launch preflight v36: 16/16 (including a fresh clean-source wheel build, source-tree binding, extracted-wheel installation smoke, repository-relative evidence links, required LICENSE/NOTICE entries in the wheel, and the focused HTTP security-review record)

The historical Qwopus3.5-9B frozen promotion matrix completed privately under a
fixed protocol: 483/552 independently verified successes (87.5%), zero unsafe
attempts, 100% trace validity, and 100% runtime/replay agreement. The separate
promotion decision rejected the checkpoint. This is failure-localization
evidence, not a claim that the model is generally capable or that RL improved
it. Separately, the clean-source Qwopus3.5-9B candidate completed audited SFT,
but its frozen promotion matrix was intentionally paused at 96/480 task-seed
attempts. That partial matrix has no promotion decision and cannot authorize
native evaluation or RL. See
`docs/CLAIMS_AND_EVIDENCE_MATRIX.md` and
`docs/RESEARCH_LAUNCH_BRIEF.md` for the evidence boundaries; `STATUS.md`
records the current program state and gated next steps.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python -m unittest discover -s tests -v
python -m pip wheel . --no-deps --wheel-dir work/package-dist
python -m experiments.launch_preflight --with-tests --output experiments/results/launch-preflight-local.json
```

### Try the developer preview

After installation, run the offline verified-write workflow and replay its
trace without executing the tool again:

```powershell
python -m app.cli demo --trace-out work\preview-demo-trace.jsonl
python -m app.cli replay work\preview-demo-trace.jsonl
```

For a bounded state-inspection/recovery example and a trace-recorded
high-risk-action denial, see [the user workflow guide](docs/USER_WORKFLOW_GUIDE.md).

The companion project uses intentionally local package names such as
`runtime` and `experiments`; run its suite from its own root:

```powershell
Push-Location projects/local-action-model
python -m unittest discover -s tests -v
Pop-Location
```

To score a completed run without confusing a local proxy with an external
benchmark, use `harness-scorecard` (or `python -m experiments.scorecard`). An
`external_native` scorecard requires a hexadecimal suite commit, native metric
and value, native report SHA-256, grader identity, and runner/runtime/platform
metadata.

## Research direction

The central hypothesis is that compact policy specialization becomes more
useful when training and promotion are driven by independently verified
outcomes rather than plausible prose or unverified tool claims. The research
materials cover Action IR specialization, verifier-backed post-training,
failure-family analysis, replayable evidence, and current external benchmark
bar-setting. Start with `docs/RESEARCH_LANDSCAPE_2026-07-29.md` and the
preregistered `docs/RESEARCH_BREAKTHROUGH_PROTOCOL_2026-07-29.md`.

## Public boundary

This repository contains source, synthetic fixtures, documentation, and
reproducibility metadata only. Local checkpoints, model weights, private
traces, generated result dumps, raw training curricula, credentials, and
machine-specific watcher state are intentionally excluded.

Licensed under Apache-2.0. See `LICENSE`, `NOTICE`, and `SECURITY.md`.
