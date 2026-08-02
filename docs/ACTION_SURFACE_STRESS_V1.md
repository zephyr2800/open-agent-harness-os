# Action-surface stress v1

`task-spec-action-surface-stress-v1.json` is a 36-task, post-freeze local
diagnostic for a gap the active promotion surface does not measure well:
five-step action selection under a fixed six-step H3 budget.

Each completion task requires this shape:

1. retrieve three pieces of task-specific evidence;
2. derive and write a receipt without prompt-visible payload values; and
3. move it into its required final location.

Every task exposes at least two registered, valid-but-irrelevant tool types.
An unnecessary tool call consumes the only remaining step needed to issue a
finish decision. All tool output is explicitly untrusted data, and every
successful result requires independent trace replay, exact final state, and
evidence-grounded result markers.

This is deliberately **not** part of promotion protocol `v2`, is not an
external benchmark, and does not change the active SFT run, frozen evaluator,
or verifier-backed-RL gate. It complements the existing v2 local safety slices;
it does not replace them.

The tracked [registration artifact](../experiments/results/action-surface-stress-v1-registration.json)
binds the fixture to the frozen clean-9B source without publishing raw task or
corpus content: 0 overlaps across 741 direct-contract markers, and 0/36
high-affinity tasks under the existing normalized-template screen (mean 0.184,
maximum 0.200; thresholds 0.55 per task and 5% per suite). Those are local
isolation checks, not a semantic-novelty or external-capability claim.

## Future data guard

The suite was authored after the current clean SFT corpus froze. Do not add its
tasks, markers, or reference trajectories to any future SFT or RL corpus. The
active promotion audit intentionally remains unchanged while the current run
is live. Before using this diagnostic with a future trained checkpoint, run
the standalone direct and normalized-template audits against that future
corpus and retain their local manifests beside the checkpoint evidence.

## Run after promotion only

Use the same promoted checkpoint for a model-only and repair condition after
the GPU is free. Keep task results and traces in ignored local evidence paths.

```powershell
python -m experiments.project2_checkpoint_run `
  --project1-root <project-1-root> `
  --checkpoint <immutable-merged-checkpoint> `
  --task-spec benchmarks\fixtures\task-spec-action-surface-stress-v1.json `
  --variant H3 --hide-contract-hints --no-repair --quantization 4bit `
  --output work\action-surface-stress-model-only.json

python -m experiments.local_diagnostic_validator `
  --run work\action-surface-stress-model-only.json `
  --task-spec benchmarks\fixtures\task-spec-action-surface-stress-v1.json `
  --output work\action-surface-stress-model-only-validation.json
```

Repeat with repair enabled under the same checkpoint, seed, generation budget,
and quantization. A validator pass proves only that the local result is bound
to the fixture and independently replayable. It cannot support an external or
general-agent capability claim.
