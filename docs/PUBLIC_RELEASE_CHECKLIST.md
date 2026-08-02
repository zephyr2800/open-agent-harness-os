# Public Release Checklist

Status: 0.1.8 developer-preview release candidate with fresh v33 readiness evidence, 2026-08-02

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 202 total (201 passed;
  one Windows symlink-capability skip), including dense-reliability, source-bound
  wheel integrity, claim-safe scorecard, promotion-protocol,
  native-evaluation-launcher, energy-measurement, and action-surface-stress
  checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v33: 16/16 checks passing, including a fresh
  clean-source wheel build, extracted-wheel install smoke, bytecode
  exclusion, complete archive-manifest, package-digest, and console-script
  binding to a fresh reference wheel and the companion suite.
- Wheel build: `open_agent_harness_os-0.1.8-py3-none-any.whl` (no Python
  bytecode caches; 89 archive entries; source/package fingerprint
  `eb423768a0469fdbbd6b03412194898f7b6de49dd28a01280d454e2c8a09b401`).
- Clean-source wheel SHA-256 (recorded in the v33 smoke artifact):
  `6eb30aa8bff5ca8d59428a8e0e1bf741c9407d396e0738fb1fc4e0b6bd871041`.
- Source-derived wheel archive-manifest SHA-256:
  `38326a46d3c4ce08156fd17f1395f2fd05fa8f7780e04add7f6e0dba46ecf370`.
- The release gate rebuilds from a clean source copy and records each raw
  wheel hash in its evidence; the archive-manifest hash is the cross-build
  provenance binding.
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
