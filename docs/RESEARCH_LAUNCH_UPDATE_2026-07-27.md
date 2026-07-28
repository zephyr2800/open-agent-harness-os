# Research and launch update — 2026-07-27

Status: active 9B promotion evaluation; developer-preview candidate; public
launch and research-breakthrough claims remain gated.

## Live experimental update

The RTX 5090 is currently running the resumable Qwopus3.5-9B frozen matrix.
The three seed-0 slices are complete: research-v4 is 116/120 verified (96.7%),
industry-proxy-v1 is 37/48 (77.1%), and industry-proxy-v2 is 8/16 (50.0%).
Seed 1 research-v4 is now complete at 120/120 rows (116 verified), and
industry-proxy-v1 seed 1 is complete at 37/48 verified. Seed 2 is in progress;
the refreshable partial matrix contains only the currently committed prefix,
with the remaining seed-2 slices pending. The observed policy failures
are repeated verified actions followed by step-budget exhaustion, while the
research-v4 failures are exact-payload contamination and finish-evidence
failures. No promotion, RL, or public-launch claim is valid until all three
task slices and all three seeds are complete and independently audited.
The observed industry-proxy-v1 policy-sequence tasks are also materially
slower than the other families: completed seed-0 examples took approximately
851–1,343 seconds each, commonly ending in step-budget exhaustion. This is a
measured throughput constraint of the current model/harness combination, not
evidence that the active matrix process is stalled.
An opt-in `stop_on_complete_json` generation criterion has been added to the
Transformers backend for future serving/remediation runs. It stops only after
the generated first JSON object is structurally complete, defaults to off, and
was not used for this frozen matrix; its latency and semantic equivalence must
be measured on a disjoint comparison before it can support a launch claim.
The last independent audit covers every committed row and has found perfect
trace validity and runtime/replay agreement, zero protocol failures, zero unsafe
attempts, zero unknown actions, and zero unverified action rows;
the remaining negative rows are independently rejected task completions.

The remediation path now includes a fresh, disjoint 80-row policy-recovery
curriculum (write, move, retry-until-recovered, audit write, verified finish)
in addition to the exact-payload and finish-convergence rows. The combined
queued set is 536 synthetic rows, with zero frozen-holdout task identifiers.
This is a targeted intervention hypothesis, not evidence of improvement; the
same frozen matrix must measure whether it works.
The curriculum provenance audit is also clean: 536/536 rows use the expected
schema, declare all six frozen-surface exclusions, and have zero overlap with
the 248 checked holdout task IDs.

The post-run automation was also audited: stale PID-based waiters were changed
to identify the active matrix by its command/output fingerprint, preventing a
completed evaluation from being missed after a process restart.

## Decision in one paragraph

The work should be positioned as a verified action-policy/control-plane
experiment, not as a claim that a 9B model is generally intelligent. The
current 9B QLoRA branch is the right scale comparison for the 32 GB RTX 5090,
but it must first clear the frozen matrix, independent replay, and external
bar. The research result worth pursuing is a causal systems claim: a compact
protocol-specialized policy plus independent authority/evidence/replay can
increase verified utility on stateful tasks without increasing unauthorized
actions. A model score alone is insufficient.

### Scaling finding (interim, not a promotion result)

The larger checkpoint is not automatically better on the current control
surface. A prior 7B v7 model-only run on the same `research-v4` and
`industry-proxy-v1` task-spec hashes recorded 120/120 and 39/48 verified
successes. The completed 9B seed-0 and seed-1 cells record 116/120 and 37/48
on those same slices. This is not a final 7B-versus-9B claim: the checkpoints
have different training histories and the 9B matrix is still incomplete.
It is, however, evidence that parameter scaling alone is not the intervention
to promote. The causal comparison must isolate base model, Action IR SFT,
failure-targeted remediation, and verifier-backed RL under the same frozen
evaluator.

## What the current literature and launches imply

