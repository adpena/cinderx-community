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

## Verify import only

```python
import cinderx
print('cinderx import ok')
```

:::info TODO
Detailed runtime feature checks will be added after we validate behavior by reading code/tests and running compatibility suites.
:::
