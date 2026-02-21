---
title: CPython project quickstart
---

# CPython project quickstart

This is the practical path for developers who already have a CPython 3.14 app and want to wire
in CinderX intentionally (JIT + static-loader options), not just test `import cinderx`.

## What upstream usage actually looks like

- `import cinderx` calls `init()` automatically in module import path.
  Source: [cinderx/PythonLib/cinderx/**init**.py#L571](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/PythonLib/cinderx/__init__.py#L571)
- JIT controls are exposed via `cinderx.jit.*` (`auto`, `compile_after_n_calls`, `disable`, etc.).
  Source: [cinderx/PythonLib/cinderx/jit.py#L17](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/PythonLib/cinderx/jit.py#L17)
- Runtime `-X jit-*` and `PYTHONJIT*` config flags are registered in JIT init code.
  Source: [cinderx/Jit/pyjit.cpp#L299](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/Jit/pyjit.cpp#L299)
- Static/strict loader runtime bootstrap routes through frame-evaluator and module-watch hooks.
  Source: [cinderx/PythonLib/cinderx/compiler/strict/loader.py#L793](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/PythonLib/cinderx/compiler/strict/loader.py#L793)

## 1) Install and verify

```bash
uv pip install cinderx
python - <<'PY'
import cinderx
print(cinderx.__file__)
print("initialized:", getattr(cinderx, "is_initialized", lambda: None)())
PY
```

If local install fails on macOS arm64 (`malloc` / `free` undeclared in bundled `fmt`), use:

```bash
make cinderx-install-local-macos
```

## 2) Add one bootstrap module in your app

Create `your_app/cinderx_bootstrap.py`:

```python
import importlib
import importlib.util
import os


def activate() -> None:
    if importlib.util.find_spec("cinderx") is None:
        return

    import cinderx

    if hasattr(cinderx, "init"):
        cinderx.init()

    jit_mode = os.getenv("CINDERX_JIT_MODE", "leave-default")
    if jit_mode != "leave-default":
        cinderx_jit = importlib.import_module("cinderx.jit")
        if jit_mode == "all":
            cinderx_jit.compile_after_n_calls(0)
        elif jit_mode == "auto":
            cinderx_jit.auto()
        elif jit_mode == "compile-after-n-calls":
            threshold = int(os.getenv("CINDERX_JIT_THRESHOLD", "40000"))
            cinderx_jit.compile_after_n_calls(threshold)
        elif jit_mode == "disable":
            cinderx_jit.disable()
            if hasattr(cinderx, "remove_frame_evaluator"):
                cinderx.remove_frame_evaluator()

    if os.getenv("CINDERX_INSTALL_STATIC_LOADER", "0") == "1":
        strict_loader = importlib.import_module("cinderx.compiler.strict.loader")
        strict_loader.install(enable_patching=os.getenv("PYTHONENABLEPATCHING") == "1")
```

Call `activate()` at the very top of your process entrypoint, before other app imports.

## 3) Static Python note for real projects

- Upstream docs call out that loader installation must happen in your main launcher module before
  importing modules that should be strict/static.
- Launcher module itself should not be strict/static-marked.
- For static modules, use `import __static__` as module marker.

Sources:

- [Docs/StrictModules/guide/quickstart.rst](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/Docs/StrictModules/guide/quickstart.rst)
- [Docs/StaticPython/tutorial.md](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/Docs/StaticPython/tutorial.md)

## 4) Reproduce the same behavior in this repo

Use the helper script:

```bash
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode all
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode auto
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode compile-after-n-calls --jit-compile-after-n-calls 40000
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --install-static-loader
```

## 5) Wire this into pyperformance runs

For benchmark runs with `--cpython-cinderx`, the harness auto-applies CinderX profile
`cinderx-all-features` on the `cpython-cinderx` lane (`JIT all` + static loader):

```bash
cxc bench run \
  --suite pyperformance \
  --python /path/to/python3.14 \
  --cpython-cinderx /path/to/cinderx-python \
  --require-cinderx-baseline
```

Harness behavior:

- `cpython` runtime row runs without bootstrap (plain CPython baseline)
- `cinderx-all-features` bootstrap is applied only to `cpython-cinderx` runtime row

If you need a different bootstrap profile, override with:

```bash
cxc bench run \
  --suite pyperformance \
  --python /path/to/python3.14 \
  --cpython-cinderx /path/to/cinderx-python \
  --require-cinderx-baseline \
  --pyperformance-bootstrap-profile cinderx-jit-compile-after-n-calls \
  --pyperformance-bootstrap-jit-compile-after-n-calls 40000
```

Other supported profile values:

- `cinderx-init`
- `cinderx-all-features`
- `cinderx-jit-all`
- `cinderx-jit-auto`
- `cinderx-jit-compile-after-n-calls` (plus `--pyperformance-bootstrap-jit-compile-after-n-calls`)
- `cinderx-jit-disable`
- `cinderx-static-loader`
- `cinderx-static-loader-patching`
