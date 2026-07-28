# Changelog

## 0.1.0 — 2026-07-25

- Added Action IR v0 structural validator.
- Added canonical JSON digests and replayable trajectory lineage.
- Added deterministic four-task evaluator fixture.
- Added JSONL replay loader and a lineage-checked abstention trajectory fixture.
- Added explicit tool registration, risk gating, and independent verification boundary.
- Added versioned eight-task JSON specification with held-in and held-out splits.
- Added provider-neutral model request parsing and `action-sft/v0` trajectory conversion CLI.
- Corrected packaging metadata to use the standard setuptools backend.
- Added split-aware benchmark CLI and recorded the 8-task reference baseline.
- Added four-cell model × harness factorial runner, config, interaction metric, and fixture-only regression coverage.
- Added pinned Qwen2.5-0.5B-Instruct baseline config, optional Transformers backend, and initial model card.
- Added deterministic in-memory file tools with safe-path and independent state verification.
- Added stateful verified evaluator and retry-operation fixture coverage.
- Fixed evaluator-fixture aliasing and risk metadata after verified tests exposed both issues.
- Added checkpoint sweep CLI with raw-output capture and tokenizer-backed timing/token metrics.
- Recorded the first real negative result: Qwen2.5-0.5B zero-shot produced 0/8 valid Action IR decisions.
- Added deterministic bootstrap SFT generation and data-provenance documentation.
- Added optional Transformers SFT entry point with deterministic dry-run and label masking.
- Verified the pinned tokenizer dry-run over all 8 bootstrap examples.
- Recorded the one-epoch synthetic SFT negative result: 0/8 valid Action IR decisions after training.
- Added primary-source literature and architecture review with experiment mappings.
- Added architecture atlas and living paper draft with preliminary negative results.
- Added synthetic preference-pair and hard-negative generation with explicit rejection reasons.
- Added regression tests and initial research checkpoint documents.
- Added phased execution plan: small action model, then harness OS, then
  integrated factorial optimization.
- Added RTX 5090 Phase 1 run config with fixed-time search/train/RL lanes,
  promotion gates, and required hardware/reproducibility manifest fields.
- Recorded Karpathy nanochat/autoresearch, Hugging Face TRL/PEFT, dataset
  streaming, and Parameter Golf as implementation references.
- Installed a separate project-local CUDA 12.8 PyTorch runtime for the RTX
  5090 and recorded the first GPU-backed zero-shot checkpoint sweep.
- Added the 5090 zero-shot negative result with raw task outputs and hardware
  timing in `experiments/results/`.
- Ran the first RTX 5090 synthetic SFT fixture cycle: 8/8 protocol-valid,
  6/8 verified success overall, 4/6 held-out, with training/evaluation
  manifests and an explicit synthetic-only warning.
- Added a real checkpoint-backed four-cell factorial runner with raw output,
  stateful verification, timing, VRAM, and interaction reporting.
- Fixed the verified evaluator to score expected-kind mismatches as structured
  failures instead of aborting with a `KeyError`; added regression coverage.
- Recorded the corrected real checkpoint factorial: all four cells completed,
  39 tests pass, and the preliminary interaction is -0.500 with explicit
  synthetic-data and smoke-suite limitations.
- Hardened Action IR enum validation against unhashable model values after a
  mid-training checkpoint exposed a `TypeError` on object-valued risk.
- Added and ran the synthetic `action-midtrain/v0` generator/trainer path,
  recorded its negative 5090 result, and added the optional TRL + PEFT DPO/LoRA
  post-training path with a validated dry-run.
- Added verifier-backed RL reward shaping and an 8-pair synthetic reward
  calibration smoke result; explicitly deferred online RL until independent
  trajectories and reward-hacking tests exist.
- Added a clean-environment reproducibility runbook covering core checks,
  CUDA/RTX 5090 setup, staged training, and the real four-cell factorial.
- Re-ran the real factorial as v2 with task-spec SHA-256 and runtime/device
  metadata in the recorded JSON result.
- Completed the Project 1 prototype closure audit: 42 tests pass, core and
  held-out checks pass, staged dry-runs pass, and the real four-cell v2 result
  is reproducibly recorded with explicit limitations.
