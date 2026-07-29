# Capability Placement in Small Agent Policies

## Working abstract

Small local language models are often evaluated as reduced general assistants.
This project instead studies compact policies specialized for typed agent
actions: tool selection, argument generation, state updates, abstention,
recovery, and verified stopping. We separate these probabilistic decisions
from deterministic harness responsibilities including authority, execution,
state persistence, and verification. The central experiment treats model and
harness as independent variables and measures verified utility per deployment
budget. The first pinned 0.5B zero-shot baseline produced 0/8 valid Action IR
decisions. A five-epoch synthetic SFT fixture reached 8/8 valid decisions and
4/6 held-out verified successes, while a one-epoch synthetic mid-training run
remained at 0/8. These results motivate, but do not prove, the need for
protocol-native specialization and independently sourced training data.

## 1. Hypothesis and research questions

**H1:** On bounded local-agent tasks, a small model specialized for Action IR,
tool selection, abstention, and recovery can improve verified utility per
parameter, token, latency, memory, and energy relative to a same-size generic
instruction model.

**H2:** An advanced harness can improve a specialized small model
disproportionately, producing a positive model–harness interaction on at least
some task families.

The project asks which capabilities belong in weights, which belong in the
harness, whether action/state representations increase semantic density, and
where specialization fails under held-out tools, misleading context, and
permission constraints.

## 2. Related work

The literature review in `docs/LITERATURE_REVIEW.md` covers ReAct, Toolformer,
TinyAgent, xLAM, Hammer, Agent Distillation, SWE-agent, Agentless, Granite
function calling, and recent abstention/irrelevance evaluations. The common
lesson is that interface, data, and tool selection can be causal variables;
the open question here is how far those variables can be externalized for a
small local policy under deployment budgets.

## 3. System boundary and protocol

The model emits Action IR v0 decisions: `act`, `observe`, `abstain`, or
`finish`. Each decision carries task/step identity, uncertainty, and a typed
state update. The paired runtime validates structure, gates permissions,
executes registered tools, records lineage, and independently verifies effects.
The model cannot authorize destructive actions or promote its own checkpoint.

## 4. Method

The repository freezes a versioned eight-task specification with held-in and
held-out tasks covering file actions, unknown tools, finish verification,
permission boundaries, recovery, and ambiguity. The evaluator reports valid
decisions, verified success, correct abstention, invalid actions, output-token
proxies, useful transitions per token, and structured information density.

The required factorial cells are:

| | Baseline harness | Advanced harness |
|---|---|---|
| Generic model | A | C |
| Specialized model | B | D |

The interaction term is `D − B − C + A`. The repository’s fixture runner
executes all four cells and labels its scores as wiring-only. The real result
must use checkpoint-backed policies, real verifiers, held-out workflows, and
hardware measurements.

## 5. Preliminary results

### 5.1 Zero-shot checkpoint

`Qwen/Qwen2.5-0.5B-Instruct` at pinned revision
`7ae557604adf67be50417f59c2c2f167def9a775` was run on CPU through the Action IR
adapter. Across 8 tasks, valid decision rate was 0.0, verified task success
was 0.0, and protocol-error rate was 1.0. The model emitted loose or malformed
action objects rather than the required envelope. Mean wall time was 3750.1 ms
per task and total output was 833 tokens.

### 5.2 Synthetic SFT smoke run

One CPU epoch over 8 synthetic oracle examples completed in 17.98 s with mean
loss 1.0978. The resulting checkpoint still produced 0/8 valid decisions and
0/8 verified successes. Outputs moved toward Action IR-like fields but
remained malformed or structurally flattened. This is a pipeline result, not
evidence that the training objective or data is sufficient.

### 5.3 RTX 5090 baseline and staged training

The pinned checkpoint was also run on an RTX 5090 using PyTorch 2.11.0 with
CUDA 12.8 and BF16. The zero-shot run remained at 0/8 valid and 0/8 verified
success, with 4.7 s load time and 3.44 s mean task wall time. Five epochs of
the eight-example synthetic SFT fixture trained in 5.22 s, reached 8/8 valid
decisions and 4/6 held-out verified successes, and used 4.884 GiB peak
training VRAM. This is protocol-learning and pipeline evidence only because
the data is synthetic.

A one-epoch synthetic Action IR mid-training run over 16 rows trained in 3.00
s but evaluated at 0/8 valid and 0/8 verified success. The negative result
shows that a small domain-adaptive causal-LM corpus is not automatically a
replacement for prompt-aligned supervised trajectories.

### 5.4 Real checkpoint factorial smoke result

The checkpoint-backed runner completed all four model-by-harness cells with
stateful execution and independent verifiers. Verified task success was 0.000
for generic/baseline, 0.750 for synthetic-specialized/baseline, 0.375 for
generic/advanced, and 0.625 for synthetic-specialized/advanced, yielding
interaction `-0.500`. This is a reproducible smoke result, not a capability
claim: the specialized checkpoint uses eight synthetic examples, the task
suite is small, and the advanced harness currently changes context and safely
abstains on malformed output.

## 6. Limitations and threats to validity

- The current tasks are small deterministic fixtures, not a broad local-agent benchmark.
- The bootstrap SFT data is synthetic and derived from the task oracle.
- The current mid-training and preference fixtures are also synthetic and
  derived from the same frozen task specification.
- A local RTX 5090 smoke confirms one quantized 9B serving path (NF4 loading,
  BF16 compute, valid Action IR), but no broad quantized benchmark or
  edge-device energy measurement exists yet.
- The current harness and verifier coverage is mostly in-memory file state.
- The zero-shot and SFT results cover one checkpoint and one prompt protocol.
- No positive specialization or model–harness interaction claim is made.