| Reference | What it makes measurable | Consequence for this project |
|---|---|---|
| [OSWorld](https://arxiv.org/abs/2404.07972) and [OSWorld 2.0](https://arxiv.org/abs/2606.29537) | Real applications, hidden state, cross-application workflows, long horizons, and partial versus binary completion | Report state reconstruction, final verification, step budget, and partial utility; never present the local fixture score as computer-use competence. |
| [BrowserGym](https://arxiv.org/abs/2412.05467) | Reproducible web environments and multi-benchmark agent comparison | Add browser-state recovery and untrusted page-content cases to the external track. |
| [TUA-Bench](https://arxiv.org/abs/2606.28480) | Execution-graded terminal work across routine, scientific, and engineering families | This is the closest external comparison for our terminal-first Action IR; report family scores, latency, and cost rather than one aggregate. |
| [π-Bench](https://arxiv.org/html/2605.14678) | Persistent, multi-session assistance, hidden preferences, proactivity, and task completion | Add memory/persistence and user-burden metrics before claiming a self-evolving harness. |
| [PaperBench](https://openai.com/index/paperbench/) | Whether an agent can reproduce research, with independent grading | Use independent graders and artifact provenance for any “research agent” claim. |
| [LifeSciBench](https://openai.com/index/introducing-life-sci-bench/) and [GeneBench-Pro](https://openai.com/index/introducing-genebench-pro/) | Realistic multi-round research work, ambiguity, consequential judgment, and follow-up rather than one-shot answers | Extend the harness evaluation beyond tool correctness: measure round-to-round state, uncertainty/escalation quality, artifact provenance, and researcher time saved. |
| [Karpathy autoresearch](https://github.com/karpathy/autoresearch) | Fixed-time, single-GPU experiments with an agent modifying a constrained training program and retaining only measured improvements | Borrow the fixed budget, immutable evaluator, experiment ledger, and accept/reject loop; do not let the harness modify its own grader. |
| [Thinking Machines Inkling](https://thinkingmachines.ai/news/introducing-inkling/) and [Tinker](https://thinkingmachines.ai/news/announcing-tinker/) | Inkling is reported as a 975B-total/41B-active MoE with a 12B-active smaller preview, multimodal inputs, long context, and a self-fine-tuning demonstration; Tinker exposes customization as a product surface | Supports our two-layer product thesis: Project 1 is the adaptable local policy; Project 2 is the portable authority/evidence plane. It also makes our 9B branch a cost/locality experiment, not a frontier-scale comparison. |
| [π-Bench](https://arxiv.org/abs/2605.14678) and [PBT-Bench](https://arxiv.org/abs/2605.15229) | Persistent hidden-intent workflows and documentation-grounded invariant discovery expose failures missed by one-shot success rates | Add cross-session state, proactive intent, invariant discovery, and partial utility to the next external track; preserve independent verification. |
| [Moonshot’s official research organization](https://github.com/MoonshotAI) and [Kimi K2.5](https://arxiv.org/abs/2602.02276) | Open agentic models, MoE/long-context directions, and reproducible technical references for K2/K2.5 | Treat Kimi K3 architecture/parameter claims as a market signal until an official technical report, weights, and native eval package are available. Do not use third-party K3 numbers as our baseline. |

### Primary-source positioning refresh

- [PaperBench](https://openai.com/index/paperbench/) makes the research-agent bar concrete: 20 ICML papers, 8,316 gradable subtasks, and a reported best tested agent score of 21%. Our claim should therefore include independently graded artifacts and reproducible experiments, not just a fluent research report.
- [Karpathy's autoresearch protocol](https://github.com/karpathy/autoresearch/blob/master/program.md) fixes a five-minute single-GPU budget and keeps the evaluator/data preparation outside the agent's editable surface. Our bounded remediation loop follows the same principle: it may mine failures and train candidates, but it cannot edit the evaluator or holdout specs.
- [Thinking Machines' Tinker](https://thinkingmachines.ai/news/announcing-tinker/) exposes low-level `forward_backward` and `sample` primitives for post-training. This reinforces the product split: a local policy-training surface can be modular, while authority, evidence, replay, and promotion remain in the independent harness.
- [Thinking Machines' Inkling release](https://thinkingmachines.ai/news/introducing-inkling/) makes the current product pattern explicit: a large open-weights model, a smaller active-parameter variant, and a customization workflow including a self-fine-tuning demonstration. Our defensible wedge is narrower: local, typed-action specialization with an immutable evaluator and independent evidence/replay.
- [π-Bench](https://arxiv.org/abs/2605.14678) separates task completion from proactivity in 100 multi-turn, cross-session workflows. A future self-evolving claim for this project must report those dimensions separately instead of collapsing them into a single success rate.

The differentiating experiment is consequently not “we self-improve.” It is:
**under a frozen evaluator, does verifier-issued evidence and failure-targeted
post-training improve independently replayed utility without increasing unsafe
actions, false completions, or evaluator disagreement?**

## Research claim to test

**Verifier-backed specialization improves independently verified utility on
stateful action tasks while preserving the safety boundary.**

The claim is deliberately narrower than a generic structured-agent claim.
StructAgent is now a close comparison point for verifier-backed state,
checkpointing, and evidence-grounded completion. Our differentiator must be
the interaction between (a) a compact typed-action policy, (b) an authority /
evidence / replay plane independent of that policy, and (c) a failure-targeted
self-improvement loop that cannot edit its own evaluator. The result must be
measured with the same base model, same tool contract, and a disjoint
author-heldout.

The minimum publishable comparison is a fixed-base 2×2 ablation:

1. generic/model-only policy;
2. Action IR SFT policy;
3. Action IR SFT with verifier-first repair;
4. verifier-backed post-training only after the reward is shown to be
   correlated with independent replay.

Every cell must use a frozen, independently authored holdout; three decoding
seeds; family-level results; exact failure labels; trace validity; replay
agreement; unauthorized-action rate; and resource measurements on the RTX
5090. RL is an experiment, not a promotion assumption. The prior 7B RL smoke
was neutral/negative, so another RL run is justified only if the 9B SFT branch
clears the same-base gate and the reward audit passes.

The minimum differentiating ablation is five cells: base model, policy SFT
only, verifier harness only, policy SFT plus verifier harness, and policy SFT
plus verifier harness plus frozen-evaluator remediation/RL. The last cell must
improve independently verified utility without increasing unsafe attempts,
false completions, or replay disagreement.

## Current execution order

1. Finish the resumable Qwopus3.5-9B matrix across research-v4,
   industry-proxy-v1, and industry-proxy-v2, seeds 0/1/2.
2. Run the independent promotion decision and resource report. A high score
   with a missing slice, unsafe attempt, invalid trace, or replay mismatch is
   a failure, not a promotion.
3. Run the disjoint external-bar-lite bridge and preserve it as diagnostic
   evidence; then run at least one native external suite (initially
   AgentDojo, TUA-Bench, or τ³-bench) before making a generalized claim.
4. If the frozen integrity and diagnostic gate passes, run the actual
   verifier-backed 9B REINFORCE stage,
   merge it, and compare before/after on `research-v2`; only an improvement
   with zero unsafe actions and perfect replay/trace validity is eligible for
   the next finish-convergence remediation. The remediation then reruns the
   full frozen matrix before exact-payload SFT. If RL is held, the remediation
   starts from the baseline and publishes the RL failure analysis.
5. Close product gates independently: real-model latency/cost, usability
   sessions, tool-by-tool security review, identity/tenant operations,
   licensing/provenance, and a reproducible release bundle.

## Launch wording now

Allowed: “A local developer preview provides typed actions, allowlisted
execution, independent verification, and replayable evidence. Protocol
specialization improved the frozen local tasks; the larger 9B branch is under
held-out evaluation.”

Not yet allowed: “generally capable computer-use agent,” “beats frontier
agents,” “RL improved the policy,” “prevents all unsafe actions,” or
“production-ready.”

## Evidence rule

Local proxies are for diagnosis. An external benchmark result must use the
external suite’s native environment, grader, metric, version/commit, and
limitations. The evaluator, task authoring history, model checkpoint hash,
prompt/tool contract, and replay artifacts must ship with the claim.
