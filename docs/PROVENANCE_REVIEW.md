# Provenance and licensing launch review

Status: engineering inventory complete; commercial/legal sign-off remains open.

This document separates what is known from the local checkout from what must be
reviewed before redistributing model weights, datasets, traces, or a hosted
product. It is an engineering checklist, not legal advice.

## In-scope artifacts

| Artifact | Current evidence | Current boundary |
|---|---|---|
| Open Agent Harness OS source and wheel | `LICENSE`, `NOTICE`, `pyproject.toml`, fresh wheel smoke | Core source is marked Apache-2.0 and has no third-party runtime dependency; confirm bundled notices before redistribution. |
| Open Local Action Model source | `local-action-model/LICENSE`, `pyproject.toml` | Source is marked Apache-2.0; optional ML dependencies remain separate third-party works. |
| Bootstrap and remediation datasets | `local-action-model/docs/DATA_PROVENANCE.md`, fixture JSONL provenance fields | Synthetic deterministic-oracle data; suitable for plumbing and controlled experiments, not evidence of human preference or independent generalization. |
| Qwen/Qwopus checkpoints | `docs/QWOPUS35_REFERENCE.md`, local manifests, upstream model cards | Base model, derivative checkpoint, tokenizer, training traces, and redistribution rights require separate review. |
| Optional runtime dependencies | `pyproject.toml` optional extras | PyTorch, Transformers, PEFT, TRL, and datasets licenses/notices must be inventoried for the chosen distribution. |
| External benchmark environments | `docs/EXTERNAL_BAR_UPDATE_2026-07-26.md` and benchmark manifests | Keep benchmark code/data under each upstream license; do not package external evaluation assets into the product wheel without review. |

## Required sign-off before a public or commercial launch

1. Record the exact base-model revision, derivative revision, tokenizer, and
   quantization/export form.
2. Verify the upstream model and dataset licenses permit the intended use and
   redistribution; retain copies of the applicable model cards and notices.
3. Inventory every training source and transformation, including synthetic
   oracle traces, distilled traces, human data, and benchmark-derived data.
4. Generate a third-party notice bundle for the shipped wheel/container and
   document which optional dependencies are installed.
5. Decide whether the first release ships source only, harness-only, adapter
   weights, merged weights, or a hosted endpoint; each has a different review
   boundary.
6. Have a human owner approve the final commercial-use and data-provenance
   record before publishing weights or accepting customer data.

## Claims permitted before sign-off

- The harness source is presented as Apache-2.0 in the local package metadata.
- The current training fixtures are explicitly synthetic and provenance-tagged.
- The Qwopus branch is an internal evaluation candidate, not a cleared
  redistribution package.

Do not claim that the model stack is commercially redistributable, that every
training source is cleared, or that benchmark assets can ship with the product
until the sign-off record exists.

## Upstream Qwopus review — 2026-07-27

The [Qwopus3.5-9B-v3 model page](https://huggingface.co/Jackrong/Qwopus3.5-9B-v3)
currently exposes an Apache-2.0 license label and identifies a Qwen3.5-9B
lineage. Its model card also describes the checkpoint as a test version for
academic research and technical exploration, and describes the training data
only at a high level as a mixture of open-source Hugging Face sources. That
metadata is useful provenance, but it is not a complete commercial clearance
record for the weights, source datasets, distilled traces, or derivatives.

The linked [Jackrong fine-tuning guide](https://github.com/R6410418/Jackrong-llm-finetuning-guide)
is itself displayed as Apache-2.0, but repository licensing does not establish
that every dataset, upstream Qwen material, generated trace, or published
checkpoint form is redistributable under the same terms.

Decision: keep the Qwopus branch internal and evaluation-only until a human
owner records upstream model permission, dataset/source provenance, tokenizer
and dependency notices, and the intended adapter/merged-weight distribution
boundary. Public wording may describe an internal research checkpoint and
developer-preview experiment; it must not promise commercial model-weight
redistribution yet.
