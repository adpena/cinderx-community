---
title: Hands-on runtime scripts
---

# Hands-on runtime scripts

This tutorial gives small scripts you can run in your own repo to make CinderX usage concrete.

## 1) Verify runtime identity before any claim

```bash
.venv/bin/python scripts/tutorials/runtime_identity_report.py
$CINDERX_PYTHON scripts/tutorials/runtime_identity_report.py
```

You should see:

- exact interpreter path
- implementation/version
- whether `import cinderx` is available
- CinderX runtime hook visibility (`install_frame_evaluator`, `watch_sys_modules`, etc.)
- JIT capability/state (`is_enabled`, `compile_after_n_calls`, available JIT entrypoints)
- static-loader entrypoint discovery (`cinderx.compiler.strict.loader.install`)
- environment toggles snapshot (`PYTHONJITAUTO`, `PYTHONJITDISABLE`, `PYTHONINSTALLSTRICTLOADER`, ...)

## 2) Try project-style bootstrap actions directly

```bash
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode auto
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode compile-after-n-calls --jit-compile-after-n-calls 40000
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --install-static-loader
```

This mirrors what developers usually do in existing CPython apps:

- initialize CinderX early
- choose a JIT mode intentionally
- optionally install static/strict loader before importing app modules

## 3) Run one app-shaped hot path under both runtimes

```bash
.venv/bin/python scripts/tutorials/json_hot_path.py --iterations 4000 --payload-size 512
$CINDERX_PYTHON scripts/tutorials/json_hot_path.py --iterations 4000 --payload-size 512
```

Both runs use identical workload shape and print:

- `mean_seconds`
- standard deviation field from the script output
- `mean_us_per_iteration`

## 4) Keep comparison framing honest

- same machine and power profile
- same payload and iteration counts
- same dependency lock
- explicit runtime identity output archived with results

## 5) Move from script checks to publishable benchmark runs

Use these scripts for app-level sanity checks, then run canonical full pyperformance publication flow:

```bash
CINDERX_PYTHON=/path/to/cinderx-python make bench-pyperformance-local-cinderx
make bench-publish-check
```

Optional benchmark bootstrap profile experiments:

```bash
CINDERX_PYTHON=/path/to/cinderx-python \
PYPERF_BOOTSTRAP_PROFILE=cinderx-jit-compile-after-n-calls \
PYPERF_BOOTSTRAP_JIT_COMPILE_AFTER_N_CALLS=40000 \
bash scripts/bench/run_quickstart_matrix.sh
```

Without `PYPERF_BOOTSTRAP_PROFILE`, pyperformance CinderX runs auto-apply `cinderx-all-features`
on the `cpython-cinderx` lane and keep plain `cpython` as control.

If guard checks fail, keep results labeled as diagnostics.
