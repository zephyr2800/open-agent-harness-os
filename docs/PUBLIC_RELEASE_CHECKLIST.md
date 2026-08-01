# Public Release Checklist

Status: 0.1.8 developer-preview release candidate with version-aware readiness evidence, 2026-08-01

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 114/114 passing, including
  dense-reliability, source-bound wheel integrity, claim-safe scorecard, and
  matched-budget-control checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v6: 16/16 checks passing, including a fresh
  clean-source wheel build, extracted-wheel install smoke, bytecode
  exclusion, complete archive-manifest, package-digest, and console-script
  binding to a fresh reference wheel, and the companion suite; the historical
  v5 artifact records an 83-test source suite,
  while v6 records 114.
- Wheel build: `open_agent_harness_os-0.1.8-py3-none-any.whl` (no Python
  bytecode caches; 74 archive entries; source/package fingerprint
  `575dcdf63a6d5f583fa167a374078e0cab618393e16b57c6fff70dec1cae9480`).
- Paired clean-wheel candidate SHA-256 (recorded in
  `experiments/results/clean-wheel-smoke-v5.json`):
  `ce82e914bec3f07cb4b776e342db48a93a820e7a2f124a2f215df4ec3be15b78`.
- Wheel archive-manifest SHA-256 (identical across the paired clean builds):
  `84e426643575b4562ebc12db00df3150e6e43f5b2808dd2a75728bb50ebc96c7`.
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
