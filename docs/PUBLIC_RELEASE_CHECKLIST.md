# Public Release Checklist

Status: 0.1.8 developer-preview release candidate with version-aware readiness evidence, 2026-08-01

This checklist records the evidence attached to the current public repository snapshot. It is deliberately separate from model-quality claims: the repository is a reproducible harness and research package, not a claim that a checkpoint has been promoted.

## Verified locally

- Open Agent Harness OS unit and integration suite: 107/107 passing, including
  dense-reliability, source-bound wheel integrity, and claim-safe scorecard checks.
- Local Action Model companion suite: 47/47 passing.
- Launch preflight v6: 16/16 checks passing, including a fresh
  source-distribution wheel build, extracted-wheel install smoke, bytecode
  exclusion, complete archive-manifest, package-digest, and console-script
  binding to a fresh reference wheel, and the companion suite; the historical
  v5 artifact records an 83-test source suite,
  while v6 records 107.
- Wheel build: `open_agent_harness_os-0.1.8-py3-none-any.whl` (no Python
  bytecode caches; 74 archive entries; source/package fingerprint
  `5461faa6bc472952029d9cfcfde4682cabafd115160060aa936b687682735948`).
- Wheel SHA-256: `47fb8236bed4e88e2e063aceeabbcd927fddda049b947ef3edfe7c1c0899a57f`.
- Wheel archive-manifest SHA-256: `cc0ab3d8b0db5d76dc3c3e05a6460168701af3fadbf57624f3f21d144c4a5354`.
- Source distribution: `open_agent_harness_os-0.1.8.tar.gz` (no Python
  bytecode caches; 107 archive entries).
- Source distribution SHA-256: `7491a43ff7062b3ba5dc0dac0e49b442887d2acc040e5f1542a86113560c746c`.
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
