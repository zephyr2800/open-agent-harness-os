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

## D7 - Freeze evaluation before post-training promotion

The clean 9B candidate must pass a source-bound train/holdout audit and a
frozen stochastic promotion matrix before native external evaluation or
verifier-backed RL. A historical result whose source split cannot be audited
remains diagnostic context, even if its local aggregate score is high.

## D8 - Treat native external evaluation as a source-bound diagnostic

AgentDojo and tau2 selectors, budgets, policy settings, benchmark commits,
adapter source trees, and output artifacts are preregistered and validated.
The resulting report is still a bounded native diagnostic: it does not prove
general agent capability, independent cryptographic attestation, or a security
certification. Adaptive injection evaluation is a separate Phase B.

## D9 - Make curriculum order a measured intervention

The active clean SFT uses a uniform full-coverage permutation. If the frozen
baseline exposes an appropriate failure family, weighted ordering is tested as
a separate full-coverage ablation with the same data hash and budget; it is
not silently substituted for the baseline and it does not justify oversampling
or evaluator changes.

## D10 - Treat 27B scale as a feasibility branch, not a rescue claim

The single RTX 5090 may be used for a staged 27B NF4 QLoRA memory/loss smoke
only after the clean 9B evaluation chain frees the GPU. It begins with a small
rank, short context, and fixed step budget, and proceeds only after finite
loss, complete coverage, checkpoint integrity, and memory headroom are shown.
It must consume an audited clean curriculum and pass the same held-out,
replay, safety, and deployment measurements; a larger parameter count does
not repair an invalid baseline or establish a scaling-law claim on its own.
