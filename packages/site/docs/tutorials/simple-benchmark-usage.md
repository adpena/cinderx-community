---
title: Simple benchmark usage (quickstart)
---

# Simple benchmark usage (quickstart)

This is the fastest path to run the benchmark harness with script-first commands and inspect
artifacts that mirror published data flow.

## What this walkthrough gives you

- one smoke summary JSON
- one pyperformance summary JSON (CI-mode subset)
- one metadata dossier JSON
- comparator wiring visibility (PyPy detection)
- a clear next step for publishable CinderX-baselined runs

## Prerequisites

- repo root: `cinderx-community`
- workspace venv available at `.venv`
- dependencies installed (`make python-dev`)

## 1) List suites

```bash
.venv/bin/cxc bench list
```

Expected shape:

- `smoke (runnable)`
- `pyperformance (runnable)`
- planned suites listed separately

## 2) Install comparator toolchain helpers

```bash
bash scripts/bench/install_comparison_toolchain.sh
```

This installs required benchmark tools (`pyperformance`) and prints detected comparator
executable paths.

## 3) Run a quick local benchmark matrix (script)

```bash
bash scripts/bench/run_quickstart_matrix.sh
```

For a publishable-policy run when a real CinderX runtime is available:

```bash
CINDERX_PYTHON=/path/to/cinderx-python bash scripts/bench/run_quickstart_matrix.sh
```

For full local pyperformance (non-`ci_mode`) on your laptop, use:

```bash
make bench-pyperformance-local
CINDERX_PYTHON=/path/to/cinderx-python make bench-pyperformance-local-cinderx
```

## 4) Inspect latest summaries and runtime coverage

```bash
jq '{suite,run_id,machine,baseline_runtime,runtimes:(.runtimes|map({runtime,executed})),skipped_runtimes}' data/summary/latest-smoke.json
jq '{suite,run_id,machine,baseline_runtime,runtimes:(.runtimes|map({runtime,executed})),skipped_runtimes}' data/summary/latest-pyperformance.json
```

Current adapter coverage in this repo:

- smoke: CPython, CinderX, PyPy
- pyperformance: CPython, CinderX, PyPy

## 5) Sync local site data from published benchmark history

To preview the site with real published benchmark artifacts:

```bash
bash scripts/bench/sync_site_data_from_bench_results.sh
```

Then build/serve docs:

```bash
make build
```

## 6) Move from diagnostics to publishable claims

Local quickstart runs are diagnostics unless they pass publish policy with a real CinderX baseline.
For full publish guard checks:

```bash
cd python
../.venv/bin/cxc bench verify-publish \
  --summary-root ../data/summary \
  --static-summary-root ../packages/site/static/data/summary \
  --require-suite pyperformance
```
