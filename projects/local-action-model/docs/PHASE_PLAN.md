# Phased execution plan

Status: Phase 1 active; Phase 2 queued behind the Phase 1 exit gate.

This repository contains two related projects. They should not be optimized
independently: the model needs a stable harness contract to learn against, and
the harness needs a model whose outputs are measurable. The execution order is
therefore:

```text
M0 protocol and evaluator (complete)
        |
        v
Phase 1: Open Local Action Model (model-first)
        |
        | exit gate: a reproducible checkpoint emits valid Action IR and earns
        | independently verified held-out progress under the safety boundary
        v
Phase 2: Open Agent Harness OS (harness-first)
        |
        | exit gate: baseline and advanced harnesses are replayable, auditable,
        | and model-agnostic against the frozen Action IR
        v
Phase 3: integrated four-cell optimization and paper results
```

## Phase 0: freeze the measurement substrate (complete)

Keep the Action IR, task spec, replay format, stateful memory tools, independent
verifiers, and factorial arithmetic stable while model training is iterated.
Changes to the protocol or scoring require a new version and an explicit
decision record.

## Phase 1: small local action model

The immediate objective is to move the pinned Qwen2.5-0.5B baseline from its
observed `0/8` valid decisions to a model that can act, observe, abstain, and
finish through the same verified boundary. The first real checkpoint result is
already useful: it shows that a general chat checkpoint does not learn the
Action IR merely from an instruction prompt.

### Training ladder

1. **Stack probe and baseline.** Run the same pinned checkpoint on the RTX
   5090, record CUDA/dtype/peak VRAM/throughput, and preserve the CPU result as
   a cross-device reference. Do not change the task spec during this run.

2. **Scratch micro-model track (optional, not the core model).** Use a tiny
   Karpathy-style causal LM to prove the local pretraining/data/checkpoint loop
   and to explore the Parameter Golf tradeoff. This is a systems and scaling
   experiment, not a claim that a tiny scratch model replaces the open base
   checkpoint.

3. **Mid-training/domain adaptation.** Continue the open base model on a
   carefully deduplicated corpus of Action IR examples, tool schemas, concise
   tool documentation, state-transition descriptions, and valid/invalid
   protocol contrasts. The objective is next-token modeling of the local
   action domain, not conversational polish. Keep provenance and train/held-out
   task separation explicit.

4. **Post-training SFT.** Train on verified teacher trajectories rendered with
   the model's chat template. Include positive `act`/`observe`/`finish` examples
   and explicit `abstain`/recovery examples. Start with LoRA/PEFT for fast
   iteration; compare against one full-fine-tune control when the data path is
   stable.

5. **Preference optimization.** Convert verifier-backed chosen/rejected pairs
   into DPO-compatible data. Rejected examples must have a reason that an
   independent verifier can support: wrong tool, wrong arguments, premature
   finish, unsafe escalation, or failure to abstain. Synthetic pairs remain
   plumbing until replaced or audited by independent teacher/human data.

6. **Environment-grounded RL.** Only after SFT/DPO produces valid outputs and
   the reward is audited. Use the stateful evaluator as the environment and
   reward verified progress, correct abstention, protocol validity, and safe
   recovery. Penalize unapproved calls, false finish, invalid JSON, and reward
   hacking. The first RL experiment should be a short offline/online smoke run,
   not a long unconstrained search.

7. **Local deployment measurement.** Quantize only after a capable checkpoint
   exists, then measure model bytes, peak VRAM, prompt-plus-generation latency,
   output tokens, and verified task success together. This is the project
   equivalent of Parameter Golf: optimize the capability/size/latency Pareto
   frontier rather than treating compression as an isolated leaderboard.

### Phase 1 gates

Candidate checkpoints are promoted only when all of the following are recorded
from a pinned config and seed:

- no unapproved high/critical call and no false `verified` finish on held-out
  tasks;
- at least 95% protocol-valid outputs on the frozen eight-task smoke suite;
- at least 3/6 independently verified held-out task successes, including a
  correct abstention on the unknown-tool or permission-boundary cases;
