---
title: Suites we plan to include
---

# Suites we plan to include

Current status:

- `smoke` (implemented): reproducibility-focused sanity suite with normalized JSON output
- `CinderX` adapter baseline (implemented for smoke): run with `--cpython-cinderx /path/to/cinderx-python`
- optional comparison runtimes (implemented for smoke): `--pypy` (or auto-detected from `PATH`), `--nuitka` (or auto-detected from `PATH`)
- `pyperformance` (implemented adapter): `cxc bench run --suite pyperformance ...` (CI mode uses a focused benchmark subset for quick validation)
- Numba ASV-style benchmarks
- Real application workloads (to be defined with reproducibility checklists)

Source baseline for methodology: [pyperformance docs](https://pyperformance.readthedocs.io/)

:::info Adapter status
`cxc bench run --suite smoke` and `cxc bench run --suite pyperformance` are runnable now.
Use `--require-cinderx-baseline` for comparison publishing policy enforcement.
Provided `--cpython-cinderx` runtimes are validated and rejected if they do not expose CinderX.
:::
