# Focused HTTP Security Review - 2026-08-02

Status: fixed findings verified in the local developer-preview source tree.
This is a focused code and regression review, not a production-security
certification or a substitute for deployment-specific penetration testing.

The fresh source-bound `experiments/results/launch-preflight-v36.json` includes
this record in its required release documentation and records the complete
214-test Project 2 suite (one Windows capability skip).

## Scope

- HTTP listener, authentication, tenant trace isolation, rate limiting, and
  TLS setup in `app/cli.py`;
- local OpenAI-compatible model adapter in `adapters/http.py`;
- exposed registered in-memory tools and user-facing security documentation.

## Findings and remediation

| ID | Severity | Finding | Remediation | Regression coverage |
|---|---|---|---|---|
| HTTP-01 | High | An authenticated `/run` caller could previously choose `model_endpoint` and `model`, allowing server-side requests to arbitrary loopback routes through URL path/query/fragment tricks. | Model endpoint and identity are now operator-owned `serve` settings. HTTP callers cannot override them; accepted endpoints are canonical loopback root or `/v1` URLs and redirects are refused. | `test_product_model_endpoint_is_loopback_only`, `test_product_http_rejects_client_selected_model_routing`, `test_product_model_adapter_refuses_redirects` |
| HTTP-02 | High | The threaded listener previously had no pre-auth connection cap or socket read deadline, permitting slow partial requests to consume workers. | `BoundedThreadingHTTPServer` limits concurrent connections and applies a per-connection deadline before request parsing; excess sockets are closed. TLS handshakes run in the bounded worker path. | `test_product_http_connection_cap_and_deadline_release_capacity`, server-security argument validation |

## Current boundary

The harness remains loopback-only by default. Non-loopback binding still
requires explicit opt-in, bearer authentication, and TLS 1.2+. The local
connection controls constrain accidental or low-scale abuse but do not replace
a maintained reverse proxy/API gateway, distributed quota system, identity
lifecycle, certificate rotation, monitoring, network segmentation, dependency
maintenance, or a deployment-specific security review.

No claim is made that all adapters, tools, model servers, network paths, or
customer deployments are secure. The review establishes only that these two
identified HTTP paths fail closed in the current developer-preview source.
