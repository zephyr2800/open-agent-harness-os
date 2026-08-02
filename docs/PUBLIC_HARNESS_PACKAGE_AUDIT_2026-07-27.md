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
