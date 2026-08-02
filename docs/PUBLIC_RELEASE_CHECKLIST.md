# Public Release Checklist

Status: 0.1.8 developer-preview release candidate with fresh v36 readiness evidence, 2026-08-02

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 214 total (213 passed;
  one Windows symlink-capability skip), including dense-reliability, source-bound
  wheel integrity, claim-safe scorecard, promotion-protocol,
  native-evaluation-launcher, energy-measurement, and action-surface-stress
  checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v36: 16/16 checks passing, including a fresh
  clean-source wheel build, extracted-wheel install smoke, bytecode
  exclusion, complete archive-manifest, package-digest, and console-script
  binding to a fresh reference wheel and the companion suite, plus required
  Apache LICENSE and NOTICE entries in the built wheel.
- Wheel build: `open_agent_harness_os-0.1.8-py3-none-any.whl` (no Python
  bytecode caches; 90 archive entries; source/package fingerprint
  `25df159debdfca52927885bd268bfb0bb5ae94e4738dd5ea62ebefa1878220e3`).
- Clean-source wheel SHA-256 (recorded in the v36 smoke artifact):
  `34c95d0f7742775113ceaa313751e9aca006084d557b53c49fd331be2973b72d`.
- Source-derived wheel archive-manifest SHA-256:
  `7a98cc0b61925943989770f17b80302065367bc9d0d9d8348938d272eefaf3e6`.
- The release gate rebuilds from a clean source copy and records each raw
  wheel hash in its evidence; the archive-manifest hash is the cross-build
  provenance binding.
- The focused HTTP review records and regresses client-selected model routing,
  redirects, connection caps, and per-connection deadlines; it remains a
  developer-preview hardening control, not a production security certification.
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
