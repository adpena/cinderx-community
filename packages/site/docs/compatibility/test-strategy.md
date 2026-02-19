---
title: Test strategy under CinderX
---

# Test strategy under CinderX

Use layered validation rather than a single pass/fail signal.

## Layer 1: unit tests

- Run the same unit suite under stock CPython 3.14 and CinderX runtime.
- Keep failures grouped by dependency class (pure Python vs extension-heavy).

## Layer 2: integration tests

- Run service-level integration tests with the exact dependency lock and runtime binary intended for
  deployment.
- Enable crash diagnostics (`-X faulthandler`) for C-extension triage.

## Layer 3: performance smoke

- Use smoke harness for shape/regression checks:

```bash
make bench-smoke-local
CINDERX_PYTHON=/path/to/cinderx-python make bench-smoke-local-cinderx
```

- Use `--ci-mode` for fast non-claim checks.
- Use `--require-cinderx-baseline` for any comparison run that may be published.

## Layer 4: publishable benchmark validation

- Export run metadata dossiers:

```bash
make bench-dossier
```

- Enforce publish guard:

```bash
make bench-publish-check
```

If publish guard fails, results are non-publishable by policy and should remain internal.
