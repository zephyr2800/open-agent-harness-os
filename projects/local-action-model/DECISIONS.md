# Decisions

## ADR-0001: Start with Action IR and evaluator (2026-07-25)

### Decision

Freeze a small, dependency-free Action IR v0 and deterministic evaluator as
the first implementation milestone. Do not begin model training until the
protocol and scoring behavior have executable regression tests.

### Rationale

The design document makes the evaluator a prerequisite and requires model,
harness, and benchmark variables to remain separable. A stable protocol lets
generic and specialized policies be compared under the same task and tool
contract.

### Consequences

- The validator checks structure, not permissions or real-world effects.
- The evaluator reports protocol validity separately from task success.
- Unknown extension fields remain permitted for forward-compatible adapters.
- A future schema version must be explicit; silent shape changes are not allowed.

### Rejected alternatives

- Free-form natural-language plans: difficult to validate and replay.
- Training a model first: would confound model behavior with a moving evaluator.
- Making the model the authority for destructive actions: violates the system boundary.

## ADR-0002: Factorial runner before checkpoint claims (2026-07-25)

### Decision

Implement the complete four-cell runner and interaction arithmetic before
connecting a trained checkpoint. Bundle deterministic fixture policies only as
plumbing tests, and label their results as non-scientific.

### Rationale

The research claim depends on separating model and harness variables. A runner
that cannot execute all cells, preserve task definitions, or report failures at
the task level would make later checkpoint results uninterpretable. The fixture
also verifies that safe harness recovery can change validity without silently
turning an invalid model output into a successful task.

### Consequences

- A negative fixture interaction is retained rather than optimized away.
- Real model and harness adapters must implement the existing interfaces.
- Fixture scores must never be presented as evidence for specialization.
- The next empirical milestone requires a checkpoint-backed policy and real
  verifier outcomes.

## ADR-0003: Pin the first open checkpoint (2026-07-25)

### Decision

Use `Qwen/Qwen2.5-0.5B-Instruct` at revision
`7ae557604adf67be50417f59c2c2f167def9a775` as the first generic local
baseline candidate, accessed through an optional Transformers backend.

### Evidence

The upstream model card identifies the checkpoint as a 0.49B-parameter causal
LM, reports Apache-2.0 licensing, and documents a Transformers loading path.
The repository records the model id, revision, generation settings, and
measurement fields in `model/configs/qwen2.5-0.5b-instruct.json`.

### Consequences

- The checkpoint is suitable for the 0.5–3B initial scope and makes the first
  baseline concrete.
- The current environment still lacks the optional inference dependencies;
  no performance claim is made until they are installed and the model runs.
- A later checkpoint may replace this baseline only through a versioned
  decision record and the same held-out evaluation.

## Checkpoint note: verifier audit (2026-07-25)

The first stateful evaluator run found two defects before being accepted:

- the reference policy reused the task's mutable argument dictionary, allowing
  a test mutation to alter the oracle;
- the reference policy labeled `move_file` as low risk while the registered
  tool required medium risk.

Both were fixed, covered by regression tests, and the reference policy now
passes 8/8 stateful tasks with independent verification. This is evidence that
the evaluator can catch integrity failures; it is not evidence about a trained
model.

## ADR-0004: Sequence the two projects as dependent phases (2026-07-25)

### Decision

Approach the Open Local Action Model before the Open Agent Harness OS. Keep the
Action IR/evaluator frozen, promote a reproducible local model candidate, then
build the second project's wider harness surface, and only then run the full
model-by-harness experiment.

### Rationale

The harness is an experimental variable in the paper, while the model is the
first subject of the current goal. Building both broadly at once would mix
model failures, permission behavior, recovery behavior, and changing tool
surfaces. The phase gate keeps the model contract stable and makes the later
factorial comparison interpretable.

### Consequences

- Phase 1 owns the first RTX 5090 budget and training ladder.
- Phase 2 may extend adapters and policies but must not silently change Action
  IR v0 or the frozen task spec.
- Phase 3 is the first place where the two projects are optimized together.
- The separate Phase 2 goal remains queued rather than being started as a
  competing unfinished goal in this thread.

## ADR-0005: Use Parameter Golf as a constraint track, not the core target (2026-07-25)

### Decision

Adopt Parameter Golf's discipline of reporting artifact size, fixed compute,
and tokenizer-agnostic compression metrics, but do not force the 0.5B Action
Model checkpoint into the 16 MB challenge. Maintain a separate scratch-model
and deployment Pareto track.

### Rationale

The 16 MB challenge is useful for architecture and compression experiments, but
the core research question requires a capable typed-action model and verified
execution. Treating the hard challenge limit as the only objective would
optimize away the model capability and protocol evidence we need.

## Checkpoint note: mid-training smoke (2026-07-25)

The first `action-midtrain/v0` run completed on the RTX 5090 and produced a
reproducible 0/8 validity and success result after one epoch over 16 synthetic
rows. This stage is retained as training-pipeline evidence only. It does not
justify replacing the generic checkpoint or claiming that domain-adaptive
training improves Action IR behavior.

## Checkpoint note: real factorial v2 (2026-07-25)

The corrected checkpoint-backed factorial completed all 32 model/harness task
evaluations. The cells scored 0.000 (generic/baseline), 0.750
(specialized/baseline), 0.375 (generic/advanced), and 0.625
(specialized/advanced), yielding interaction -0.500. Retain this as a
reproducible smoke result only: the specialized model is trained on eight
synthetic examples and the task suite is too small for a capability claim.
The result does establish that the real four-cell path, stateful verifier, raw
output capture, and interaction arithmetic are runnable together.

## Closure note: Project 1 prototype completion (2026-07-25)

Project 1 now satisfies its prototype completion bar: the typed Action IR,
stateful benchmark/verifier, training and evaluation scripts, real checkpoint
four-cell smoke experiment, model/data documentation, reproducibility runbook,
and defensible paper draft are all checked in and exercised. Closure does not
promote the synthetic checkpoint to a general capability claim. Independent
teacher/human trajectories, larger held-out tools, multiple seeds, quantized
deployment, and edge energy remain explicitly listed as follow-up research.

## Checkpoint note: malformed enum audit (2026-07-25)

The mid-training checkpoint evaluation found a second validator boundary bug:
an untrusted model output containing an object-valued `action.risk` raised a
Python `TypeError` during set membership instead of returning a protocol issue.
Enum checks for kind, recovery strategy, and risk now require strings before
membership tests, with regression coverage. The failed evaluation is retained
as a bug-finding event, not a model result.

## Checkpoint note: factorial verifier audit (2026-07-25)

The first real checkpoint factorial exposed a verifier bug: a structurally
valid `abstain` decision on a task expecting `finish` entered the finish-only
branch and raised `KeyError` instead of producing a scored failure. The
verifier now checks expected decision kind before kind-specific execution and
has a regression test. The interrupted factorial run is not evidence and must
be rerun from the corrected evaluator.
