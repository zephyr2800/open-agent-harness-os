# Open Agent Harness OS

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
- The companion local-action-model source under `projects/local-action-model/`

## Current evidence

The local developer-preview harness passes its documented product checks:

- Project 2 tests: 59/59
- Project 1 tests: 45/45
- Launch preflight: 12/12

The associated Qwopus3.5-9B promotion matrix was intentionally stopped at a
preserved 508/552 partial checkpoint. It is not a promotion result, and this
repository does not claim that the model is generally capable or that RL
improved it. See `docs/CLAIMS_AND_EVIDENCE_MATRIX.md` and
`docs/RESEARCH_LAUNCH_BRIEF.md` for the evidence boundaries.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python -m unittest discover -s tests -v
python -m pip wheel . --no-deps --wheel-dir work/package-dist
python -m experiments.launch_preflight --with-tests
```

## Research direction

The central hypothesis is that compact policy specialization becomes more
useful when training and promotion are driven by independently verified
outcomes rather than plausible prose or unverified tool claims. The research
materials cover Action IR specialization, verifier-backed post-training,
failure-family analysis, replayable evidence, and current external benchmark
bar-setting.

## Public boundary

This repository contains source, synthetic fixtures, documentation, and
reproducibility metadata only. Local checkpoints, model weights, private
traces, generated result dumps, raw training curricula, credentials, and
machine-specific watcher state are intentionally excluded.

Licensed under Apache-2.0. See `LICENSE`, `NOTICE`, and `SECURITY.md`.
