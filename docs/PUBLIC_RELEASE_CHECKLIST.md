# Public Release Checklist

Status: 0.1.8 developer-preview release candidate with version-aware readiness evidence, 2026-08-02

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 184/184 passing, including
  dense-reliability, source-bound wheel integrity, claim-safe scorecard, promotion-protocol, native-evaluation-launcher, and energy-measurement checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v28: 16/16 checks passing, including a fresh
  clean-source wheel build, extracted-wheel install smoke, bytecode
  exclusion, complete archive-manifest, package-digest, and console-script
  binding to a fresh reference wheel, and the companion suite; the historical
  v5 artifact records an 83-test source suite,
  while v6 records 110.
- Wheel build: `open_agent_harness_os-0.1.8-py3-none-any.whl` (no Python
  bytecode caches; 86 archive entries; source/package fingerprint
  `c32e07fa98c97be971bd18f3434a774c08052f0755934a0d82e89be2b3dfeb4e`).
- Clean-source wheel SHA-256 (recorded in the smoke artifact):
  `36bc9d8de1c6e187ea3c22c2dd019c9076158da90f26fe5533e8a81e202fcdec`.
- Source-derived wheel archive-manifest SHA-256:
  `37c96dad5051ccf2c4c83f1d87b0ba7dff0343b93e34ffb02215ecf68376d5a5`.
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
