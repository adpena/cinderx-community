#!/usr/bin/env python3
"""Apply CinderX bootstrap settings for existing CPython projects."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import pathlib
import sys
from typing import Any

DEFAULT_JIT_COMPILE_AFTER_N_CALLS = 40000
JIT_MODES = ("leave-default", "all", "auto", "compile-after-n-calls", "disable")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jit-mode",
        choices=JIT_MODES,
        default="leave-default",
        help="How to configure cinderx.jit in this process.",
    )
    parser.add_argument(
        "--jit-compile-after-n-calls",
        type=int,
        default=DEFAULT_JIT_COMPILE_AFTER_N_CALLS,
        help="Threshold for --jit-mode=compile-after-n-calls.",
    )
    parser.add_argument(
        "--install-static-loader",
        action="store_true",
        help="Install cinderx.compiler.strict.loader into sys.path_hooks.",
    )
    parser.add_argument(
        "--enable-patching",
        action="store_true",
        help="When static loader is installed, call install(enable_patching=True).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON report instead of key=value lines.",
    )
    return parser.parse_args()


def _safe_call(member: object, *args: object, **kwargs: object) -> Any:
    if not callable(member):
        return None
    try:
        return member(*args, **kwargs)
    except Exception:
        return None


def apply_bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    report: dict[str, Any] = {
        "cinderx_available": False,
        "actions_applied": [],
        "warnings": [],
        "jit_mode": args.jit_mode,
        "jit_compile_after_n_calls": None,
        "jit_is_enabled": None,
        "static_loader_installed": False,
        "strict_stubs_path": None,
        "strict_stubs_exists": None,
    }

    if args.jit_mode == "compile-after-n-calls" and args.jit_compile_after_n_calls <= 0:
        report["warnings"].append("--jit-compile-after-n-calls must be > 0; skipping JIT threshold")
        args.jit_compile_after_n_calls = DEFAULT_JIT_COMPILE_AFTER_N_CALLS

    try:
        import cinderx  # type: ignore[import-not-found]
    except Exception as exc:
        report["warnings"].append(f"import cinderx failed: {type(exc).__name__}: {exc}")
        return report

    report["cinderx_available"] = True
    report["cinderx_module_path"] = getattr(cinderx, "__file__", None)
    strict_stubs_path: str | None = None
    configured_stub_path = (
        (getattr(sys, "_xoptions", {}) or {}).get("strict-module-stubs-path")
        or os.environ.get("PYTHONSTRICTMODULESTUBSPATH")
    )
    if configured_stub_path:
        strict_stubs_path = str(pathlib.Path(configured_stub_path).expanduser())
    elif report["cinderx_module_path"]:
        strict_stubs_path = str(
            pathlib.Path(str(report["cinderx_module_path"])).resolve().parent
            / "compiler"
            / "strict"
            / "stubs"
        )
    report["strict_stubs_path"] = strict_stubs_path
    report["strict_stubs_exists"] = bool(
        strict_stubs_path and pathlib.Path(strict_stubs_path).exists()
    )

    if hasattr(cinderx, "init"):
        _safe_call(cinderx.init)
        report["actions_applied"].append("cinderx.init()")

    jit_module = None
    if args.jit_mode != "leave-default":
        try:
            jit_module = importlib.import_module("cinderx.jit")
        except Exception as exc:
            report["warnings"].append(
                f"import cinderx.jit failed while applying jit mode: {type(exc).__name__}: {exc}"
            )
        else:
            if args.jit_mode == "all" and hasattr(jit_module, "compile_after_n_calls"):
                _safe_call(jit_module.compile_after_n_calls, 0)
                report["actions_applied"].append("cinderx.jit.compile_after_n_calls(0)")
            elif args.jit_mode == "all" and hasattr(jit_module, "auto"):
                _safe_call(jit_module.auto)
                report["actions_applied"].append("cinderx.jit.auto()")
            elif args.jit_mode == "auto" and hasattr(jit_module, "auto"):
                _safe_call(jit_module.auto)
                report["actions_applied"].append("cinderx.jit.auto()")
            elif args.jit_mode == "compile-after-n-calls" and hasattr(
                jit_module, "compile_after_n_calls"
            ):
                _safe_call(jit_module.compile_after_n_calls, args.jit_compile_after_n_calls)
                report["actions_applied"].append(
                    f"cinderx.jit.compile_after_n_calls({args.jit_compile_after_n_calls})"
                )
            elif args.jit_mode == "disable" and hasattr(jit_module, "disable"):
                _safe_call(jit_module.disable)
                report["actions_applied"].append("cinderx.jit.disable()")
                if hasattr(cinderx, "remove_frame_evaluator"):
                    _safe_call(cinderx.remove_frame_evaluator)
                    report["actions_applied"].append("cinderx.remove_frame_evaluator()")
            else:
                report["warnings"].append(
                    f"jit mode '{args.jit_mode}' was requested, but required API was missing."
                )

    if jit_module is None:
        try:
            jit_module = importlib.import_module("cinderx.jit")
        except Exception:
            jit_module = None

    if jit_module is not None:
        report["jit_is_enabled"] = _safe_call(getattr(jit_module, "is_enabled", None))
        report["jit_compile_after_n_calls"] = _safe_call(
            getattr(jit_module, "get_compile_after_n_calls", None)
        )

    if args.install_static_loader:
        if not report["strict_stubs_exists"]:
            report["warnings"].append(
                "strict stubs path is missing; static loader install may fail. "
                "Set PYTHONSTRICTMODULESTUBSPATH to a valid strict stubs directory."
            )
        try:
            strict_loader = importlib.import_module("cinderx.compiler.strict.loader")
        except Exception as exc:
            report["warnings"].append(
                "import cinderx.compiler.strict.loader failed while applying static loader: "
                f"{type(exc).__name__}: {exc}"
            )
        else:
            install_fn = getattr(strict_loader, "install", None)
            if callable(install_fn):
                _safe_call(install_fn, enable_patching=bool(args.enable_patching))
                report["actions_applied"].append(
                    "cinderx.compiler.strict.loader.install("
                    f"enable_patching={bool(args.enable_patching)})"
                )
                report["static_loader_installed"] = True
            else:
                report["warnings"].append(
                    "cinderx.compiler.strict.loader.install() was not available."
                )

    return report


def main() -> int:
    args = parse_args()
    report = apply_bootstrap(args)

    if args.json:
        print(json.dumps(report, sort_keys=True))
        return 0

    print(f"cinderx_available={report['cinderx_available']}")
    print(f"cinderx_module_path={report.get('cinderx_module_path')}")
    print(f"jit_mode={report['jit_mode']}")
    print(f"jit_is_enabled={report['jit_is_enabled']}")
    print(f"jit_compile_after_n_calls={report['jit_compile_after_n_calls']}")
    print(f"static_loader_installed={report['static_loader_installed']}")
    actions = report["actions_applied"]
    print(f"actions_applied={','.join(actions) if actions else 'none'}")
    warnings = report["warnings"]
    print(f"warnings={'; '.join(warnings) if warnings else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
