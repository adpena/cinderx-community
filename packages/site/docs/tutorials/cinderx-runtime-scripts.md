---
title: Hands-on runtime scripts
---

# Hands-on runtime scripts

This tutorial gives you two tiny scripts you can run in your own repo to make CinderX usage concrete.

## 1) Verify runtime identity before any claim

```bash
.venv/bin/python scripts/tutorials/runtime_identity_report.py
$CINDERX_PYTHON scripts/tutorials/runtime_identity_report.py
```

You should see:

- exact interpreter path
- implementation/version
- whether `import cinderx` is available
- discovered CinderX entrypoints (`init`, `enable`, etc.) when present

## 2) Run one app-shaped hot path under both runtimes

```bash
.venv/bin/python scripts/tutorials/json_hot_path.py --iterations 4000 --payload-size 512
$CINDERX_PYTHON scripts/tutorials/json_hot_path.py --iterations 4000 --payload-size 512
```

Both runs use identical workload shape and print:

- `mean_seconds`
- standard deviation field from the script output
- `mean_us_per_iteration`

## 3) Keep comparison framing honest

- same machine and power profile
- same payload and iteration counts
- same dependency lock
- explicit runtime identity output archived with results

## 4) Move from script checks to publishable benchmark runs

Use these scripts for app-level sanity checks, then run canonical full pyperformance publication flow:

```bash
CINDERX_PYTHON=/path/to/cinderx-python make bench-pyperformance-local-cinderx
make bench-publish-check
```

If guard checks fail, keep results labeled as diagnostics.
