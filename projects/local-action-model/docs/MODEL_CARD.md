# Model Card — Qwen2.5-0.5B-Instruct Baseline Candidate

## Status

This is the selected baseline checkpoint configuration for the first local
action-model experiment. A synthetic-fixture SFT checkpoint and a synthetic
mid-training checkpoint now exist in the local work area; they are not
redistribution-ready model releases and no general capability claim is made.

## Provenance

- Model: `Qwen/Qwen2.5-0.5B-Instruct`
- Pinned revision: `7ae557604adf67be50417f59c2c2f167def9a775`
- Reported license: Apache-2.0
- Reported parameter count: approximately 0.49B
- Source model card: <https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct>
- Local configuration: `model/configs/qwen2.5-0.5b-instruct.json`

The revision is pinned in the local configuration so later measurements can
record the exact upstream snapshot. Base-model, adapter, and derived-dataset
licenses must be checked separately before redistribution.

## Intended use

The checkpoint is an inference baseline and starting point for supervised
Action IR specialization on bounded, permissioned local-agent tasks. The
adapter requests one JSON Action IR v0 decision per step and does not allow the
model to execute tools directly.

## Out of scope and limitations

- It is not a general autonomous agent and is not authorized for destructive actions.
- The checked-in core remains dependency-free; the local experiment used a
  separate project-local CUDA 12.8 PyTorch runtime on an RTX 5090.
- The model card's upstream instruction-tuning behavior is not evidence of Action IR competence.
- Latency, memory, energy, tokenization, and safety metrics must be measured on target hardware.
- The current fine-tuning and mid-training fixtures are synthetic oracle data;
  independent teacher/human data provenance, filtering, and licenses are not
  yet established.

## Evaluation plan

The pinned checkpoint and the versioned synthetic-specialized checkpoint have
been run through the fixed task spec and four factorial cells. The runner
records model revisions, device/dtype, input/output tokens, wall time, peak
memory, verifier outcomes, raw outputs, and failure traces. The first smoke
result is in `experiments/results/checkpoint-factorial-v2.{json,md}`; it must be
replaced or supplemented with independently sourced data before a capability
claim.

Clean-environment commands and the CUDA/CPU split are documented in
`docs/REPRODUCIBILITY.md`.
