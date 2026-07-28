# Decisions

## D1 — Preserve Project 1 Action IR v0

The harness validates the existing `action-ir/v0` contract at its public
boundary. It does not silently fork the model protocol or import private model
implementation details.

## D2 — Verification is an execution boundary

The model may propose an action, but only the registered tool, authority policy,
and independent verifier can make it observable or count it as progress.

## D3 — Evidence is separate from the transcript

Verified claims live in an evidence ledger with source-trace lineage. The model
cannot turn a self-asserted `finish.verified` flag into task success.

## D4 — H0 is deliberately weak but still bounded

H0 is a control condition with permissive policy and transcript context. It
still executes only registered tools so a benchmark comparison cannot become a
destructive side effect.

## D5 — Self-improvement protects the evaluator

H4 can propose only editable middleware surfaces. Evaluators, traces, budgets,
model identity, sandbox, authority, and promotion logic are protected.

## D6 — Fixture factorial results are plumbing evidence

The deterministic policies are useful for testing interaction arithmetic and
trace completeness, but they cannot support a model capability claim. Real
model, hidden-task, renamed-tool, and multi-seed evidence is required.
