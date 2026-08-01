# Train/holdout integrity

## Rule

A result is not held-out evidence merely because its evaluator is frozen. The
training corpus must be auditable against every fixture used for scoring.

`experiments.data_split_audit` fails closed when a training row contains a
frozen task ID, prompt, expected action argument, expected file, API endpoint
or response marker, browser page marker, or expected answer marker. This
conservative lexical check is a minimum bar, not a substitute for independent
external evaluation.

## Required candidate artifacts

- Immutable training-mixture manifest with source paths, row counts, and SHA-256 values.
- Passing `train-holdout-audit/v1` manifest for all frozen fixtures.
- Checkpoint training manifest, merge manifest, greedy evaluation, stochastic
  decoding audit, and independent replay.

## Current interpretation

The legacy rank-64 9B training manifest does not identify its source corpus,
so its frozen matrix is context-only. A later targeted curriculum failed the
audit because its rows preserved frozen proxy contracts after partial renaming.
That run remains useful for failure diagnosis, but no result from it is
eligible for held-out, causal, promotion, or breakthrough claims.

The clean-split 9B candidate begins from the original base model and records
the required corpus and audit artifacts before training.
