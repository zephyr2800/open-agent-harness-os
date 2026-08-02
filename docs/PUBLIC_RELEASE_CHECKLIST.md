# Public Release Checklist

Status: 0.1.8 developer-preview release candidate with version-aware readiness evidence, 2026-08-01

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 164/164 passing, including
  dense-reliability, source-bound wheel integrity, claim-safe scorecard, promotion-protocol, and native-evaluation-launcher checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v17: 16/16 checks passing, including a fresh
  clean-source wheel build, extracted-wheel install smoke, bytecode
  exclusion, complete archive-manifest, package-digest, and console-script
  binding to a fresh reference wheel, and the companion suite; the historical
  v5 artifact records an 83-test source suite,
  while v6 records 110.
- Wheel build: `open_agent_harness_os-0.1.8-py3-none-any.whl` (no Python
  bytecode caches; 83 archive entries; source/package fingerprint
  `17269b9c99e16b2cb77bf58aebeefb00cd1c637ea5c0e78a5ec110e51c349121`).
- Clean-source wheel SHA-256 (recorded in the smoke artifact):
  `1214f06ae5b8be413e2f2d8b1775288b6b2c4743c214c8c51fab21194e54afc1`.
- Source-derived wheel archive-manifest SHA-256:
  `49c17ada85a104786bdfc92acf62ec46d3668949a7bf512b9e91bdeba301d3db`.
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
