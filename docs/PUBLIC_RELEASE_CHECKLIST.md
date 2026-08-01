# Public Release Checklist

Status: 0.1.7 developer-preview release candidate with clean package artifacts, 2026-08-01

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 81/81 passing, including
  dense-reliability and claim-safe scorecard checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v4: 15/15 checks passing, including extracted-wheel install
  smoke and the companion suite; the artifact records the current 81-test
  source suite.
- Wheel build: `open_agent_harness_os-0.1.7-py3-none-any.whl` (no Python
  bytecode caches; 72 archive entries).
- Wheel SHA-256: `a0788a4cbc8186d6050ed897c59550bbe743ee903fbcc573cda4a11e6e4b3b21`.
- Source distribution: `open_agent_harness_os-0.1.7.tar.gz` (no Python
  bytecode caches; 103 archive entries).
- Source distribution SHA-256: `b89cbb39fd5a34c15ca8339505c132bbd58059a1242a1e49d2523566ff927421`.
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
