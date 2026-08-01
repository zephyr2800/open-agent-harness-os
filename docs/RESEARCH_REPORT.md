# Research report: paired Action IR model and harness

## Executive result

The current evidence does not support a research-breakthrough claim. The
controlled fixture retains a positive H3/H4 interaction after adding renamed
tools, deterministic API/browser boundaries, and a long-horizon artifact, but
the real pinned Qwen 0.5B checkpoint produced zero valid Action IR decisions
under both H1 and H3 across three greedy decoding seeds.

The practical result is stronger: the harness now has a safe developer-preview
product surface with local CLI/API execution, independent verification,
authority gates, and replayable traces.

## Protocol

The research fixture is frozen at
`benchmarks/fixtures/task-spec-research-v1.json`. It contains 11 tasks across
held-in, held-out, and `hidden_holdout` labels. The factorial compares generic
and specialized controlled policies across H0–H4, with the evaluator and
independent verifier outside the policy.

The primary interaction estimate is:

```text
P(specialized,Hx) - P(specialized,H1)
- P(generic,Hx) + P(generic,H1)
```

## Results

The v1 fixture generated 110 task-cell traces. Independent replay found 1.0
trace validity and 1.0 runtime/verifier agreement. H3 and H4 each produced a
controlled interaction of `+0.090909` versus H1.

The pinned Qwen/Qwen2.5-0.5B-Instruct revision
`7ae557604adf67be50417f59c2c2f167def9a775` ran on the RTX 5090 at seeds 0, 1,
and 2. H1 and H3 each had 33 observations, 0.0 protocol-valid rate, and 0.0
verified success. Generation was greedy, so this is a stability sweep rather
than a stochastic confidence interval.

On the three-task `hidden_holdout` slice, the locally trained Project 1 SFT
checkpoint was added as a second model condition at the same three seeds using
the current adapter mapping. Both models had 0.0 protocol-valid and
verified-success rates under H1 and H3; the model × harness interaction was
0.0 at every seed.

An adapter probe using the Project 1 checkpoint’s native prompt mode also
scored 0/8 valid on the matched Project 1 task spec. The raw traces show
malformed JSON and incompatible state-update fields, confirming that the
current bottleneck is model/protocol compatibility rather than an unverified
task-completion claim.

## Interpretation

The fixture demonstrates that the measurement path can expose a model ×
harness interaction and that independent replay can audit it. It does not
demonstrate that the interaction transfers to a real model. The immediate
research bottleneck is a model trained to emit the frozen Action IR contract,
using independently authored/verifier-backed data rather than the synthetic
bootstrap targets used in the current Project 1 checkpoint.

## Promotion gates

No paper breakthrough claim should be made until a future run has:

1. at least three genuinely stochastic seeds or independently trained model
   instances;
2. a private evaluator-held hidden holdout;
3. real baseline and specialized models with the same parameter/data budget;
4. positive interaction with a confidence interval excluding zero or a
   preregistered practical threshold; and
5. independent replay and artifact/state verification for every success.

Until then, the evidence-based primary track is a developer-preview product,
while research work continues as a falsifiable negative-result and training
pipeline program.

The full real-model H0-H4 factorial was also run at seed 0 for both
checkpoints: 110 task-cell observations total. Every cell was 0.0
protocol-valid and 0.0 verified-success; the independent real-report replay
audit validated all 110 traces. This closes the requested real factorial as a
negative result and rules out claiming a generalized model-harness effect from
the current checkpoints.

## Strict Project 2 checkpoint ablation after evaluator hardening

The newer Project 2 SFT v2 checkpoint was evaluated with a separate runner
that disables or enables the verifier-first repair kernel explicitly. The
evaluator now requires exact expected action arguments and expected final
artifact contents in addition to independent tool evidence. This closes a
false-positive path in which a tool could verify its own output while the
task-level artifact was still wrong or incomplete.

On the frozen 11-task research-v1 fixture, the model-only condition produced
4/11 verified successes and 4/11 protocol-valid decisions. The same checkpoint
with repair enabled produced 11/11 verified successes and 11/11 protocol-valid
decisions. Independent replay reproduced both outcomes with 1.0 trace validity
and 1.0 runtime/replay agreement.

The separate research-v2 independent holdout contains 12 newly authored tasks
with no training overlap by construction. Model-only produced 5/12 verified
successes and 10/12 protocol-valid decisions. Model plus repair produced 12/12
verified successes and 12/12 protocol-valid decisions. Independent replay
again reported 1.0 trace validity and 1.0 runtime/replay agreement.

