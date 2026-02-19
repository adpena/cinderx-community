---
title: C extensions & ABI notes
---

# C extensions & ABI notes

This page focuses on practical compatibility triage for extension-heavy projects migrating to
CinderX.

## CPython ABI landscape (practical)

- Most extension wheels target a CPython-version-specific ABI.
- `abi3` wheels use CPython's stable ABI subset for broader CPython minor-version compatibility.
- Using `abi3` does not guarantee behavior across all runtime implementations or all extension usage
  patterns.

## Maintainer checklist

For each extension dependency in your service:

- Identify whether the wheel is CPython-version-specific or `abi3`.
- Confirm whether the package touches CPython internals beyond stable API guarantees.
- Check whether your stack depends on frame/tracing internals for profiling/debugging behavior.
- Record wheel tags and platform coverage (for example manylinux vs source-only builds).
- Run import + representative integration tests under the exact CinderX runtime used in production.

## Crash and mismatch triage flow

1. Validate runtime identity:

```bash
$CINDERX_PYTHON -c "import importlib.util,sys; print(sys.executable); print(bool(importlib.util.find_spec('cinderx')))"
```

2. Reproduce with fault details enabled:

```bash
$CINDERX_PYTHON -X faulthandler -m pytest -q path/to/your/tests
```

3. Inspect problematic extension links:

```bash
otool -L path/to/extension.so
```

4. Compare behavior against stock CPython 3.14 on the same host and dependency lock.

5. Capture the minimal reproducer and publish issue metadata (runtime, wheel tags, platform).

## About CinderX-specific extension claims

We do not publish strong extension-compatibility claims unless they are backed by:

- upstream CinderX code/tests, or
- reproducible experiments in this repository's compatibility/benchmark artifacts.

Source baseline for CinderX platform/runtime constraints:
[facebookincubator/cinderx README](https://github.com/facebookincubator/cinderx).
