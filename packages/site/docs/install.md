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

## Verify import

```python
import cinderx
print(cinderx.__file__)
```

:::caution TODO
Feature-level validation (JIT/static behavior, runtime flags, and extension compatibility) will be confirmed via code-reading and differential tests in later phases.
:::
