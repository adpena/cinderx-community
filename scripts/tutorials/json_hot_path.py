#!/usr/bin/env python3
"""Run a tiny JSON-heavy workload for quick local CPython vs CinderX comparisons."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=2000, help="Loop count")
    parser.add_argument("--payload-size", type=int, default=256, help="List length in payload")
    parser.add_argument("--warmups", type=int, default=2, help="Warmup rounds before timed samples")
    parser.add_argument("--samples", type=int, default=5, help="Timed samples")
    return parser.parse_args()


def build_payload(payload_size: int) -> dict[str, Any]:
    return {
        "service": "cinderx-community",
        "active": True,
        "numbers": [index * 3 for index in range(payload_size)],
        "meta": {
            "owner": "community",
            "version": 1,
            "tags": ["json", "tutorial", "benchmark-shape"],
        },
    }


def run_once(*, payload: dict[str, Any], iterations: int) -> float:
    start = time.perf_counter()
    checksum = 0
    for _ in range(iterations):
        encoded = json.dumps(payload, separators=(",", ":"))
        decoded = json.loads(encoded)
        checksum += int(decoded["active"])
    elapsed = time.perf_counter() - start
    if checksum <= 0:
        raise RuntimeError("Unexpected checksum")
    return elapsed


def main() -> int:
    args = parse_args()
    if args.iterations <= 0:
        raise SystemExit("--iterations must be > 0")
    if args.payload_size <= 0:
        raise SystemExit("--payload-size must be > 0")
    if args.samples <= 0:
        raise SystemExit("--samples must be > 0")

    payload = build_payload(args.payload_size)

    for _ in range(max(args.warmups, 0)):
        run_once(payload=payload, iterations=args.iterations)

    sample_seconds = [run_once(payload=payload, iterations=args.iterations) for _ in range(args.samples)]

    mean_seconds = statistics.fmean(sample_seconds)
    stdev_seconds = statistics.stdev(sample_seconds) if len(sample_seconds) > 1 else 0.0

    print(f"iterations={args.iterations}")
    print(f"payload_size={args.payload_size}")
    print(f"samples={args.samples}")
    print(f"mean_seconds={mean_seconds:.6f}")
    print(f"stdev_seconds={stdev_seconds:.6f}")
    print(f"mean_ms={(mean_seconds * 1000):.3f}")
    print(f"mean_us_per_iteration={(mean_seconds / args.iterations) * 1_000_000:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
