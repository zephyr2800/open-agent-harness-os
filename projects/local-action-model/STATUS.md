# Status

## Current clean 9B research branch - 2026-08-02

State: the Project 1 prototype remains complete at smoke level, while its
first clean, source-audited 9B QLoRA candidate is actively training. This is
an evidence-gathering branch, not a promoted checkpoint or a research result.

### Facts

- The active candidate uses 3,232 audited rows, one uniform full-coverage
  epoch, rank-128 4-bit QLoRA, gradient checkpointing, and a frozen evaluation
  protocol. Row weights exist in the curriculum but are intentionally inactive
  in this uniform baseline.
- The historical 9B matrix is context-only: it was rejected despite strong
  local trace/replay/safety checks because its source-corpus split was not
  auditable.
- The clean candidate must first complete a train/holdout audit and a
  three-seed stochastic promotion matrix. Native AgentDojo/tau2 evaluation and
  any verifier-backed RL are gated on that decision.
- A 27B NF4 QLoRA staged feasibility smoke is documented for the RTX 5090 but
  is queued behind the clean 9B chain. It must consume audited clean data and
  cannot be used to bypass an invalid or rejected baseline.

### Next steps

1. Preserve the active trainer source, dataset, and frozen evaluator until its
   manifest is emitted.
2. Record the promotion decision and failure-family evidence.
3. If rejected, choose a named remediation or the full-coverage
   uniform-versus-weighted order ablation; if promoted, run the registered
   native diagnostics before considering RL.
4. Only after a credible checkpoint result, run the real four-cell
   model-by-harness experiment with deployment and energy measurements.

## Current checkpoint — 2026-07-25

State: Project 1 prototype is complete at reproducible smoke level. M0 and the
Phase 1 model/evaluator slice are complete; broader research promotion still
requires independently reviewed data, a larger held-out suite, and edge-device
measurements. Phase 2 (Open Agent Harness OS) remains queued as the next
project.

### Facts