- tokenizer-backed token counts, wall time, peak VRAM, and checkpoint size;
- a fresh run can reproduce the reported aggregate metrics from the repository
  instructions.

These are promotion gates, not the final scientific claim. The final claim
still requires multiple seeds, a larger held-out suite, and the four-cell
model-by-harness experiment.

## Phase 2: Open Agent Harness OS

Do not start broad harness construction until Phase 1 has a promoted candidate
and the model-facing Action IR is stable. Then implement the second project in
this order:

1. externalize the tool/permission/recovery policy as a versioned harness
   configuration;
2. implement baseline and advanced harnesses behind the same model adapter;
3. add replay, checkpoints, failure taxonomy, and independent verification for
   filesystem, browser/API, and local-device adapters;
4. make approval, rollback, retry, and abstention behavior observable without
   changing model outputs;
5. run harness-only tests before reintroducing model training.

The harness must remain the authority for authorization, execution, verification,
state persistence, and rollback. The model proposes a typed decision; it does
not gain permission by generating a convincing explanation.

## Phase 3: integrated result

Run the four cells with the same checkpoint, task splits, seeds, and measurement
fields:

| Model | Harness | Purpose |
| --- | --- | --- |
| generic | baseline | lower-bound reference |
| specialized | baseline | model contribution |
| generic | advanced | harness contribution |
| specialized | advanced | combined system |

Report verified success, protocol validity, correct abstention, safe recovery,
latency, output tokens, peak VRAM, artifact size, and the interaction term
`D - B - C + A`. Do not claim that a specialized model or a harness caused a
gain until the corresponding cell and interaction are measured.

## RTX 5090 run policy

The local machine reports an NVIDIA GeForce RTX 5090 with 32,607 MiB visible
VRAM, driver 595.79, and compute capability 12.0. The exact usable memory and
dtype behavior must be measured by the run manifest rather than assumed.

Use four lanes:

| Lane | Fixed budget | Purpose | Promotion metric |
| --- | ---: | --- | --- |
| smoke | 2-5 minutes | catch OOM, dtype, tokenizer, and verifier errors | completes with a manifest |
| search | 5 minutes per candidate | Karpathy/autoresearch-style comparable iteration | held-out verified score, then latency/VRAM tie-break |
| train | 30-120 minutes | run the selected mid/SFT/preference stage | loss plus Action IR metrics |
| RL | 15-60 minutes | short environment-grounded reward test | verified reward with safety penalties |

Every run records the git/config/model/data revisions, seed, stage, device,
dtype, tokens, steps, wall time, throughput, peak VRAM, losses, and verified
Action IR metrics. One experimental change is allowed per search candidate.

The core checkpoint is not required to fit the Parameter Golf 16 MB rule. We
will maintain a separate scratch-model challenge track with that rule's spirit:
model bytes, tokenizer bytes, inference cost, and Action IR verified score are
reported together. A compressed 0.5B adapter or quantized deployment artifact
can be compared on the practical local Pareto frontier without pretending it
is a compliant Parameter Golf submission.

## Research references used for this plan

- [Karpathy nanochat](https://github.com/karpathy/nanochat): cohesive
  tokenization, pretraining, SFT, evaluation, inference, and RL pipeline.
- [Karpathy autoresearch](https://github.com/karpathy/autoresearch): fixed-time,
  single-GPU, one-metric, reviewable experiment loop.
- [OpenAI Parameter Golf](https://github.com/openai/parameter-golf): hard
  artifact/compute constraint and tokenizer-agnostic bits-per-byte evaluation.
- [Hugging Face TRL](https://huggingface.co/docs/trl/en/index): SFT, DPO, GRPO,
  reward, and other post-training trainers.
- [Hugging Face PEFT LoRA](https://huggingface.co/docs/peft/main/package_reference/lora):
  adapter training for memory-efficient iteration.
- [Hugging Face dataset streaming](https://huggingface.co/docs/hub/en/datasets-streaming):
  progressive access to large training corpora.