The preliminary positive specialized-baseline cell and negative interaction
are not generalization claims; independent teacher/human-reviewed data,
larger held-out tools, multiple seeds, and confidence intervals remain
required.

## 7. Next experiments

1. Add independently reviewed teacher trajectories, hard negatives, renamed tools, and paired abstention tasks.
2. Run PEFT/LoRA and DPO on non-synthetic preference data, then conduct a short audited environment-grounded RL smoke run.
3. Expand the held-out task suite and run generic and specialized checkpoints through H0-H3 at equal budgets and multiple seeds.
4. Extend the quantized serving smoke into a broad deployment benchmark, then measure edge-device latency/energy and cost per verified success.
5. Publish negative results and confidence intervals, including task-family interaction signs.

## 8. Paired-program update — 2026-07-26

The paired Project 2 harness now provides a stronger systems result than the
early 0.5B model-only smoke. On the frozen 120-task hidden-contract v4 slice,
the promoted 7B v6 Action IR checkpoint achieved 120/120 verified successes;
on the 48-task industry proxy v1 slice it achieved 48/48 with zero unsafe
attempts and independent replay agreement. These are local, verifier-backed
measurements, not external benchmark scores.

The evidence also contains a useful negative result. A targeted external-gap
revision (v7) retained 120/120 on the hidden slice but fell to 39/48 on the
industry proxy, including a policy-sequence regression from 12/12 to 3/12.
Repeating a narrow curriculum therefore did not produce robust specialization.
A verifier-backed 7B RL smoke was neutral/negative: reward stayed at
`-0.78125` and greedy success remained 0/8, so that adapter was not promoted.

The strongest current controlled local ablation result is the harness
comparison: on the strict 11-task local fixture, model-only scored 4/11 while the same checkpoint
with verifier-first repair scored 11/11; on a separately authored 12-task
holdout, the comparison was 5/12 versus 12/12. Every trace independently
replayed with full runtime agreement. This supports a bounded systems claim:
an independent evidence/recovery layer can repair a small policy on these
fixtures. It does not support a general agent or model-breakthrough claim.

The Qwopus3.5-9B-v3 branch completed rank-64 4-bit QLoRA SFT and merge on the
RTX 5090. Its frozen promotion matrix is complete across three slices and
three seeds: 483/552 independently verified successes (87.5%), zero unsafe
attempts, perfect trace validity, and perfect runtime/replay agreement. The
machine promotion gate correctly rejects the checkpoint because the failed
rows cluster in long-horizon policy sequences and evidence-grounded
finalization. The v1 and adversarial v2 external-bar diagnostics and
verifier-backed RL remain downstream of that failure analysis.

### Revised paper claim

The publishable hypothesis is now narrower and more interesting than “scale
the model”: under equal model, task, and decoding budgets, independent
verification, evidence-grounded completion, bounded recovery, and replay can
improve verified utility and reduce false completion for small local action
policies. The final test is a three-way model-only/SFT/verifier-backed
factorial that survives a fresh holdout, adversarial tool schemas, and at
  least one native external suite.

### External-method update — 2026-07-26

Two current research directions sharpen the follow-up design. ToolVerse
([paper](https://arxiv.org/abs/2607.15660)) uses tool-dependency graphs for
long-horizon task construction and turn-aware credit assignment. We therefore
add expected action/tool horizon, first-invalid-step, and recovery distance as
planned stratification variables rather than reporting only aggregate success.
Tinker’s documentation ([SDFT discussion](https://thinkingmachines.ai/tinker/))
also motivates a verifier-filtered self-distillation arm: the policy samples
its own Action IR trajectory, an independent checker filters it, and the
result is compared with ordinary SFT on a fresh holdout. This is a future
ablation, not evidence for the current 9B branch, and it cannot change the
protected evaluator or promotion rules.

### Exact-payload fidelity diagnostic — 2026-07-26

The first complete seed-0 slice of the frozen Qwopus3.5-9B research-v4 matrix
was 120/120 tasks, with 116 verified successes. The family
breakdown is 70/70 across alias-write, move, alias-move, retry, structured-JSON,
API-lookup, and browser-lookup tasks; 10/10 on long-horizon-alias; 10/10 on
long-horizon; 10/10 on unknown-capability abstention; and 10/10 on high-risk
abstention, versus 6/10 on exact-write.
All four observed failures are exact-write false completions: the
policy performed the requested write but appended a `STATE_DIGEST` metadata
line, which correctly failed the byte-exact verifier. There were no unknown-tool
or unsafe-action attempts in these failures. This separates action selection
from artifact serialization fidelity and gives the next causal intervention a
specific target. The complete three-seed matrix confirms the same four exact-
write failures per seed. A held-out-safe 120-row verifier-backed curriculum
was added with runtime digest metadata in state and exact payloads in the
targets. It is an intervention candidate, not a claimed improvement; the
fresh remediation comparison remains to be run.

### Field refresh: reward hacking and credit assignment — 2026-07-26

The design now includes two additional requirements motivated by recent
primary work. The [Reward Hacking Benchmark](https://arxiv.org/abs/2605.02964)
shows why multi-step tool-use evaluation should expose shortcut opportunities,
including skipped verification, metadata leakage, and evaluator-relevant
tampering. We therefore treat artifact-content fidelity, unsupported evidence,
and evaluator-integrity violations as separate metrics rather than hiding them
inside aggregate success. The [TRACE paper](https://arxiv.org/abs/2607.13988)
also motivates reporting first-invalid-step, recovery distance, and verified
prefix utility before launching another RL intervention. These sources inform
the design; they are not performance claims about this checkpoint.
