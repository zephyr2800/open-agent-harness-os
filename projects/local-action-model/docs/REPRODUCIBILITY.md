# Reproducibility runbook

The checked-in protocol, evaluator, fixtures, and factorial arithmetic run on
Python 3.10+ with the standard library. Model experiments add the optional
Transformers stack. All model ids, revisions, task specs, seeds, and output
paths below are versioned or explicit.

## Core checks

From the repository root:

```text
python -m unittest discover -s tests -v
python -m eval.benchmark --task-spec fixtures/tasks/task-spec-v0.json
python -m eval.benchmark --task-spec fixtures/tasks/task-spec-v0.json --split held_out
python -m experiments.factorial --task-spec fixtures/tasks/task-spec-v0.json
```

The fixture factorial is plumbing evidence. The real checkpoint factorial is
the result under `experiments/results/checkpoint-factorial-v2.{json,md}`.

## Optional model environment

Install the repository and model dependencies in a clean environment:

```text
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e ".[transformers]"
```

For an RTX 5090/Blackwell device, use a PyTorch build with CUDA 12.8 or newer.
The recorded run used `torch==2.11.0+cu128`, `transformers==4.57.6`, and
BF16. Verify the device before loading a checkpoint:

```text
.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0), torch.cuda.is_bf16_supported())"
```

The model snapshot is pinned to
`7ae557604adf67be50417f59c2c2f167def9a775`. Set `HF_HOME` to a controlled cache
and use offline mode after the snapshot has been fetched when exact replay is
required.

## Staged training smoke

Generate the explicitly synthetic fixtures:

```text
.venv\Scripts\python.exe -m train.generate_reference_sft --task-spec fixtures/tasks/task-spec-v0.json --output fixtures/training/action-sft-v0.jsonl
.venv\Scripts\python.exe -m train.generate_midtrain --task-spec fixtures/tasks/task-spec-v0.json --output work/action-midtrain-v0.jsonl
.venv\Scripts\python.exe -m train.generate_preferences --task-spec fixtures/tasks/task-spec-v0.json --output work/action-preferences-v0.jsonl
.venv\Scripts\python.exe -m train.rl_smoke --task-spec fixtures/tasks/task-spec-v0.json --output work/rl-reward-smoke-v0.json
```

Run dry-runs before allocating GPU time:

```text
.venv\Scripts\python.exe -m train.transformers_sft --train-jsonl fixtures/training/action-sft-v0.jsonl --revision 7ae557604adf67be50417f59c2c2f167def9a775 --dry-run
.venv\Scripts\python.exe -m train.transformers_midtrain --train-jsonl work/action-midtrain-v0.jsonl --revision 7ae557604adf67be50417f59c2c2f167def9a775 --dry-run
.venv\Scripts\python.exe -m train.transformers_dpo --preferences work/action-preferences-v0.jsonl --revision 7ae557604adf67be50417f59c2c2f167def9a775 --dry-run
```

The optional DPO command requires `pip install -e ".[post-training]"` for
actual training and uses TRL + PEFT LoRA. Do not treat synthetic adapters as
independent research evidence.

The recorded synthetic SFT smoke used the following GPU command:

```text
.venv\Scripts\python.exe -m train.transformers_sft --train-jsonl fixtures/training/action-sft-v0.jsonl --revision 7ae557604adf67be50417f59c2c2f167def9a775 --output-dir work/action-model-sft-5090-v0 --epochs 5 --batch-size 1 --learning-rate 1e-5 --max-length 512 --device cuda --seed 0
```

## Real four-cell smoke

After producing a specialized checkpoint, run:

```text
.venv\Scripts\python.exe -m experiments.checkpoint_factorial --task-spec fixtures/tasks/task-spec-v0.json --generic-model-id Qwen/Qwen2.5-0.5B-Instruct --generic-revision 7ae557604adf67be50417f59c2c2f167def9a775 --specialized-model-id work/action-model-sft-5090-v0 --specialized-revision main --max-new-tokens 128 --output work/checkpoint-factorial-v0.json
```

The runner loads each model once, executes baseline and advanced harness cells,
uses the stateful independent verifier, records raw outputs and hardware
measurements, and computes `D - B - C + A`. A result using synthetic training
data must carry that limitation into any paper or model card.

## Data boundary

`fixtures/` and the current `work/` checkpoints are development artifacts. A
research release requires independently reviewed teacher or human trajectories,
source/license/filtering records, train/validation/held-out tool splits, and
reward-hacking tests. See `docs/DATA_PROVENANCE.md` and
`docs/PREFERENCE_TRAINING.md` before promoting a checkpoint.
