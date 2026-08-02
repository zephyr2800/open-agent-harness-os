# Public Release Checklist

Status: 0.1.8 developer-preview release candidate with fresh v34 readiness evidence, 2026-08-02

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 210 total (209 passed;
  one Windows symlink-capability skip), including dense-reliability, source-bound
  wheel integrity, claim-safe scorecard, promotion-protocol,
  native-evaluation-launcher, energy-measurement, and action-surface-stress
  checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v34: 16/16 checks passing, including a fresh
  clean-source wheel build, extracted-wheel install smoke, bytecode
  exclusion, complete archive-manifest, package-digest, and console-script
  binding to a fresh reference wheel and the companion suite.
- Wheel build: `open_agent_harness_os-0.1.8-py3-none-any.whl` (no Python
  bytecode caches; 90 archive entries; source/package fingerprint
  `19b68dfa514840f107f5d60b465e9c10aef27e23ec630cf6a7d8c656054bf7c9`).
- Clean-source wheel SHA-256 (recorded in the v34 smoke artifact):
  `2d22a1374b615db3afea2adbaec128f8e55bdc92811b0177c43f059001c22055`.
- Source-derived wheel archive-manifest SHA-256:
  `b03a21ee940bd3657ad762b931c63c34793fb6ee7a3aa90fa6eb09521c9cfc55`.
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
