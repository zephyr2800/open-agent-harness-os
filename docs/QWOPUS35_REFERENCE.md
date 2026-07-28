# Qwopus3.5-9B-v3: external reference and integration plan

Date: 2026-07-26

## Sources reviewed

- [Qwopus3.5-9B-v3 model card](https://huggingface.co/Jackrong/Qwopus3.5-9B-v3)
- [Jackrong fine-tuning guide repository](https://github.com/R6410418/Jackrong-llm-finetuning-guide)
- [Qwopus3.5-27B PDF guide](https://github.com/R6410418/Jackrong-llm-finetuning-guide/blob/main/guidePDF/Qwopus3-5-27b-Colab_complete_guide_to_llm_finetuning.pdf)
- [Qwen3.5-9B base model](https://huggingface.co/Qwen/Qwen3.5-9B)
- [Qwopus3.5 model collection](https://huggingface.co/collections/Jackrong/qwopus35-v35-v3)
- [Qwopus3.5-9B-v3 GGUF release](https://huggingface.co/Jackrong/Qwopus3.5-9B-v3-GGUF)

The PDF was downloaded locally to `work/external/Qwopus3-5-27b-Colab_complete_guide_to_llm_finetuning.pdf` and inspected with text extraction plus rendered-page review. The repository was cloned with Git LFS smudging disabled because the upstream LFS budget prevented a normal shallow checkout.

## What the reference actually establishes

The 9B model card describes a Qwen3.5-9B derivative using SFT plus LoRA and response-only masking at the assistant reasoning span. It presents an execution-driven “act-then-refine” motivation and reports self-published HumanEval and MMLU-Pro results. Those scores are useful hypotheses, not project evidence: they use a different model family, evaluator, prompt/template, and task distribution from our harness.

The linked PDF is primarily an SFT engineering guide for Qwopus3.5-27B, not a proof of an RL-trained Qwopus3.5-9B checkpoint. Its reproducible ideas are:

1. Normalize heterogeneous conversations into one schema before templating.
2. Validate role order, non-empty assistant targets, template serialization, and length limits.
3. Train on assistant responses only; do not spend the loss budget reproducing user/system tokens.
4. Sweep low-rank capacity, learning rate, sequence length, and effective batch size under a fixed seed.
5. Keep adapter checkpoints, merged BF16/16-bit exports, and GGUF exports as separate artifacts.
6. Inspect labels before training and compare runs under the same evaluation variables.

The 9B Kaggle notebook adds fixed-seed sampling, deduplication after mixing, length filtering, format QA, and a Qwen thinking template. The separate GRPO notebook uses SFT cold-start first, then grouped rollouts with structural, correctness, and anti-repetition rewards. Its rewards are math-specific and must not be copied into the action model unchanged.

## How this changes our two-project design

### Project 1: Open Local Action Model

Add a controlled 9B comparison branch:

`Qwen3.5-9B -> Qwopus3.5-9B-v3 -> Action IR response-only SFT -> verifier-backed preference/RL`

The Qwen2.5-7B v6 candidate remains the current controlled baseline because it has the strongest end-to-end evidence on our hidden-contract and native-tool slices. The Qwopus branch must use the same prompts, hidden hints, tool schemas, seeds, and independent replay evaluator; otherwise a larger score is not interpretable.

The target is not to train hidden chain-of-thought. We will supervise compact, auditable Action IR and evidence-grounded final results. If the Qwopus scaffold produces internal reasoning, it is an inference behavior to measure, not a security or correctness proof.

### Project 2: Open Agent Harness OS

Implement the “act-then-refine” idea at the harness boundary:

`model proposes -> allowlisted executor acts -> verifier records evidence/error -> model repairs or continues -> bounded replay`

The harness, rather than an untrusted model claim, decides whether an action executed, whether evidence is valid, and whether a retry is allowed. A useful RL reward vector is:

- valid Action IR and exact registered schema;
- correct state-dependent tool ordering;
- evidence-grounded consequence completion;
- independent verifier agreement;
- no prompt-injection compliance or unsafe action;
- useful recovery after an explicit tool failure;
- bounded cost/latency and no repetitive retry loop.

This is the direct translation of Qwopus’s execution-feedback thesis into our safety model. The current neutral QLoRA REINFORCE smoke run is not promoted; a larger reward-driven run only starts after the native-tool and failure-recovery dataset is expanded.

## 5090 deployment implications

The full Qwopus checkpoint is about 19.3 GB across four BF16 shards, so it is plausible for inference on the 32 GB RTX 5090 but leaves less headroom than the current 7B model. A 4-bit QLoRA adapter is the intended training mode. GGUF variants are for inference/packaging, not for training. The local metadata/tokenizer load successfully under the current Transformers runtime; full-weight loading and adapter attachment remain a separate compatibility gate because Qwen3.5 is a hybrid vision/text architecture.

Compatibility has now been partially validated: the local four-shard checkpoint loads in BF16 at about 17.1 GiB, and a real 4-bit QLoRA smoke completed four optimizer steps at about 17.8 GiB peak VRAM. The base model does not emit Action IR zero-shot; its default template produces visible reasoning and natural-language output. The branch therefore requires response-only Action IR SFT before it can be compared as an action policy. The tokenizer path uses `fix_mistral_regex=True` when supported by the installed Transformers version.

Recommended ablation order:

1. Full-weight Qwopus3.5-9B-v3 inference on the 120-task hidden contract.
2. The same 9B model with Action IR SFT on the native-tool curriculum.
3. A verifier-backed preference/RL run using only externally checkable rewards.
4. Compare 7B v6, Qwopus 9B base, and Qwopus 9B adapted on hidden, proxy, AgentDojo, and recovery slices.

The first targeted v7 7B revision is not promoted: repeating the external-gap rows 5x preserved protocol validity and injection resistance, but reduced the industry policy-sequence family from 12/12 to 3/12 and did not repair the clean AgentDojo task. This is evidence for mixture balance and exact-slot regression tests, not evidence that more targeted examples should simply be repeated.

## Guardrails on claims and licensing

Do not use the model-card HumanEval/MMLU numbers as our project score. Do not call the Qwopus “tool-calling reinforcement” claim independently verified until a public training manifest and a reproducible harness benchmark support it. Before any commercial launch, audit the Qwopus model, upstream base, datasets, distilled traces, and repository dependencies separately; the model card and repository state Apache-2.0, but that does not automatically settle every dataset or provenance obligation.
