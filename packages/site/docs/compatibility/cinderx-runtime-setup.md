---
title: CinderX runtime setup
---

# CinderX runtime setup

This project treats CinderX runtime availability as a first-class prerequisite for publishable
benchmark comparisons.

## Source-backed baseline requirements

From upstream CinderX README:

- Python 3.14+
- Linux x86_64 (primary supported environment)
- GCC 13+ or Clang 18+
- macOS can build/import but most features are disabled
- Windows is not supported

Source: [facebookincubator/cinderx README](https://github.com/facebookincubator/cinderx)

## Workspace preflight

From repo root:

```bash
make cinderx-env-check
```

This prints Python path/version, toolchain visibility (`cmake`, `clang`, `ninja`), current
`CINDERX_PYTHON`, and whether `cinderx` imports in the workspace runtime.

## Configure project metadata and install path

```bash
uv add --project ./python --optional cinderx cinderx --no-sync
uv pip install --python .venv/bin/python setuptools
uv pip install --python .venv/bin/python --no-build-isolation cinderx
```

If local install succeeds, confirm:

```bash
.venv/bin/python -c "import cinderx,sys; print(sys.executable); print(cinderx.__file__)"
```

Then point benchmark runs to that runtime:

```bash
export CINDERX_PYTHON="$PWD/.venv/bin/python"
make bench-smoke-local-cinderx
make bench-pyperformance-local-cinderx
```

## Known local caveat in this workspace

As of 2026-02-19 on macOS arm64 in this workspace, upstream `cinderx` source build still fails
inside bundled `fmt` during C++ compilation (`malloc` / `free` undeclared), even after local
prerequisites are installed. Until that upstream issue is resolved or a compatible wheel is used,
publishable CinderX-baselined benchmark runs are blocked by design.

## Publishability guardrail

`cxc bench verify-publish` requires:

- baseline runtime is `cpython-cinderx`
- run metadata marks `require_cinderx_baseline=true`
- executed CinderX runtime rows exist

If those are not present, publication is rejected to prevent CPython-framed headline comparisons.
