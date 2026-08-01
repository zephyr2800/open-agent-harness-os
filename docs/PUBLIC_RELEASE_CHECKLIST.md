# Public Release Checklist

Status: 0.1.8 developer-preview release candidate with version-aware readiness evidence, 2026-08-01

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 116/116 passing, including
  dense-reliability, source-bound wheel integrity, and claim-safe scorecard checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v6: 16/16 checks passing, including a fresh
  clean-source wheel build, extracted-wheel install smoke, bytecode
  exclusion, complete archive-manifest, package-digest, and console-script
  binding to a fresh reference wheel, and the companion suite; the historical
  v5 artifact records an 83-test source suite,
  while v6 records 116.
- Wheel build: `open_agent_harness_os-0.1.8-py3-none-any.whl` (no Python
  bytecode caches; 75 archive entries; source/package fingerprint
  `7eb9f40f7b97b32abc96d4702c8493a161e191c55f59fe0960fbbbe1c10a127a`).
- Paired clean-wheel candidate SHA-256 (recorded in the smoke artifact):
  `d42d948e576e9688d6845f2951b1152fa335924069a8b6b76c8aa09d5d7d2113`.
- Wheel archive-manifest SHA-256 (identical across the paired clean builds):
  `4c2522a8834b0765d64785ca2cb34aceb8db2e0691d44b71e12c4123dff223f1`.
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
