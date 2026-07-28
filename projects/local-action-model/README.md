# Open Local Action Model

This repository is an open research prototype for a small local Action IR
policy. It freezes the model-facing protocol, stateful verifier, staged
training interfaces, and model-by-harness measurements before making a
capability claim.

## M0 quick start

The M0 code uses only the Python standard library. From this directory:

```text
python -m unittest discover -s tests -v
python -m eval.benchmark
python -m eval.benchmark --task-spec fixtures/tasks/task-spec-v0.json --split held_out
python -m experiments.factorial --task-spec fixtures/tasks/task-spec-v0.json
python -m experiments.run_checkpoint --task-spec fixtures/tasks/task-spec-v0.json --revision 7ae557604adf67be50417f59c2c2f167def9a775
python -m train.transformers_sft --train-jsonl fixtures/training/action-sft-v0.jsonl --revision 7ae557604adf67be50417f59c2c2f167def9a775 --dry-run
python -m train.generate_midtrain --task-spec fixtures/tasks/task-spec-v0.json --output work/action-midtrain-v0.jsonl
python -m train.transformers_midtrain --train-jsonl work/action-midtrain-v0.jsonl --revision 7ae557604adf67be50417f59c2c2f167def9a775 --dry-run
python -m train.transformers_dpo --preferences work/action-preferences-v0.jsonl --revision 7ae557604adf67be50417f59c2c2f167def9a775 --dry-run
```

The protocol is intentionally narrow. A model emits one of `act`, `observe`,
`abstain`, or `finish`; the harness remains responsible for authorization,
execution, verification, state persistence, and rollback.

`runtime.ToolRegistry` is the first executable version of that boundary. It
rejects unregistered tools, mismatched risk declarations, and unapproved
high-risk calls. A handler result is not considered successful unless its
independent verifier returns true.

The evaluator is a smoke benchmark for regression testing, not evidence that a
model is capable. It keeps task definitions, available tools, splits, and
scoring fixed while policies change. It reports success, validity, abstention,
and transparent protocol-density metrics. Checkpoint runners use the tested
model tokenizer for token counts and record wall time, peak VRAM, raw outputs,
and independent verifier outcomes.

The model adapter accepts a `ModelRequest` and validates JSON responses against
the requested Action IR schema and available tool surface. The SFT converter
preserves request/decision pairs without assuming a particular tokenizer or
training framework.

## Layout

- `action_ir/`: Action IR v0 validation, canonical digests, and trajectory lineage.
- `eval/`: deterministic tasks and evaluator.
- `runtime/`: explicit tool registry, risk gate, and independent verifier boundary.
- `runtime/memory_tools.py`: deterministic in-memory file tools used for verifier-backed tests.
- `eval/verified.py`: stateful evaluation that executes supported actions and checks independent evidence.
- `fixtures/`: checked-in replayable JSONL trajectories and versioned task specs.
- `model/`: provider-neutral request and JSON decision adapter.
- `data/`: trajectory-to-SFT JSONL conversion.
- `train/`: SFT, synthetic mid-training, preference/DPO dry-run, and optional model-training backends.
- `docs/DATA_PROVENANCE.md`: synthetic-fixture warning and required provenance fields.
- `docs/LITERATURE_REVIEW.md`: primary-source facts, inferences, hypotheses, and validation experiments.
- `docs/ARCHITECTURE_ATLAS.md`: capability-placement candidates and rejection criteria.
- `docs/PAPER_DRAFT.md`: living paper draft with preliminary negative results.
- `docs/PREFERENCE_TRAINING.md`: hard-negative and preference-pair contract.
- `docs/REPRODUCIBILITY.md`: clean-environment, staged-training, and four-cell runbook.
- `experiments/`: fixture and real checkpoint-backed four-cell model × harness runners and configurations.
- `tests/`: protocol, replay, and evaluator tests.
- `docs/`: research notes and architecture decisions.
- `STATUS.md`, `DECISIONS.md`, `CHANGELOG.md`: checkpoint records.
