# Native τ³-bench evaluation launcher

`experiments/tau2_native_launcher.py` plans or executes a checkpoint-bound native τ³-bench (`tau2`) evaluation. It preserves τ³-bench's own runner, native task execution, and grader; the harness contributes only a loopback OpenAI-compatible policy bridge.

The registered local-only condition is intentionally narrow:

- τ³-bench `telecom` task set, `base` split;
- official `llm_agent_solo` with official `dummy_user`;
- an explicit, non-empty list of task IDs; and
- a local `openai/local-action-policy` endpoint, no external user-simulator model.

This is a native solo-condition result, not an interactive τ³-bench user-simulator result. It must be reported with that condition intact.

## Integrity rules

The launcher rejects a run unless all of these are true:

- The checkpoint is a merged v2 checkpoint cryptographically bound to a passed clean train/holdout audit.
- The official τ³-bench checkout is clean, its commit is recorded, and the selected Python runtime imports `tau2` from that checkout.
- Requested task IDs exist in the pinned `telecom/base` catalog and are valid for τ³-bench solo mode.
- The local run directory and τ³-bench output directory are both new, so the benchmark cannot resume or mix an earlier score.
- The model is deterministic (`temperature=0`), uses one local worker, has explicit step/error/token limits, and disables benchmark retries.
- The adapter has a unique loopback port, a health check, and is stopped only if this launcher started it.

Every plan records the selector-catalog hash, checkpoint and source hashes, τ³-bench commit/runtime details, commands, environment, and the exact adapter variant. Execution writes the official output to τ³-bench's native result directory and copies that tree into the immutable run directory alongside adapter and benchmark logs.

## Dry-plan example

Run this only after a clean merged checkpoint exists. Omit `--execute` to validate every invariant without loading the model.

```powershell
python -m experiments.tau2_native_launcher `
  --checkpoint C:\path\to\merged-checkpoint `
  --train-holdout-audit C:\path\to\train-holdout-audit.json `
  --project1-root C:\path\to\local-action-model `
  --tau2-root C:\path\to\tau2-bench `
  --tau2-runtime C:\path\to\tau2-runtime `
  --python C:\path\to\tau2-runtime\Scripts\python.exe `
  --run-dir C:\path\to\new-native-run `
  --task-id "[mobile_data_issue]airplane_mode_on|user_abroad_roaming_enabled_off[PERSONA:None]"
```

Use `--execute` only for the registered run. For evidence, retain `run_manifest.json`, `tau2-native-results`, `adapter.jsonl`, and both process logs. Do not describe a dry plan as a score.

## Promotion use

Use the same task list, seeds, limits, and checkpoint binding for every compared variant. Run `model-only` before `repair`; repair is a harness ablation, not a model-only result. A τ³-bench result complements the AgentDojo path but does not substitute for it or for the frozen local promotion matrix.
