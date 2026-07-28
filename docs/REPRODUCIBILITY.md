# Reproducibility

From this directory:

```powershell
$py = 'python'
& $py -m unittest discover -s tests -v
& $py -m experiments.factorial --task-spec benchmarks/fixtures/task-spec-v0.json --output experiments/results/factorial-v0.json
& $py -m verify.independent experiments/results/factorial-v0.json --task-spec benchmarks/fixtures/task-spec-v0.json --output experiments/results/independent-verification-v0.json
```

The task specification is externalized at
`benchmarks/fixtures/task-spec-v0.json`. The factorial JSON records its
SHA-256, all ten cells, all task outcomes, metrics, and the interaction term.
The current fixture produces 80 task-cell traces; the independent report
checks trace validity, held-in/held-out completion, and runtime agreement
without executing tool handlers.

To validate a captured trace:

```powershell
& $py -m traces.replay path\to\trace.jsonl
```

Replay validates JSON, event type, sequence, task identity, and parent
digests. It does not call a model or execute a tool.

The current package deliberately has no third-party runtime dependencies. The
optional GPU/local-model adapter records model identity, tokenizer, decoding
configuration, device, dtype, seed, and software versions in the run manifest.
`adapters.http.OpenAICompatibleAdapter` is available for a running local
OpenAI-compatible endpoint; invoking it is intentionally separate from the
deterministic fixture command.

When the Project 1 optional Transformers dependencies and checkpoint are
available, run the actual paired-model path with:

```powershell
& $py -m experiments.project1_transformers_run --project1-root ..\local-action-model --model-id Qwen/Qwen2.5-0.5B-Instruct --revision 7ae557604adf67be50417f59c2c2f167def9a775
```

That command records the model id, revision, protocol failures, verified
successes, metrics, and raw replayable traces. It is intentionally not run by
the dependency-free fixture test suite.

For the matched Project 1 task specification and the local SFT checkpoint:

```powershell
& $py -m experiments.project1_task_run --project1-root ..\local-action-model --task-spec ..\local-action-model\fixtures\tasks\task-spec-v0.json --checkpoint ..\work\action-model-sft-5090-p2 --variant H3 --output experiments/results/project1-sft-5090-h3-v0.json
```

