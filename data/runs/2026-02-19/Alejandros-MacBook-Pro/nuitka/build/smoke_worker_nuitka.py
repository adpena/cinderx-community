import gc
import hashlib
import json
import math
import sys
import tempfile
import time

try:
    import resource
except ImportError:  # pragma: no cover - non-POSIX fallback
    resource = None

case = sys.argv[1]
warmups = int(sys.argv[2])
samples = int(sys.argv[3])
loops = int(sys.argv[4])

def run_case(name: str, n: int) -> int:
    if name == "dynamic_dispatch":
        class Box:
            __slots__ = ("value",)

            def __init__(self, value: int) -> None:
                self.value = value

        boxes = [Box(i) for i in range(32)]
        total = 0
        for i in range(n):
            item = boxes[i & 31]
            total += getattr(item, "value")
            item.value = (item.value + i) & 255
        return total

    if name == "compute_numeric":
        total = 0.0
        for i in range(1, n + 1):
            total += (i * i) / (i + 1)
        return int(math.fsum([total]))

    if name == "serialization_json":
        payload = {
            "name": "cinderx-community",
            "values": [1, 2, 3, 4, 5],
            "nested": {"jit": True, "static": True, "phase": 3},
        }
        total = 0
        for i in range(n):
            payload["i"] = i
            encoded = json.dumps(payload, sort_keys=True)
            decoded = json.loads(encoded)
            total += int(decoded["i"])
        return total

    if name == "io_tempfile":
        blob = b"cinderx-benchmark-payload\n" * 4
        total = 0
        for i in range(n):
            with tempfile.NamedTemporaryFile() as handle:
                handle.write(blob)
                handle.flush()
                handle.seek(0)
                total += len(handle.read()) + i
        return total

    if name == "hashlib_sha256":
        seed = b"cinderx-community"
        total = 0
        for i in range(n):
            digest = hashlib.sha256(seed + i.to_bytes(8, "little")).digest()
            total += digest[0]
        return total

    raise ValueError(f"unknown benchmark case: {name}")

def measure_once() -> float:
    gc.collect()
    start = time.perf_counter()
    run_case(case, loops)
    end = time.perf_counter()
    return end - start

warmup_times = [measure_once() for _ in range(warmups)]
sample_times = [measure_once() for _ in range(samples)]

rss_max_bytes = None
if resource is not None:
    try:
        raw_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if raw_rss > 0:
            if sys.platform == "darwin":
                rss_max_bytes = raw_rss
            else:
                rss_max_bytes = raw_rss * 1024
    except (TypeError, ValueError, OSError):
        rss_max_bytes = None

print(
    json.dumps(
        {
            "warmups": warmup_times,
            "samples": sample_times,
            "rss_max_bytes": rss_max_bytes,
        }
    )
)
