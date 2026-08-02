# Train/holdout integrity

## Rule

A result is not held-out evidence merely because its evaluator is frozen. The
training corpus must be auditable against all six pinned fixtures: the three
promotion slices, the exact-payload holdout, and external-bar-lite v1 and v2.

`experiments.data_split_audit` fails closed when a training row contains a
frozen task ID, prompt, expected action argument, expected file, API endpoint
or response marker, browser page marker, or expected answer marker. It also
checks task-specific expected-file/API/browser mapping keys. Strings of three
to seven characters are compared as exact JSON values; one- and two-character
strings are intentionally excluded because they are not reliable contract
signals. This conservative lexical check is a minimum bar, not a substitute
for independent external evaluation.

Direct-marker isolation alone is insufficient: renamed IDs and files can
preserve an easy task template. `experiments.holdout_novelty_audit` therefore
normalizes paths and number-bearing identifiers, then reports the closest
training-goal token-set overlap for each held-out prompt. Its threshold is a
transparent template-affinity screen, not a semantic-novelty proof. A high
affinity result is diagnostic only and cannot support a promotion or RL
authorization claim; neither local audit substitutes for a native external
benchmark.

## Required candidate artifacts

- Immutable training-mixture manifest with source paths, row counts, and SHA-256 values.
- Passing `train-holdout-audit/v1` manifest whose
  `required_fixture_gate.passed` is true for all six pinned fixture hashes.
- Passing `holdout-novelty-audit/v1` manifest, bound to the same training
  source hashes and the three frozen promotion slices.
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

## Mechanical enforcement

`run_promotion_matrix`, `promotion_decision`, and `verified_rl_gate` each
require both audit-manifest paths. They recompute the direct-isolation and
template-affinity report digests, reject a missing, dirty, incomplete, or
unbound report, and require the matrix and decision to link those digests. A
passing standalone audit is therefore necessary but cannot be silently
detached from the evaluation or RL authorization it is meant to support. The
SFT training manifest records the training JSONL hash and row count; merge
copies that manifest into the checkpoint, and the gates reject a checkpoint
whose recorded source fingerprints differ from either audit.
