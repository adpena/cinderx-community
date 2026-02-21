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

If the default path fails on macOS arm64 with bundled `fmt` compile errors (`malloc` / `free`
undeclared), retry with the validated workaround:

```bash
CXXFLAGS='-include cstdlib' CMAKE_ARGS='-DCMAKE_VERBOSE_MAKEFILE:BOOL=ON' uv pip install --python .venv/bin/python -v --no-cache-dir --reinstall cinderx
```

Repo make wrapper:

```bash
make cinderx-install-local-macos
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

## Verify JIT and static-loader surfaces before benchmarking

```bash
.venv/bin/python scripts/tutorials/runtime_identity_report.py
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode all
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode auto
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --install-static-loader
```

These checks validate that CinderX APIs used by this repo's bootstrap profiles are available in
your local runtime.

## Known local caveat in this workspace

As of 2026-02-19 on macOS arm64 in this workspace, default local source-build path can fail inside
bundled `fmt` C++ compilation (`malloc` / `free` undeclared). A reproducible local workaround is
available via `CXXFLAGS='-include cstdlib'` plus explicit `CMAKE_ARGS` (or
`make cinderx-install-local-macos`).

Additional validation notes from this workspace:

- default `uv pip install cinderx` failed with the same `fmt` error
- default `python -m pip install cinderx` failed with the same `fmt` error
- `PYTHONPATH=src` did not change the failure mode
- separate local failure mode observed on 2026-02-20: `import cinderx` succeeded but
  `get_import_error()` reported `_cinderx.so` missing symbol `__ZNSt3__113__hash_memoryEPKvm`;
  in that state JIT/runtime hooks were unavailable (`scripts/tutorials/runtime_identity_report.py`)

## Hosted-runner caveat (GitHub Actions)

As of 2026-02-19 in workflow run `22202746458`, both:

- `ubuntu-latest` diagnostics lane
- pinned publishable lane (`ubuntu-22.04`, CPython `3.14.0`)

completed `cinderx` install plus direct import probe successfully via
`scripts/ci/install_and_probe_cinderx.sh` (`selected_attempt=default-wheel` in both lanes).

Historical note: earlier run `22196352820` had an `import cinderx` crash on `ubuntu-latest`
(exit `139`). Keep diagnostics artifacts enabled because hosted-runner image/toolchain drift can
reintroduce regressions.

Additional hosted-runner caveat seen on 2026-02-20:

- `import cinderx` passed, but strict/static loader failed with
  `Strict module stubs path does not exist: .../site-packages/cinderx/compiler/strict/stubs`.
- Root cause: some wheels do not include `compiler/strict/stubs` package data.

CI mitigation in this repo:

- `scripts/ci/install_and_probe_cinderx.sh --require-static-loader` now resolves a strict stubs
  path (site-packages first, upstream sparse checkout fallback) and runs a fast strict/static probe.
- Bench preflight/run steps set `PYTHONSTRICTMODULESTUBSPATH` from the installer output, so
  `cinderx-all-features` can install strict loader on Linux when wheel stubs are absent.

## Publishability guardrail

`cxc bench verify-publish` requires:

- baseline runtime is `cpython-cinderx`
- run metadata marks `require_cinderx_baseline=true`
- executed CinderX runtime rows exist

If those are not present, publication is rejected to prevent CPython-framed headline comparisons.

Pyperformance with `--cpython-cinderx` auto-applies profile `cinderx-all-features` on the
`cpython-cinderx` lane (plain `cpython` remains control). In this repo that profile means
`JIT all` + static loader. For explicit profile overrides:

```bash
CINDERX_PYTHON=/path/to/cinderx-python \
PYPERF_BOOTSTRAP_PROFILES=cinderx-jit-all,cinderx-jit-auto,cinderx-jit-compile-after-n-calls \
PYPERF_BOOTSTRAP_JIT_COMPILE_AFTER_N_CALLS=40000 \
bash scripts/bench/run_quickstart_matrix.sh
```