- The workspace started without a repository, source files, or `STATUS.md`.
- The first implementation uses Python standard-library modules only.
- Action IR v0 requires a schema id, task and step ids, one decision kind, uncertainty, and a typed state update.
- `act` decisions carry typed intent, arguments, preconditions, risk, expected effect, and escalation conditions.
- `finish` requires independent evidence and `verified: true`.
- Trajectory events carry monotonic sequence numbers and a parent digest for tamper detection.
- JSONL traces can be loaded without executing tools; malformed or tampered traces are rejected.
- The deterministic fixture benchmark contains action, inspection, abstention, and verified-finish cases.
- Each fixture declares its split, available tool surface, and output budget.
- The evaluator reports useful state transitions, successful actions, verified progress, and structured information density per estimated output token.
- The runtime boundary rejects unregistered tools, risk mismatches, and unapproved high-risk calls; handler output is separately verified.
- A versioned `action-task-spec/v0` JSON file now freezes eight tasks: two held-in and six held-out, including unknown-tool, permission, ambiguity, and recovery cases.
- The deterministic reference policy runs against the externalized eight-task file with 1.0 verified task success and 1.0 correct abstention rate.
- A provider-neutral `ModelRequest`/decision parser and `action-sft/v0` trajectory converter are available without a model framework.
- The evaluator CLI can run the frozen task spec as a whole or report held-in/held-out splits separately.
- A reproducible four-cell runner now separates generic/specialized policy fixtures from baseline/advanced harness fixtures and computes the interaction term.
- A pinned Apache-2.0 0.49B baseline candidate and lazy Transformers adapter are recorded; current runtime inspection found no `torch` or `transformers` installation.
- Deterministic in-memory write, read, and move tools now exercise actual state transitions with independent verifiers and safe-path checks.
- `eval.verified` now runs the reference policy through those stateful tools and separates protocol validity, execution, independent verification, and task success.
- The first real CPU inference of the pinned checkpoint loaded in about 26.6 seconds but emitted a plan-shaped object missing required Action IR fields; the adapter rejected it as invalid rather than executing it.
- A reusable `experiments.run_checkpoint` CLI now records per-task raw failures, input/output token counts, generation time, wall time, verifier evidence, and aggregate valid-action/success metrics.
- The pinned Qwen2.5-0.5B zero-shot sweep is recorded in `experiments/results/qwen2.5-0.5b-zero-shot-v0.{json,md}`: 0/8 valid Action IR decisions, 0/8 verified success, 1.0 protocol-error rate.
- One CPU epoch on the synthetic SFT fixture completed in 17.98 s with mean loss 1.0978, but post-training evaluation remained 0/8 valid and 0/8 verified; result is recorded in `experiments/results/qwen2.5-0.5b-sft-fixture-v0.{json,md}`.
- A deterministic bootstrap SFT generator now emits complete Action IR targets with explicit synthetic-oracle provenance; it is not treated as research evidence.
- `fixtures/training/action-sft-v0.jsonl` contains 8 generated examples and is covered by a regression test.
- A primary-source literature review now covers ReAct, Toolformer, TinyAgent, xLAM, Hammer, Agent Distillation, SWE-agent, Agentless, Granite function calling, and emerging irrelevance/abstention work, with a validation experiment per source.
- An architecture atlas and living paper draft now record capability placement, preliminary negative results, threats to validity, and next experiments.
- `data.preferences` and `train.generate_preferences` now produce verifier-oriented synthetic hard negatives for preference-optimization plumbing.
- `train.transformers_sft` now provides deterministic tokenization/label construction and a dry-run path before optional full fine-tuning.
- Pinned-tokenizer SFT dry-run: 8 examples; sequence lengths 328–360; mean 345.5 tokens; `sft-run/v0` report emitted successfully.
- CPU SFT smoke run is configured to use float32 explicitly; any resulting checkpoint will remain synthetic-fixture-only until held-out, independently verified evaluation is run.
- The execution order is now explicit in `docs/PHASE_PLAN.md`: model first,
  harness second, integrated four-cell experiment third.
- The local target reports an NVIDIA GeForce RTX 5090 with 32,607 MiB visible
  VRAM, driver 595.79, and compute capability 12.0. The phase config records
  this observation and requires a dtype/memory probe before promotion.
- The Phase 1 run manifest is frozen in `experiments/configs/phase1-5090-v0.json`.
- The reproducibility runbook is frozen in `docs/REPRODUCIBILITY.md`, including
  clean-environment core checks, CUDA 12.8 setup, staged training, and the real
  factorial command.
- Research inputs now include Karpathy's `nanochat` stage separation,
  `autoresearch` fixed-time single-GPU loop, Hugging Face TRL/PEFT/data
  streaming, and the OpenAI Parameter Golf constraint track.
- The Parameter Golf track is explicitly local and non-leaderboard: its
  official 16 MB, 10-minute-on-8xH100, FineWeb bits-per-byte benchmark is
  distinct from this RTX 5090 Action IR deployment-Pareto objective.
- The first real RTX 5090 sweep is recorded in
  `experiments/results/qwen2.5-0.5b-5090-zero-shot-v0.{json,md}`: PyTorch
  2.11.0+cu128/CUDA 12.8/BF16, 4,737.1 ms load, 3,440.3 ms mean task wall
  time, 842 output tokens, 0/8 valid Action IR decisions, and 0/8 verified
  successes. This matches the CPU negative result on validity/success while
  adding a working Blackwell GPU path.
- The first RTX 5090 SFT fixture cycle is recorded in
  `experiments/results/qwen2.5-0.5b-sft-5090-fixture-v0.md` and adjacent JSON
  manifests: five epochs on eight synthetic examples reduced the protocol
  error rate to 0.0, reached 6/8 overall and 4/6 held-out verified task
  successes, used 4,884.0 MiB peak training VRAM, and trained in 5,218.7 ms.
  This is a pipeline/plumbing result only because the targets are synthetic.
