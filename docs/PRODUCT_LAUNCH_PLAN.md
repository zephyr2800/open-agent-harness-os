# Product launch plan

## Current decision

The evidence favors a local developer-preview product over claiming a model
breakthrough. The product value is verifiable local execution: a user can ask
for a registered action, receive independently checked output, and retain a
tamper-evident trace for replay.

## Distribution split

The launch boundary is now explicitly two-track:

1. **Public harness track:** ship the Apache-2.0 harness source/wheel, typed
   Action IR, registered tools, verifier/replay plane, documentation, and
   bring-your-own-model adapter. Do not bundle Qwopus weights, distilled
   traces, benchmark assets, or uncleared training data.
2. **Internal research track:** keep the Qwopus3.5-9B checkpoint, adapters,
   remediation curricula, and RL artifacts private until upstream model,
   dataset, tokenizer, dependency, and intended-distribution review is signed
   off by a human owner.

This split allows the harness product gates to be closed independently while
preserving the research checkpoint's provenance boundary. A public harness
release must still pass identity/operations, usability, security, and
external-evaluation gates; the split is not a waiver of those requirements.

## Delivered slice

- `python -m app.cli demo` offline smoke workflow;
- `tools`, `run`, and `replay` CLI commands;
- loopback-only HTTP API at `/health`, `/tools`, `/run`, and `/replay`;
- optional loopback OpenAI-compatible model endpoint;
- no arbitrary shell execution;
- default denial of high-risk delete;
- typed Action IR and independently verified tool output;
- JSONL trace returned from every run.
- wheel build and clean extracted-package demo smoke test.
- versioned API response schema and loopback-only model endpoint policy;
- bounded content-addressed trace retention;
- atomic trace publication with restart and concurrent-writer regression
  coverage;
- explicit per-run step, timeout, token, and request-size limits.
- OpenAI-compatible model calls cap their socket timeout to the harness-owned
  per-decision budget, with regression coverage for the budget boundary.
- authenticated per-principal rolling request-rate limit with `429`/
  `Retry-After` behavior and preflight coverage.
- loopback bind guard with an explicit opt-in for authenticated, TLS-protected
  non-loopback serving.

## Launch gates

- package installation and clean-machine smoke test;
- authenticated or explicitly local-only endpoint policy (non-loopback now
  requires a bearer token plus TLS 1.2+; loopback remains the default);
- user-facing task templates and error recovery;
- persistence/retention policy validation under restart and concurrent use;
- token-principal trace namespace isolation;
- performance/resource report under a real local model;
- usability testing with at least three representative workflows;
- security review of every enabled tool and adapter.

The current slice is therefore launch-candidate infrastructure, not a public
product launch. It is intentionally honest about the remaining gates.

The completed 9B frozen matrix records per-task latency, total wall time,
Python and CUDA versions, device identity, and peak allocated/reserved GPU
memory alongside correctness and replay data. The quantized-serving smoke adds
an RTX 5090 memory/timing baseline. Broader deployment-cost measurement across
the external suite and representative workflows remains open.

The current wheel (`open_agent_harness_os-0.1.8-py3-none-any.whl`) was built
from a fresh clean source copy, matched to the current complete archive
manifest, package-module digest, and console-script manifest, installed into a
fresh target directory without dependencies, and passed `python -m app.cli
demo` with verified success. This closes the packaging smoke gate for the
developer preview; it does not close multi-user isolation, production
operational, security-review, or external-agent benchmark gates.

The current consolidated source-checkout preflight is recorded at
`experiments/results/launch-preflight-v34.json`. It passes the six-case product
 smoke, MCP contract and replay, local-only endpoint policy, bearer
 authentication, high-risk denial, persistence, wheel integrity,
launch-document presence, the non-loopback token-plus-TLS gate, tenant trace
isolation, tool-by-tool security metadata auditing, the external evaluation
note and fixture. At artifact creation, the Project 2 source suite had 82
tests and the recorded v5 preflight artifact contains an 83-test subcheck.
The historical source-bound v9 preflight contains a 137-test subcheck; the
historical v11 preflight contains a 150-test subcheck; the historical v12
preflight contains a 151-test subcheck; the historical v13 preflight contains
a 154-test subcheck; the historical v32 preflight contains a 191-test subcheck;
the current v34 preflight contains a 210-test subcheck (one Windows
symlink-capability skip). The
preflight deliberately reports its scope as `local-developer-preview`; public
launch gates remain separate.

The 2026-07-27 timeout-boundary artifact recorded Project 2 source tests at
81/81 and Project 1 source tests at 47/47; those are historical artifact
counts. The current suites are 210 total (209 passed; one Windows
symlink-capability skip) and 47/47, respectively, and the
consolidated launch preflight remains green. This closes the adapter-level
budget-enforcement regression; it does not by itself close real-model
performance, usability, security-review, licensing, or external-benchmark
gates.

## Latest candidate evidence

The current source and wheel both pass the offline demo/replay smoke. The
source and extracted wheel also pass the MCP stdio initialize/tools-list smoke
with protocol `2025-06-18`. The strict research package records 4/11 versus
11/11 on research-v1 and 5/12 versus 12/12 on the independent research-v2
holdout for model-only versus model-plus-repair conditions, respectively.

This supports a local developer-preview launch to technically capable users.
It does not close the public-launch gates above: multi-user isolation,
production operational hardening, user studies, external benchmark
comparisons, and security review are still required. The regression suite also covers a prompt-injected
high-risk delete and forged finish evidence; both are denied or rejected
without state change.

## 2026-07-29 launch-candidate update (historical)

At that release, the public branch had 137/137 harness tests, 47/47 companion tests, and a
16-check launch preflight. The preflight runs the companion suite from its own
package root so same-name modules from the two projects cannot silently
replace one another. It builds a fresh clean-source wheel, validates
the extracted install, and compares the complete archive manifest, package
module digest, and console scripts against the fresh reference before checking
the claim-safe scorecard, which rejects an external-native label without
complete native provenance.

This closes a reproducibility and claim-control gap in the developer preview.
It does not close production identity/operations, usability sessions,
deployment-specific security review, licensing/provenance sign-off, or a
native external benchmark run.
