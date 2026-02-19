---
title: How to add a benchmark
---

# How to add a benchmark

This project is CinderX-first for published comparisons. Any benchmark contribution must preserve
that policy.

## 1) Choose scope

- Add a workload to an existing suite (`smoke` or `pyperformance`) first.
- Add a new adapter only when output normalization is clear and testable.

## 2) Implement in harness

- Runtime/adapters live in `python/cinderx_community/bench/runner.py`.
- CLI wiring lives in `python/cinderx_community/cli.py`.
- Keep output fields consistent with existing summary schema.

## 3) Preserve policy and metadata

- Do not bypass `--require-cinderx-baseline` enforcement.
- Keep metadata fields complete (host/toolchain/guardrails/run config).
- Ensure publish guard behavior remains strict.

## 4) Add tests

- Add/extend tests in `python/cinderx_community/tests/`.
- Include failure tests for policy violations where relevant.

## 5) Validate locally

```bash
make fmt
make lint
make test
make build
make bench-smoke-local
make bench-pyperformance-local
```

If you have a real CinderX runtime path:

```bash
CINDERX_PYTHON=/path/to/cinderx-python make bench-smoke-local-cinderx
CINDERX_PYTHON=/path/to/cinderx-python make bench-pyperformance-local-cinderx
make bench-publish-check
```
