# Public Release Checklist

Status: 0.1.4 developer-preview release candidate with research/launch update, 2026-07-29

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 73/73 passing, including
  dense-reliability and claim-safe scorecard checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v4: 15/15 checks passing, including extracted-wheel install
  smoke and the companion suite; the artifact records the current 73-test
  source suite.
- Wheel build: `open_agent_harness_os-0.1.4-py3-none-any.whl`.
- Wheel SHA-256: `65cd1e8561d049b69f20fa89397fb016860704e9f08c910231ce39ddd91e94f8`.
- Source distribution: `open_agent_harness_os-0.1.4.tar.gz`.
- Source distribution SHA-256: `c9da40be06d8e5cf630d9e1f9cfa302b515d6e4695f4492fcb7e52ebc7796537`.
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
