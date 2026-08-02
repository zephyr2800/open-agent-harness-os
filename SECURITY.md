# Security policy

## Scope

The supported security boundary is the local developer-preview surface:

- registered tools only; no arbitrary shell execution;
- explicit authority and risk metadata for every enabled tool;
- independent tool verification and evidence-grounded completion;
- bounded steps, tokens, time, request bodies, trace size, and retention;
- loopback-only serving by default;
- bearer authentication plus TLS 1.2+ before non-loopback serving;
- per-principal trace namespaces and rolling request limits when token-file
  tenants are configured;
- bounded concurrent HTTP connections and per-connection read deadlines before
  authentication or request parsing;
- operator-owned canonical loopback model endpoints; HTTP callers cannot
  select model routing and adapter redirects are refused;
- replay validation that does not call a model or execute a tool handler.

This file does not certify a production deployment. Reverse-proxy policy,
identity lifecycle, secret rotation, distributed quotas, monitoring, network
segmentation, dependency updates, and a deployment-specific security review
remain the operator's responsibility.

The focused HTTP review and its fixed findings are recorded in
`docs/SECURITY_REVIEW_2026-08-02.md`.

## Reporting a vulnerability

Please do not disclose a suspected vulnerability in a public issue. Use a
private security-advisory channel on the project repository when available;
otherwise contact the project maintainer through the private distribution
channel and include a minimal reproduction, affected version, impact, and
whether the issue crosses an authority, trace-isolation, or replay boundary.

Do not include real credentials, private user data, or production traces in a
report. The maintainer should acknowledge receipt, reproduce in an isolated
environment, publish a remediation or mitigation, and credit reporters only
with their permission.

## Pre-release review

Before a public launch, run:

```powershell
python -m experiments.launch_preflight --with-tests
python -m unittest discover -s tests -q
```

Then review every enabled tool's authority, schema, preconditions, side
effects, verifier, model adapter, dependency provenance, and deployment
configuration. A passing local preflight is necessary but not sufficient for
public production readiness.
