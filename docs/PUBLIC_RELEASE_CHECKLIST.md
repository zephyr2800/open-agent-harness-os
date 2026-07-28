# Public Release Checklist

Status: draft public release snapshot, 2026-07-27

This checklist records the evidence attached to the first public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 59/59 passing.
- Local Action Model companion suite: 45/45 passing.
- Launch preflight: 12/12 checks passing.
- Wheel build: `open_agent_harness_os-0.1.0-py3-none-any.whl`.
- Wheel SHA-256: `3ee233610176eb17c19f9bbd8e7578960d6e9aa08071e6443083d5726e935210`.
- Public package audit: no credentials, model weights, generated result directories, or private local traces included.

## Interpretation boundary

The Qwopus3.5-9B evaluation work is preserved as research context and failure evidence. The stopped matrix reached the preserved 508/552 result, but it is not represented as a promotion or general capability result. The next model-training claim requires a fresh, blinded holdout evaluation with the documented gates.

## Before a production launch

- Re-run the complete suite on a clean machine and record environment versions.
- Run the external-agent and industry-proxy benchmark plans with independently held-out tasks.
- Publish checkpoint provenance, dataset licenses, and reproducible commands for any released model artifact.
- Require the promotion decision and verified-RL gates to pass before advertising a model as production-ready.
