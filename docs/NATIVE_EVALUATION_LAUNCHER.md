# Native AgentDojo evaluation launcher

`experiments.agentdojo_native_launcher` is the checkpoint-bound handoff from
the local v2 promotion protocol to a native AgentDojo run. It does not
translate AgentDojo tools into local Action IR or manufacture a local score:
AgentDojo remains the runner and source of utility/security metrics.

The command is dry-run by default. It verifies the clean train/holdout audit,
the merged checkpoint's source binding, the AgentDojo checkout, exact command
lines, adapter source hash, executable Project 1 and harness source-tree
fingerprints, model-weight hash, and task selectors against the pinned suite's
own selector catalog; then writes `run_manifest.json`. Add
`--execute` only after the active SFT job has
finished and no other process owns the GPU.

An executed native run additionally requires a checked-in preregistration. The
current clean-9B protocol is
`benchmarks/fixtures/native-external-registration-v1.json`; see
[`NATIVE_EVALUATION_REGISTRATION_2026-08-01.md`](NATIVE_EVALUATION_REGISTRATION_2026-08-01.md).

```powershell
# Run this block from the repository root, using the Python environment with
# the pinned native-evaluation dependencies installed.
$py = (Get-Command python -ErrorAction Stop).Source
$root = (Get-Location).Path
& $py -m experiments.agentdojo_native_launcher `
  --checkpoint <merged-clean-9b-checkpoint> `
  --train-holdout-audit <clean-seven-fixture-audit.json> `
  --project1-root (Join-Path $root 'outputs\local-action-model') `
  --agentdojo-root (Join-Path $root 'work\external\agentdojo') `
  --agentdojo-runtime (Join-Path $root 'work\external\agentdojo-runtime') `
  --run-dir (Join-Path $root 'work\external\agentdojo-clean-9b-model-only') `
  --registration benchmarks/fixtures/native-external-registration-v1.json `
  --variant model-only `
  --user-task user_task_17
```

For an injection evaluation, declare the exact user task, injection task, and
native attack together. The launcher refuses an implicit all-injection run:

```powershell
  --user-task user_task_17 `
  --injection-task injection_task_3 `
  --attack direct
```

Repeat the same frozen selectors and budgets with `--variant repair` for the
registered repair ablation. Do not compare a wider task set, a different
checkpoint, or changed token budget to the model-only condition.

## Deliberate current boundary

The launcher supports only `model-only` and `repair`. The repository's
lookup-first adapter guard requires a task-bound
`metadata.adapter_task_instance_id`; the pinned AgentDojo OpenAI-compatible
client does not emit it. Running that guard anyway would make acknowledgement
semantics differ by client behavior, so it is not a fair native ablation. Add
a separately reviewed, task-bound client wrapper before registering that
condition.

The result remains a native external evaluation only after `--execute` has
completed, AgentDojo's own logs are present, and the native utility/security
metrics are reported alongside this run manifest. The launcher records a hash
and byte count for every native JSON log and its adapter log at completion.
Validate those records before reporting a result:

```powershell
& $py -m experiments.agentdojo_native_result_validator `
  --run-manifest <completed-native-run\run_manifest.json> `
  --output <new-agentdojo-validation.json>
```

The validator accepts the registered clean condition and the registered
`direct`-injection condition. It rejects missing, extra, modified, source-
rebound, or errored task logs, and keeps injection-task utility controls
separate from the user-task utility/security pairs. A successful dry plan is
readiness evidence, not a benchmark result.
