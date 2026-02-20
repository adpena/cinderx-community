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

## Verify import only

```python
import cinderx
print('cinderx import ok')
```

:::info Validation scope
Import checks are only the first gate. Use compatibility pages plus benchmark guardrails before
making production or performance claims.
:::
