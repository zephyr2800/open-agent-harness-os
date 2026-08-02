# GPU energy measurement

`harness-gpu-energy` measures sampled NVIDIA **device** power while a bounded
evaluation command runs, integrates the samples with the trapezoidal rule, and
writes a `gpu-energy/v1` JSON sidecar. It is intended for a future clean
checkpoint matrix, external diagnostic, or factorial run after the GPU is
otherwise idle.

```powershell
harness-gpu-energy --output experiments/results/clean-9b-v2-energy.json --sample-seconds 1 -- `
  python -m experiments.run_promotion_matrix <the frozen registered arguments>
```

The sidecar includes the exact launched argv, return code, raw monotonic and
wall-clock samples, sampled energy in joules and watt-hours, and collection
errors. A successful child command is only reported as `status: complete` when
at least two valid samples were collected without telemetry errors. Otherwise
the tool exits non-zero and writes `status: incomplete`; that file must not be
used for a numeric energy claim.

## Claim boundary

NVIDIA's `power.draw` is whole-device telemetry. This utility does **not**
measure a process, CPU/RAM/storage/network, monitor, or wall-socket energy. A
per-evaluation comparison therefore requires an exclusive GPU window, the same
device/power settings, a recorded sampling interval, and the sidecar alongside
the corresponding source-bound evaluation artifact. It cannot retroactively
measure the already-running clean 9B training job, and no such estimate is
published for that job.
