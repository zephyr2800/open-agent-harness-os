# Public Release Checklist

Status: public release snapshot with research/launch update, 2026-07-29

This checklist records the evidence attached to the first public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 66/66 passing, including
  claim-safe scorecard checks.
- Local Action Model companion suite: 45/45 passing.
- Launch preflight: 15/15 checks passing, including extracted-wheel install
  smoke and the companion suite.
- Wheel build: `open_agent_harness_os-0.1.0-py3-none-any.whl`.
- Wheel SHA-256: `55d7744ab920a56016ae5805991a4c32bf48380183b5d945503a54a79dcbc737`.
- Public package audit: no credentials, model weights, generated result directories, or private local traces included.

## Interpretation boundary

The Qwopus3.5-9B evaluation work is preserved as research context and failure evidence. The stopped matrix reached the preserved 508/552 result, but it is not represented as a promotion or general capability result. The next model-training claim requires a fresh, blinded holdout evaluation with the documented gates.

## Before a production launch

- Re-run the complete suite on a clean machine and record environment versions.
- Run the external-agent and industry-proxy benchmark plans with independently held-out tasks.
- Publish checkpoint provenance, dataset licenses, and reproducible commands for any released model artifact.
- Require the promotion decision and verified-RL gates to pass before advertising a model as production-ready.
