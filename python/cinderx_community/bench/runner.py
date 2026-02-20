"""Benchmark harness utilities for reproducible smoke benchmarking."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from cinderx_community import upstream

SMOKE_SUITE = "smoke"
PYPERFORMANCE_SUITE = "pyperformance"
PLANNED_ONLY_SUITES = ["numba-asv", "real-apps"]
SUPPORTED_SUITES = [
    SMOKE_SUITE,
    PYPERFORMANCE_SUITE,
    *PLANNED_ONLY_SUITES,
]
PUBLISHABLE_SUITES = [SMOKE_SUITE, PYPERFORMANCE_SUITE]
PYPERFORMANCE_BOOTSTRAP_PROFILES = [
    "cinderx-init",
    "cinderx-all-features",
    "cinderx-jit-auto",
    "cinderx-jit-compile-after-n-calls",
    "cinderx-jit-disable",
    "cinderx-static-loader",
    "cinderx-static-loader-patching",
]
DEFAULT_PYPERFORMANCE_JIT_COMPILE_AFTER_N_CALLS = 40000
AUTO_PYPERFORMANCE_BOOTSTRAP_PROFILE = "cinderx-all-features"

WORKLOAD_TAXONOMY = [
    {
        "class": "interpreter-heavy-dynamic-dispatch",
        "why_it_matters": (
            "Exercises call overhead, attribute lookup, and frame dispatch "
            "where JIT/frame-eval behavior is most visible."
        ),
    },
    {
        "class": "compute-bound-numeric",
        "why_it_matters": (
            "Measures numeric steady-state loops where lowering and optimization "
            "quality can dominate."
        ),
    },
    {
        "class": "io-bound",
        "why_it_matters": (
            "Captures filesystem/network style latency where VM speedups may be "
            "bounded by system calls."
        ),
    },
    {
        "class": "serialization-heavy",
        "why_it_matters": (
            "Stresses JSON/pickle/msgpack-style payload handling common in services and APIs."
        ),
    },
    {
        "class": "web-framework",
        "why_it_matters": (
            "Represents end-to-end request throughput and latency under realistic framework stacks."
        ),
    },
    {
        "class": "c-extension-dominated",
        "why_it_matters": (
            "Shows optimization ceilings when most cycles occur in native "
            "extensions (NumPy/Pandas/etc.)."
        ),
    },
]

SMOKE_WORKER = textwrap.dedent(
    """
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
            blob = b"cinderx-benchmark-payload\\n" * 4
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
    """
).strip()


@dataclass(slots=True)
class BenchmarkPlan:
    suite: str
    python_executable: Path
    notes: str


@dataclass(slots=True)
class SmokeCase:
    benchmark: str
    workload_class: str
    description: str
    loops: int
    ci_loops: int


@dataclass(slots=True)
class RuntimeTarget:
    key: str
    label: str
    mode: str
    executable: Path | None
    available: bool
    reason: str | None
    source: str


@dataclass(slots=True)
class BenchmarkRunResult:
    suite: str
    run_id: str
    machine: str
    output_root: str
    summary_path: str
    latest_summary_path: str
    static_summary_path: str | None
    runtime_reports: list[str]
    skipped_runtimes: list[str]
    benchmark_rows: int
    notes: list[str]


@dataclass(slots=True)
class PublishVerificationResult:
    summary_root: str
    static_summary_root: str | None
    suites_checked: list[str]
    checked_files: list[str]
    notes: list[str]


@dataclass(slots=True)
class MetadataDossierResult:
    summary_root: str
    output_root: str
    suites_exported: list[str]
    output_files: list[str]
    notes: list[str]


@dataclass(slots=True)
class PyperformancePreflightResult:
    suite: str
    runtime: str
    runtime_executable: str
    commands: list[str]
    bootstrap_profile: str | None
    bootstrap_profile_source: str
    bootstrap_mode: str
    bootstrap_target_runtime_key: str | None
    bootstrap_inline_sha256: str | None
    notes: list[str]


SMOKE_CASES = [
    SmokeCase(
        benchmark="dynamic_dispatch",
        workload_class="interpreter-heavy-dynamic-dispatch",
        description="Attribute lookup and dynamic dispatch loops.",
        loops=36_000,
        ci_loops=8_000,
    ),
    SmokeCase(
        benchmark="compute_numeric",
        workload_class="compute-bound-numeric",
        description="Pure-Python numeric loop with arithmetic accumulation.",
        loops=260_000,
        ci_loops=65_000,
    ),
    SmokeCase(
        benchmark="serialization_json",
        workload_class="serialization-heavy",
        description="JSON encode/decode roundtrip over nested payloads.",
        loops=8_000,
        ci_loops=2_000,
    ),
    SmokeCase(
        benchmark="io_tempfile",
        workload_class="io-bound",
        description="Filesystem write/read roundtrip through temporary files.",
        loops=550,
        ci_loops=140,
    ),
    SmokeCase(
        benchmark="hashlib_sha256",
        workload_class="c-extension-dominated",
        description="Hashing loop using stdlib native extension pathways.",
        loops=22_000,
        ci_loops=6_000,
    ),
]


def list_suites() -> list[str]:
    return list(SUPPORTED_SUITES)


def list_workload_taxonomy() -> list[dict[str, str]]:
    return [dict(item) for item in WORKLOAD_TAXONOMY]


def validate_suite(suite: str) -> None:
    if suite not in SUPPORTED_SUITES:
        known = ", ".join(SUPPORTED_SUITES)
        raise ValueError(f"Unknown suite '{suite}'. Expected one of: {known}")


def build_plan(suite: str, python_executable: Path) -> BenchmarkPlan:
    validate_suite(suite)

    path = Path(os.path.abspath(str(python_executable.expanduser())))
    if not path.exists():
        raise ValueError(f"Python executable does not exist: {path}")

    if suite == SMOKE_SUITE:
        note = "Executable smoke suite: produces raw run artifacts + normalized summary JSON."
    elif suite == PYPERFORMANCE_SUITE:
        note = (
            "Executable pyperformance suite: runs pyperformance per runtime adapter and "
            "normalizes outputs into summary JSON."
        )
    else:
        note = (
            "Planning mode: this suite is declared but not yet automated in the harness. "
            "Use --suite smoke or --suite pyperformance "
            "for runnable, reproducible baselines."
        )

    return BenchmarkPlan(suite=suite, python_executable=path, notes=note)


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _stdev(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def _approx_p_value(reference: list[float], candidate: list[float]) -> float | None:
    if len(reference) < 2 or len(candidate) < 2:
        return None
    ref_var = statistics.variance(reference)
    cand_var = statistics.variance(candidate)
    denominator = math.sqrt((ref_var / len(reference)) + (cand_var / len(candidate)))
    if denominator <= 0:
        return 1.0
    z_score = abs((_mean(reference) - _mean(candidate)) / denominator)
    return max(0.0, min(1.0, math.erfc(z_score / math.sqrt(2.0))))


def _classify_benchmark_name(name: str) -> str:
    lower = name.lower()
    if any(token in lower for token in ("json", "pickle", "msgpack", "marshal")):
        return "serialization-heavy"
    if any(token in lower for token in ("django", "flask", "uvicorn", "gunicorn", "http", "web")):
        return "web-framework"
    if any(token in lower for token in ("numpy", "pandas", "scipy")):
        return "c-extension-dominated"
    if any(
        token in lower
        for token in ("nbody", "spectral", "fannkuch", "float", "hexiom", "chaos", "math")
    ):
        return "compute-bound-numeric"
    if any(token in lower for token in ("sqlite", "io", "pathlib", "logging", "regex")):
        return "io-bound"
    return "interpreter-heavy-dynamic-dispatch"


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _warmup_values(payload: Any) -> list[float]:
    if not isinstance(payload, list):
        return []

    values: list[float] = []
    for item in payload:
        if isinstance(item, list | tuple):
            for candidate in reversed(item):
                parsed = _coerce_float(candidate)
                if parsed is not None:
                    values.append(parsed)
                    break
            continue
        parsed = _coerce_float(item)
        if parsed is not None:
            values.append(parsed)
    return values


def _available_python_runtime_keys(targets: list[RuntimeTarget]) -> list[str]:
    return [
        target.key for target in targets if target.available and target.mode == "python-runtime"
    ]


@lru_cache(maxsize=16)
def _runtime_cinderx_probe(executable: str) -> tuple[bool, str]:
    script = textwrap.dedent(
        """
        import json
        import importlib
        import platform
        import sys

        payload = {
            "has_module": False,
            "branded": False,
            "is_initialized": False,
            "has_jit_module": False,
            "jit_entrypoints": [],
            "has_static_loader_install": False,
            "error": None,
            "result": False,
        }
        try:
            import cinderx
            payload["has_module"] = True
            payload["is_initialized"] = bool(getattr(cinderx, "is_initialized", lambda: False)())

            try:
                jit_module = importlib.import_module("cinderx.jit")
            except BaseException:
                jit_module = None
            if jit_module is not None:
                payload["has_jit_module"] = True
                jit_candidates = [
                    "auto",
                    "compile_after_n_calls",
                    "disable",
                    "enable",
                    "is_enabled",
                ]
                payload["jit_entrypoints"] = [
                    name for name in jit_candidates if hasattr(jit_module, name)
                ]

            try:
                strict_loader = importlib.import_module("cinderx.compiler.strict.loader")
            except BaseException:
                strict_loader = None
            payload["has_static_loader_install"] = bool(
                strict_loader is not None and hasattr(strict_loader, "install")
            )
        except BaseException as exc:
            payload["error"] = f"{type(exc).__name__}: {exc}"

        payload["branded"] = "cinder" in sys.version.lower()
        if not payload["branded"]:
            payload["branded"] = "cinder" in platform.python_implementation().lower()
        payload["result"] = bool(payload["has_module"] or payload["branded"])
        print(json.dumps(payload))
        """
    ).strip()

    try:
        completed = subprocess.run(
            [executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except FileNotFoundError:
        return False, f"probe executable not found: {executable}"
    except subprocess.TimeoutExpired:
        return False, "probe timed out after 20s"

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        stderr_text = stderr or "(no stderr)"
        return (
            False,
            f"probe exited with code {completed.returncode}; stderr={stderr_text}",
        )

    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            result = bool(payload.get("result"))
            has_module = bool(payload.get("has_module"))
            branded = bool(payload.get("branded"))
            is_initialized = bool(payload.get("is_initialized"))
            has_jit_module = bool(payload.get("has_jit_module"))
            has_static_loader_install = bool(payload.get("has_static_loader_install"))
            jit_entrypoints = payload.get("jit_entrypoints")
            if isinstance(jit_entrypoints, list):
                jit_entrypoints_text = ",".join(str(item) for item in jit_entrypoints)
            else:
                jit_entrypoints_text = ""
            error = str(payload.get("error") or "")
            return (
                result,
                " ".join(
                    [
                        f"result={result}",
                        f"has_module={has_module}",
                        f"branded={branded}",
                        f"is_initialized={is_initialized}",
                        f"has_jit_module={has_jit_module}",
                        f"jit_entrypoints={jit_entrypoints_text or 'none'}",
                        f"has_static_loader_install={has_static_loader_install}",
                        f"error={error!r}",
                    ]
                ),
            )

    truncated_stdout = "\n".join(stdout.splitlines()[-5:])
    stderr_text = stderr or "(no stderr)"
    return (
        False,
        "probe succeeded but emitted no parseable JSON payload; "
        f"stdout_tail={truncated_stdout!r} stderr={stderr_text!r}",
    )


def _runtime_has_cinderx_support(executable: str) -> bool:
    supported, _ = _runtime_cinderx_probe(executable)
    return supported


def _enforce_cinderx_baseline_policy(
    *, targets: list[RuntimeTarget], require_cinderx_baseline: bool
) -> None:
    cinderx_target = next((target for target in targets if target.key == "cpython-cinderx"), None)
    if (
        cinderx_target is not None
        and cinderx_target.available
        and cinderx_target.executable is not None
    ):
        executable = str(cinderx_target.executable)
        if not _runtime_has_cinderx_support(executable):
            _, probe_detail = _runtime_cinderx_probe(executable)
            raise ValueError(
                "The executable provided to --cpython-cinderx does not appear to expose CinderX "
                "(`import cinderx` failed). Provide a real CinderX-enabled interpreter or omit "
                f"--cpython-cinderx. Probe detail: {probe_detail}"
            )

    if not require_cinderx_baseline:
        return

    available_runtime_keys = [target.key for target in targets if target.available]
    comparison_runtime_keys = [key for key in available_runtime_keys if key != "cpython"]
    cinderx_available = "cpython-cinderx" in available_runtime_keys

    if comparison_runtime_keys and not cinderx_available:
        raise ValueError(
            "CinderX baseline is required for comparison runs. "
            "Provide --cpython-cinderx /path/to/cinderx-python."
        )


def _select_baseline_runtime(runtime_case_means: dict[str, dict[str, float]]) -> str:
    baseline_runtime = "cpython-cinderx"
    if baseline_runtime not in runtime_case_means:
        baseline_runtime = "cpython"
    if baseline_runtime not in runtime_case_means:
        baseline_runtime = next(iter(runtime_case_means), "unknown")
    return baseline_runtime


def _apply_baseline_metrics(
    *,
    benchmark_rows: list[dict[str, Any]],
    runtime_case_means: dict[str, dict[str, float]],
    runtime_case_samples: dict[str, dict[str, list[float]]],
    baseline_runtime: str,
) -> None:
    baseline_means = runtime_case_means.get(baseline_runtime, {})
    baseline_samples = runtime_case_samples.get(baseline_runtime, {})

    for row in benchmark_rows:
        benchmark = str(row["benchmark"])
        baseline_mean = baseline_means.get(benchmark)
        runtime = str(row["runtime"])
        mean_seconds = float(row["mean_seconds"])
        if baseline_mean is None or mean_seconds <= 0:
            row["speedup_vs_baseline"] = None
        elif runtime == baseline_runtime:
            row["speedup_vs_baseline"] = 1.0
        else:
            row["speedup_vs_baseline"] = baseline_mean / mean_seconds

        if runtime == baseline_runtime:
            row["p_value"] = None
            continue

        row["p_value"] = _approx_p_value(
            baseline_samples.get(benchmark, []),
            runtime_case_samples.get(runtime, {}).get(benchmark, []),
        )


def _safe_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file did not contain an object payload: {path}")
    return payload


def _validate_publishable_summary_payload(
    *, payload: dict[str, Any], expected_suite: str, source: str
) -> list[str]:
    failures: list[str] = []
    allowed_runtime_keys = {"cpython", "cpython-cinderx", "pypy"}

    for key in ("run_id", "generated_at_utc", "machine"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"{source}: required top-level field '{key}' is missing or empty.")

    if payload.get("suite") != expected_suite:
        failures.append(
            f"{source}: expected suite '{expected_suite}', found '{payload.get('suite')}'."
        )

    if payload.get("baseline_runtime") != "cpython-cinderx":
        failures.append(
            f"{source}: baseline_runtime must be 'cpython-cinderx' for publishable comparisons."
        )

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        failures.append(f"{source}: metadata object is missing.")
        return failures

    host = metadata.get("host")
    if not isinstance(host, dict):
        failures.append(f"{source}: metadata.host is missing.")
    else:
        for key in ("os", "kernel", "architecture", "cpu_model", "cpu_logical_count"):
            if key not in host:
                failures.append(f"{source}: metadata.host.{key} is missing.")
        if "ram_total_bytes" not in host:
            failures.append(f"{source}: metadata.host.ram_total_bytes is missing.")

    run_config = metadata.get("run_config")
    if not isinstance(run_config, dict):
        failures.append(f"{source}: metadata.run_config is missing.")
    else:
        if run_config.get("require_cinderx_baseline") is not True:
            failures.append(f"{source}: metadata.run_config.require_cinderx_baseline must be true.")
        if "ci_mode" not in run_config:
            failures.append(f"{source}: metadata.run_config.ci_mode is missing.")

    toolchain = metadata.get("toolchain")
    if not isinstance(toolchain, dict):
        failures.append(f"{source}: metadata.toolchain is missing.")
    else:
        if not isinstance(toolchain.get("benchmark_repo_sha"), str):
            failures.append(f"{source}: metadata.toolchain.benchmark_repo_sha is missing.")
        cinderx_upstream = toolchain.get("cinderx_upstream")
        if not isinstance(cinderx_upstream, dict):
            failures.append(f"{source}: metadata.toolchain.cinderx_upstream is missing.")
        else:
            for key in ("repo_url", "commit_sha", "clone_timestamp_utc"):
                if not isinstance(cinderx_upstream.get(key), str):
                    failures.append(
                        f"{source}: metadata.toolchain.cinderx_upstream.{key} is missing."
                    )

    guardrails = metadata.get("guardrails")
    if not isinstance(guardrails, dict):
        failures.append(f"{source}: metadata.guardrails is missing.")
    elif not isinstance(guardrails.get("checks"), list):
        failures.append(f"{source}: metadata.guardrails.checks is missing.")

    runtimes = payload.get("runtimes")
    runtime_rows = (
        [item for item in runtimes if isinstance(item, dict)] if isinstance(runtimes, list) else []
    )
    cinderx_runtime = next(
        (item for item in runtime_rows if item.get("runtime") == "cpython-cinderx"),
        None,
    )
    unexpected_runtime_rows = sorted(
        {
            str(item.get("runtime"))
            for item in runtime_rows
            if str(item.get("runtime")) not in allowed_runtime_keys
        }
    )
    if unexpected_runtime_rows:
        failures.append(
            f"{source}: runtimes contains unsupported runtime key(s): "
            f"{', '.join(unexpected_runtime_rows)}."
        )

    if cinderx_runtime is None:
        failures.append(f"{source}: runtimes is missing an executed 'cpython-cinderx' row.")
    elif cinderx_runtime.get("executed") is not True:
        failures.append(f"{source}: runtime row 'cpython-cinderx' exists but executed is not true.")
    else:
        if not isinstance(cinderx_runtime.get("runtime_version"), str):
            failures.append(f"{source}: runtime row 'cpython-cinderx' is missing runtime_version.")
        if "runtime_details" not in cinderx_runtime:
            failures.append(f"{source}: runtime row 'cpython-cinderx' is missing runtime_details.")

    benchmarks = payload.get("benchmarks")
    benchmark_rows = (
        [item for item in benchmarks if isinstance(item, dict)]
        if isinstance(benchmarks, list)
        else []
    )
    cinderx_benchmark_rows = [
        row for row in benchmark_rows if row.get("runtime") == "cpython-cinderx"
    ]
    unexpected_benchmark_rows = sorted(
        {
            str(row.get("runtime"))
            for row in benchmark_rows
            if str(row.get("runtime")) not in allowed_runtime_keys
        }
    )
    if unexpected_benchmark_rows:
        failures.append(
            f"{source}: benchmarks contains unsupported runtime key(s): "
            f"{', '.join(unexpected_benchmark_rows)}."
        )

    if not cinderx_benchmark_rows:
        failures.append(f"{source}: benchmarks is missing rows for runtime 'cpython-cinderx'.")
    else:
        invalid_speedups = 0
        for row in cinderx_benchmark_rows:
            speedup = _coerce_float(row.get("speedup_vs_baseline"))
            if speedup is None or abs(speedup - 1.0) > 1e-9:
                invalid_speedups += 1
        if invalid_speedups:
            failures.append(
                f"{source}: cpython-cinderx benchmark rows must have speedup_vs_baseline=1.0."
            )

    return failures


def _validate_summary_index_for_suites(
    *, index_payload: dict[str, Any], suites: list[str], source: str
) -> list[str]:
    failures: list[str] = []
    entries_raw = index_payload.get("entries")
    if not isinstance(entries_raw, list):
        return [f"{source}: index entries list is missing."]

    entries = [item for item in entries_raw if isinstance(item, dict)]
    if not entries:
        failures.append(f"{source}: index has no entries.")
        return failures

    for suite in suites:
        if not any(entry.get("suite") == suite for entry in entries):
            failures.append(f"{source}: index has no entry for suite '{suite}'.")
    return failures


def _parse_generated_at_utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    normalized = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _validate_publish_suite_coherence(
    *,
    payload_by_suite: dict[str, dict[str, Any]],
    source: str,
    max_generated_at_skew_seconds: int = 3600,
) -> list[str]:
    failures: list[str] = []
    if len(payload_by_suite) < 2:
        return failures

    run_id_by_suite = {
        suite: str(payload.get("run_id") or "").strip()
        for suite, payload in payload_by_suite.items()
    }
    machine_by_suite = {
        suite: str(payload.get("machine") or "").strip()
        for suite, payload in payload_by_suite.items()
    }
    repo_sha_by_suite = {
        suite: str(
            ((payload.get("metadata") or {}).get("toolchain") or {}).get("benchmark_repo_sha") or ""
        ).strip()
        for suite, payload in payload_by_suite.items()
    }
    generated_at_by_suite = {
        suite: _parse_generated_at_utc(payload.get("generated_at_utc"))
        for suite, payload in payload_by_suite.items()
    }

    if any(not value for value in run_id_by_suite.values()):
        detail = ", ".join(
            f"{suite}={run_id or '<missing>'}" for suite, run_id in sorted(run_id_by_suite.items())
        )
        failures.append(f"{source}: suite run_id is missing ({detail}).")

    machines = {value for value in machine_by_suite.values() if value}
    if len(machines) != 1:
        detail = ", ".join(
            f"{suite}={machine or '<missing>'}"
            for suite, machine in sorted(machine_by_suite.items())
        )
        failures.append(f"{source}: suite machine mismatch ({detail}).")

    repo_shas = {value for value in repo_sha_by_suite.values() if value}
    if len(repo_shas) != 1:
        detail = ", ".join(
            f"{suite}={sha or '<missing>'}" for suite, sha in sorted(repo_sha_by_suite.items())
        )
        failures.append(f"{source}: suite benchmark_repo_sha mismatch ({detail}).")

    if any(value is None for value in generated_at_by_suite.values()):
        detail = ", ".join(
            f"{suite}={payload_by_suite[suite].get('generated_at_utc')!r}"
            for suite, value in sorted(generated_at_by_suite.items())
            if value is None
        )
        failures.append(f"{source}: invalid generated_at_utc for suite(s) ({detail}).")
    else:
        generated_values = [value for value in generated_at_by_suite.values() if value is not None]
        skew_seconds = (max(generated_values) - min(generated_values)).total_seconds()
        if skew_seconds > max_generated_at_skew_seconds:
            detail = ", ".join(
                f"{suite}={payload_by_suite[suite].get('generated_at_utc')}"
                for suite in sorted(payload_by_suite)
            )
            failures.append(
                f"{source}: suite generated_at_utc skew is {skew_seconds:.1f}s "
                f"(limit={max_generated_at_skew_seconds}s; {detail})."
            )

    return failures


def _run_command(
    args: list[str], *, timeout_s: int = 90, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
        )
    except FileNotFoundError as exc:
        raise ValueError(f"Executable not found: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or "(no stderr)"
        raise ValueError(f"Command failed: {' '.join(args)}\n{stderr}") from exc


def _version_line(executable: Path) -> str:
    commands = [
        [str(executable), "-VV"],
        [str(executable), "--version"],
    ]
    for command in commands:
        try:
            completed = _run_command(command, timeout_s=20)
        except ValueError:
            continue
        combined = (completed.stdout + "\n" + completed.stderr).strip()
        if combined:
            return combined.splitlines()[0].strip()
    return "unknown"


def _render_pyperformance_bootstrap_profile(
    *, profile: str, jit_compile_after_n_calls: int | None
) -> tuple[str, int | None]:
    if profile not in PYPERFORMANCE_BOOTSTRAP_PROFILES:
        raise ValueError(
            "Unsupported pyperformance bootstrap profile: "
            f"{profile!r}. Supported values: {', '.join(PYPERFORMANCE_BOOTSTRAP_PROFILES)}"
        )

    if profile == "cinderx-jit-compile-after-n-calls":
        if jit_compile_after_n_calls is None:
            jit_compile_after_n_calls = DEFAULT_PYPERFORMANCE_JIT_COMPILE_AFTER_N_CALLS
        if jit_compile_after_n_calls <= 0:
            raise ValueError(
                "pyperformance bootstrap jit threshold must be > 0 when using "
                "'cinderx-jit-compile-after-n-calls'."
            )
    elif jit_compile_after_n_calls is not None:
        raise ValueError(
            "--pyperformance-bootstrap-jit-compile-after-n-calls is only valid with "
            "--pyperformance-bootstrap-profile=cinderx-jit-compile-after-n-calls."
        )

    common_prefix = textwrap.dedent(
        """
        import importlib.util
        if importlib.util.find_spec("cinderx") is not None:
            import cinderx
            if hasattr(cinderx, "init"):
                cinderx.init()
        """
    ).strip()

    if profile == "cinderx-init":
        return common_prefix, None

    if profile == "cinderx-all-features":
        return (
            textwrap.dedent(
                """
                import importlib
                import importlib.util
                import os
                import pathlib
                import sys
                if importlib.util.find_spec("cinderx") is not None:
                    import cinderx
                    if hasattr(cinderx, "init"):
                        cinderx.init()
                    try:
                        import cinderx.jit as cinderx_jit
                    except Exception:
                        cinderx_jit = None
                    if cinderx_jit is not None and hasattr(cinderx_jit, "auto"):
                        cinderx_jit.auto()
                    try:
                        strict_loader = importlib.import_module("cinderx.compiler.strict.loader")
                    except Exception:
                        strict_loader = None
                    if strict_loader is not None and hasattr(strict_loader, "install"):
                        strict_stubs_dir = None
                        configured_stub_path = None
                        try:
                            xoptions = getattr(sys, "_xoptions", {}) or {}
                            configured_stub_path = (
                                xoptions.get("strict-module-stubs-path")
                                or os.environ.get("PYTHONSTRICTMODULESTUBSPATH")
                            )
                        except Exception:
                            configured_stub_path = None
                        if configured_stub_path:
                            configured_candidate = pathlib.Path(configured_stub_path).expanduser()
                            if configured_candidate.exists():
                                strict_stubs_dir = configured_candidate
                        cinderx_file = getattr(cinderx, "__file__", None)
                        if strict_stubs_dir is None and cinderx_file:
                            candidate = (
                                pathlib.Path(cinderx_file).resolve().parent
                                / "compiler"
                                / "strict"
                                / "stubs"
                            )
                            if candidate.exists():
                                strict_stubs_dir = candidate
                        if strict_stubs_dir is not None:
                            try:
                                strict_loader.install(enable_patching=True)
                            except ValueError as exc:
                                if "Strict module stubs path does not exist" not in str(exc):
                                    raise
                """
            ).strip(),
            None,
        )

    if profile == "cinderx-jit-auto":
        return (
            textwrap.dedent(
                """
                import importlib.util
                if importlib.util.find_spec("cinderx") is not None:
                    import cinderx
                    if hasattr(cinderx, "init"):
                        cinderx.init()
                    try:
                        import cinderx.jit as cinderx_jit
                    except Exception:
                        cinderx_jit = None
                    if cinderx_jit is not None and hasattr(cinderx_jit, "auto"):
                        cinderx_jit.auto()
                """
            ).strip(),
            None,
        )

    if profile == "cinderx-jit-compile-after-n-calls":
        threshold = int(
            jit_compile_after_n_calls or DEFAULT_PYPERFORMANCE_JIT_COMPILE_AFTER_N_CALLS
        )
        return (
            textwrap.dedent(
                f"""
                import importlib.util
                if importlib.util.find_spec("cinderx") is not None:
                    import cinderx
                    if hasattr(cinderx, "init"):
                        cinderx.init()
                    try:
                        import cinderx.jit as cinderx_jit
                    except Exception:
                        cinderx_jit = None
                    if cinderx_jit is not None and hasattr(cinderx_jit, "compile_after_n_calls"):
                        cinderx_jit.compile_after_n_calls({threshold})
                """
            ).strip(),
            threshold,
        )

    if profile == "cinderx-jit-disable":
        return (
            textwrap.dedent(
                """
                import importlib.util
                if importlib.util.find_spec("cinderx") is not None:
                    import cinderx
                    if hasattr(cinderx, "init"):
                        cinderx.init()
                    try:
                        import cinderx.jit as cinderx_jit
                    except Exception:
                        cinderx_jit = None
                    if cinderx_jit is not None and hasattr(cinderx_jit, "disable"):
                        cinderx_jit.disable()
                    if hasattr(cinderx, "remove_frame_evaluator"):
                        cinderx.remove_frame_evaluator()
                """
            ).strip(),
            None,
        )

    if profile == "cinderx-static-loader":
        return (
            textwrap.dedent(
                """
                import importlib
                import importlib.util
                import os
                import pathlib
                import sys
                if importlib.util.find_spec("cinderx") is not None:
                    import cinderx
                    if hasattr(cinderx, "init"):
                        cinderx.init()
                    try:
                        strict_loader = importlib.import_module("cinderx.compiler.strict.loader")
                    except Exception:
                        strict_loader = None
                    if strict_loader is not None and hasattr(strict_loader, "install"):
                        strict_stubs_dir = None
                        configured_stub_path = None
                        try:
                            xoptions = getattr(sys, "_xoptions", {}) or {}
                            configured_stub_path = (
                                xoptions.get("strict-module-stubs-path")
                                or os.environ.get("PYTHONSTRICTMODULESTUBSPATH")
                            )
                        except Exception:
                            configured_stub_path = None
                        if configured_stub_path:
                            configured_candidate = pathlib.Path(configured_stub_path).expanduser()
                            if configured_candidate.exists():
                                strict_stubs_dir = configured_candidate
                        cinderx_file = getattr(cinderx, "__file__", None)
                        if strict_stubs_dir is None and cinderx_file:
                            candidate = (
                                pathlib.Path(cinderx_file).resolve().parent
                                / "compiler"
                                / "strict"
                                / "stubs"
                            )
                            if candidate.exists():
                                strict_stubs_dir = candidate
                        if strict_stubs_dir is not None:
                            try:
                                strict_loader.install()
                            except ValueError as exc:
                                if "Strict module stubs path does not exist" not in str(exc):
                                    raise
                """
            ).strip(),
            None,
        )

    if profile == "cinderx-static-loader-patching":
        return (
            textwrap.dedent(
                """
                import importlib
                import importlib.util
                import os
                import pathlib
                import sys
                if importlib.util.find_spec("cinderx") is not None:
                    import cinderx
                    if hasattr(cinderx, "init"):
                        cinderx.init()
                    try:
                        strict_loader = importlib.import_module("cinderx.compiler.strict.loader")
                    except Exception:
                        strict_loader = None
                    if strict_loader is not None and hasattr(strict_loader, "install"):
                        strict_stubs_dir = None
                        configured_stub_path = None
                        try:
                            xoptions = getattr(sys, "_xoptions", {}) or {}
                            configured_stub_path = (
                                xoptions.get("strict-module-stubs-path")
                                or os.environ.get("PYTHONSTRICTMODULESTUBSPATH")
                            )
                        except Exception:
                            configured_stub_path = None
                        if configured_stub_path:
                            configured_candidate = pathlib.Path(configured_stub_path).expanduser()
                            if configured_candidate.exists():
                                strict_stubs_dir = configured_candidate
                        cinderx_file = getattr(cinderx, "__file__", None)
                        if strict_stubs_dir is None and cinderx_file:
                            candidate = (
                                pathlib.Path(cinderx_file).resolve().parent
                                / "compiler"
                                / "strict"
                                / "stubs"
                            )
                            if candidate.exists():
                                strict_stubs_dir = candidate
                        if strict_stubs_dir is not None:
                            try:
                                strict_loader.install(enable_patching=True)
                            except ValueError as exc:
                                if "Strict module stubs path does not exist" not in str(exc):
                                    raise
                """
            ).strip(),
            None,
        )

    raise ValueError(f"Unhandled pyperformance bootstrap profile: {profile!r}")


def _resolve_pyperformance_bootstrap_inline(
    *,
    inline_code: str | None,
    profile: str | None,
    jit_compile_after_n_calls: int | None,
) -> tuple[str | None, str | None, int | None, str]:
    bootstrap_inline = (inline_code or "").strip()
    bootstrap_profile = (profile or "").strip()

    if bootstrap_inline and bootstrap_profile:
        raise ValueError(
            "Choose either --pyperformance-bootstrap-inline or "
            "--pyperformance-bootstrap-profile, not both."
        )

    if bootstrap_profile:
        rendered, resolved_threshold = _render_pyperformance_bootstrap_profile(
            profile=bootstrap_profile,
            jit_compile_after_n_calls=jit_compile_after_n_calls,
        )
        return rendered, bootstrap_profile, resolved_threshold, "profile"

    if jit_compile_after_n_calls is not None:
        raise ValueError(
            "--pyperformance-bootstrap-jit-compile-after-n-calls requires "
            "--pyperformance-bootstrap-profile=cinderx-jit-compile-after-n-calls."
        )

    if not bootstrap_inline:
        return None, None, None, "disabled"

    return bootstrap_inline, None, None, "inline"


def _prepare_pyperformance_bootstrap(
    inline_code: str | None,
    *,
    source_mode: str,
    target_runtime_key: str | None = "cpython-cinderx",
) -> tuple[dict[str, str], tempfile.TemporaryDirectory[str] | None, str | None, str]:
    bootstrap = (inline_code or "").strip()
    if not bootstrap:
        return {}, None, None, "disabled"

    if source_mode not in {"inline", "profile"}:
        raise ValueError(f"Unsupported pyperformance bootstrap source mode: {source_mode!r}")

    tempdir = tempfile.TemporaryDirectory(prefix="cxc-pyperf-bootstrap-")
    shim_root = Path(tempdir.name)
    sitecustomize = textwrap.dedent(
        """
        import os
        import sys

        bootstrap = os.environ.get("CXC_PYPERF_BOOTSTRAP_INLINE", "").strip()
        bootstrap_target_runtime = os.environ.get(
            "CXC_PYPERF_BOOTSTRAP_TARGET_RUNTIME_KEY", ""
        ).strip()
        runtime_key = os.environ.get("CXC_PYPERF_RUNTIME_KEY", "").strip()
        should_apply = not bootstrap_target_runtime or runtime_key == bootstrap_target_runtime
        if bootstrap:
            if should_apply:
                namespace = {}
                try:
                    exec(bootstrap, namespace, namespace)
                except Exception as exc:  # pragma: no cover - surfaced in benchmark logs
                    print(
                        f"[cxc-pyperf-bootstrap] inline bootstrap failed: {exc!r}",
                        file=sys.stderr,
                    )
                    raise
        """
    ).strip()
    (shim_root / "sitecustomize.py").write_text(sitecustomize, encoding="utf-8")

    env = dict(os.environ)
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{shim_root}{os.pathsep}{current_pythonpath}" if current_pythonpath else str(shim_root)
    )
    env["CXC_PYPERF_BOOTSTRAP_INLINE"] = bootstrap
    bootstrap_mode = f"sitecustomize-{source_mode}"
    env["CXC_PYPERF_BOOTSTRAP_MODE"] = bootstrap_mode
    if target_runtime_key:
        env["CXC_PYPERF_BOOTSTRAP_TARGET_RUNTIME_KEY"] = target_runtime_key
    bootstrap_sha256 = hashlib.sha256(bootstrap.encode("utf-8")).hexdigest()
    return env, tempdir, bootstrap_sha256, bootstrap_mode


@dataclass(slots=True)
class _ResolvedPyperformanceBootstrap:
    inline_code: str | None
    profile: str | None
    jit_compile_after_n_calls: int | None
    source_mode: str
    profile_source: str
    target_runtime_key: str | None
    env: dict[str, str]
    tempdir: tempfile.TemporaryDirectory[str] | None
    sha256: str | None
    mode: str


def _describe_cinderx_pyperformance_features(
    *,
    resolved_bootstrap_profile: str | None,
    bootstrap_inline_sha256: str | None,
    resolved_bootstrap_jit_compile_after_n_calls: int | None,
) -> dict[str, Any]:
    inline_enabled = bool(bootstrap_inline_sha256)
    interpreted_profile = (
        resolved_bootstrap_profile
        if resolved_bootstrap_profile
        else ("custom-inline" if inline_enabled else "disabled")
    )

    jit_mode: str | None = "unchanged"
    jit_compile_after_n_calls: int | None = None
    static_loader_enabled: bool | None = False
    static_loader_enable_patching: bool | None = False
    feature_summary = "none (plain runtime control)"

    if interpreted_profile == "cinderx-all-features":
        jit_mode = "auto"
        static_loader_enabled = True
        static_loader_enable_patching = True
        feature_summary = "JIT auto + static loader (patching)"
    elif interpreted_profile == "cinderx-jit-auto":
        jit_mode = "auto"
        feature_summary = "JIT auto"
    elif interpreted_profile == "cinderx-jit-compile-after-n-calls":
        jit_mode = "compile-after-n-calls"
        jit_compile_after_n_calls = resolved_bootstrap_jit_compile_after_n_calls
        threshold = (
            str(jit_compile_after_n_calls) if jit_compile_after_n_calls is not None else "default"
        )
        feature_summary = f"JIT compile-after-n-calls ({threshold})"
    elif interpreted_profile == "cinderx-jit-disable":
        jit_mode = "disabled"
        feature_summary = "JIT disabled"
    elif interpreted_profile == "cinderx-static-loader":
        jit_mode = "unchanged"
        static_loader_enabled = True
        static_loader_enable_patching = False
        feature_summary = "static loader"
    elif interpreted_profile == "cinderx-static-loader-patching":
        jit_mode = "unchanged"
        static_loader_enabled = True
        static_loader_enable_patching = True
        feature_summary = "static loader (patching)"
    elif interpreted_profile == "cinderx-init":
        jit_mode = "unchanged"
        feature_summary = "cinderx.init only"
    elif interpreted_profile == "custom-inline":
        jit_mode = None
        static_loader_enabled = None
        static_loader_enable_patching = None
        feature_summary = "custom inline bootstrap (inspect bootstrap hash/script)"

    return {
        "profile": interpreted_profile,
        "summary": feature_summary,
        "jit_mode": jit_mode,
        "jit_compile_after_n_calls": jit_compile_after_n_calls,
        "static_loader_enabled": static_loader_enabled,
        "static_loader_enable_patching": static_loader_enable_patching,
    }


def _resolve_pyperformance_bootstrap_for_targets(
    *,
    targets: list[RuntimeTarget],
    pyperformance_bootstrap_inline: str | None,
    pyperformance_bootstrap_profile: str | None,
    pyperformance_bootstrap_jit_compile_after_n_calls: int | None,
) -> _ResolvedPyperformanceBootstrap:
    configured_bootstrap_inline = (pyperformance_bootstrap_inline or "").strip()
    configured_bootstrap_profile = (pyperformance_bootstrap_profile or "").strip()
    cinderx_runtime_available = any(
        target.key == "cpython-cinderx" and target.available and target.executable is not None
        for target in targets
    )

    effective_bootstrap_profile = pyperformance_bootstrap_profile
    bootstrap_profile_source = "explicit" if configured_bootstrap_profile else None
    if (
        not configured_bootstrap_inline
        and not configured_bootstrap_profile
        and cinderx_runtime_available
    ):
        effective_bootstrap_profile = AUTO_PYPERFORMANCE_BOOTSTRAP_PROFILE
        bootstrap_profile_source = "auto-default"

    (
        resolved_bootstrap_inline,
        resolved_bootstrap_profile,
        resolved_bootstrap_jit_compile_after_n_calls,
        resolved_bootstrap_source_mode,
    ) = _resolve_pyperformance_bootstrap_inline(
        inline_code=pyperformance_bootstrap_inline,
        profile=effective_bootstrap_profile,
        jit_compile_after_n_calls=pyperformance_bootstrap_jit_compile_after_n_calls,
    )

    resolved_bootstrap_profile_source = "disabled"
    if resolved_bootstrap_source_mode == "inline":
        resolved_bootstrap_profile_source = "inline"
    elif resolved_bootstrap_profile:
        resolved_bootstrap_profile_source = bootstrap_profile_source or "explicit"

    bootstrap_target_runtime_key = "cpython-cinderx" if resolved_bootstrap_inline else None
    (
        pyperformance_bootstrap_env,
        pyperformance_bootstrap_tempdir,
        pyperformance_bootstrap_sha256,
        pyperformance_bootstrap_mode,
    ) = _prepare_pyperformance_bootstrap(
        resolved_bootstrap_inline,
        source_mode=resolved_bootstrap_source_mode,
        target_runtime_key=bootstrap_target_runtime_key,
    )

    if pyperformance_bootstrap_sha256 and bootstrap_target_runtime_key:
        bootstrap_target = next(
            (target for target in targets if target.key == bootstrap_target_runtime_key),
            None,
        )
        if (
            bootstrap_target is None
            or not bootstrap_target.available
            or bootstrap_target.executable is None
        ):
            raise ValueError(
                "Pyperformance bootstrap is configured to apply to runtime "
                f"{bootstrap_target_runtime_key!r}, but that runtime is not available. "
                "Provide --cpython-cinderx /path/to/cinderx-python."
            )

    return _ResolvedPyperformanceBootstrap(
        inline_code=resolved_bootstrap_inline,
        profile=resolved_bootstrap_profile,
        jit_compile_after_n_calls=resolved_bootstrap_jit_compile_after_n_calls,
        source_mode=resolved_bootstrap_source_mode,
        profile_source=resolved_bootstrap_profile_source,
        target_runtime_key=bootstrap_target_runtime_key,
        env=pyperformance_bootstrap_env,
        tempdir=pyperformance_bootstrap_tempdir,
        sha256=pyperformance_bootstrap_sha256,
        mode=pyperformance_bootstrap_mode,
    )


def _python_runtime_details(executable: Path) -> dict[str, str]:
    script = textwrap.dedent(
        """
        import json
        import platform
        import sys
        import sysconfig

        payload = {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "compiler": platform.python_compiler(),
            "build": str(platform.python_build()),
            "config_args": str(sysconfig.get_config_var("CONFIG_ARGS") or ""),
            "abiflags": str(getattr(sys, "abiflags", "") or ""),
        }
        print(json.dumps(payload))
        """
    ).strip()

    try:
        completed = _run_command([str(executable), "-c", script], timeout_s=30)
        parsed = json.loads(completed.stdout)
    except ValueError, json.JSONDecodeError:
        return {
            "implementation": "unknown",
            "version": "unknown",
            "compiler": "unknown",
            "build": "unknown",
            "config_args": "",
            "abiflags": "",
        }

    return {key: str(value) for key, value in parsed.items()}


def _cpu_model() -> str:
    system = platform.system().lower()

    if system == "linux":
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.exists():
            for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
                if "model name" in line:
                    _, _, value = line.partition(":")
                    return value.strip() or "unknown"

    if system == "darwin":
        try:
            completed = _run_command(["sysctl", "-n", "machdep.cpu.brand_string"], timeout_s=5)
            value = completed.stdout.strip()
            if value:
                return value
        except ValueError:
            pass

    return platform.processor() or "unknown"


def _total_ram_bytes() -> int | None:
    if (
        hasattr(os, "sysconf")
        and "SC_PAGE_SIZE" in os.sysconf_names
        and "SC_PHYS_PAGES" in os.sysconf_names
    ):
        try:
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
            page_count = int(os.sysconf("SC_PHYS_PAGES"))
            if page_size > 0 and page_count > 0:
                return page_size * page_count
        except OSError, ValueError:
            pass

    if platform.system().lower() == "darwin":
        try:
            completed = _run_command(["sysctl", "-n", "hw.memsize"], timeout_s=5)
            return int(completed.stdout.strip())
        except ValueError, TypeError:
            return None

    return None


def _current_repo_sha() -> str:
    root = Path(__file__).resolve().parents[3]
    if not (root / ".git").exists():
        return "unknown"
    try:
        completed = _run_command(["git", "rev-parse", "HEAD"], timeout_s=10)
    except ValueError:
        return "unknown"
    value = completed.stdout.strip()
    return value or "unknown"


def _guardrail_checks(ci_mode: bool) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    cpu_count = os.cpu_count() or 1
    if hasattr(os, "sched_getaffinity"):
        affinity_count = len(os.sched_getaffinity(0))
        pinned = affinity_count < cpu_count
        checks.append(
            {
                "name": "cpu_affinity",
                "status": "ok" if pinned else "warn",
                "detail": f"Visible CPUs: {affinity_count} / {cpu_count}",
                "enforceable": True,
            }
        )
        if not pinned:
            failures.append("CPU affinity is not pinned to a restricted core set.")
    else:
        checks.append(
            {
                "name": "cpu_affinity",
                "status": "info",
                "detail": "Affinity API unavailable on this platform.",
                "enforceable": False,
            }
        )

    if hasattr(os, "getloadavg"):
        load_1, _, _ = os.getloadavg()
        busy = load_1 > max(cpu_count * 0.7, 1.0)
        checks.append(
            {
                "name": "background_load",
                "status": "warn" if busy else "ok",
                "detail": f"1m load average: {load_1:.2f} (cpu_count={cpu_count})",
                "enforceable": True,
            }
        )
        if busy:
            failures.append("High background load detected; results may be noisy.")
    else:
        checks.append(
            {
                "name": "background_load",
                "status": "info",
                "detail": "Load average API unavailable.",
                "enforceable": False,
            }
        )

    checks.append(
        {
            "name": "turbo_boost",
            "status": "info",
            "detail": "Turbo/boost state is not auto-detected; document manual setting in reports.",
            "enforceable": False,
        }
    )
    checks.append(
        {
            "name": "thermal_state",
            "status": "info",
            "detail": (
                "Thermal throttling is not auto-detected; run after cool-down "
                "and note chassis/power profile."
            ),
            "enforceable": False,
        }
    )

    if ci_mode:
        checks.append(
            {
                "name": "ci_mode",
                "status": "ok",
                "detail": "CI mode enabled: smoke-only quick pass; no public performance claims.",
                "enforceable": False,
            }
        )

    return {
        "checks": checks,
        "enforceable_failures": failures,
    }


def _normalize_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    return Path(os.path.abspath(str(path.expanduser())))


def _runtime_targets(
    *,
    python: Path,
    cpython_cinderx: Path | None,
    pypy: Path | None,
    include_pypy: bool = True,
) -> list[RuntimeTarget]:
    targets: list[RuntimeTarget] = [
        RuntimeTarget(
            key="cpython",
            label="CPython baseline",
            mode="python-runtime",
            executable=python,
            available=True,
            reason=None,
            source="required",
        )
    ]

    def optional_runtime(
        key: str,
        label: str,
        mode: str,
        executable: Path | None,
        *,
        discover_names: tuple[str, ...] = (),
    ) -> None:
        source = "provided"
        if executable is None and discover_names:
            for name in discover_names:
                discovered = shutil.which(name)
                if discovered:
                    executable = Path(discovered)
                    source = f"auto-detected:{name}"
                    break

        if executable is None:
            targets.append(
                RuntimeTarget(
                    key=key,
                    label=label,
                    mode=mode,
                    executable=None,
                    available=False,
                    reason="not provided",
                    source="none",
                )
            )
            return

        resolved = Path(os.path.abspath(str(executable.expanduser())))
        if not resolved.exists():
            targets.append(
                RuntimeTarget(
                    key=key,
                    label=label,
                    mode=mode,
                    executable=resolved,
                    available=False,
                    reason="path does not exist",
                    source=source,
                )
            )
            return

        targets.append(
            RuntimeTarget(
                key=key,
                label=label,
                mode=mode,
                executable=resolved,
                available=True,
                reason=None,
                source=source,
            )
        )

    optional_runtime("cpython-cinderx", "CPython + CinderX", "python-runtime", cpython_cinderx)
    if include_pypy:
        optional_runtime(
            "pypy",
            "PyPy",
            "python-runtime",
            pypy,
            discover_names=("pypy3", "pypy"),
        )

    return targets


def _parse_smoke_worker_output(
    *, benchmark: str, output: str, runtime_label: str
) -> dict[str, Any]:
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Benchmark worker did not return JSON for '{benchmark}' using {runtime_label}."
        ) from exc

    warmup_values = [float(item) for item in parsed.get("warmups", [])]
    sample_values = [float(item) for item in parsed.get("samples", [])]
    rss_max_bytes_raw = parsed.get("rss_max_bytes")
    rss_max_bytes = None
    if rss_max_bytes_raw is not None:
        try:
            rss_candidate = int(rss_max_bytes_raw)
            if rss_candidate > 0:
                rss_max_bytes = rss_candidate
        except TypeError, ValueError:
            rss_max_bytes = None
    return {
        "warmups": warmup_values,
        "samples": sample_values,
        "rss_max_bytes": rss_max_bytes,
    }


def _run_smoke_case(
    executable: Path,
    *,
    benchmark: str,
    warmups: int,
    samples: int,
    loops: int,
) -> dict[str, Any]:
    completed = _run_command(
        [
            str(executable),
            "-c",
            SMOKE_WORKER,
            benchmark,
            str(warmups),
            str(samples),
            str(loops),
        ]
    )
    return _parse_smoke_worker_output(
        benchmark=benchmark,
        output=completed.stdout,
        runtime_label=str(executable),
    )


def _measure_startup(executable: Path, samples: int) -> list[float]:
    values: list[float] = []
    for _ in range(samples):
        start = datetime.now(UTC)
        _run_command([str(executable), "-c", "pass"], timeout_s=30)
        end = datetime.now(UTC)
        values.append((end - start).total_seconds())
    return values


def _summary_entry(
    file_name: str, suite: str, run_id: str, machine: str, generated_at_utc: str
) -> dict[str, str]:
    return {
        "file": file_name,
        "suite": suite,
        "run_id": run_id,
        "machine": machine,
        "generated_at_utc": generated_at_utc,
    }


def _update_summary_index(index_path: Path, entry: dict[str, str], generated_at_utc: str) -> None:
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}

    entries = [
        item
        for item in existing.get("entries", [])
        if isinstance(item, dict) and item.get("file") != entry["file"]
    ]
    entries.insert(0, entry)

    payload = {
        "updated_at_utc": generated_at_utc,
        "entries": entries[:100],
    }
    _safe_json(index_path, payload)


def _copy_summary_to_static(
    *,
    summary_payload: dict[str, Any],
    summary_path: Path,
    latest_summary_path: Path,
    static_root: Path,
    generated_at_utc: str,
) -> Path:
    static_root.mkdir(parents=True, exist_ok=True)
    static_summary_path = static_root / summary_path.name
    static_latest_path = static_root / latest_summary_path.name

    _safe_json(static_summary_path, summary_payload)
    shutil.copy2(static_summary_path, static_latest_path)

    entry = _summary_entry(
        file_name=static_summary_path.name,
        suite=str(summary_payload["suite"]),
        run_id=str(summary_payload["run_id"]),
        machine=str(summary_payload["machine"]),
        generated_at_utc=generated_at_utc,
    )
    _update_summary_index(static_root / "index.json", entry, generated_at_utc)
    return static_summary_path


def run_smoke_suite(
    *,
    python: Path,
    out_root: Path,
    summary_root: Path,
    machine: str | None = None,
    ci_mode: bool = False,
    enforce_guardrails: bool = False,
    require_cinderx_baseline: bool = False,
    cpython_cinderx: Path | None = None,
    pypy: Path | None = None,
    static_summary_root: Path | None = None,
    sample_count: int | None = None,
    warmup_count: int | None = None,
) -> BenchmarkRunResult:
    suite_key = SMOKE_SUITE

    baseline_python = Path(os.path.abspath(str(python.expanduser())))
    if not baseline_python.exists():
        raise ValueError(f"Python executable does not exist: {baseline_python}")

    now = datetime.now(UTC)
    generated_at_utc = now.isoformat()
    run_id = now.strftime("%Y%m%dT%H%M%SZ")
    date_slug = now.strftime("%Y-%m-%d")
    machine_name = (machine or socket.gethostname()).strip() or "unknown-machine"
    machine_slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in machine_name)

    warmups = warmup_count if warmup_count is not None else (1 if ci_mode else 2)
    samples = sample_count if sample_count is not None else (3 if ci_mode else 7)
    startup_samples = 3 if ci_mode else 5

    guardrails = _guardrail_checks(ci_mode)
    if enforce_guardrails and guardrails["enforceable_failures"]:
        failures = "\n".join(f"- {item}" for item in guardrails["enforceable_failures"])
        raise ValueError(f"Guardrail enforcement failed:\n{failures}")

    targets = _runtime_targets(
        python=baseline_python,
        cpython_cinderx=_normalize_path(cpython_cinderx),
        pypy=_normalize_path(pypy),
    )
    _enforce_cinderx_baseline_policy(
        targets=targets,
        require_cinderx_baseline=require_cinderx_baseline,
    )

    cinderx_pin = upstream.read_pin_record("cinderx")
    repo_sha = _current_repo_sha()

    metadata: dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "suite": suite_key,
        "run_id": run_id,
        "machine": machine_name,
        "host": {
            "os": platform.system(),
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "cpu_model": _cpu_model(),
            "cpu_logical_count": os.cpu_count(),
            "ram_total_bytes": _total_ram_bytes(),
        },
        "run_config": {
            "ci_mode": ci_mode,
            "warmups": warmups,
            "samples": samples,
            "startup_samples": startup_samples,
            "require_cinderx_baseline": require_cinderx_baseline,
        },
        "toolchain": {
            "benchmark_repo_sha": repo_sha,
            "cinderx_upstream": {
                "repo_url": cinderx_pin.repo_url if cinderx_pin else "unknown",
                "commit_sha": cinderx_pin.commit_sha if cinderx_pin else "unknown",
                "clone_timestamp_utc": cinderx_pin.clone_timestamp_utc
                if cinderx_pin
                else "unknown",
            },
        },
        "guardrails": guardrails,
    }

    run_root = out_root.expanduser().resolve() / date_slug / machine_slug
    run_root.mkdir(parents=True, exist_ok=True)

    runtime_reports: list[str] = []
    skipped_runtimes: list[str] = []
    benchmark_rows: list[dict[str, Any]] = []
    runtime_summaries: list[dict[str, Any]] = []
    runtime_case_means: dict[str, dict[str, float]] = {}
    runtime_case_samples: dict[str, dict[str, list[float]]] = {}

    for target in targets:
        runtime_dir = run_root / target.key
        runtime_report_path = runtime_dir / f"{suite_key}-{run_id}.json"
        runtime_dir.mkdir(parents=True, exist_ok=True)

        if not target.available:
            skipped_runtimes.append(f"{target.key}: {target.reason}")
            payload = {
                "suite": suite_key,
                "runtime": target.key,
                "available": False,
                "reason": target.reason,
                "source": target.source,
                "generated_at_utc": generated_at_utc,
            }
            _safe_json(runtime_report_path, payload)
            runtime_reports.append(str(runtime_report_path))
            continue

        assert target.executable is not None
        if target.mode != "python-runtime":
            raise ValueError(f"smoke runtime target '{target.key}' is not a supported interpreter.")
        compile_time_seconds: float | None = None
        compile_command: list[str] | None = None
        startup_values = _measure_startup(target.executable, startup_samples)
        runtime_details = _python_runtime_details(target.executable)
        runtime_version = _version_line(target.executable)

        startup_mean = _mean(startup_values)
        startup_stdev = _stdev(startup_values)
        case_rows: list[dict[str, Any]] = []
        runtime_case_means[target.key] = {}
        runtime_case_samples[target.key] = {}

        for case in SMOKE_CASES:
            loops = case.ci_loops if ci_mode else case.loops
            raw = _run_smoke_case(
                target.executable,
                benchmark=case.benchmark,
                warmups=warmups,
                samples=samples,
                loops=loops,
            )
            mean_seconds = _mean(raw["samples"])
            stdev_seconds = _stdev(raw["samples"])

            case_row = {
                "benchmark": case.benchmark,
                "workload_class": case.workload_class,
                "description": case.description,
                "loops": loops,
                "warmups": raw["warmups"],
                "samples": raw["samples"],
                "mean_seconds": mean_seconds,
                "stdev_seconds": stdev_seconds,
            }
            case_rows.append(case_row)

            runtime_case_means[target.key][case.benchmark] = mean_seconds
            runtime_case_samples[target.key][case.benchmark] = list(raw["samples"])

            benchmark_rows.append(
                {
                    "benchmark": case.benchmark,
                    "workload_class": case.workload_class,
                    "runtime": target.key,
                    "runtime_label": target.label,
                    "mean_seconds": mean_seconds,
                    "stdev_seconds": stdev_seconds,
                    "sample_count": len(raw["samples"]),
                    "warmup_count": len(raw["warmups"]),
                    "speedup_vs_baseline": None,
                    "p_value": None,
                    "memory_rss_bytes": raw.get("rss_max_bytes"),
                    "compile_time_seconds": compile_time_seconds,
                    "startup_mean_seconds": startup_mean,
                    "startup_stdev_seconds": startup_stdev,
                }
            )

        runtime_payload = {
            "suite": suite_key,
            "run_id": run_id,
            "generated_at_utc": generated_at_utc,
            "runtime": target.key,
            "runtime_label": target.label,
            "runtime_source": target.source,
            "runtime_version": runtime_version,
            "runtime_details": runtime_details,
            "startup_samples_seconds": startup_values,
            "startup_mean_seconds": startup_mean,
            "startup_stdev_seconds": startup_stdev,
            "compile_time_seconds": compile_time_seconds,
            "compile_command": compile_command,
            "benchmarks": case_rows,
        }
        _safe_json(runtime_report_path, runtime_payload)
        runtime_reports.append(str(runtime_report_path))

        runtime_summaries.append(
            {
                "runtime": target.key,
                "runtime_label": target.label,
                "runtime_source": target.source,
                "runtime_version": runtime_version,
                "runtime_details": runtime_details,
                "startup_mean_seconds": startup_mean,
                "startup_stdev_seconds": startup_stdev,
                "executed": True,
            }
        )

    baseline_runtime = _select_baseline_runtime(runtime_case_means)
    _apply_baseline_metrics(
        benchmark_rows=benchmark_rows,
        runtime_case_means=runtime_case_means,
        runtime_case_samples=runtime_case_samples,
        baseline_runtime=baseline_runtime,
    )

    limitations = [
        (
            "Smoke suite is for reproducibility/sanity checks and should not be "
            "treated as a full performance claim."
        ),
    ]

    summary_payload: dict[str, Any] = {
        "suite": suite_key,
        "run_id": run_id,
        "generated_at_utc": generated_at_utc,
        "machine": machine_name,
        "baseline_runtime": baseline_runtime,
        "metadata": metadata,
        "workload_taxonomy": list_workload_taxonomy(),
        "runtimes": runtime_summaries,
        "skipped_runtimes": skipped_runtimes,
        "benchmarks": benchmark_rows,
        "limitations": limitations,
    }

    summary_root_path = summary_root.expanduser().resolve()
    summary_root_path.mkdir(parents=True, exist_ok=True)
    summary_path = summary_root_path / f"{suite_key}-{date_slug}-{machine_slug}-{run_id}.json"
    latest_summary_path = summary_root_path / f"latest-{suite_key}.json"

    _safe_json(summary_path, summary_payload)
    shutil.copy2(summary_path, latest_summary_path)
    _update_summary_index(
        summary_root_path / "index.json",
        _summary_entry(
            file_name=summary_path.name,
            suite=suite_key,
            run_id=run_id,
            machine=machine_name,
            generated_at_utc=generated_at_utc,
        ),
        generated_at_utc,
    )

    static_summary_path: Path | None = None
    if static_summary_root is not None:
        static_summary_path = _copy_summary_to_static(
            summary_payload=summary_payload,
            summary_path=summary_path,
            latest_summary_path=latest_summary_path,
            static_root=static_summary_root.expanduser().resolve(),
            generated_at_utc=generated_at_utc,
        )

    notes = [
        "Raw runtime artifacts written per runtime under data/runs/...",
        "Normalized summary JSON written under data/summary/...",
        "Summary includes startup/runtime split and speedup vs selected baseline runtime.",
    ]
    if baseline_runtime != "cpython-cinderx":
        notes.append(
            "CinderX baseline was not available in this run; fallback baseline runtime was used."
        )
    if require_cinderx_baseline:
        notes.append("CinderX baseline policy was enforced for this run.")
    if ci_mode:
        notes.append("CI mode enabled: reduced sample counts for fast sanity checks.")
    if skipped_runtimes:
        notes.append("Some runtimes/tools were skipped; see skipped_runtimes field.")

    return BenchmarkRunResult(
        suite=suite_key,
        run_id=run_id,
        machine=machine_name,
        output_root=str(run_root),
        summary_path=str(summary_path),
        latest_summary_path=str(latest_summary_path),
        static_summary_path=None if static_summary_path is None else str(static_summary_path),
        runtime_reports=runtime_reports,
        skipped_runtimes=skipped_runtimes,
        benchmark_rows=len(benchmark_rows),
        notes=notes,
    )


def _resolve_pyperformance_launcher(python_hint: Path) -> tuple[list[str], str]:
    candidate_commands: list[list[str]] = []

    def add_candidate(command: list[str]) -> None:
        if command and command not in candidate_commands:
            candidate_commands.append(command)

    # Prefer the exact interpreter path passed by the caller (for venv isolation),
    # then fall back to resolved paths and PATH-based discovery.
    add_candidate([str(Path(sys.executable)), "-m", "pyperformance"])
    add_candidate([str(Path(sys.executable).resolve()), "-m", "pyperformance"])
    add_candidate([str(python_hint), "-m", "pyperformance"])
    add_candidate([str(python_hint.resolve()), "-m", "pyperformance"])
    local_pyperformance = python_hint.parent / "pyperformance"
    if local_pyperformance.exists():
        add_candidate([str(local_pyperformance)])
    if discovered := shutil.which("pyperformance"):
        add_candidate([discovered])

    attempted: list[str] = []
    for command in candidate_commands:
        try:
            _run_command([*command, "--help"], timeout_s=30)
        except ValueError:
            attempted.append(" ".join(command))
            continue

        version = "unknown"
        try:
            completed = _run_command([*command, "--version"], timeout_s=20)
            combined = (completed.stdout + "\n" + completed.stderr).strip()
            if combined:
                version = combined.splitlines()[0].strip()
        except ValueError:
            pass
        return command, version

    attempted_text = ", ".join(attempted) if attempted else "no candidates"
    raise ValueError(
        "pyperformance is not available. Install it in your benchmark environment or provide a "
        "`pyperformance` executable on PATH. "
        f"Tried: {attempted_text}"
    )


def _benchmark_name_from_payload(entry: dict[str, Any]) -> str:
    name = entry.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()

    metadata = entry.get("metadata")
    if isinstance(metadata, dict):
        for key in ("name", "benchmark", "id"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return "unknown-benchmark"


def _rss_bytes_from_metric(key: str, value: float) -> int | None:
    if value <= 0:
        return None

    lower = key.lower()
    if "bytes" in lower:
        return int(value)
    if "kb" in lower:
        return int(value * 1024)
    if lower in {"mem_max_rss", "max_rss", "ru_maxrss"}:
        if sys.platform == "darwin":
            return int(value)
        return int(value * 1024)
    return int(value)


def _extract_compile_time_seconds(
    benchmark: dict[str, Any], runs: list[dict[str, Any]]
) -> float | None:
    compile_keys = (
        "compile_time_seconds",
        "compilation_time_seconds",
        "compile_time",
        "compilation_time",
    )

    sources: list[dict[str, Any]] = [benchmark]
    if isinstance(benchmark.get("metadata"), dict):
        sources.append(benchmark["metadata"])
    for run in runs:
        sources.append(run)
        if isinstance(run.get("metadata"), dict):
            sources.append(run["metadata"])

    for source in sources:
        for key in compile_keys:
            value = _coerce_float(source.get(key))
            if value is not None and value >= 0:
                return value
    return None


def _extract_rss_bytes(benchmark: dict[str, Any], runs: list[dict[str, Any]]) -> int | None:
    rss_keys = (
        "memory_rss_bytes",
        "max_rss_bytes",
        "rss_bytes",
        "mem_max_rss_bytes",
        "mem_max_rss",
        "max_rss",
        "ru_maxrss",
        "rss_kb",
        "max_rss_kb",
    )

    values: list[int] = []
    sources: list[dict[str, Any]] = [benchmark]
    if isinstance(benchmark.get("metadata"), dict):
        sources.append(benchmark["metadata"])
    for run in runs:
        sources.append(run)
        if isinstance(run.get("metadata"), dict):
            sources.append(run["metadata"])

    for source in sources:
        for key in rss_keys:
            value = _coerce_float(source.get(key))
            if value is None:
                continue
            normalized = _rss_bytes_from_metric(key, value)
            if normalized is not None:
                values.append(normalized)

    return max(values) if values else None


def _normalize_pyperformance_rows(raw_payload: dict[str, Any]) -> list[dict[str, Any]]:
    benchmark_entries = raw_payload.get("benchmarks", [])
    if not isinstance(benchmark_entries, list):
        return []
    root_metadata = raw_payload.get("metadata", {})
    root_metadata_map = root_metadata if isinstance(root_metadata, dict) else {}
    fallback_name_raw = root_metadata_map.get("name")
    fallback_name = fallback_name_raw.strip() if isinstance(fallback_name_raw, str) else ""
    fallback_description_raw = root_metadata_map.get("description")
    fallback_description = (
        fallback_description_raw.strip() if isinstance(fallback_description_raw, str) else ""
    )

    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(benchmark_entries):
        if not isinstance(entry, dict):
            continue

        runs_raw = entry.get("runs", [])
        runs = (
            [run for run in runs_raw if isinstance(run, dict)] if isinstance(runs_raw, list) else []
        )

        sample_values: list[float] = []
        warmup_values: list[float] = []
        for run in runs:
            values = run.get("values", [])
            if isinstance(values, list):
                for value in values:
                    parsed = _coerce_float(value)
                    if parsed is not None:
                        sample_values.append(parsed)
            warmup_values.extend(_warmup_values(run.get("warmups")))

        stats = entry.get("stats", {})
        stats_map = stats if isinstance(stats, dict) else {}
        mean_seconds = (
            _mean(sample_values) if sample_values else (_coerce_float(stats_map.get("mean")) or 0.0)
        )
        stdev_seconds = (
            _stdev(sample_values)
            if len(sample_values) > 1
            else (_coerce_float(stats_map.get("stdev")) or 0.0)
        )
        benchmark_name = _benchmark_name_from_payload(entry)
        if benchmark_name == "unknown-benchmark" and fallback_name:
            benchmark_name = fallback_name if index == 0 else f"{fallback_name}#{index + 1}"
        description = f"pyperformance benchmark: {benchmark_name}"
        if fallback_description:
            description = f"{description} ({fallback_description})"
        normalized.append(
            {
                "benchmark": benchmark_name,
                "workload_class": _classify_benchmark_name(benchmark_name),
                "description": description,
                "warmups": warmup_values,
                "samples": sample_values,
                "mean_seconds": mean_seconds,
                "stdev_seconds": stdev_seconds,
                "memory_rss_bytes": _extract_rss_bytes(entry, runs),
                "compile_time_seconds": _extract_compile_time_seconds(entry, runs),
            }
        )

    return normalized


def run_pyperformance_suite(
    *,
    python: Path,
    out_root: Path,
    summary_root: Path,
    machine: str | None = None,
    ci_mode: bool = False,
    enforce_guardrails: bool = False,
    require_cinderx_baseline: bool = False,
    cpython_cinderx: Path | None = None,
    pypy: Path | None = None,
    static_summary_root: Path | None = None,
    pyperformance_bootstrap_inline: str | None = None,
    pyperformance_bootstrap_profile: str | None = None,
    pyperformance_bootstrap_jit_compile_after_n_calls: int | None = None,
) -> BenchmarkRunResult:
    python_hint = Path(os.path.abspath(str(python.expanduser())))
    baseline_python = Path(os.path.abspath(str(python_hint)))
    if not baseline_python.exists():
        raise ValueError(f"Python executable does not exist: {baseline_python}")

    now = datetime.now(UTC)
    generated_at_utc = now.isoformat()
    run_id = now.strftime("%Y%m%dT%H%M%SZ")
    date_slug = now.strftime("%Y-%m-%d")
    machine_name = (machine or socket.gethostname()).strip() or "unknown-machine"
    machine_slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in machine_name)
    startup_samples = 3 if ci_mode else 5
    pyperformance_benchmarks = ["nbody"] if ci_mode else None

    guardrails = _guardrail_checks(ci_mode)
    if enforce_guardrails and guardrails["enforceable_failures"]:
        failures = "\n".join(f"- {item}" for item in guardrails["enforceable_failures"])
        raise ValueError(f"Guardrail enforcement failed:\n{failures}")

    targets = _runtime_targets(
        python=baseline_python,
        cpython_cinderx=_normalize_path(cpython_cinderx),
        pypy=_normalize_path(pypy),
    )
    _enforce_cinderx_baseline_policy(
        targets=targets,
        require_cinderx_baseline=require_cinderx_baseline,
    )
    resolved_bootstrap = _resolve_pyperformance_bootstrap_for_targets(
        targets=targets,
        pyperformance_bootstrap_inline=pyperformance_bootstrap_inline,
        pyperformance_bootstrap_profile=pyperformance_bootstrap_profile,
        pyperformance_bootstrap_jit_compile_after_n_calls=(
            pyperformance_bootstrap_jit_compile_after_n_calls
        ),
    )
    resolved_bootstrap_profile = resolved_bootstrap.profile
    resolved_bootstrap_jit_compile_after_n_calls = resolved_bootstrap.jit_compile_after_n_calls
    resolved_bootstrap_profile_source = resolved_bootstrap.profile_source
    bootstrap_target_runtime_key = resolved_bootstrap.target_runtime_key
    pyperformance_bootstrap_env = resolved_bootstrap.env
    pyperformance_bootstrap_tempdir = resolved_bootstrap.tempdir
    pyperformance_bootstrap_sha256 = resolved_bootstrap.sha256
    pyperformance_bootstrap_mode = resolved_bootstrap.mode
    cinderx_feature_flags = _describe_cinderx_pyperformance_features(
        resolved_bootstrap_profile=resolved_bootstrap_profile,
        bootstrap_inline_sha256=pyperformance_bootstrap_sha256,
        resolved_bootstrap_jit_compile_after_n_calls=resolved_bootstrap_jit_compile_after_n_calls,
    )
    pyperformance_command, pyperformance_version = _resolve_pyperformance_launcher(python_hint)

    cinderx_pin = upstream.read_pin_record("cinderx")
    repo_sha = _current_repo_sha()
    metadata: dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "suite": PYPERFORMANCE_SUITE,
        "run_id": run_id,
        "machine": machine_name,
        "host": {
            "os": platform.system(),
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "cpu_model": _cpu_model(),
            "cpu_logical_count": os.cpu_count(),
            "ram_total_bytes": _total_ram_bytes(),
        },
        "run_config": {
            "ci_mode": ci_mode,
            "startup_samples": startup_samples,
            "pyperformance_mode": "fast" if ci_mode else "default",
            "pyperformance_benchmarks": pyperformance_benchmarks,
            "require_cinderx_baseline": require_cinderx_baseline,
            "pyperformance_bootstrap_inline_enabled": bool(pyperformance_bootstrap_sha256),
            "pyperformance_bootstrap_inline_sha256": pyperformance_bootstrap_sha256,
            "pyperformance_bootstrap_profile": resolved_bootstrap_profile,
            "pyperformance_bootstrap_profile_source": resolved_bootstrap_profile_source,
            "pyperformance_bootstrap_jit_compile_after_n_calls": (
                resolved_bootstrap_jit_compile_after_n_calls
            ),
            "pyperformance_bootstrap_target_runtime_key": bootstrap_target_runtime_key,
            "pyperformance_cinderx_feature_profile": cinderx_feature_flags["profile"],
            "pyperformance_cinderx_feature_summary": cinderx_feature_flags["summary"],
            "pyperformance_cinderx_jit_mode": cinderx_feature_flags["jit_mode"],
            "pyperformance_cinderx_jit_compile_after_n_calls": cinderx_feature_flags[
                "jit_compile_after_n_calls"
            ],
            "pyperformance_cinderx_static_loader_enabled": cinderx_feature_flags[
                "static_loader_enabled"
            ],
            "pyperformance_cinderx_static_loader_enable_patching": cinderx_feature_flags[
                "static_loader_enable_patching"
            ],
        },
        "toolchain": {
            "benchmark_repo_sha": repo_sha,
            "pyperformance_command": pyperformance_command,
            "pyperformance_version": pyperformance_version,
            "pyperformance_bootstrap_mode": pyperformance_bootstrap_mode,
            "cinderx_upstream": {
                "repo_url": cinderx_pin.repo_url if cinderx_pin else "unknown",
                "commit_sha": cinderx_pin.commit_sha if cinderx_pin else "unknown",
                "clone_timestamp_utc": cinderx_pin.clone_timestamp_utc
                if cinderx_pin
                else "unknown",
            },
        },
        "guardrails": guardrails,
    }

    run_root = out_root.expanduser().resolve() / date_slug / machine_slug
    run_root.mkdir(parents=True, exist_ok=True)

    runtime_reports: list[str] = []
    skipped_runtimes: list[str] = []
    benchmark_rows: list[dict[str, Any]] = []
    runtime_summaries: list[dict[str, Any]] = []
    runtime_case_means: dict[str, dict[str, float]] = {}
    runtime_case_samples: dict[str, dict[str, list[float]]] = {}

    for target in targets:
        runtime_dir = run_root / target.key
        runtime_report_path = runtime_dir / f"{PYPERFORMANCE_SUITE}-{run_id}.json"
        runtime_dir.mkdir(parents=True, exist_ok=True)

        if not target.available:
            skipped_runtimes.append(f"{target.key}: {target.reason}")
            payload = {
                "suite": PYPERFORMANCE_SUITE,
                "runtime": target.key,
                "available": False,
                "reason": target.reason,
                "source": target.source,
                "generated_at_utc": generated_at_utc,
            }
            _safe_json(runtime_report_path, payload)
            runtime_reports.append(str(runtime_report_path))
            continue

        if target.mode != "python-runtime" or target.executable is None:
            raise ValueError(
                f"pyperformance runtime target '{target.key}' is not a supported interpreter."
            )

        startup_values = _measure_startup(target.executable, startup_samples)
        startup_mean = _mean(startup_values)
        startup_stdev = _stdev(startup_values)
        runtime_details = _python_runtime_details(target.executable)
        runtime_version = _version_line(target.executable)
        runtime_case_means[target.key] = {}
        runtime_case_samples[target.key] = {}

        raw_report_path = runtime_dir / f"{PYPERFORMANCE_SUITE}-raw-{run_id}.json"
        command = [
            *pyperformance_command,
            "run",
            "--python",
            str(target.executable),
            "--output",
            str(raw_report_path),
        ]
        if ci_mode:
            command.extend(["--fast", "--benchmarks", ",".join(pyperformance_benchmarks or [])])

        try:
            if pyperformance_bootstrap_env:
                runtime_bootstrap_env = dict(pyperformance_bootstrap_env)
                runtime_bootstrap_env["CXC_PYPERF_RUNTIME_KEY"] = target.key
                _run_command(
                    command,
                    timeout_s=1200 if ci_mode else 7200,
                    env=runtime_bootstrap_env,
                )
            else:
                _run_command(command, timeout_s=1200 if ci_mode else 7200)
            raw_payload = json.loads(raw_report_path.read_text(encoding="utf-8"))
            normalized_rows = _normalize_pyperformance_rows(raw_payload)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            message = f"pyperformance execution failed ({exc})"
            if target.key == "cpython":
                if pyperformance_bootstrap_tempdir is not None:
                    pyperformance_bootstrap_tempdir.cleanup()
                raise ValueError(
                    f"Failed to execute pyperformance baseline runtime: {exc}"
                ) from exc
            skipped_runtimes.append(f"{target.key}: {message}")
            payload = {
                "suite": PYPERFORMANCE_SUITE,
                "runtime": target.key,
                "available": True,
                "executed": False,
                "reason": message,
                "source": target.source,
                "generated_at_utc": generated_at_utc,
            }
            _safe_json(runtime_report_path, payload)
            runtime_reports.append(str(runtime_report_path))
            runtime_case_means.pop(target.key, None)
            runtime_case_samples.pop(target.key, None)
            continue

        if not normalized_rows:
            message = "pyperformance run completed but no benchmark rows were parsed"
            if target.key == "cpython":
                if pyperformance_bootstrap_tempdir is not None:
                    pyperformance_bootstrap_tempdir.cleanup()
                raise ValueError(message)
            skipped_runtimes.append(f"{target.key}: {message}")
            payload = {
                "suite": PYPERFORMANCE_SUITE,
                "runtime": target.key,
                "available": True,
                "executed": False,
                "reason": message,
                "source": target.source,
                "generated_at_utc": generated_at_utc,
            }
            _safe_json(runtime_report_path, payload)
            runtime_reports.append(str(runtime_report_path))
            runtime_case_means.pop(target.key, None)
            runtime_case_samples.pop(target.key, None)
            continue

        case_rows: list[dict[str, Any]] = []
        for row in normalized_rows:
            benchmark = str(row["benchmark"])
            samples = list(row["samples"])
            mean_seconds = float(row["mean_seconds"])
            stdev_seconds = float(row["stdev_seconds"])

            case_row = {
                "benchmark": benchmark,
                "workload_class": row["workload_class"],
                "description": row["description"],
                "warmups": row["warmups"],
                "samples": samples,
                "mean_seconds": mean_seconds,
                "stdev_seconds": stdev_seconds,
                "memory_rss_bytes": row["memory_rss_bytes"],
                "compile_time_seconds": row["compile_time_seconds"],
            }
            case_rows.append(case_row)

            runtime_case_means[target.key][benchmark] = mean_seconds
            runtime_case_samples[target.key][benchmark] = samples

            benchmark_rows.append(
                {
                    "benchmark": benchmark,
                    "workload_class": row["workload_class"],
                    "runtime": target.key,
                    "runtime_label": target.label,
                    "mean_seconds": mean_seconds,
                    "stdev_seconds": stdev_seconds,
                    "sample_count": len(samples),
                    "warmup_count": len(row["warmups"]),
                    "speedup_vs_baseline": None,
                    "p_value": None,
                    "memory_rss_bytes": row["memory_rss_bytes"],
                    "compile_time_seconds": row["compile_time_seconds"],
                    "startup_mean_seconds": startup_mean,
                    "startup_stdev_seconds": startup_stdev,
                }
            )

        runtime_payload = {
            "suite": PYPERFORMANCE_SUITE,
            "run_id": run_id,
            "generated_at_utc": generated_at_utc,
            "runtime": target.key,
            "runtime_label": target.label,
            "runtime_source": target.source,
            "runtime_version": runtime_version,
            "runtime_details": runtime_details,
            "pyperformance_command": command,
            "pyperformance_raw_output": str(raw_report_path),
            "startup_samples_seconds": startup_values,
            "startup_mean_seconds": startup_mean,
            "startup_stdev_seconds": startup_stdev,
            "benchmarks": case_rows,
        }
        _safe_json(runtime_report_path, runtime_payload)
        runtime_reports.append(str(runtime_report_path))

        runtime_summaries.append(
            {
                "runtime": target.key,
                "runtime_label": target.label,
                "runtime_source": target.source,
                "runtime_version": runtime_version,
                "runtime_details": runtime_details,
                "startup_mean_seconds": startup_mean,
                "startup_stdev_seconds": startup_stdev,
                "executed": True,
            }
        )

    if pyperformance_bootstrap_tempdir is not None:
        pyperformance_bootstrap_tempdir.cleanup()

    if not runtime_case_means:
        raise ValueError("No pyperformance runtime completed successfully.")

    baseline_runtime = _select_baseline_runtime(runtime_case_means)
    _apply_baseline_metrics(
        benchmark_rows=benchmark_rows,
        runtime_case_means=runtime_case_means,
        runtime_case_samples=runtime_case_samples,
        baseline_runtime=baseline_runtime,
    )

    limitations = [
        (
            "pyperformance coverage can vary by runtime environment and dependency availability; "
            "skipped runtimes are recorded explicitly."
        ),
        (
            "RSS and compile-time fields are optional and only populated when the underlying "
            "toolchain reports those metrics."
        ),
    ]

    summary_payload: dict[str, Any] = {
        "suite": PYPERFORMANCE_SUITE,
        "run_id": run_id,
        "generated_at_utc": generated_at_utc,
        "machine": machine_name,
        "baseline_runtime": baseline_runtime,
        "metadata": metadata,
        "workload_taxonomy": list_workload_taxonomy(),
        "runtimes": runtime_summaries,
        "skipped_runtimes": skipped_runtimes,
        "benchmarks": benchmark_rows,
        "limitations": limitations,
    }

    summary_root_path = summary_root.expanduser().resolve()
    summary_root_path.mkdir(parents=True, exist_ok=True)
    summary_path = (
        summary_root_path / f"{PYPERFORMANCE_SUITE}-{date_slug}-{machine_slug}-{run_id}.json"
    )
    latest_summary_path = summary_root_path / f"latest-{PYPERFORMANCE_SUITE}.json"

    _safe_json(summary_path, summary_payload)
    shutil.copy2(summary_path, latest_summary_path)
    _update_summary_index(
        summary_root_path / "index.json",
        _summary_entry(
            file_name=summary_path.name,
            suite=PYPERFORMANCE_SUITE,
            run_id=run_id,
            machine=machine_name,
            generated_at_utc=generated_at_utc,
        ),
        generated_at_utc,
    )

    static_summary_path: Path | None = None
    if static_summary_root is not None:
        static_summary_path = _copy_summary_to_static(
            summary_payload=summary_payload,
            summary_path=summary_path,
            latest_summary_path=latest_summary_path,
            static_root=static_summary_root.expanduser().resolve(),
            generated_at_utc=generated_at_utc,
        )

    notes = [
        "Raw pyperformance artifacts written per runtime under data/runs/...",
        "Normalized summary JSON written under data/summary/...",
        "Summary includes startup/runtime split, speedup vs baseline, and p-value estimates.",
    ]
    if baseline_runtime != "cpython-cinderx":
        notes.append(
            "CinderX baseline was not available in this run; fallback baseline runtime was used."
        )
    if require_cinderx_baseline:
        notes.append("CinderX baseline policy was enforced for this run.")
    if ci_mode:
        notes.append("CI mode enabled: pyperformance --fast mode ran the nbody subset.")
    if resolved_bootstrap_profile:
        if resolved_bootstrap_profile_source == "auto-default":
            notes.append(
                "Pyperformance auto-applied bootstrap profile for cpython-cinderx lane: "
                f"{resolved_bootstrap_profile}."
            )
        else:
            notes.append(
                "Pyperformance bootstrap profile applied: "
                f"{resolved_bootstrap_profile} (target runtime: "
                f"{bootstrap_target_runtime_key or 'none'})."
            )
        notes.append("Plain cpython lane remains unmodified for control comparisons.")
    elif pyperformance_bootstrap_sha256:
        notes.append(
            "Custom inline pyperformance bootstrap was applied via sitecustomize shim "
            f"(target runtime: {bootstrap_target_runtime_key or 'all'})."
        )
    if skipped_runtimes:
        notes.append("Some runtimes/tools were skipped; see skipped_runtimes field.")

    return BenchmarkRunResult(
        suite=PYPERFORMANCE_SUITE,
        run_id=run_id,
        machine=machine_name,
        output_root=str(run_root),
        summary_path=str(summary_path),
        latest_summary_path=str(latest_summary_path),
        static_summary_path=None if static_summary_path is None else str(static_summary_path),
        runtime_reports=runtime_reports,
        skipped_runtimes=skipped_runtimes,
        benchmark_rows=len(benchmark_rows),
        notes=notes,
    )


def preflight_pyperformance_suite(
    *,
    python: Path,
    cpython_cinderx: Path | None = None,
    require_cinderx_baseline: bool = False,
    pyperformance_bootstrap_inline: str | None = None,
    pyperformance_bootstrap_profile: str | None = None,
    pyperformance_bootstrap_jit_compile_after_n_calls: int | None = None,
    timeout_seconds: int = 45,
) -> PyperformancePreflightResult:
    python_hint = Path(os.path.abspath(str(python.expanduser())))
    baseline_python = Path(os.path.abspath(str(python_hint)))
    if not baseline_python.exists():
        raise ValueError(f"Python executable does not exist: {baseline_python}")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")

    targets = _runtime_targets(
        python=baseline_python,
        cpython_cinderx=_normalize_path(cpython_cinderx),
        pypy=None,
        include_pypy=False,
    )
    _enforce_cinderx_baseline_policy(
        targets=targets,
        require_cinderx_baseline=require_cinderx_baseline,
    )
    resolved_bootstrap = _resolve_pyperformance_bootstrap_for_targets(
        targets=targets,
        pyperformance_bootstrap_inline=pyperformance_bootstrap_inline,
        pyperformance_bootstrap_profile=pyperformance_bootstrap_profile,
        pyperformance_bootstrap_jit_compile_after_n_calls=(
            pyperformance_bootstrap_jit_compile_after_n_calls
        ),
    )

    target = next((item for item in targets if item.key == "cpython-cinderx"), None)
    if target is None or not target.available or target.executable is None:
        target = next(
            (
                item
                for item in targets
                if item.key == "cpython" and item.available and item.executable
            ),
            None,
        )
    if target is None or target.executable is None:
        raise ValueError("No usable Python runtime found for pyperformance preflight.")

    commands = [
        [str(target.executable), "-m", "pyperformance", "--help"],
        [str(target.executable), "-m", "pyperformance", "run", "--help"],
    ]
    command_text = [" ".join(command) for command in commands]

    try:
        for command in commands:
            preflight_env: dict[str, str] | None = None
            if resolved_bootstrap.env:
                preflight_env = dict(resolved_bootstrap.env)
                preflight_env["CXC_PYPERF_RUNTIME_KEY"] = target.key
            _run_command(command, timeout_s=timeout_seconds, env=preflight_env)
    except ValueError as exc:
        raise ValueError(
            f"Preflight failed for pyperformance bootstrap on runtime {target.key!r}: {exc}"
        ) from exc
    finally:
        if resolved_bootstrap.tempdir is not None:
            resolved_bootstrap.tempdir.cleanup()

    notes = [
        "Pyperformance preflight validated module launch under resolved bootstrap settings.",
        (
            "Run this preflight in CI before full pyperformance to fail fast "
            "on bootstrap/runtime issues."
        ),
    ]
    if resolved_bootstrap.profile:
        notes.append(f"Resolved bootstrap profile: {resolved_bootstrap.profile}.")
    elif resolved_bootstrap.sha256:
        notes.append("Resolved bootstrap mode: custom inline.")
    else:
        notes.append("Resolved bootstrap mode: disabled.")

    return PyperformancePreflightResult(
        suite="pyperformance-preflight",
        runtime=target.key,
        runtime_executable=str(target.executable),
        commands=command_text,
        bootstrap_profile=resolved_bootstrap.profile,
        bootstrap_profile_source=resolved_bootstrap.profile_source,
        bootstrap_mode=resolved_bootstrap.mode,
        bootstrap_target_runtime_key=resolved_bootstrap.target_runtime_key,
        bootstrap_inline_sha256=resolved_bootstrap.sha256,
        notes=notes,
    )


def verify_publishable_summaries(
    *,
    summary_root: Path,
    static_summary_root: Path | None = None,
    suites: list[str] | None = None,
) -> PublishVerificationResult:
    summary_root_path = summary_root.expanduser().resolve()
    selected_suites = list(suites) if suites is not None else list(PUBLISHABLE_SUITES)
    invalid_suites = [suite for suite in selected_suites if suite not in PUBLISHABLE_SUITES]
    if invalid_suites:
        raise ValueError(
            "verify-publish only supports runnable suites: "
            f"{', '.join(PUBLISHABLE_SUITES)}. "
            f"Unsupported values: {', '.join(invalid_suites)}"
        )

    if not selected_suites:
        raise ValueError("No suites were selected for publish verification.")

    failures: list[str] = []
    checked_files: list[str] = []
    summary_payload_by_suite: dict[str, dict[str, Any]] = {}
    static_payload_by_suite: dict[str, dict[str, Any]] = {}

    summary_index_path = summary_root_path / "index.json"
    if not summary_index_path.exists():
        failures.append(f"Missing summary index: {summary_index_path}")
    else:
        summary_index = _read_json_dict(summary_index_path)
        failures.extend(
            _validate_summary_index_for_suites(
                index_payload=summary_index,
                suites=selected_suites,
                source=str(summary_index_path),
            )
        )
        checked_files.append(str(summary_index_path))

    static_root_path: Path | None = None
    if static_summary_root is not None:
        static_root_path = static_summary_root.expanduser().resolve()
        static_index_path = static_root_path / "index.json"
        if not static_index_path.exists():
            failures.append(f"Missing static summary index: {static_index_path}")
        else:
            static_index = _read_json_dict(static_index_path)
            failures.extend(
                _validate_summary_index_for_suites(
                    index_payload=static_index,
                    suites=selected_suites,
                    source=str(static_index_path),
                )
            )
            checked_files.append(str(static_index_path))

    for suite in selected_suites:
        latest_name = f"latest-{suite}.json"
        summary_latest_path = summary_root_path / latest_name
        if not summary_latest_path.exists():
            failures.append(f"Missing required summary file: {summary_latest_path}")
            continue

        summary_payload = _read_json_dict(summary_latest_path)
        failures.extend(
            _validate_publishable_summary_payload(
                payload=summary_payload,
                expected_suite=suite,
                source=str(summary_latest_path),
            )
        )
        summary_payload_by_suite[suite] = summary_payload
        checked_files.append(str(summary_latest_path))

        if static_root_path is None:
            continue

        static_latest_path = static_root_path / latest_name
        if not static_latest_path.exists():
            failures.append(f"Missing required static summary file: {static_latest_path}")
            continue

        static_payload = _read_json_dict(static_latest_path)
        failures.extend(
            _validate_publishable_summary_payload(
                payload=static_payload,
                expected_suite=suite,
                source=str(static_latest_path),
            )
        )
        static_payload_by_suite[suite] = static_payload
        if static_payload != summary_payload:
            failures.append(
                f"Summary/static mismatch for suite '{suite}' between "
                f"{summary_latest_path} and {static_latest_path}."
            )
        checked_files.append(str(static_latest_path))

    failures.extend(
        _validate_publish_suite_coherence(
            payload_by_suite=summary_payload_by_suite,
            source=f"{summary_root_path}/latest-*.json",
        )
    )
    if static_root_path is not None:
        failures.extend(
            _validate_publish_suite_coherence(
                payload_by_suite=static_payload_by_suite,
                source=f"{static_root_path}/latest-*.json",
            )
        )

    if failures:
        detail = "\n".join(f"- {item}" for item in failures)
        raise ValueError(f"Publish verification failed:\n{detail}")

    notes = [
        "All required latest summary files are CinderX-baselined and policy-enforced.",
        "Required host/toolchain/guardrail metadata is present for each verified suite.",
        "Summary and static summary payloads match for each verified suite.",
        "Verified suites are coherent (machine/repo SHA alignment and bounded timestamp skew).",
    ]
    return PublishVerificationResult(
        summary_root=str(summary_root_path),
        static_summary_root=None if static_root_path is None else str(static_root_path),
        suites_checked=selected_suites,
        checked_files=checked_files,
        notes=notes,
    )


def export_metadata_dossiers(
    *,
    summary_root: Path,
    suites: list[str] | None = None,
    output_root: Path | None = None,
) -> MetadataDossierResult:
    summary_root_path = summary_root.expanduser().resolve()
    selected_suites = list(suites) if suites is not None else list(PUBLISHABLE_SUITES)
    invalid_suites = [suite for suite in selected_suites if suite not in PUBLISHABLE_SUITES]
    if invalid_suites:
        raise ValueError(
            "export-dossier only supports runnable suites: "
            f"{', '.join(PUBLISHABLE_SUITES)}. "
            f"Unsupported values: {', '.join(invalid_suites)}"
        )
    if not selected_suites:
        raise ValueError("No suites were selected for metadata dossier export.")

    if output_root is None:
        output_root_path = (summary_root_path / "reports").resolve()
    else:
        output_root_path = output_root.expanduser().resolve()
    output_root_path.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    output_files: list[str] = []
    suites_exported: list[str] = []

    for suite in selected_suites:
        latest_path = summary_root_path / f"latest-{suite}.json"
        if not latest_path.exists():
            failures.append(f"Missing required summary file: {latest_path}")
            continue

        payload = _read_json_dict(latest_path)
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            failures.append(f"{latest_path}: metadata object is missing.")
            continue

        dossier = {
            "suite": payload.get("suite"),
            "run_id": payload.get("run_id"),
            "generated_at_utc": payload.get("generated_at_utc"),
            "machine": payload.get("machine"),
            "baseline_runtime": payload.get("baseline_runtime"),
            "metadata": metadata,
        }
        dossier_path = output_root_path / f"{suite}-metadata-dossier.json"
        _safe_json(dossier_path, dossier)
        output_files.append(str(dossier_path))
        suites_exported.append(suite)

    if failures:
        detail = "\n".join(f"- {item}" for item in failures)
        raise ValueError(f"Metadata dossier export failed:\n{detail}")

    notes = [
        "Metadata dossier JSON files were exported from latest suite summaries.",
        "Use these artifacts for local/public report configuration transparency.",
    ]
    return MetadataDossierResult(
        summary_root=str(summary_root_path),
        output_root=str(output_root_path),
        suites_exported=suites_exported,
        output_files=output_files,
        notes=notes,
    )


def to_json(
    payload: (
        BenchmarkPlan
        | BenchmarkRunResult
        | PublishVerificationResult
        | MetadataDossierResult
        | PyperformancePreflightResult
    ),
) -> str:
    return json.dumps(asdict(payload), indent=2, sort_keys=True)
