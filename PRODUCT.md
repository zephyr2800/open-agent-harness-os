# Local product candidate

The launch candidate is a local-first execution service around the same
authority, verifier, and trace contracts used by the research harness.

## CLI

```powershell
$py = 'python'
& $py -m app.cli tools
& $py -m app.cli demo --trace-out work\demo-trace.jsonl
& $py -m app.cli replay work\demo-trace.jsonl
& $py -m app.cli run --task-id api-demo --prompt 'Read the health endpoint.' --tool api_get --argument endpoint=/health
```

To connect a local Ollama/vLLM/llama.cpp-compatible endpoint, add
`--model-endpoint http://127.0.0.1:11434 --model <model-name>`. The service
accepts only loopback model endpoints by default.

## Local API

Start only on loopback by default:

```powershell
& $py -m app.cli serve --host 127.0.0.1 --port 8787
```

Non-loopback binding is rejected unless `--allow-non-loopback` is explicit and
an at-least-16-character bearer token is supplied with `--auth-token` or
`HARNESS_AUTH_TOKEN`, together with `--tls-certfile` and `--tls-keyfile`.
Configured servers require that token on every request; non-loopback serving
therefore cannot expose bearer credentials over plaintext HTTP. Local-only
serving remains the default and may stay HTTP for development.

For a small shared deployment, `--auth-token-file <path>` accepts a JSON object
mapping principal names to bearer tokens. Retained traces are then stored under
opaque per-principal namespaces: users can list and read their own traces but
cannot enumerate or fetch another principal's trace digest. This is tenant
namespacing, not a complete identity, distributed rate-limit, or account-management
system.

For a non-loopback deployment, provide a certificate chain and private key in
PEM format:

```powershell
& $py -m app.cli serve --host 0.0.0.0 --port 8787 `
  --allow-non-loopback --auth-token $env:HARNESS_AUTH_TOKEN `
  --tls-certfile .\certs\server-chain.pem --tls-keyfile .\certs\server-key.pem
```

TLS is enforced at TLS 1.2 or newer. Production deployments should still put
the service behind a maintained reverse proxy, certificate rotation, network
policy, and an operational audit.

Authenticated HTTP requests are bounded by a rolling per-principal rate limit
(120 requests per minute by default; configure with
`--rate-limit-per-minute`). The server returns `429` with `Retry-After` when
the limit is exceeded. This is a local protection against accidental or
unbounded use, not a replacement for production API-gateway quotas,
distributed rate limiting, or account-level abuse monitoring.

Endpoints are `GET /health`, `GET /tools`, `GET /traces`, `GET /traces/<sha256>`,
`POST /run`, and `POST /replay`.
The API is intentionally small: `/run` accepts a named registered tool and
arguments, then returns verified status plus the replayable JSONL trace.
`POST /run` may also include `model_endpoint` and `model` for a loopback
OpenAI-compatible model, and `initial_files` for a bounded workspace fixture.
Start the server with `--trace-dir <directory>` to enable bounded,
content-addressed trace retention. `/run` accepts `max_steps` 1â€“8,
`timeout_seconds` 0.1â€“30, and `token_budget` 64â€“10,000; every JSON response
advertises `open-agent-harness-api/v1` and the `X-Harness-API-Version: 1`
header.

## Product boundary

- The service never exposes arbitrary shell execution.
- High-risk deletion remains denied under the default sandbox authority.
- Tool outputs are independently verified before completion is reported.
- Trace validation does not call models or tool handlers.
- Retained traces are validated before storage, addressed by SHA-256, and
  bounded by size/count policy.
- Retained traces are atomically published; restart and 12-way concurrent
  writer coverage passes in the source test suite.
- Token-file tenants receive isolated trace namespaces, with cross-tenant read
  rejection covered by the launch preflight.
- Run budgets and request bodies are bounded before execution.
- The demo policy is an offline smoke path, not a claim of autonomous model
  capability; connect `adapters.http.OpenAICompatibleAdapter` only when a
  local model endpoint is explicitly configured.

This is a credible developer-preview surface. A general public launch still
requires user studies, full multi-user identity/operations, real-model reliability, and a
security/licensing review; non-loopback serving now has an explicit
authentication-plus-TLS gate.

Run the consolidated source-checkout gate with
`python -m experiments.launch_preflight --with-tests`. Its recorded result is
`experiments/results/launch-preflight-v4.json`; it verifies the local preview
surface and intentionally does not certify public multi-user deployment.

## MCP stdio integration

The same verification kernel is available as a local MCP server:

```powershell
& $py -m app.cli mcp
```

It implements the MCP initialize handshake plus `tools/list` and `tools/call`
for `harness_run`, `harness_tools`, and `harness_replay`. The server has no
network listener. Every `harness_run` remains subject to the registered tool
surface, authority policy, independent verifier, bounded trace, and replay
checks used by the CLI and HTTP API.

Example client configuration:

```json
{
  "mcpServers": {
    "open-agent-harness": {
      "command": "python",
      "args": ["-m", "app.cli", "mcp"]
    }
  }
}
```

An earlier informal ablation recorded 7/11 verified successes for the trained
0.5B model and 11/11 with the repair kernel. That number is retained as
historical context only; the corrected strict runner below supersedes it.

### Corrected strict launch evidence

The preceding informal 7/11 figure is superseded by the reproducible strict
runner. With exact action-argument and final-artifact checks, the same Project
2 SFT v2 checkpoint scores 4/11 model-only versus 11/11 with verifier-first
repair on research-v1. On the separately authored 12-task research-v2
holdout, it scores 5/12 model-only versus 12/12 with repair. All traces replay
independently with 1.0 validity and 1.0 runtime/replay agreement.

This strengthens the developer-preview case: the product kernel is useful
even when the local model is imperfect, and it refuses unsupported or
high-risk actions. It still does not justify a public autonomous-agent claim;
production authentication/TLS, multi-user isolation, user studies, external
benchmark comparisons, and security review remain launch gates.

