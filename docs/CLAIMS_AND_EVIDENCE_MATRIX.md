# Claims and evidence matrix

This is the claim-control sheet for the paired research and launch effort. A
claim is publishable only when the evidence in the right column exists and its
scope matches the wording. Local proxy results must not be described as
external benchmark results.

The public scorecard enforces this boundary: local fixtures and proxies are
marked `local_fixture`, while `external_native` requires a validated native
suite commit, metric/value, report hash, grader identity, and environment
metadata.

| Claim | Status | Authoritative evidence | Allowed wording now |
|---|---|---|---|
| A local developer preview exists | Supported | `experiments/results/launch-preflight-v9.json` | “The local developer preview passes its documented smoke, safety, auth/TLS, isolation, replay, source-bound packaging, security-metadata, and test gates.” |
| The harness executes typed actions with independent verification and replay | Supported | source tests, product smoke, MCP replay artifact, trace schemas | “The harness provides a deterministic authority/evidence/replay plane.” |
| The local policy learned the Action IR task family | Supported only on local fixtures | completed 7B v6/v6 proxy reports and independent replay reports | “Protocol specialization improves these frozen local tasks.” |
| The system is generally capable on terminal or computer-use work | Not supported | TUA-Bench/OSWorld 2.0 run is still absent | Do not make this claim. |
| The system beats frontier agents | Not supported | no native external benchmark comparison | Do not make this claim. |

| Qwopus3.5-9B is a better action policy than the promoted 7B | Not supported | frozen 9B matrix is complete but promotion decision is reject | Do not make this claim; use the 483/552 failure-localization result instead. |
| Qwopus3.5-9B SFT completed | Supported | adapter manifest and merged checkpoint manifest | “The 9B scale branch completed QLoRA SFT and merge.” |
| Verifier-backed RL improves the policy | Not supported | prior 7B RL was neutral/negative; 9B RL has not run | Do not make this claim. |
| The harness prevents all unsafe actions | Not supported | only registered-tool and local-scope safety evidence exists | Say “configured high-risk actions are denied by the tested policy boundary.” |
| The product is public-launch ready | Not supported | public identity/operations, usability, security review, licensing, and external benchmark gates remain | Say “developer-preview candidate,” not “production-ready.” |

Evidence freshness: `launch-preflight-v9.json` above remains a valid historical
artifact, but `experiments/results/launch-preflight-v15.json` is the current
developer-preview evidence: 16/16 checks, 156/156 Project 2 tests, and 47/47
companion-project tests.

## Promotion decision rule

The 9B branch may replace the 7B promotion baseline only when the separate
machine-readable decision gate reports `decision=promote`. It must include all
three frozen slices, seeds 0/1/2, 100% verified success, 100% independent
replay agreement, valid traces, zero unsafe attempts, and no unknown task
specifications. The external-bar-lite fixture is diagnostic and remains
separate from this promotion rule.

## Research-breakthrough rule

The paper claim requires more than a high task score. It needs a held-out,
independently authored suite; a model-only versus verifier-backed comparison;
multiple decoding and training seeds where practical; family-level failures;
final-answer evidence checks; safety results; replay agreement; and an
external-suite run reported with the external suite's native metric. Until
those artifacts exist, the strongest defensible result is a local systems
ablation and developer-preview infrastructure result.
