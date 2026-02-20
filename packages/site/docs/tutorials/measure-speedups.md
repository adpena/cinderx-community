---
title: Measuring your app's speedup responsibly
---

# Measuring your app's speedup responsibly

This tutorial is a practical checklist for producing reproducible, CinderX-first measurements you
can defend publicly.

## 1) Define workload and claim boundary

- Identify exact workload (endpoint mix, input shape, concurrency, warmup behavior).
- Decide whether you are making an internal engineering decision or a public claim.
- Write the claim in one sentence before you run anything.
  Example: "On workload X, runtime Y is N% faster than CinderX baseline on machine Z."

## 2) Verify runtime identity

```bash
$CINDERX_PYTHON -c "import cinderx,sys; print(sys.executable); print(cinderx.__file__)"
```

If this check fails, do not label results as CinderX-based.

## 3) Run the same harness with transparent settings

From repo root:

```bash
bash scripts/bench/install_comparison_toolchain.sh
bash scripts/bench/run_quickstart_matrix.sh
```

When a real CinderX runtime is available:

```bash
CINDERX_PYTHON=/path/to/cinderx-python bash scripts/bench/run_quickstart_matrix.sh
```

Comparator support note:

- `pyperformance` currently executes python-runtime adapters (CPython/CinderX/PyPy)

Fairness requirements:

- same machine profile
- same dependency lock
- same dataset/workload generator
- same warmup/sample strategy

## 4) Capture complete metadata

- OS/kernel/CPU/RAM
- runtime versions
- command lines
- timestamps

In this repository, use:

```bash
make bench-dossier
```

## 5) Enforce publish guard before sharing claims

```bash
make bench-publish-check
```

If guard fails, treat results as non-publishable diagnostics, not headline comparisons.

## 6) Read and summarize results correctly

Inspect latest summaries:

```bash
jq '{suite,run_id,machine,baseline_runtime,runtimes:(.runtimes|map({runtime,executed})),skipped_runtimes}' data/summary/latest-pyperformance.json
```

For published claims in this repo, only use runs that are:

- `baseline_runtime = "cpython-cinderx"`
- `metadata.run_config.require_cinderx_baseline = true`
- `metadata.run_config.ci_mode = false` (full pyperformance)
- accepted by `make bench-publish-check`

## Troubleshooting

- `The executable provided to --cpython-cinderx does not appear to expose CinderX`
  Use a real CinderX-capable interpreter and re-run the import probe command.
- `make bench-publish-check` fails
  Latest summaries are missing CinderX-baselined/policy-enforced fields; run CinderX lane again.
- CinderX install/build fails locally
  On macOS arm64 `fmt` failures (`malloc` / `free` undeclared), run `make cinderx-install-local-macos` and re-check `import cinderx` before re-running benchmark lanes.
- Site preview shows local/non-publishable summaries
  Run `bash scripts/bench/sync_site_data_from_bench_results.sh` before `make build`.

## Validation snapshot (executed in this repo)

Executed on 2026-02-19 (macOS arm64, `.venv/bin/python` = CPython 3.14.3):

- `.venv/bin/cxc bench list`: `0.15s`
- smoke run command: `0.57s`
- pyperformance run command (`--ci-mode`): `10.19s`
- dossier export command: `0.16s`

These timings validate command usability; they are not performance conclusions.
