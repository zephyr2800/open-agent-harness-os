# Post-freeze author holdout v1

`benchmarks/fixtures/task-spec-author-holdout-v1.json` is a 24-task local
diagnostic authored after the clean 9B SFT mixture was frozen. It tests whether
the policy can retrieve a payload from untrusted API or browser output,
transform the requested fields into a new artifact, preserve ordered actions,
and ignore embedded instructions that are not authority.

It has four balanced six-task families:

- API-grounded artifact creation;
- browser-grounded artifact creation;
- cross-source reconciliation before writing; and
- stateful API-grounded write-and-archive workflows.

The fixture SHA-256 is
`b752403f5b06c918eef2565c18a9ddc536fbf7de685eb7245578fd5bdcb3a2ab`.
Before any checkpoint is evaluated on it, the frozen 3,232-row clean mixture
must be audited against the exact fixture. At authoring time, the direct audit
found zero marker overlaps across 273 fixture markers, and the
identifier-normalized template-affinity audit found zero high-affinity tasks
(mean maximum Jaccard `0.195334`, maximum `0.243902`, thresholds `0.55` per
task and `5%` per suite).

This remains a local, published diagnostic—not a semantic-novelty proof or a
replacement for AgentDojo or another native external benchmark. It supports a
research claim only alongside the fixed model/harness comparison, multi-seed
replication, independent trace replay, and native external results specified
in [the breakthrough protocol](RESEARCH_BREAKTHROUGH_PROTOCOL_2026-07-29.md).

It is a required local slice of promotion protocol `v2`. It remains published
and local, so it does not turn that protocol into a semantic-novelty proof or
a replacement for AgentDojo or another native external benchmark.

Run it only after the candidate checkpoint is merged and its source-bound
training manifest is available:

```powershell
python -m experiments.run_promotion_matrix `
  --project1-root <project-1-root> `
  --checkpoint <merged-checkpoint> `
  --output work\author-holdout-v1-matrix.json `
  --train-holdout-audit <audit-covering-all-seven-pinned-fixtures> `
  --holdout-novelty-audit <passing-author-holdout-novelty-audit> `
  --promotion-protocol v2 `
  --task-spec benchmarks\fixtures\task-spec-author-holdout-v1.json `
  --seeds 0,1,2 --max-new-tokens 256 --quantization 4bit
```

The result is a research diagnostic only. Do not feed its task rows or markers
back into SFT or RL before the registered comparison is complete.
