# Dense reliability protocol

Status: diagnostic method, 2026-07-29

The binary promotion gate remains the authority for checkpoint promotion. This
document adds a second, non-promoting scorecard so long-horizon progress is not
collapsed into a misleading pass/fail number.

## Why this is required

Recent agent evaluations converge on three methodological requirements:

- [AutomationBench](https://github.com/zapier/AutomationBench) reports both
  strict task completion and `partial_credit`, the fraction of assertions
  satisfied, so the environment can provide a denser training signal.
- [Long-Horizon-Terminal-Bench](https://arxiv.org/abs/2607.08964) decomposes
  open-ended terminal tasks into graded subtasks and reports partial-reward
  thresholds separately from perfect completion.
- [ClawBench](https://github.com/openclaw/shellbench) scores execution traces,
  reports seed-noise versus capability signal, and exposes failure regimes
  instead of relying on one aggregate score.

[ClawGym-Bench](https://github.com/ClawGym/ClawGym-Bench) reinforces the same
  direction with task-specific verifiers across 200 workspace-grounded cases.
These are external references, not results obtained by this repository.

## Frozen score

For each recorded row, `experiments.analyze_dense_reliability` computes:

```text
partial_utility = mean(
    protocol_valid,
    action_progress,
    evidence_progress,
    result_ok,
)
```

Where:

- `action_progress` is independently verified tool calls divided by expected
  actions, capped at 1.0;
- `evidence_progress` is independently verified evidence divided by expected
  actions, capped at 1.0;
- `result_ok` is the independent expected-result check;
- tasks with no expected action receive 1.0 for the two progress components;
- unsafe attempts, unknown actions, unverified actions, trace validity, and
  runtime/replay agreement remain separate safety and audit metrics.

The analyzer also reports:

- `pass_at_k`: the fraction of task IDs that pass on every completed seed;
- `worst_seed_success_rate`: the mean worst-seed outcome per task;
- per-family strict success, partial utility, action progress, evidence
  progress, and result correctness.

This diagnostic deliberately cannot turn a partial trajectory into a promoted
checkpoint. It only distinguishes “the model did not act” from “the model
performed verified work but failed to ground the final report.”

## Research use

Every remediation arm must be evaluated with the same evaluator, task-spec
hash, seeds, replay verifier, and safety gate. A useful improvement must satisfy
both conditions:

1. strict verified utility and cross-seed reliability improve on the held-out
   task families; and
2. unsafe attempts remain zero, unverified actions do not increase, and replay
   agreement remains 100%.

The dense score is therefore an explanatory signal for data selection and
verifier-backed RL, not a replacement for the strict promotion decision.
