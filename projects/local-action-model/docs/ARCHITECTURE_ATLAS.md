# Architecture atlas

This atlas records candidate placements of capability between model weights,
the Action IR decoder, and the paired harness. It is a decision surface, not a
claim that any candidate is best.

| Candidate | Model owns | Harness owns | Deployment upside | Main risk | Decisive experiment |
|---|---|---|---|---|---|
| Dense decoder, 0.5–3B | tool selection, arguments, uncertainty, recovery policy | tools, authority, state, verification, rollback | mature local runtimes and quantization | protocol brittleness and low tool coverage | generic vs specialized SFT under fixed Action IR |
| Dense decoder + LoRA/adapters | task/domain policy delta | base model plus all deterministic controls | cheap checkpoint branching and rollback | adapter overfit or base-license constraints | full fine-tune vs LoRA at equal train tokens and held-out schemas |
| Action-format constrained decoder | next typed field/token and schema adherence | semantic authorization and execution | fewer invalid outputs and lower repair cost | constraints can hide model uncertainty or overconstrain novel tools | free JSON vs grammar/constrained decoding on renamed tools |
| Recurrent/state-space policy | compact persistent action state | durable state graph and evidence ledger | lower long-context memory/latency on edge | hidden state loss and harder replay/debugging | same task traces at increasing horizon and context budgets |
| Small MoE action policy | sparse expert specialization by tool/task family | routing safety and expert/version promotion | conditional compute and specialization | expert collapse, routing overhead, reproducibility | dense vs MoE at equal active parameters and wall/energy budget |
| Policy + verifier head | action proposal and local confidence | independent artifact/state verifier | earlier rejection and fewer invalid calls | correlated policy/verifier errors | calibrated abstention and verifier disagreement study |
| Coordinator + deterministic action macros | intent selection, macro choice, escalation | macro implementation, parameters, rollback | high semantic/action density per token | hidden workflow code can fake capability | macro ablation against primitive tools on unseen workflows |
| Hybrid local policy + escalation model | bounded local decisions, uncertainty | escalation, budget, authority, checkpointing | local-first latency/privacy with fallback | routing thresholds and cost leakage | four-cell local/general model matrix with fixed budgets |

## First-prototype decision

Start with the dense decoder plus optional LoRA/adapters and structured Action
IR validation. Do not introduce recurrent, MoE, or custom action vocabularies
until the dense baseline has a verified task suite, an edge measurement path,
and a complete factorial result.

## Capability placement rule

The model may propose probabilistic actions and confidence. The harness must
retain authority over permissions, destructive effects, exact state, tool
execution, independent verification, checkpoint promotion, and rollback. A
model-generated `verified: true` field is not evidence by itself.

## Rejection criteria

Reject an architecture that improves raw pass rate but worsens any of:

- independent verification rate;
- correct abstention or permission compliance;
- held-out or renamed-tool performance;
- reproducibility under replay;
- latency, memory, energy, or cost budget;
- failure observability.
