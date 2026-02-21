---
title: Suites we plan to include
---

# Suites we plan to include

Current status:

- `smoke` (implemented): reproducibility-focused sanity suite with normalized JSON output
- `CinderX` adapter baseline (implemented for smoke): run with `--cpython-cinderx /path/to/cinderx-python`
- optional interpreter comparison runtime (implemented for smoke): `--pypy` (or auto-detected from `PATH`)
- `pyperformance` (implemented adapter): `cxc bench run --suite pyperformance ...` (interpreter comparators only: CPython/CinderX/PyPy; canonical published results are full pyperformance runs)
- Numba ASV-style benchmarks (future standalone suite; not a pyperformance comparator path)
- Real application workloads (to be defined with reproducibility checklists)
- Roadmap benchmark additions (next): expand smoke toy workloads, add tutorial-facing pyperformance slices, and add app-shaped scripts that map directly to CinderX user workflows

Source baseline for methodology: [pyperformance docs](https://pyperformance.readthedocs.io/)

:::info Adapter status
`cxc bench run --suite smoke` and `cxc bench run --suite pyperformance` are runnable now.
Smoke is debug-focused and not part of canonical published headline results.
Use `--require-cinderx-baseline` for comparison publishing policy enforcement.
Provided `--cpython-cinderx` runtimes are validated and rejected if they do not expose CinderX.
Optional pyperformance bootstrap profiles are available for controlled feature-enablement
experiments (`--pyperformance-bootstrap-profile ...`). When `--cpython-cinderx` is provided
without an explicit profile, the harness auto-applies `cinderx-all-features` to the
`cpython-cinderx` lane only; plain `cpython` remains control. In this repo, `cinderx-all-features`
maps to eager JIT (`jit-all`) plus strict/static loader when stubs are available. Custom inline
hooks are retained as an escape hatch.
:::
