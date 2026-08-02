# TUA-Bench host preflight

`experiments.tua_bench_preflight` records whether a pinned
[TUA-Bench](https://github.com/facebookresearch/TUA-Bench) checkout has the
host prerequisites needed to prepare a later native benchmark run.

It is deliberately read-only with respect to TUA-Bench and the local model. It
does not install Docker, Podman, or `uv`; download benchmark assets; run
`setup-env`; start a container; load a model; or create a score. A passing
report means only that the inspected checkout, a container backend, `uv`, and
caller-specified setup assets are present. It does not mean that this project
has a TUA policy bridge or an external benchmark result.

## Use

After cloning and pinning the official repository, run the preflight before
using its setup command. The command below is expected to report blockers on a
host that does not yet have a container backend or `uv`:

```powershell
python -m experiments.tua_bench_preflight `
  --tua-root C:\path\to\TUA-Bench `
  --expected-commit <full-40-hex-TUA-Bench-commit> `
  --output work\external\tua-bench-host-preflight.json `
  --fail-on-blocker
```

After the pinned checkout's own setup procedure has created/downloaded known
assets, name one or more paths inside that checkout explicitly. This avoids
treating a source checkout alone as proof that its generated task assets exist:

```powershell
python -m experiments.tua_bench_preflight `
  --tua-root C:\path\to\TUA-Bench `
  --expected-commit <full-40-hex-TUA-Bench-commit> `
  --required-asset <path-created-by-setup-env> `
  --output work\external\tua-bench-host-preflight.json `
  --fail-on-blocker
```

The expected commit is mandatory. The report passes its checkout gate only
when `git rev-parse HEAD` is a clean, full SHA-1 matching that exact value;
recording an arbitrary clean checkout is not source-bound evidence.

Do not run TUA-Bench until a separately reviewed, source-bound policy bridge,
task selection, fixed budgets, native grader, and artifact-preservation plan
exist. Keep its CC BY-NC benchmark/data boundary separate from the Apache-2.0
harness distribution.