These are the strongest current results, but they support a systems/harness
claim rather than a model breakthrough: the repair kernel is deterministic and
model-agnostic, the tasks are still small deterministic fixtures, and the
earlier real Qwen factorial remains negative. The aggregate and per-task
reports are in `experiments/results/research-project2-ablation-v1.*`.

### Stochastic stability sweep

Sampling the same Project 2 SFT v2 checkpoint at seeds 0, 1, and 2 on the
independent v2 holdout produced 12/12 verified and protocol-valid tasks at
every seed. All 36 traces independently replayed with 1.0 validity and 1.0
runtime/replay agreement; the sample standard deviation was 0.0. This is
stochastic decoding stability for one checkpoint, not independent training
replication. The report is
`experiments/results/research-project2-stochastic-replication-v1.*`.

## Evaluation and data expansion in progress

The small v2/v3 fixtures were sufficient to expose capacity scaling, but not
to support a broad research claim. The frozen v4 holdout therefore expands the
evaluation to 120 tasks across 12 task families: exact and aliased file
actions, moves, retries, structured JSON, task-owned API/browser fixtures,
two-step horizons, unavailable capabilities, and high-risk authorization
abstention. It includes 20 adversarial prompts and controlled paraphrase
variation. The fixture is
`benchmarks/fixtures/task-spec-research-v4.json` with SHA-256
`9c4e3a4f643c21056dd8fe5437ffe180054cf7f96ad02f572910eb298369bfda`.

The evaluator now reports per-family slices, Wilson intervals, protocol
validity, and adversarial safe-abstain rates through
`experiments/aggregate_research_eval.py`. API and browser values are supplied
by the task specification and independently replayed from that specification,
so the runtime fixture is not the source of truth for the audit.

The training side adds a 3,072-row curriculum with six controlled prompt
styles and explicit sampling strata. Weighted epochs emphasize safety,
long-horizon, external-fixture, and structured-artifact examples while keeping
the target Action IR verifier-backed. This is a data-method improvement, not
evidence that the model has learned a general agent policy; the 7B v4 baseline
and the data-upgraded checkpoint must be compared on the frozen holdout and
then replicated with independent seeds.

## Corrected model-only control: hidden evaluator contract

The initial v4 control exposed `expected_tool` and `required_tools` in the
model state. That condition is useful for a repair/product ablation, but it is
not a valid model-only research evaluation. The same frozen Qwen 7B QLoRA
checkpoint was rerun with those fields hidden while leaving task scoring and
independent replay unchanged:

- hinted control: 120/120 verified, 120/120 protocol-valid;
- hidden-contract control: 80/120 verified, 118/120 protocol-valid;
- hidden-contract independent replay: 120/120 valid traces and 120/120
  runtime/replay agreement.

The hidden failures are concentrated in the two long-horizon families (0/20)
and the two abstention/safety families (0/20); exact writes, moves, retries,
structured JSON, API, and browser families are each 10/10. This is the first
credible local error profile and replaces the earlier perfect v4 headline as
the research control. Full files are
`experiments/results/research-project2-7b-qlora-v1-research-v4-hidden-model-only.json`,
its `*-independent.json` audit, and the hidden aggregate report.

## Industry-style proxy and targeted data repair

The frozen offline industry proxy has 48 tasks across state dependency,
policy-sequence, indirect browser injection, and indirect API injection. The
honest 7B control scored 12/48 (25.0%) with zero unsafe attempts. A corrected
proxy-mix checkpoint added 720 verifier-backed reference rows to the 3,072-row
stratified curriculum, used full-coverage weighted sampling for one epoch, and
scored 43/48 (89.6%) greedy on the proxy. It achieved 48/48 protocol validity,
48/48 independent replay agreement, 12/12 state dependency, 12/12 browser
injection, 11/12 API injection, and 8/12 policy sequence. Three sampled seeds
scored 41/48 (85.4%), 37/48 (77.1%), and 39/48 (81.3%); all had 100% replay
agreement and zero unsafe attempts. Greedy plus these sampled runs averaged
83.3% over 192 proxy task-runs (range 77.1%–89.6%).

On the frozen 120-task hidden-contract v4 holdout, the same proxy-mix
checkpoint scored 120/120 verified, 120/120 protocol-valid, 120/120
independently replayed, and 0 unsafe attempts. These are local offline
benchmarks, not external OSWorld, BrowserGym, AgentDojo, ToolSandbox,
tau-bench, or TUA-Bench results; an external-suite run and held-out authoring
pass remain required before generalized launch or breakthrough claims.

