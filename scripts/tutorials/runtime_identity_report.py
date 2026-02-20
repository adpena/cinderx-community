#!/usr/bin/env python3
"""Print runtime identity details for CPython/CinderX verification."""

from __future__ import annotations

import argparse
import json
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


def cinderx_info() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "available": False,
        "module_path": None,
        "feature_entrypoints": [],
    }
    try:
        import cinderx  # type: ignore[import-not-found]
    except Exception:
        return payload

    payload["available"] = True
    payload["module_path"] = getattr(cinderx, "__file__", None)
    candidates = ["init", "enable", "install", "disable"]
    payload["feature_entrypoints"] = [name for name in candidates if hasattr(cinderx, name)]
    return payload


def build_report() -> dict[str, Any]:
    return {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
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
    print(
        "cinderx_feature_entrypoints="
        f"{','.join(cinderx_payload['feature_entrypoints']) if cinderx_payload['feature_entrypoints'] else 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
