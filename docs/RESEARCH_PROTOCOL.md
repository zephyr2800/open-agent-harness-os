# Research protocol

## Primary question

Does a controlled harness improve independently verified agent completion for a
fixed model under the same task, tool, and budget conditions? Does an Action
IR-aware harness produce a superadditive gain for the paired small model?

## Required controls

- same model weights and decoding seed across harness variants;
- same task specification, tool implementation, and output budget;
- evaluator, trace recorder, authority boundary, and hidden holdout immutable;
- independent artifact/state verification;
- renamed tool and schema perturbations;
- at least two task families and multiple seeds;
- raw traces plus replay validation for every reported success.

## Metrics

- verified completion and process correctness;
- protocol-valid decisions and correct abstention;
- useful progress per output token;
- latency, tool time, memory, energy, and cost;
- recovery success, unnecessary calls, state loss, escalation precision;
- evaluator-gaming rate and held-out regression.

For GPU energy, use `harness-gpu-energy` during an exclusive, bounded
evaluation window and preserve its `gpu-energy/v1` sidecar with the evaluation
artifact. This is sampled whole-device energy, not per-process or wall-socket
energy; see `docs/GPU_ENERGY_MEASUREMENT.md`.

## Interaction estimate

For specialized model `M_s`, generic model `M_g`, baseline `H1`, and variant
`Hx`, report:

```text
Delta_MH = P(M_s,Hx) - P(M_s,H1) - P(M_g,Hx) + P(M_g,H1)
```

Do not collapse a positive interaction into a general scaling law until it
survives task-family, model, tool-name, and seed perturbations.
