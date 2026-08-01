# External evaluation runbook

This runbook is the handoff from local proxy evidence to native external
benchmark evidence. It is intentionally conservative about what counts as a
result.

## Before the run

Record, in a versioned run manifest:

- benchmark name, release/version, repository commit, and license;
- environment image or setup-script revision;
- model identifier and immutable checkpoint/tokenizer revisions;
- harness name, commit, configuration, prompt/template revision, and tool
  schema;
- decoding seed, sampling settings, step/token/time budgets, and retry policy;
- native task count, grader version, and native metric definition;
- wall-clock time, output/input tokens when available, peak device memory, and
  cost estimate;
- whether the environment contains untrusted content or consequential tools.

Use an isolated VM/container for any benchmark that executes third-party code
or touches a browser, terminal, API, or filesystem. Do not run the public
repository's deterministic in-memory proxy and label it as the external suite.

## AgentDojo track

Use the [official AgentDojo repository](https://github.com/ethz-spylab/agentdojo)
and its pinned benchmark version. Start with a clean user-task/injection pair
and then expand to a preregistered subset. Preserve the benchmark's native
utility and security metrics, the attack name, user task, injection task,
defense configuration, and full environment commit.

The public repository now supplies a dependency-free, loopback-only OpenAI
bridge at `experiments/agentdojo_adapter_server.py`. It does **not** bundle or
replace AgentDojo: install the official benchmark in an isolated environment
under its own pinned revision, then configure its OpenAI client to use
`http://127.0.0.1:8089/v1`. Start each ablation with an explicit configuration
and a distinct log path:

```powershell
# Model-only baseline: no repair and no evidence-first intervention.
python -m experiments.agentdojo_adapter_server `
  --model-checkpoint <immutable-merged-checkpoint> `
  --log work\external\agentdojo-model-only.jsonl `
  --harness-variant H3-agentdojo-model-only

# Registered-schema repair and evidence-first are separate harness ablations.
python -m experiments.agentdojo_adapter_server `
  --model-checkpoint <immutable-merged-checkpoint> `
  --enable-repair `
  --enable-evidence-first-guard `
  --log work\external\agentdojo-evidence-first.jsonl `
  --harness-variant H3-agentdojo-evidence-first
```

The adapter labels every native tool result as `UNTRUSTED_TOOL_OUTPUT`, keeps
it out of verified harness evidence, retains the native function schema,
records the selected intervention, and binds the local model
checkpoint/revision to each decision record. Keep these local logs out of the
source tree when they contain benchmark data or task content.

Report separately:

- clean utility without injection;
- utility under injection;
- attack success or unsafe-action rate;
- task completion and final-answer grounding;
- harness/replay validity where the bridge exposes it;
- false positives on benign controls.

One repaired task is an ablation, not an AgentDojo average. The bridge must
not silently translate a native tool schema into Action IR and then claim the
native model score for the translated interface.

## TUA-Bench track

Use the [official TUA-Bench site and code](https://tuabench.ai/) with its
deterministic setup scripts and native execution grader. Report the five
families separately, including document/email/web and scientific/engineering
tasks. Preserve the benchmark's native overall metric and per-family metrics;
do not substitute local verified-success terminology.

The first useful experiment is a fixed-model harness comparison: the same
policy and budgets under a thin tool loop, the Open Agent Harness OS control
plane, and verifier-first repair where the benchmark permits it. If a native
grader cannot observe the harness's evidence plane, report it as a harness
ablation and keep the native score primary.

## Scorecard conversion

Convert only after the native run is complete:

```powershell
python -m experiments.scorecard `
  --report work\external\<benchmark>-rows.json `
  --output work\external\<benchmark>-scorecard.json `
  --suite <benchmark-name> `
  --suite-kind external_native `
  --suite-version <version> `
  --suite-commit <commit> `
  --native-metric <native-metric-name> `
  --native-metric-value <native-score> `
  --native-report work\external\<benchmark>-native-report.json `
  --native-grader <grader-id> `
  --native-environment-json '{"runner":"docker","runtime":"python-3.12","platform":"linux-x86_64"}' `
  --model <model-id> `
  --harness <harness-id>
```

The command refuses to create an `external_native` scorecard without a
hexadecimal suite commit, non-empty task rows, numeric native metric value,
SHA-256 of the native report, grader identity, and runner/runtime/platform
metadata. The resulting scorecard is a reporting companion, not a replacement
for the benchmark's grader.

## Publication gate

Publish the native report, scorecard, setup revision, model/checkpoint
provenance, and failed-run accounting together. A result is not a research
breakthrough claim until it also has the preregistered holdout comparison,
multi-seed replication, independent replay where applicable, safety metrics,
and cost/latency tradeoffs described in
`docs/RESEARCH_BREAKTHROUGH_PROTOCOL_2026-07-29.md`.
