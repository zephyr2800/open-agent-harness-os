# Corpus quality audit

`harness-corpus-audit` produces a `corpus-quality-audit/v1` report for an SFT
JSONL source without copying raw prompts, targets, state, or tool arguments
into the report. It records source hashes, schema-field presence, Action IR and
provenance distributions, exact row/input/target duplication statistics, and
serialized-size distributions.

```powershell
harness-corpus-audit --train-jsonl work/clean-9b-sft-mixture-v3.jsonl `
  --source-label work/clean-9b-sft-mixture-v3.jsonl `
  --expected-sha256 d226a3246cd646ce1b1e7d1350d665749f4a986ec854d4314a885e12702d5ed6 `
  --require-unique-rows --require-unique-inputs `
  --output experiments/results/clean-9b-corpus-quality-audit-v2.json
```

The audit is a data-integrity control, not evidence of model generalization.
A low SFT loss only describes fit to supervised target tokens; promotion still
requires the frozen held-out matrix, independent replay, and safety gates.
