# External bar update — 2026-07-26

This note records the current external evaluation bar used for the research
and launch decision. Local proxy scores remain useful for debugging, but they
are not evidence of general agent competence.

## What the newest benchmarks reveal

### TUA-Bench

[TUA-Bench](https://arxiv.org/abs/2606.28480) evaluates general-purpose
terminal-use agents on 120 manually designed, execution-graded tasks across
five families. It includes routine digital work as well as scientific and
engineering workflows. The reported strongest frontier configuration,
Claude Code with Claude Opus 4.8 at maximum reasoning effort, reaches 65.8%
overall. This is the closest external reference for our terminal-first
Action IR and research-workflow positioning.

Implication for this project: a meaningful local result must include task
families, state transitions, user-facing completion evidence, and cost/latency
instead of one aggregate success percentage. Our next proxy should include
document, email, web, and scientific/engineering-style workflows with hidden
state and deterministic graders.

### OSWorld 2.0

[OSWorld 2.0](https://arxiv.org/abs/2606.29537) contains 108 long-horizon
computer-use workflows. The paper reports a median human task duration of
about 1.6 hours and an average of roughly 318 tool calls for a strong model.
Even the best reported frontier configuration completes only 20.6% of tasks
under the primary binary-completion metric at a 500-step limit, with a 54.8%
partial score.

Implication for this project: the important failures are constraint tracking,
mid-task information, implicit state, asking for clarification, and final
verification. Our harness should expose those as separately measured failure
categories rather than hiding them inside a final answer score.

### SWE-bench as an evaluation-design warning

[OpenAI's original SWE-bench Verified release](https://openai.com/index/introducing-swe-bench-verified/)
made human screening and reproducible containerized evaluation explicit.
OpenAI later documented why it [no longer uses SWE-bench Verified as a frontier
capability measure](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/),
including contamination and benchmark-quality concerns.

Implication for this project: every reported number needs provenance, a
held-out authoring story, evaluator audits, and a clear statement of what the
metric does not establish. A perfect local score should trigger harder task
generation, not a stronger claim.

## Revised research gate

Before claiming a research breakthrough, a candidate checkpoint must show all
of the following:

1. Improvement over the same-base model-only policy on a held-out, independently
   authored stateful suite.
2. Replication across at least three decoding seeds and, where practical,
   more than one training seed.
3. 100% trace validity and runtime/replay agreement on successful and failed
   trajectories.
4. Zero unauthorized high-risk mutations under adversarial tool output.
5. Evidence-grounded final answers, including correct abstention and
   confirmation when information is insufficient or the action is consequential.
6. A fresh run on at least one external suite, reported with its native metric
   and limitations.
7. A cost/latency/resource report that makes the result reproducible on the
   RTX 5090 deployment target.

## Revised local suite to build next

The next local revision should be a separate benchmark, not an expansion of
the training generator:

- 20 terminal-style tasks across document, email, web, data, and
  scientific/engineering families;
- hidden initial state and canonicalization traps;
- delayed or contradictory observations;
- explicit insufficient-information and confirmation-required cases;
- adversarial untrusted tool output;
- 25/50/100-step budgets with per-category failure reports;
- independent state reconstruction and final-answer checks.

That suite is now materialized as
`benchmarks/fixtures/task-spec-external-bar-lite-v1.json` with 20 tasks and
SHA-256 `8d1d852b4cd181079effd7023df13655406de73ddfd6a65329ec6597adf6cae3`.
It is the bridge between the current deterministic proxy and a real external
run. It is also the minimum experiment needed to test the project’s actual
hypothesis: whether verifier-backed execution improves reliable, auditable
utility rather than merely improving formatted tool calls.