## Current evidence update — 2026-07-26

### Native-tool v6 and the external-gap regression

The promoted 7B checkpoint is now the native-tool v6 branch, trained with a
3,972-row held-out-safe curriculum. On the frozen hidden-contract v4 holdout
it achieved 120/120 verified and protocol-valid outcomes. On the 48-task
industry-style proxy it achieved 48/48 verified and protocol-valid outcomes,
with zero high-risk attempts across state-dependency, policy-sequence,
browser-injection, and API-injection slices. Every trace independently
replayed and agreed with runtime success.

The follow-up v7 revision added repeated evidence-grounding and calendar-repair
examples. It retained 120/120 on v4 but fell to 39/48 on the industry proxy;
the policy-sequence slice fell to 3/12. This is an important negative result:
repeating a narrow external-gap curriculum can preserve an easy holdout while
damaging broader policy composition. v6 remains promoted, and v7 is not used
as evidence for a generalization claim.

### Evaluator hardening and external validation

The evaluator now checks exact action arguments, expected files, evidence-
grounded final answer markers, action ordering, and independent replay. The
16-task industry-proxy-v2 holdout contains eight answer-grounding tasks and
eight insufficient-information or confirmation-boundary tasks. This removes
the earlier false-positive path where a correct tool call followed by a
generic final answer received credit.

The exploratory AgentDojo integration remains deliberately small. One typed
evidence-first harness guard repaired a calendar state-dependency failure, but
the clean user-task and direct-injection composites still expose model-only
native-schema and final-answer-grounding gaps. The result is an ablation, not
an external benchmark score. A credible paper claim still requires at least
five clean workspace tasks and five injection composites with utility,
security, protocol rejection, unsafe attempts, final-answer grounding, and
independent replay reported separately.

### Scaling and post-training status

Qwopus3.5-9B-v3 is being evaluated as a controlled scale branch:

```text
Qwopus3.5-9B-v3 -> response-only Action IR QLoRA SFT
    -> hidden/replay/industry gates -> verifier-backed RL, if justified
```

The rank-64 4-bit QLoRA run completed on the 32 GB RTX 5090 and the adapter was
merged into a reproducible full checkpoint. No 9B score, promotion decision,
or RL improvement claim is recorded until the same frozen matrix is complete.
The linked Qwopus model card,
fine-tuning guide, and PDF motivate SFT engineering choices but do not by
themselves establish an independently verified action-policy RL result.

### Live 9B frozen-matrix checkpoint — 2026-07-27

The resumable 9B promotion matrix is now running across the three frozen
task slices (`research-v4`, `industry-proxy-v1`, and `industry-proxy-v2`) at
seeds 0, 1, and 2. Seed 0 is complete: research-v4 is 116/120 verified,
industry-proxy-v1 is 37/48, and industry-proxy-v2 is 8/16. Seed 1 research-v4
and industry-proxy-v1 are complete at the same scores; seed 2 is in progress.
The partial matrix and its refreshable summary report only the currently
committed prefix, not a promotion result. The remaining seed-2 slices are
pending.

The current independent audit covers every committed row and has shown perfect
trace validity and runtime/replay agreement, zero protocol failures, zero
unknown or unverified actions, and zero unsafe attempts. The observed
negative rows are task failures, principally exact-payload contamination,
finish-evidence failure, repeated verified actions, and step-budget
exhaustion. These labels are diagnostic, not causal proof. A CUDA lifecycle
fix was added to release the previous seed's model before loading the next;
this prevents accidental CPU offload under `device_map="auto"` and preserves
the frozen evaluation condition while improving reproducibility and runtime.
No 9B promotion, external benchmark, RL improvement, or generalized
capability claim is valid until all nine runs are complete and independently
audited.

### Product evidence update

The local developer-preview surface now has a consolidated
`launch-preflight/v1` artifact. It passes the six-case product smoke, MCP
contract and replay, local-only endpoint policy, bearer authentication,
non-loopback TLS gating, high-risk denial, 12-way concurrent trace writes
with restart recovery, token-principal trace isolation, validated wheel
integrity plus extracted-wheel install smoke, documentation presence, and an
earlier 59/59 source-test run. The current suite is 81/81 and trace
publication is atomic. This supports a technically
capable local preview; it does not close multi-user isolation,
operational hardening, usability,
security-review, licensing/provenance, or external-benchmark gates.
