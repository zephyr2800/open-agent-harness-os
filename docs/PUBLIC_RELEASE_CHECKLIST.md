# Public Release Checklist

Status: 0.1.5 developer-preview release candidate with research/launch update, 2026-08-01

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 74/74 passing, including
  dense-reliability and claim-safe scorecard checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v4: 15/15 checks passing, including extracted-wheel install
  smoke and the companion suite; the artifact records the current 74-test
  source suite.
- Wheel build: `open_agent_harness_os-0.1.5-py3-none-any.whl`.
- Wheel SHA-256: `74ccb97f810142cffd69148e85f38332af4b69d86deb6c8c1ce783167ee08024`.
- Source distribution: `open_agent_harness_os-0.1.5.tar.gz`.
- Source distribution SHA-256: `5cb0540bf2c8889226eb20501b3b7990c3e0496c86d00ec7705f7ca2c5ce26f9`.
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
