#!/usr/bin/env python3
"""Simple HTTP request loop for tutorial-level local latency checks."""

from __future__ import annotations

import argparse
import time
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8010/health/", help="HTTP URL to hit")
    parser.add_argument("--count", type=int, default=50, help="Number of requests")
    parser.add_argument("--timeout", type=float, default=5.0, help="Per-request timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.count <= 0:
        raise SystemExit("--count must be > 0")

    start = time.perf_counter()
    for _ in range(args.count):
        with urllib.request.urlopen(args.url, timeout=args.timeout) as response:  # nosec B310
            response.read()
    elapsed = time.perf_counter() - start

    print(f"url={args.url}")
    print(f"requests={args.count}")
    print(f"elapsed_seconds={elapsed:.4f}")
    print(f"mean_ms={(elapsed / args.count) * 1000:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