- A real checkpoint-backed four-cell factorial runner now exists at
  `experiments/checkpoint_factorial.py`; its first corrected run is recorded in
  `experiments/results/checkpoint-factorial-v2.{json,md}`. Generic/baseline,
  specialized/baseline, generic/advanced, and specialized/advanced scored
  0.000, 0.750, 0.375, and 0.625 verified task success respectively; the
  preliminary interaction was -0.500. The specialized checkpoint is synthetic
  fixture-only, so this is reproducible smoke evidence rather than an
  independent capability claim.

### Inferences

- Freezing the protocol before training makes later model comparisons less vulnerable to changing output contracts.
- A dependency-free validator is a useful compatibility anchor for local and edge runtimes.

### Hypotheses

- Explicit state and uncertainty fields will reduce invalid-action and premature-finish rates relative to unconstrained text output.
- A typed action IR will make token and recovery measurements easier to reproduce.

### Verification

- `python -m unittest discover -s tests -v`: 23 tests passed after adapter and SFT additions.
- `python -m eval.benchmark`: 4/4 reference tasks succeeded; valid decision rate 1.0; invalid action rate 0.0; token-efficiency metrics are emitted using a documented proxy.
- `python -m train.prepare_sft --input fixtures/trajectories/reference-abstention.jsonl --output <temporary-jsonl>`: converted 1 example successfully.
- `python -m eval.benchmark --task-spec fixtures/tasks/task-spec-v0.json --split held_out`: 6/6 reference tasks succeeded; valid decision rate 1.0; correct abstention rate 1.0.
- `python -m eval.benchmark --task-spec fixtures/tasks/task-spec-v0.json`: 8/8 reference tasks succeeded; held-in 2/2; held-out 6/6; valid decision rate 1.0; invalid action rate 0.0.
- `python -m experiments.factorial --task-spec fixtures/tasks/task-spec-v0.json`: all four cells ran; generic/baseline 0.25, specialized/baseline 1.0, generic/advanced 0.375, specialized/advanced 1.0; fixture interaction −0.125.
- `python -m unittest discover -s tests -v`: 25 tests passed, including factorial arithmetic and all-cell coverage.
- `python -m unittest discover -s tests -v`: 33 tests passed after the pinned-checkpoint and verified-evaluator additions.
- `evaluate_verified(reference_policy, task_spec)`: 8/8 verified task success; protocol-valid rate 1.0; independent-verification rate 1.0; stateful action-execution rate 0.5.
- `TransformersActionPolicy()` fails clearly with `TransformersBackendUnavailable` and the optional install command; no checkpoint inference has been claimed.
- Pinned CPU inference was attempted from the isolated runtime; model output was captured and rejected by protocol validation, so no task success is reported.
- Full cached sweep: 8 tasks; 833 output tokens; 3319.3 ms load; 3750.1 ms mean wall time per task.
- `python -m unittest discover -s tests -v`: 37 tests passed after phase-plan,
  GPU instrumentation, and synthetic SFT updates.
- RTX 5090 CUDA probe: `torch 2.11.0+cu128`, CUDA 12.8, one device,
  capability `(12, 0)`, BF16 supported, and a BF16 CUDA matmul completed.
- RTX 5090 zero-shot sweep: 8 tasks; 842 output tokens; 4737.1 ms load;
  3440.3 ms mean wall time; 0/8 valid; 0/8 verified success.
- RTX 5090 synthetic SFT/evaluation: 5 epochs, 13820 training tokens,
  5218.7 ms train time, 4884.0 MiB peak training VRAM; 8/8 valid and 6/8
  verified success overall, including 4/6 held-out.
- `python -m unittest discover -s tests -v`: 42 tests passed after the
  checkpoint factorial, mid-training, reward, and validator-hardening slices.
- `train.rl_smoke --task-spec fixtures/tasks/task-spec-v0.json`: 8/8 chosen
  rewards beat their declared hard negatives; mean chosen reward 1.0 and mean
  rejected reward -0.5625.
