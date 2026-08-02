# Versioned promotion protocols

A protocol name records the immutable local task-spec set used to make a
promotion or verifier-backed-RL decision. It prevents an older diagnostic
from being silently reused after the evidence standard changes.

| Protocol | Status | Required frozen slices |
|:---|:---|:---|
| `v1` | historical/reproducible only | research-v4, industry-proxy-v1, industry-proxy-v2 |
| `v2` | active for new candidates | research-v4, industry-proxy-v2, author-holdout-v1 |

The clean 3,232-row 9B SFT mixture passed direct-contract isolation for the
legacy v1 proxy, but its identifier-normalized template-affinity audit found
24 of 48 v1-proxy tasks above the configured similarity threshold. That
result makes the v1 proxy unsuitable as fresh held-out evidence. It remains
an immutable diagnostic so prior results can be reproduced and compared.

The v2 author holdout was authored after that clean mixture froze and passed
both local isolation screens. It is published and local, so it is not hidden
evaluation or a native external benchmark. A v2 result still requires the
matched-budget ablation and a native external-suite metric before it can
support a breakthrough claim.

For a new candidate, pass `--promotion-protocol v2` to the matrix runner,
promotion decision, and verified-RL gate. The matrix runner rejects a task
set with a missing, substituted, duplicated, or hash-mismatched fixture; the
decision and RL gate reject a matrix/decision bound to another protocol.
