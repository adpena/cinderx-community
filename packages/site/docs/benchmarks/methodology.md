---
title: Methodology
---

# Methodology

Our benchmarking policy starts with reproducibility and comparability.

pyperformance is designed for running and comparing Python performance benchmarks, and its docs emphasize consistent benchmarking workflows.

Source: [pyperformance documentation](https://pyperformance.readthedocs.io/)

## Measurement principles

- Pin environment details (CPU, OS, compiler, Python build)
- Record runtime/version metadata for every run
- Use repeated measurements and compare distributions, not one-off runs
- Publish benchmark commands and raw outputs alongside summaries
- Separate microbenchmarks from real-application results

## Runtime modes

- `smoke` mode: fast sanity checks with reduced samples; suitable for CI gates and output-shape validation.
- `pyperformance` mode: real pyperformance execution with normalized ingestion and per-benchmark stats.
- pyperformance comparator scope is interpreter runtimes only (`cpython`, `cpython-cinderx`, `pypy`).
- CI fast mode for pyperformance can be used for local/debug validation, but publishable headline data must
  come from full pyperformance runs (`ci_mode=false`).
- `--cpython-cinderx` is strictly validated; if the runtime does not expose CinderX (`import cinderx`),
  the run fails instead of labeling it as a CinderX baseline.

## CinderX bootstrap policy for pyperformance

When `--cpython-cinderx` is provided, pyperformance runs auto-apply CinderX bootstrap profile
`cinderx-all-features` via a temporary `sitecustomize` shim. In this repo, that profile now uses
eager JIT (`jit-all` behavior) plus strict/static loader install:

```bash
cxc bench run \
  --suite pyperformance \
  --python /path/to/python3.14 \
  --cpython-cinderx /path/to/cinderx-python \
  --require-cinderx-baseline
```

Notes:

- This default bootstrap is lane-targeted: plain `cpython` remains the control run.
- Override the default profile with `--pyperformance-bootstrap-profile <name>` when needed.
- Supported profiles: `cinderx-init`, `cinderx-all-features`, `cinderx-jit-all`, `cinderx-jit-auto`,
  `cinderx-jit-compile-after-n-calls`,
  `cinderx-jit-disable`, `cinderx-static-loader`, `cinderx-static-loader-patching`.
- Custom inline hooks still exist via `--pyperformance-bootstrap-inline`, but profile mode is the
  preferred path for reproducible CinderX feature experiments.
- The dashboard surfaces bootstrap-enabled state, profile, mode, and bootstrap hash for traceability.

Example smoke run with CinderX baseline plus interpreter comparison runtime:

```bash
cxc bench run \
  --suite smoke \
  --python /path/to/python3.14 \
  --cpython-cinderx /path/to/cinderx-python \
  --pypy /path/to/pypy3 \
  --require-cinderx-baseline \
  --ci-mode
```

## Reproducibility guardrails

`cxc bench run` records guardrail checks in run metadata:

- CPU affinity visibility (warns when not pinned)
- background load checks (warns when host load is high)
- explicit notes for turbo/thermal state (manual confirmation required)

You can enforce guardrails with `--enforce-guardrails` to fail noisy/unsafe runs.

## Output model

- Raw artifacts: `data/runs/<date>/<machine>/<runtime>/...`
- Normalized summaries: `data/summary/*.json`
- Static site mirror: `packages/site/static/data/summary/*.json`

Each summary includes:

- machine metadata and timestamp
- runtime/tool versions
- baseline-relative speedup and per-benchmark p-value estimates
- startup-time metrics separated from steady-state benchmark timings
- optional RSS and compile-time metrics when adapters expose them

## Publish guard

Use `cxc bench verify-publish` before publishing benchmark artifacts. For headline publishing, require
`pyperformance` and fail CI-mode outputs:

```bash
cxc bench verify-publish --require-suite pyperformance
```

It fails unless latest summaries are truly CinderX-baselined and policy-enforced, and host/toolchain/
guardrail metadata is present.

## Local publish path

Local benchmark publication is supported when you:

- run with a real CinderX runtime (`--cpython-cinderx`) and `--require-cinderx-baseline`
- keep full metadata in the generated summaries
- pass `cxc bench verify-publish --require-suite pyperformance`
- export metadata dossiers with `cxc bench export-dossier` (or `make bench-dossier`) for report attachment

## Near-term expansion track

- Increase smoke-suite breadth with additional interpreter-heavy and serialization-heavy toy workloads.
- Add targeted pyperformance slices for tutorial demos, while keeping full-suite runs canonical for publishing.
- Add tutorial-backed app-shaped scripts so users can reproduce CPython vs CinderX comparisons quickly.
