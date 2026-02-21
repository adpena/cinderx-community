---
title: Static Python Usage
---

# Static Python Usage

This page focuses on how Static Python is actually activated and used from normal CPython projects.

## Core model

Static Python is not a global runtime switch. It is module-by-module behavior that depends on:

1. strict/static loader being installed before your app modules import
2. target modules being marked with `import __static__`
3. those modules being compiled/executed through the strict loader path

## Marker and placement rules

Static marker detection is explicit and strict:

- `import __static__` marks a module static.
- `import __strict__` marks strict-only behavior.
- marker imports must be at the top (after docstring and `__future__` imports).
- marker imports cannot be aliased and cannot be combined with other imports on the same line.

`import __static__` implies strict semantics; you should not combine both markers.

## Loader config knobs

`cinderx.compiler.strict.loader.install(enable_patching=False)` installs the loader into
`sys.path_hooks` and clears `sys.path_importer_cache`.

`enable_patching=True` uses patch-capable strict module behavior (mainly for tests/dev workflows).

Stubs path resolution in strict loader:

- `-X strict-module-stubs-path=<path>` (available via `sys._xoptions`)
- `PYTHONSTRICTMODULESTUBSPATH=<path>`
- fallback default inside the package: `cinderx/compiler/strict/stubs`

If the resolved stubs path does not exist, loader init raises:

`ValueError: Strict module stubs path does not exist: ...`

## Runtime hooks Static Python relies on

When static code is present, loader initialization routes through:

- `install_frame_evaluator()`
- `watch_sys_modules()`
- `install_sp_audit_hook()`

This is why static support should be bootstrapped at process entry before app imports.

## Using Static Python in an existing CPython project

Use this pattern:

1. In launcher entrypoint, early bootstrap:

```python
import importlib
import importlib.util

if importlib.util.find_spec("cinderx") is not None:
    import cinderx
    cinderx.init()
    strict_loader = importlib.import_module("cinderx.compiler.strict.loader")
    strict_loader.install(enable_patching=False)
```

2. In modules you want static behavior for, add marker near top:

```python
import __static__
from __static__ import int64, cbool, box
```

3. Verify behavior at runtime:

```python
from cinderx.static import is_static_module
print(is_static_module(your_module))
```

## `__static__` entry points developers actually use

Most common imports in static modules:

- primitive types: `cbool`, `int8/int16/int32/int64`, `uint*`, `double`, `char`
- container helpers: `CheckedDict`, `CheckedList`, `Array`, `Vector`
- conversion/utilities: `box`, `clen`, `crange`, `cast`
- decorators/protocol helpers: `inline`, `dynamic_return`, `ClassDecorator`, `TClass`

These are used by the static compiler/runtime to enable stronger typing assumptions and specialized
execution paths.

## Important benchmarking implication

Installing strict loader alone does not guarantee large speedups:

- workload modules need `__static__` markers and compatible typed patterns
- hot paths need to actually benefit from static semantics and JIT lowering

That is why this repo records which CinderX features were enabled, and keeps full pyperformance
publication runs source-traceable.

## Source references

- [cinderx/Docs/StaticPython/tutorial.md](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/Docs/StaticPython/tutorial.md)
- [cinderx/PythonLib/cinderx/compiler/strict/flag_extractor.py](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/PythonLib/cinderx/compiler/strict/flag_extractor.py)
- [cinderx/PythonLib/cinderx/compiler/strict/loader.py](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/PythonLib/cinderx/compiler/strict/loader.py)
- [cinderx/PythonLib/cinderx/compiler/strict/common.py](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/PythonLib/cinderx/compiler/strict/common.py)
- [cinderx/PythonLib/cinderx/static.py](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/PythonLib/cinderx/static.py)
