# 9B frozen matrix result — 2026-07-29

This note records the current local evidence for the merged Qwopus 3.5 9B
Action IR checkpoint. It is a research artifact, not a claim of general
terminal or computer-use capability.

## Aggregate result

| Measure | Result |
| --- | ---: |
| Frozen runs | 9 (3 slices × 3 deterministic greedy replicas) |
| Task rows | 552 |
| Independently verified successes | 483 / 552 (87.5%) |
| Unsafe attempts | 0 |
| Trace-valid rate | 100% in every run |
| Runtime/replay agreement | 100% in every run |
| Promotion decision | Reject |

The frozen matrix was run with `do_sample=false`; seeds 0, 1, and 2 are
therefore reproducibility replicas, not independent stochastic decoding
samples. A separate `do_sample=true` audit is required before making a
stochastic decoding-robustness claim.

The public aggregate is
[experiments/results/research-project2-qwopus35-9b-promotion-summary-v1.json](../experiments/results/research-project2-qwopus35-9b-promotion-summary-v1.json).
The source report artifact is
`research-project2-qwopus35-9b-promotion-greedy-v1.json` with SHA-256
`077f936ed932a939302e5974d251e28f649c95c832093ed89591dcdceed1277b`. The
machine-checked decision artifact is
`research-project2-qwopus35-9b-promotion-decision-v1.json` with SHA-256
`dad70c92fb331c3eb1f1bb84329a129029464b748eb60c777739df9a643ed2e2`.
The raw source and decision files remain local because they contain full
replay traces and local checkpoint paths; the committed summary preserves the
aggregate evidence and source hashes without pretending to bundle the model.

## Slice breakdown

| Slice | Verified success | Repeated failure mode |
| --- | ---: | --- |
| research-v4 | 348 / 360 (96.7%) | Four exact-write tasks per seed finished without independently verified evidence |
| industry-proxy-v1 | 111 / 144 (77.1%) | Eleven long-horizon policy-sequence tasks per seed exhausted the six-step budget |
| industry-proxy-v2 | 24 / 48 (50.0%) | API/browser evidence-to-answer tasks finished without independently bound evidence |

The same task IDs fail across all three greedy replicas. That repetition is
useful as deterministic reproducibility evidence, but it is not a test of
sampling variance. The model can execute many typed actions safely, but it is
weak at the transition from verified
intermediate state to a correctly evidenced final answer and at completing
long action sequences within the harness budget.

## Research interpretation

The strongest defensible result is a systems failure-localization result:
independent authority, evidence, and replay make unsafe behavior measurable and
rejectable, while exposing two separable bottlenecks—long-horizon control and
evidence-grounded finalization. The result does not support a promotion claim,
because the frozen gate correctly rejects any slice with failed tasks.

The highest-value next experiment is a fixed-base, disjoint remediation ablation
targeting only those failure modes:

1. baseline 9B Action IR policy;
2. finish/evidence convergence remediation;
3. long-horizon policy-sequence remediation;
4. both remediations under the same verifier and step budget.

All four cells must use fresh task IDs, three genuinely stochastic decoding
seeds (or independently trained replicas, explicitly labeled), independent
replay, and the same unsafe-action gate. A publishable improvement must raise verified
utility without increasing unsafe attempts, false completions, or replay
disagreement. RL remains downstream of this audit; it is not a substitute for
the failure-targeted ablation.

## Claim boundary

Allowed: “On a frozen local action-task matrix, the verifier-first harness
produced replay-valid, zero-unsafe traces and localized the 9B policy’s failures
to long-horizon completion and evidence-grounded finalization.”

Not allowed: “The 9B model is generally capable,” “the system beats frontier
agents,” or “the product is production-ready.” Native external evaluation,
licensing/provenance review, operational identity controls, usability sessions,
and the public launch gates remain open.
