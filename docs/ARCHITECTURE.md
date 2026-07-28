# Architecture

```text
model adapter
    ↓ Action IR v0
context compiler ← typed state ← evidence ledger
    ↓
authority policy → bounded executor → independent verifier
    ↓                    ↓               ↓
state update       tool observation   trace recorder
    ↓                    └───────────────┘
checkpoint / recovery / branch search
    ↓
replay + evaluation → bounded H4 proposal → held-out promotion gate
```

The evaluator and promotion gate are control-plane components. Model-generated
text cannot edit them during a run. The runtime exposes H0 through H4 as
controlled ablation variants, not as separate implementations with different
tasks.
