# Public Release Checklist

Status: 0.1.8 developer-preview release candidate with version-aware readiness evidence, 2026-08-01

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 95/95 passing, including
  dense-reliability and claim-safe scorecard checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v5: 15/15 checks passing, including extracted-wheel install
  smoke and the companion suite; the historical artifact records an 83-test
  source suite, while the current suite has 95 tests.
- Wheel build: `open_agent_harness_os-0.1.8-py3-none-any.whl` (no Python
  bytecode caches; 72 archive entries).
- Wheel SHA-256: `c6995127e0e6da0f6e4f112b440b2c5b21be7aff625b180d28e2289d597cd2ff`.
- Source distribution: `open_agent_harness_os-0.1.8.tar.gz` (no Python
  bytecode caches; 103 archive entries).
- Source distribution SHA-256: `8a607d8b5ae08b5936c7e7fdf6b399915afbc89f31ce55a2328f2a215f59918b`.
- Public package audit: no credentials, model weights, generated result directories, or private local traces included.

## Interpretation boundary

The Qwopus3.5-9B evaluation work is preserved as research context and failure
evidence. The completed local summary records 483/552 independently verified
successes, zero unsafe attempts, and a rejected promotion gate; it is not a
general capability result. Any next model-training claim requires a fresh,
blinded holdout evaluation with the documented gates.

## Before a production launch

- Re-run the complete suite on a clean machine and record environment versions.
- Run the external-agent and industry-proxy benchmark plans with independently held-out tasks.
- Publish checkpoint provenance, dataset licenses, and reproducible commands for any released model artifact.
- Require the promotion decision and verified-RL gates to pass before advertising a model as production-ready.
