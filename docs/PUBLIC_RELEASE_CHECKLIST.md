# Public Release Checklist

Status: 0.1.8 developer-preview release candidate with version-aware readiness evidence, 2026-08-01

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 104/104 passing, including
  dense-reliability, source-bound wheel integrity, and claim-safe scorecard checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v6: 16/16 checks passing, including a fresh
  source-distribution wheel build, extracted-wheel install smoke, bytecode
  exclusion, source-to-wheel package-digest and console-script binding, and the
  companion suite; the historical v5 artifact records an 83-test source suite,
  while v6 records 104.
- Wheel build: `open_agent_harness_os-0.1.8-py3-none-any.whl` (no Python
  bytecode caches; 74 archive entries; source/package fingerprint
  `f4cd251a23da998edc454b1ca9634734f68fea5889b0e1df9c33559efbcd3b9a`).
- Wheel SHA-256: `95c657c96b7cf1f3d325b6a177b7791142f2d6513658ea4f84288365bd115c0b`.
- Source distribution: `open_agent_harness_os-0.1.8.tar.gz` (no Python
  bytecode caches; 107 archive entries).
- Source distribution SHA-256: `41dcc508892d84166893578785c99d9b1cd3518448f59415be7d37da93793fb9`.
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
