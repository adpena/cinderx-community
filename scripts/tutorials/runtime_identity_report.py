#!/usr/bin/env python3
"""Print runtime identity details for CPython/CinderX/JIT/static-loader verification."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of key=value lines.",
    )
    return parser.parse_args()


def _safe_call_bool(obj: object, attr: str) -> bool | None:
    member = getattr(obj, attr, None)
    if not callable(member):
        return None
    try:
        return bool(member())
    except Exception:
        return None


def _safe_call_value(obj: object, attr: str) -> Any:
    member = getattr(obj, attr, None)
    if not callable(member):
        return None
    try:
        return member()
    except Exception:
        return None


def cinderx_info() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "available": False,
        "module_path": None,
        "is_initialized": None,
        "import_error": None,
        "feature_entrypoints": [],
        "runtime_hooks": {},
        "jit": {
            "module_available": False,
            "is_enabled": None,
            "compile_after_n_calls": None,
            "entrypoints": [],
        },
        "static_loader": {
            "module_available": False,
            "entrypoints": [],
        },
    }
    try:
        import cinderx  # type: ignore[import-not-found]
    except Exception as exc:
        payload["import_error"] = f"{type(exc).__name__}: {exc}"
        return payload

    payload["available"] = True
    payload["module_path"] = getattr(cinderx, "__file__", None)
    payload["is_initialized"] = _safe_call_bool(cinderx, "is_initialized")

    import_error = _safe_call_value(cinderx, "get_import_error")
    if import_error is not None:
        payload["import_error"] = repr(import_error)

    candidates = ["init", "install_frame_evaluator", "remove_frame_evaluator", "watch_sys_modules"]
    payload["feature_entrypoints"] = [name for name in candidates if hasattr(cinderx, name)]
    payload["runtime_hooks"] = {
        "install_frame_evaluator": hasattr(cinderx, "install_frame_evaluator"),
        "remove_frame_evaluator": hasattr(cinderx, "remove_frame_evaluator"),
        "is_frame_evaluator_installed": hasattr(cinderx, "is_frame_evaluator_installed"),
        "watch_sys_modules": hasattr(cinderx, "watch_sys_modules"),
    }

    try:
        cinderx_jit = importlib.import_module("cinderx.jit")
    except Exception:
        cinderx_jit = None
    if cinderx_jit is not None:
        jit_candidates = [
            "auto",
            "compile_after_n_calls",
            "disable",
            "enable",
            "is_enabled",
            "force_compile",
        ]
        payload["jit"] = {
            "module_available": True,
            "is_enabled": _safe_call_bool(cinderx_jit, "is_enabled"),
            "compile_after_n_calls": _safe_call_value(cinderx_jit, "get_compile_after_n_calls"),
            "entrypoints": [name for name in jit_candidates if hasattr(cinderx_jit, name)],
        }

    try:
        strict_loader = importlib.import_module("cinderx.compiler.strict.loader")
    except Exception:
        strict_loader = None
    if strict_loader is not None:
        loader_candidates = ["install", "init_static_python"]
        payload["static_loader"] = {
            "module_available": True,
            "entrypoints": [name for name in loader_candidates if hasattr(strict_loader, name)],
        }
    return payload


def build_report() -> dict[str, Any]:
    env_keys = [
        "CINDERX_DISABLE",
        "PYTHON_GIL",
        "PYTHONJITAUTO",
        "PYTHONJITDISABLE",
        "PYTHONINSTALLSTRICTLOADER",
        "PYTHONENABLEPATCHING",
    ]
    return {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "env": {key: os.environ.get(key) for key in env_keys},
        "cinderx": cinderx_info(),
    }


def main() -> int:
    args = parse_args()
    report = build_report()

    if args.json:
        print(json.dumps(report, sort_keys=True))
        return 0

    print(f"python_executable={report['python_executable']}")
    print(f"python_implementation={report['python_implementation']}")
    print(f"python_version={report['python_version']}")
    platform_payload = report["platform"]
    print(
        "platform="
        f"{platform_payload['system']} {platform_payload['release']} {platform_payload['machine']}"
    )

    cinderx_payload = report["cinderx"]
    print(f"cinderx_available={cinderx_payload['available']}")
    print(f"cinderx_module_path={cinderx_payload['module_path']}")
    print(f"cinderx_is_initialized={cinderx_payload['is_initialized']}")
    print(f"cinderx_import_error={cinderx_payload['import_error']}")
    print(
        "cinderx_feature_entrypoints="
        f"{','.join(cinderx_payload['feature_entrypoints']) if cinderx_payload['feature_entrypoints'] else 'none'}"
    )
    runtime_hooks = cinderx_payload["runtime_hooks"]
    print(
        "cinderx_runtime_hooks="
        f"install_frame_evaluator:{runtime_hooks.get('install_frame_evaluator')},"
        f"remove_frame_evaluator:{runtime_hooks.get('remove_frame_evaluator')},"
        f"is_frame_evaluator_installed:{runtime_hooks.get('is_frame_evaluator_installed')},"
        f"watch_sys_modules:{runtime_hooks.get('watch_sys_modules')}"
    )

    jit_payload = cinderx_payload["jit"]
    print(f"cinderx_jit_module_available={jit_payload['module_available']}")
    print(f"cinderx_jit_is_enabled={jit_payload['is_enabled']}")
    print(f"cinderx_jit_compile_after_n_calls={jit_payload['compile_after_n_calls']}")
    print(
        "cinderx_jit_entrypoints="
        f"{','.join(jit_payload['entrypoints']) if jit_payload['entrypoints'] else 'none'}"
    )

    loader_payload = cinderx_payload["static_loader"]
    print(f"cinderx_static_loader_module_available={loader_payload['module_available']}")
    print(
        "cinderx_static_loader_entrypoints="
        f"{','.join(loader_payload['entrypoints']) if loader_payload['entrypoints'] else 'none'}"
    )

    env_payload = report["env"]
    print(
        "cinderx_env_toggles="
        f"CINDERX_DISABLE:{env_payload['CINDERX_DISABLE']},"
        f"PYTHON_GIL:{env_payload['PYTHON_GIL']},"
        f"PYTHONJITAUTO:{env_payload['PYTHONJITAUTO']},"
        f"PYTHONJITDISABLE:{env_payload['PYTHONJITDISABLE']},"
        f"PYTHONINSTALLSTRICTLOADER:{env_payload['PYTHONINSTALLSTRICTLOADER']},"
        f"PYTHONENABLEPATCHING:{env_payload['PYTHONENABLEPATCHING']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
