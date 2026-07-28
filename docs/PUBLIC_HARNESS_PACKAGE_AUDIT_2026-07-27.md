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