- Real checkpoint factorial v2: 42 tests passing; all four cells completed with
  stateful verification, raw output capture, tokenizer-backed token counts,
  wall/generation timing, and peak VRAM. The first attempt exposed and fixed a
  wrong-kind verifier `KeyError`; the corrected run completed 32 task-cell
  evaluations.
- Factorial v2 records task-spec SHA-256
  `06960a114620b801d6a80eab6a29565eb7fd6e1789298a6f0cfeb11fa7f136b7`,
  PyTorch `2.11.0+cu128`, CUDA `12.8`, RTX 5090, BF16 support, greedy
  generation, and seed `0`.
- The synthetic Action IR mid-training path is now runnable through
  `train.generate_midtrain` and `train.transformers_midtrain`. A one-epoch RTX
  5090 smoke run over 16 rows trained in 3,002.9 ms with 4,822.3 MiB peak
  training VRAM, then evaluated at 0/8 valid and 0/8 verified success. It is
  recorded as a negative pipeline result in
  `experiments/results/qwen2.5-0.5b-midtrain-5090-v0.md`.
- `train.transformers_dpo` now validates preference rows and exposes an
  optional TRL + PEFT LoRA/DPO trainer; its synthetic 8-pair dry-run completed.
- `eval.reward.reward_decision` and `train.rl_smoke` now define and calibrate
  the verifier-backed RL reward: mean chosen reward 1.0, mean rejected reward
  -0.5625, and chosen > rejected on 8/8 synthetic pairs. This is reward
  calibration only; no online RL claim is made.

### Next steps

1. For a stronger research release, replace synthetic-only SFT/mid-training/
   preference data with verifier-backed teacher/human-reviewed data. The
   prototype deliberately does not claim this work is complete.
2. Run DPO/LoRA only after independent preference data is available, followed
   by a short
   audited environment-grounded RL smoke run.
3. Expand the held-out tool/state suite and rerun the corrected four-cell
   experiment across multiple seeds.
4. Use the completed Project 1 checkpoint as the input contract for Project 2's
   broader harness implementation; keep the Action IR and task-spec versions
   explicit when that next project starts.

## Latest RTX 5090 staged run — 2026-07-25

The local training sequence completed as continued pretraining, Action IR
mid-training, SFT, LoRA/DPO, merged checkpoint evaluation, and verifier-backed
REINFORCE. The final checkpoint scored 8/8 valid and 8/8 verified on the current
eight-task Project 1 suite. The complete measured report is recorded in
`experiments/results/training-pipeline-5090-v1.{json,md}`.

This remains a reproducible engineering baseline, not a research breakthrough:
the continued-pretraining corpus is a mixed TinyStories/protocol corpus, all
Action IR SFT/preferences/RL rows are synthetic reference-policy data, and the
eight-task suite is too small for a generalization or product-launch claim.

The QLoRA SFT runner now supports periodic `training_progress.json` sidecar
manifests via `--progress-every N` (default 50, or `0` to disable). This makes
long consumer-GPU runs observable before the final adapter and training
manifest are written; it does not change the current 9B run, which was started
before this option was added.
## 5090 scaling controls — 2026-07-26

The QLoRA SFT entry point now exposes optional activation checkpointing and
gradient accumulation. These controls are intended for the post-matrix
larger-model branch (including a 27B-class 4-bit feasibility experiment) and
are recorded in the training manifest when used. The change is backward
compatible with the existing rank-64 9B run. The module compiles, its dry-run
reports both controls, and the Project 1 test suite passes 43/43.

`docs/QWOPUS35_27B_FEASIBILITY.md` now freezes the staged maximum-scale
experiment: 4-bit NF4 QLoRA, rank-16 first, activation checkpointing,
micro-batch 1, accumulation 8, and an eight-step memory/loss smoke before any
full run. It is queued behind the active 9B evaluation and is not auto-started
on the single GPU.
