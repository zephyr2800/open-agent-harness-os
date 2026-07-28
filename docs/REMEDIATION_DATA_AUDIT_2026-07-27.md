# Remediation data audit — 2026-07-27

Status: schema and holdout-overlap audit passed; data are synthetic training
fixtures, not evidence of capability improvement.

The audit checked the queued SFT curricula against the frozen
`research-v4`, `industry-proxy-v1`, `industry-proxy-v2`, and
`exact-payload-holdout-v1` task identifiers.

| Curriculum | Rows | Unique task IDs | Schema errors | Frozen-ID overlap |
|---|---:|---:|---:|---:|
| `action-finish-convergence-v1.jsonl` | 336 | 336 | 0 | 0 |
| `action-exact-payload-fidelity-v1.jsonl` | 120 | 60 | 0 | 0 |
| `action-policy-sequence-recovery-v1.jsonl` | 80 | 80 | 0 | 0 |
| `action-qwopus35-9b-remediation-v2.jsonl` | 536 | 476 | 0 | 0 |

Every row uses schema `action-sft/v0` and contains the expected `input`,
`target`, and `task_id` fields. The lower unique-ID count in the exact-payload
and combined files is intentional: some provenance strata contribute multiple
examples for the same synthetic task identifier.

This audit establishes data-contract validity and disjoint identifiers only.
It does not establish independent authorship, task difficulty, causal reward
quality, or post-training improvement. The frozen evaluator and holdout remain
the authority for those claims.

## Live curriculum re-check — 2026-07-27 18:09 ET

The queued combined curriculum was re-parsed before post-training:

- 536 rows total: 412 `finish` targets and 124 `act` targets.
- 536 unique `(task_id, target.step_id)` pairs; zero duplicate trajectory-step
  examples.
- 0 schema errors, 0 non-synthetic rows, and 0 rows missing the declared
  frozen-holdout exclusion list.
- Source mix remains 336 finish-convergence, 120 exact-payload, and 80
  policy-sequence rows.

The 476 unique trajectory IDs are therefore not a contamination finding: the
exact-payload curriculum intentionally contributes multiple supervised steps
for some trajectories. This is a data-integrity check only; it does not prove
that the curriculum will improve held-out capability.
