# Evaluation-surface audit

`experiments.evaluation_surface_audit` is a content-free check of what a task
specification structurally asks a policy to do. It reports action horizon,
available versus reference-contract tool types, tool-output visibility,
evidence/state exposure, task families, difficulty labels, and legacy
single-action contract use.

It does not run a model, inspect task text or state values, change any frozen
fixture, or participate in the promotion decision. Its purpose is to prevent a
high local score from being mistaken for evidence that the task surface itself
is broad, long-horizon, or externally realistic.

## Active v2 snapshot

The tracked [`evaluation-surface-audit-v1.json`](../experiments/results/evaluation-surface-audit-v1.json)
binds the three fixtures in promotion protocol `v2` by SHA-256:

- `task-spec-research-v4.json` (120 tasks);
- `task-spec-industry-proxy-v2.json` (16 tasks); and
- `task-spec-author-holdout-v1.json` (24 tasks).

The snapshot makes two constraints explicit:

- every local `finish` task exposes only tool types already present in its
  reference contract; and
- no `finish` contract requires more than three actions.

The author holdout is still useful: it adds 24 post-freeze, adversarial,
tool-output-grounded two- and three-action tasks. It strengthens local
evidence-to-action and stateful-workflow regression testing. It does **not**
turn the local suite into a broad agent benchmark.

The older research fixture also contains 80 legacy single-action contracts.
Their required tool call is represented by `expected_tool`, rather than an
`expected_actions` sequence. The audit reports both the explicit trajectory
length and the minimum contract action count so diagnostics do not confuse
those legacy contracts with zero-action abstentions.

## Use

```powershell
python -m experiments.evaluation_surface_audit `
  --task-spec benchmarks\fixtures\task-spec-research-v4.json `
  --source-label benchmarks/fixtures/task-spec-research-v4.json `
  --task-spec benchmarks\fixtures\task-spec-industry-proxy-v2.json `
  --source-label benchmarks/fixtures/task-spec-industry-proxy-v2.json `
  --task-spec benchmarks\fixtures\task-spec-author-holdout-v1.json `
  --source-label benchmarks/fixtures/task-spec-author-holdout-v1.json `
  --output experiments\results\evaluation-surface-audit-v1.json
```

Interpret the output only as a structural complexity floor. It cannot measure
semantic difficulty, data contamination beyond the separate isolation audits,
model capability, real-world environment fidelity, security robustness, or
native-benchmark performance. Those gaps are why the native AgentDojo/tau2
diagnostics and subsequent external benchmark tracks remain required after a
local promotion decision.
