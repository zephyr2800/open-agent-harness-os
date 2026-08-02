# Public harness package audit — 2026-07-27

Status: package-content boundary passed; public product gates remain open.

Audited wheel:

`work/package-dist/open_agent_harness_os-0.1.0-py3-none-any.whl`

- Entries: 108
- Size: 204,582 bytes
- SHA-256: `38e2479e49f1808060256f74a855c641d2165912ef7e5496ad4efac091c268b3`
- Qwopus/model-name entries: 0
- Model-weight extensions (`.safetensors`, `.bin`, `.pt`, `.pth`): 0
- Training-data or fixture entries: 0

The four filename matches from a broad checkpoint/training keyword scan are
generic Python modules (`experiments/project2_checkpoint_run.py`,
`experiments/verify_checkpoint_run.py`, `runtime/checkpoint.py`, and a Python
cache file). They contain harness code, not model parameters or training data.

This supports the proposed public harness-only / bring-your-own-model
distribution boundary. It does not establish public operational readiness,
usability, external-benchmark validity, or licensing clearance for optional
model providers.

## v33 addendum — 2026-08-02

The v0.1.0 audit above is retained as a historical record. The current
public-harness evidence is `experiments/results/launch-preflight-v33.json` and
`experiments/results/clean-wheel-smoke-v33.json`, generated from a fresh clean
source copy:

- wheel: `open_agent_harness_os-0.1.8-py3-none-any.whl`;
- size: 208,672 bytes; 89 archive entries; no Python bytecode entries;
- wheel SHA-256:
  `6eb30aa8bff5ca8d59428a8e0e1bf741c9407d396e0738fb1fc4e0b6bd871041`;
- source/package SHA-256:
  `eb423768a0469fdbbd6b03412194898f7b6de49dd28a01280d454e2c8a09b401`;
- archive-manifest SHA-256:
  `38326a46d3c4ce08156fd17f1395f2fd05fa8f7780e04add7f6e0dba46ecf370`.

The v33 clean-source build excludes `work`, which holds local checkpoints,
adapters, model metadata, raw run outputs, and external benchmark checkouts.
`pyproject.toml` sets `include-package-data = false` and the repository's
ignore rules exclude model-weight extensions, JSONL runtime outputs, secrets,
and generated evaluation evidence by default. The versioned preflight artifact
is an exception because it is a content-free public reproducibility record.

This audit still covers the harness wheel only. A source checkout intentionally
contains small synthetic fixtures for tests and reproducibility; that does not
authorize release of the Qwopus model, its adapter, merged weights, or any
non-synthetic training corpus.

## v34 addendum - 2026-08-02

The v33 addendum remains historical. At this revision, the public-harness evidence was
`experiments/results/launch-preflight-v34.json` and
`experiments/results/clean-wheel-smoke-v34.json`, generated from a fresh clean
source copy:

- wheel: `open_agent_harness_os-0.1.8-py3-none-any.whl`;
- size: 217,078 bytes; 90 archive entries; no Python bytecode entries;
- wheel SHA-256:
  `2d22a1374b615db3afea2adbaec128f8e55bdc92811b0177c43f059001c22055`;
- source/package SHA-256:
  `19b68dfa514840f107f5d60b465e9c10aef27e23ec630cf6a7d8c656054bf7c9`;
- archive-manifest SHA-256:
  `b03a21ee940bd3657ad762b931c63c34793fb6ee7a3aa90fa6eb09521c9cfc55`.

The v34 sidecar links back to its preflight artifact with the repository-
relative path `experiments/results/launch-preflight-v34.json`; the evidence
generator redacts external/local paths so a public sidecar does not expose a
machine username or workspace location.

## v35 addendum - 2026-08-02

The v34 addendum remains historical. At this revision, the public-harness evidence was
`experiments/results/launch-preflight-v35.json` and
`experiments/results/clean-wheel-smoke-v35.json`, generated from a fresh clean
source copy:

- wheel: `open_agent_harness_os-0.1.8-py3-none-any.whl`;
- size: 217,171 bytes; 90 archive entries; no Python bytecode entries;
- wheel SHA-256:
  `36842cc3ac258b28c0d56bf95a74eb6b17842d8adf8d7edc43103b1f0c1b91b5`;
- source/package SHA-256:
  `861213308324fd725fa64066fb6ad32be0c1427fea8cf311f5fb07fa3d87d417`;
- archive-manifest SHA-256:
  `c600082ea6f7ad9b9315ab91928d2e8bceb43212a27bf9ec5943644ea8ea4115`.

The v35 wheel-integrity gate additionally verifies that the built archive
contains its Apache LICENSE and NOTICE entries, rather than relying on source
metadata alone. The public sidecar retains only repository-relative evidence
paths and redacts external/local paths.

## v36 addendum - 2026-08-02

The v35 addendum remains historical. The current public-harness evidence is
`experiments/results/launch-preflight-v36.json` and
`experiments/results/clean-wheel-smoke-v36.json`, generated from a fresh clean
source copy:

- wheel: `open_agent_harness_os-0.1.8-py3-none-any.whl`;
- size: 218,215 bytes; 90 archive entries; no Python bytecode entries;
- wheel SHA-256:
  `34c95d0f7742775113ceaa313751e9aca006084d557b53c49fd331be2973b72d`;
- source/package SHA-256:
  `25df159debdfca52927885bd268bfb0bb5ae94e4738dd5ea62ebefa1878220e3`;
- archive-manifest SHA-256:
  `7a98cc0b61925943989770f17b80302065367bc9d0d9d8348938d272eefaf3e6`.

The v36 artifact validates the public package after the focused HTTP boundary
hardening and requires its associated security-review record as a release
document. It retains the v35 legal-notice checks and repository-relative,
redacted public evidence paths.
