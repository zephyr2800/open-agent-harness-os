# Public Release Checklist

Status: 0.1.6 developer-preview release candidate with research/launch update, 2026-08-01

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 81/81 passing, including
  dense-reliability and claim-safe scorecard checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v4: 15/15 checks passing, including extracted-wheel install
  smoke and the companion suite; the artifact records the current 80-test
  source suite.
- Wheel build: `open_agent_harness_os-0.1.6-py3-none-any.whl`.
- Wheel SHA-256: `c9597a2db35821704d90357ecfa2c6109325f30d1d51dc6f816f723e877166de`.
- Source distribution: `open_agent_harness_os-0.1.6.tar.gz`.
- Source distribution SHA-256: `71a178cdf5ce77d9ba1bbb22a36c1361679b937bf9e821a1452cbe2213ba97fa`.
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
