---
title: Install
slug: /install
---

# Install

## What upstream states

The upstream CinderX README lists these requirements:

- CPython 3.14+
- Linux x86_64
- GCC 13+ or Clang 18+
- macOS can build, but most features are currently disabled
- Windows is not supported

Source: [facebookincubator/cinderx README](https://github.com/facebookincubator/cinderx)

## Basic install command

```bash
uv pip install cinderx
```

## Troubleshooting (macOS arm64)

If local source build fails in bundled `fmt` with:

- `use of undeclared identifier 'malloc'`
- `use of undeclared identifier 'free'`

use this local workaround command:

```bash
CXXFLAGS='-include cstdlib' CMAKE_ARGS='-DCMAKE_VERBOSE_MAKEFILE:BOOL=ON' uv pip install --python .venv/bin/python -v --no-cache-dir --reinstall cinderx
```

Repository shortcut:

```bash
make cinderx-install-local-macos
```

Notes:

- This was reproduced in this workspace on 2026-02-19 (macOS 26.3 arm64, CPython 3.14.3).
- `PYTHONPATH=src` does not address this native build failure mode.

## Verify import

```python
import cinderx
print(cinderx.__file__)
```

:::caution Validation scope
The command above confirms importability only. For feature-level validation (JIT/static behavior,
runtime flags, extension compatibility), use the compatibility and benchmark verification workflows
in this repository.
:::
