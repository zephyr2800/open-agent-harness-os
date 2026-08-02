# Public Release Checklist

Status: 0.1.8 developer-preview release candidate with version-aware readiness evidence, 2026-08-02

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 190/190 passing, including
  dense-reliability, source-bound wheel integrity, claim-safe scorecard, promotion-protocol, native-evaluation-launcher, and energy-measurement checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v31: 16/16 checks passing, including a fresh
  clean-source wheel build, extracted-wheel install smoke, bytecode
  exclusion, complete archive-manifest, package-digest, and console-script
  binding to a fresh reference wheel and the companion suite.
- Wheel build: `open_agent_harness_os-0.1.8-py3-none-any.whl` (no Python
  bytecode caches; 86 archive entries; source/package fingerprint
  `006e024aebd6349d6cb9ad7a903ee5180c2959cce27da51b9ab3bad434fb0f06`).
- Clean-source wheel SHA-256 (recorded in the smoke artifact):
  `13c907876eae2ca321e95643352641532a0ebd326c9f19332246f711a0b6cfd3`.
- Source-derived wheel archive-manifest SHA-256:
  `c28321232c5a6f131b5b1af2ae7bc099f016b6bc0255c50c73e9a4872ca1378d`.
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
