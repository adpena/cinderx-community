---
title: Installation
---

# Installation

## Requirements (from upstream README)

- CPython 3.14+
- Linux x86_64
- GCC 13+ or Clang 18+
- Windows: not supported
- macOS: build may work, but most features are currently disabled

Source: [facebookincubator/cinderx README](https://github.com/facebookincubator/cinderx)

## Install from PyPI

```bash
uv pip install cinderx
```

## Troubleshooting (macOS arm64)

If install fails while compiling bundled `fmt` and logs show `malloc` / `free` undeclared, retry with:

```bash
CXXFLAGS='-include cstdlib' CMAKE_ARGS='-DCMAKE_VERBOSE_MAKEFILE:BOOL=ON' uv pip install --python .venv/bin/python -v --no-cache-dir --reinstall cinderx
```

From this repository, the make wrapper is:

```bash
make cinderx-install-local-macos
```

`PYTHONPATH=src` does not resolve this build failure because it occurs in native C++ compilation.
Separate runtime caveat: install may succeed while `_cinderx.so` fails symbol resolution at import
time (`get_import_error()` reports missing `__ZNSt3__113__hash_memoryEPKvm`), which disables JIT
and static-loader hooks.

## Troubleshooting (Linux strict/static loader)

If benchmark bootstrap (or explicit strict loader install) fails with:

`Strict module stubs path does not exist: .../cinderx/compiler/strict/stubs`

your installed wheel likely omitted strict-module stubs data. In this repo, run:

```bash
bash scripts/ci/install_and_probe_cinderx.sh --python .venv/bin/python --mode strict --require-static-loader
```

The script resolves a usable stubs path and reports it as `strict_stubs_path`. Export it before
benchmark runs:

```bash
export PYTHONSTRICTMODULESTUBSPATH="/path/from/strict_stubs_path"
```

Benchmark profile expectation in this repo:

- default publish path uses `cinderx-jit-all` (does not require strict stubs)
- `cinderx-all-features` and `cinderx-static-loader*` require strict stubs and now fail fast when
  stubs are missing

## Verify import only

```python
import cinderx
print('cinderx import ok')
```

## Verify runtime feature surfaces

```bash
.venv/bin/python scripts/tutorials/runtime_identity_report.py
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode all
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode auto
```

For existing CPython apps, use:

- [CPython project quickstart](../tutorials/cpython-project-quickstart)

:::info Validation scope
Import checks are only the first gate. Use compatibility pages plus benchmark guardrails before
making production or performance claims.
:::
