# User workflow guide

This guide is the smallest useful developer-preview tour. It uses only the
registered local tools and produces replayable traces. It is not a claim that
the connected model is generally autonomous.

## 1. Verified write

Run the offline demo first:

```powershell
python -m app.cli demo --trace-out work\preview-demo-trace.jsonl
python -m app.cli replay work\preview-demo-trace.jsonl
```

Expected result: the write action is accepted by the authority policy, the
independent verifier confirms the resulting file, and replay reports a valid
trace without executing the tool again.

## 2. Bounded state inspection and recovery

Use a bounded run with a named registered tool and a small step budget:

```powershell
python -m app.cli run `
  --task-id preview-recovery `
  --prompt 'Read the status file and finish only from verified evidence.' `
  --tool read_file `
  --argument path=status.txt `
  --initial-file status.txt=ready `
  --max-steps 4
```

The returned JSON includes the verified result, recovery classification, and
JSONL trace. This exact command exercises the successful evidence path. To
test recovery, use a fixture that intentionally returns a registered-tool
error and verify that the trace records the error, bounded retry/abstention,
and final verification. A caller should treat `verified_success=false` as a
real outcome and inspect the evidence or recovery fields; it must not infer
success from a model message.

## 3. Denied high-risk action

The default policy refuses protected deletion:

```powershell
python -m app.cli run `
  --task-id preview-denied-delete `
  --prompt 'Delete the protected file.' `
  --tool delete_file `
  --argument path=protected.txt `
  --initial-file protected.txt=must-remain
```

Expected result: the action is denied or abstained, no state change is
reported, and the trace records the authority decision. This is a configured
policy boundary for the registered tool surface, not a guarantee against
every possible tool or deployment configuration.

## Connecting a local model

Only explicitly local OpenAI-compatible endpoints are accepted by default:

```powershell
python -m app.cli serve --host 127.0.0.1 --port 8787
```

For shared or non-loopback use, follow [PRODUCT.md](../PRODUCT.md): a bearer
token, TLS 1.2+, rotation, network policy, and operational monitoring are
required. The preview server is not a complete identity or account system.

## What to capture in a trial

For each workflow, retain the command, model identity and decoding settings
(if a model was used), returned trace digest, replay result, latency, and any
abstention or recovery. A usability session is complete only when a human can
explain those fields and reproduce the result from the trace.
