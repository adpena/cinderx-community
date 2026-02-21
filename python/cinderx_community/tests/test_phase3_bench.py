from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from cinderx_community import upstream
from cinderx_community.bench import runner
from cinderx_community.bench.runner import (
    PYPERFORMANCE_SUITE,
    SMOKE_SUITE,
    build_plan,
    list_suites,
)


def _publishable_summary_payload(*, suite: str) -> dict[str, object]:
    return {
        "suite": suite,
        "run_id": "20260219T000000Z",
        "generated_at_utc": "2026-02-19T00:00:00+00:00",
        "machine": "publish-check-host",
        "baseline_runtime": "cpython-cinderx",
        "metadata": {
            "host": {
                "os": "Darwin",
                "kernel": "24.3.0",
                "architecture": "arm64",
                "cpu_model": "Apple M-series",
                "cpu_logical_count": 8,
                "ram_total_bytes": 17179869184,
            },
            "run_config": {
                "ci_mode": False,
                "require_cinderx_baseline": True,
                "pyperformance_cinderx_jit_audit_required": True,
                "pyperformance_cinderx_static_loader_required": False,
            },
            "toolchain": {
                "benchmark_repo_sha": "deadbeef",
                "cinderx_upstream": {
                    "repo_url": "https://github.com/facebookincubator/cinderx",
                    "commit_sha": "cafebabe",
                    "clone_timestamp_utc": "2026-02-19T00:00:00+00:00",
                },
            },
            "guardrails": {
                "checks": [{"name": "cpu_affinity", "status": "ok"}],
                "enforceable_failures": [],
            },
        },
        "runtimes": [
            {
                "runtime": "cpython-cinderx",
                "runtime_label": "CPython + CinderX",
                "runtime_version": "Python 3.14.3",
                "runtime_details": {"implementation": "CPython"},
                "jit_audit": {
                    "record_count": 3,
                    "jit_module_available_any": True,
                    "jit_enabled_any": True,
                    "compiled_during_run": True,
                    "static_loader_statuses": ["not-requested"],
                },
                "executed": True,
            }
        ],
        "benchmarks": [
            {
                "benchmark": "dynamic_dispatch",
                "runtime": "cpython-cinderx",
                "speedup_vs_baseline": 1.0,
            }
        ],
    }


def _write_index(path: Path, *, suites: list[str], latest_file_by_suite: dict[str, str]) -> None:
    entries = [
        {
            "file": latest_file_by_suite[suite],
            "suite": suite,
            "run_id": "20260219T000000Z",
            "machine": "publish-check-host",
            "generated_at_utc": "2026-02-19T00:00:00+00:00",
        }
        for suite in suites
    ]
    payload = {"updated_at_utc": "2026-02-19T00:00:00+00:00", "entries": entries}
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_suite_list_includes_smoke() -> None:
    suites = list_suites()
    assert SMOKE_SUITE in suites
    assert PYPERFORMANCE_SUITE in suites


def test_build_plan_for_pyperformance_is_runnable() -> None:
    plan = build_plan(suite=PYPERFORMANCE_SUITE, python_executable=Path(sys.executable))
    assert plan.suite == PYPERFORMANCE_SUITE
    assert "Executable pyperformance suite" in plan.notes


def test_build_plan_for_planned_suite_uses_planning_mode() -> None:
    plan = build_plan(suite="numba-asv", python_executable=Path(sys.executable))
    assert plan.suite == "numba-asv"
    assert "Planning mode" in plan.notes


def test_run_smoke_suite_writes_summary_and_indexes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")

    result = runner.run_smoke_suite(
        python=Path(sys.executable),
        out_root=tmp_path / "runs",
        summary_root=tmp_path / "summary",
        static_summary_root=tmp_path / "static-summary",
        machine="ci-test-machine",
        ci_mode=True,
        sample_count=2,
        warmup_count=1,
    )

    summary_path = Path(result.summary_path)
    latest_summary_path = Path(result.latest_summary_path)
    assert summary_path.exists()
    assert latest_summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["suite"] == "smoke"
    assert summary["baseline_runtime"] == "cpython"
    assert summary["machine"] == "ci-test-machine"
    assert summary["benchmarks"]

    baseline_rows = [row for row in summary["benchmarks"] if row["runtime"] == "cpython"]
    assert baseline_rows
    assert all(row["speedup_vs_baseline"] == 1.0 for row in baseline_rows)

    summary_index = json.loads((tmp_path / "summary" / "index.json").read_text(encoding="utf-8"))
    assert summary_index["entries"]
    assert summary_index["entries"][0]["file"] == summary_path.name

    static_summary_path = Path(result.static_summary_path or "")
    assert static_summary_path.exists()
    static_index = json.loads(
        (tmp_path / "static-summary" / "index.json").read_text(encoding="utf-8")
    )
    assert static_index["entries"]


def test_run_smoke_suite_executes_pypy_adapter_when_provided(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")

    result = runner.run_smoke_suite(
        python=Path(sys.executable),
        pypy=Path(sys.executable),
        out_root=tmp_path / "runs",
        summary_root=tmp_path / "summary",
        machine="pypy-adapter-test",
        ci_mode=True,
        sample_count=2,
        warmup_count=0,
    )

    summary = json.loads(Path(result.summary_path).read_text(encoding="utf-8"))
    pypy_rows = [row for row in summary["benchmarks"] if row["runtime"] == "pypy"]

    assert pypy_rows
    assert all(row["speedup_vs_baseline"] is not None for row in pypy_rows)
    assert all(row["p_value"] is not None for row in pypy_rows)


def test_require_cinderx_baseline_rejects_comparison_without_cinderx(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")

    try:
        runner.run_smoke_suite(
            python=Path(sys.executable),
            pypy=Path(sys.executable),
            out_root=tmp_path / "runs",
            summary_root=tmp_path / "summary",
            machine="require-cinderx-baseline",
            ci_mode=True,
            sample_count=1,
            warmup_count=0,
            require_cinderx_baseline=True,
        )
    except ValueError as exc:
        assert "CinderX baseline is required for comparison runs" in str(exc)
    else:
        raise AssertionError("Expected CinderX baseline policy error")


def test_require_cinderx_baseline_rejects_non_cinderx_runtime_path(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")
    monkeypatch.setattr(runner, "_runtime_has_cinderx_support", lambda _executable: False)

    try:
        runner.run_smoke_suite(
            python=Path(sys.executable),
            cpython_cinderx=Path(sys.executable),
            pypy=Path(sys.executable),
            out_root=tmp_path / "runs",
            summary_root=tmp_path / "summary",
            machine="require-real-cinderx-baseline",
            ci_mode=True,
            sample_count=1,
            warmup_count=0,
            require_cinderx_baseline=True,
        )
    except ValueError as exc:
        assert "--cpython-cinderx" in str(exc)
        assert "import cinderx" in str(exc)
    else:
        raise AssertionError("Expected strict CinderX runtime validation error")


def test_rejects_non_cinderx_runtime_path_even_without_require_flag(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")
    monkeypatch.setattr(runner, "_runtime_has_cinderx_support", lambda _executable: False)

    try:
        runner.run_smoke_suite(
            python=Path(sys.executable),
            cpython_cinderx=Path(sys.executable),
            out_root=tmp_path / "runs",
            summary_root=tmp_path / "summary",
            machine="reject-non-cinderx-cpython-cinderx",
            ci_mode=True,
            sample_count=1,
            warmup_count=0,
        )
    except ValueError as exc:
        assert "--cpython-cinderx" in str(exc)
        assert "import cinderx" in str(exc)
    else:
        raise AssertionError("Expected strict CinderX runtime validation error")


def test_cinderx_runtime_becomes_baseline_when_provided(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")
    monkeypatch.setattr(runner, "_runtime_has_cinderx_support", lambda _executable: True)

    result = runner.run_smoke_suite(
        python=Path(sys.executable),
        cpython_cinderx=Path(sys.executable),
        out_root=tmp_path / "runs",
        summary_root=tmp_path / "summary",
        machine="cinderx-baseline-test",
        ci_mode=True,
        sample_count=1,
        warmup_count=0,
    )

    summary = json.loads(Path(result.summary_path).read_text(encoding="utf-8"))
    assert summary["baseline_runtime"] == "cpython-cinderx"

    cinderx_rows = [row for row in summary["benchmarks"] if row["runtime"] == "cpython-cinderx"]
    assert cinderx_rows
    assert all(row["speedup_vs_baseline"] == 1.0 for row in cinderx_rows)


def test_run_pyperformance_suite_normalizes_results(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")

    cpython_link = tmp_path / "cpython-runtime"
    cpython_link.symlink_to(Path(sys.executable))
    cinderx_link = tmp_path / "cpython-cinderx-runtime"
    cinderx_link.symlink_to(Path(sys.executable))
    pypy_link = tmp_path / "pypy-runtime"
    pypy_link.symlink_to(Path(sys.executable))

    monkeypatch.setattr(
        runner,
        "_resolve_pyperformance_launcher",
        lambda _python_hint: (["fake-pyperformance"], "v1"),
    )
    monkeypatch.setattr(runner, "_runtime_has_cinderx_support", lambda _executable: True)
    monkeypatch.setattr(runner, "_measure_startup", lambda _executable, samples: [0.01] * samples)
    monkeypatch.setattr(
        runner,
        "_python_runtime_details",
        lambda _executable: {"implementation": "CPython", "version": "3.14"},
    )
    monkeypatch.setattr(runner, "_version_line", lambda _executable: "Python 3.14")

    observed_env_by_runtime_key: dict[str, dict[str, str]] = {}
    original_run_command = runner._run_command

    def fake_run_command(
        args: list[str],
        *,
        timeout_s: int = 90,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if args and args[0] == "fake-pyperformance":
            if env:
                runtime_key = env.get("CXC_PYPERF_RUNTIME_KEY", "unknown")
                observed_env_by_runtime_key[runtime_key] = dict(env)
                audit_dir = env.get("CXC_PYPERF_JIT_AUDIT_DIR")
                if runtime_key == "cpython-cinderx" and audit_dir:
                    audit_payload = {
                        "jit_module_available": True,
                        "jit_enabled": True,
                        "compiled_function_count": 7,
                        "static_loader_status": "not-requested",
                    }
                    Path(audit_dir).mkdir(parents=True, exist_ok=True)
                    (Path(audit_dir) / "jit-audit-test.json").write_text(
                        json.dumps(audit_payload),
                        encoding="utf-8",
                    )
            assert "--benchmarks" in args
            assert "nbody" in args
            runtime_arg = args[args.index("--python") + 1]
            output_arg = Path(args[args.index("--output") + 1])
            scale = 1.0
            if "cpython-cinderx" in runtime_arg:
                scale = 0.8
            elif "pypy" in runtime_arg:
                scale = 1.1

            payload = {
                "benchmarks": [
                    {
                        "metadata": {
                            "name": "json_dumps",
                            "mem_max_rss": 10240,
                            "compile_time_seconds": 0.12,
                        },
                        "runs": [
                            {"values": [0.10 * scale, 0.11 * scale], "warmups": [[1, 0.12 * scale]]}
                        ],
                    },
                    {
                        "metadata": {"name": "nbody"},
                        "runs": [
                            {"values": [0.40 * scale, 0.42 * scale], "warmups": [0.45 * scale]}
                        ],
                    },
                ]
            }
            output_arg.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        return original_run_command(args, timeout_s=timeout_s, env=env)

    monkeypatch.setattr(runner, "_run_command", fake_run_command)

    result = runner.run_pyperformance_suite(
        python=cpython_link,
        cpython_cinderx=cinderx_link,
        pypy=pypy_link,
        out_root=tmp_path / "runs",
        summary_root=tmp_path / "summary",
        machine="pyperformance-test",
        ci_mode=True,
        require_cinderx_baseline=True,
    )

    summary = json.loads(Path(result.summary_path).read_text(encoding="utf-8"))
    assert summary["suite"] == PYPERFORMANCE_SUITE
    assert summary["baseline_runtime"] == "cpython-cinderx"
    run_config = summary["metadata"]["run_config"]
    assert run_config["pyperformance_bootstrap_inline_enabled"] is True
    assert (
        run_config["pyperformance_bootstrap_profile"] == runner.AUTO_PYPERFORMANCE_BOOTSTRAP_PROFILE
    )
    assert run_config["pyperformance_bootstrap_profile_source"] == "auto-default"
    assert run_config["pyperformance_bootstrap_target_runtime_key"] == "cpython-cinderx"
    assert run_config["pyperformance_cinderx_jit_audit_required"] is True
    assert run_config["pyperformance_cinderx_static_loader_required"] is False
    assert observed_env_by_runtime_key["cpython"]["CXC_PYPERF_BOOTSTRAP_TARGET_RUNTIME_KEY"] == (
        "cpython-cinderx"
    )
    assert (
        observed_env_by_runtime_key["cpython-cinderx"]["CXC_PYPERF_BOOTSTRAP_TARGET_RUNTIME_KEY"]
        == "cpython-cinderx"
    )
    assert summary["benchmarks"]
    assert any(row["runtime"] == "pypy" for row in summary["benchmarks"])
    assert any(
        row["p_value"] is not None for row in summary["benchmarks"] if row["runtime"] == "pypy"
    )
    assert any(row["memory_rss_bytes"] is not None for row in summary["benchmarks"])
    assert any(row["compile_time_seconds"] is not None for row in summary["benchmarks"])
    cinderx_runtime = next(
        item for item in summary["runtimes"] if item.get("runtime") == "cpython-cinderx"
    )
    assert cinderx_runtime["jit_audit"]["compiled_during_run"] is True


def test_resolve_pyperformance_bootstrap_profile_compile_after_defaults() -> None:
    inline_code, profile, threshold, source_mode = runner._resolve_pyperformance_bootstrap_inline(
        inline_code=None,
        profile="cinderx-jit-compile-after-n-calls",
        jit_compile_after_n_calls=None,
    )
    assert source_mode == "profile"
    assert profile == "cinderx-jit-compile-after-n-calls"
    assert threshold == runner.DEFAULT_PYPERFORMANCE_JIT_COMPILE_AFTER_N_CALLS
    assert inline_code is not None
    assert "compile_after_n_calls" in inline_code
    assert str(runner.DEFAULT_PYPERFORMANCE_JIT_COMPILE_AFTER_N_CALLS) in inline_code


def test_resolve_pyperformance_bootstrap_profile_all_features() -> None:
    inline_code, profile, threshold, source_mode = runner._resolve_pyperformance_bootstrap_inline(
        inline_code=None,
        profile="cinderx-all-features",
        jit_compile_after_n_calls=None,
    )
    assert source_mode == "profile"
    assert profile == "cinderx-all-features"
    assert threshold is None
    assert inline_code is not None
    assert "cinderx.jit" in inline_code
    assert "compile_after_n_calls(0)" in inline_code
    assert "strict_stubs_dir" in inline_code
    assert "PYTHONSTRICTMODULESTUBSPATH" in inline_code
    assert "CXC_PYPERF_STATIC_LOADER_STATUS" in inline_code
    assert "requires strict loader stubs" in inline_code
    assert "strict_loader.install(enable_patching=True)" in inline_code


def test_describe_cinderx_pyperformance_features_all_features() -> None:
    features = runner._describe_cinderx_pyperformance_features(
        resolved_bootstrap_profile="cinderx-all-features",
        bootstrap_inline_sha256="abc123",
        resolved_bootstrap_jit_compile_after_n_calls=None,
    )
    assert features["profile"] == "cinderx-all-features"
    assert features["jit_mode"] == "all"
    assert features["jit_compile_after_n_calls"] == 0
    assert features["static_loader_enabled"] is True
    assert features["static_loader_enable_patching"] is True
    assert features["summary"] == "JIT all + static loader (patching; strict stubs required)"


def test_resolve_pyperformance_bootstrap_profile_jit_all() -> None:
    inline_code, profile, threshold, source_mode = runner._resolve_pyperformance_bootstrap_inline(
        inline_code=None,
        profile="cinderx-jit-all",
        jit_compile_after_n_calls=None,
    )
    assert source_mode == "profile"
    assert profile == "cinderx-jit-all"
    assert threshold is None
    assert inline_code is not None
    assert "compile_after_n_calls(0)" in inline_code


def test_describe_cinderx_pyperformance_features_jit_all() -> None:
    features = runner._describe_cinderx_pyperformance_features(
        resolved_bootstrap_profile="cinderx-jit-all",
        bootstrap_inline_sha256="abc123",
        resolved_bootstrap_jit_compile_after_n_calls=None,
    )
    assert features["profile"] == "cinderx-jit-all"
    assert features["jit_mode"] == "all"
    assert features["jit_compile_after_n_calls"] == 0
    assert features["summary"] == "JIT all"


def test_describe_cinderx_pyperformance_features_custom_inline() -> None:
    features = runner._describe_cinderx_pyperformance_features(
        resolved_bootstrap_profile=None,
        bootstrap_inline_sha256="deadbeef",
        resolved_bootstrap_jit_compile_after_n_calls=None,
    )
    assert features["profile"] == "custom-inline"
    assert features["jit_mode"] is None
    assert features["static_loader_enabled"] is None
    assert features["static_loader_enable_patching"] is None


def test_profile_expects_jit_compilation() -> None:
    assert runner._profile_expects_jit_compilation("cinderx-all-features") is True
    assert runner._profile_expects_jit_compilation("cinderx-jit-all") is True
    assert runner._profile_expects_jit_compilation("cinderx-jit-compile-after-n-calls") is True
    assert runner._profile_expects_jit_compilation("cinderx-jit-disable") is False
    assert runner._profile_expects_jit_compilation("cinderx-static-loader") is False
    assert runner._profile_expects_jit_compilation(None) is False


def test_profile_expects_static_loader() -> None:
    assert runner._profile_expects_static_loader("cinderx-all-features") is True
    assert runner._profile_expects_static_loader("cinderx-static-loader") is True
    assert runner._profile_expects_static_loader("cinderx-static-loader-patching") is True
    assert runner._profile_expects_static_loader("cinderx-jit-all") is False
    assert runner._profile_expects_static_loader(None) is False


def test_collect_pyperformance_jit_audit(tmp_path: Path) -> None:
    audit_dir = tmp_path / "jit-audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "jit-audit-1.json").write_text(
        json.dumps(
            {
                "jit_module_available": True,
                "jit_enabled": True,
                "compiled_function_count": 4,
                "static_loader_status": "installed",
            }
        ),
        encoding="utf-8",
    )
    (audit_dir / "jit-audit-2.json").write_text(
        json.dumps(
            {
                "jit_module_available": True,
                "jit_enabled": False,
                "compiled_function_count": 0,
                "static_loader_status": "installed",
            }
        ),
        encoding="utf-8",
    )

    payload = runner._collect_pyperformance_jit_audit(audit_dir)
    assert payload["record_count"] == 2
    assert payload["expected_executable"] is None
    assert payload["matching_expected_executable_record_count"] == 0
    assert payload["matching_expected_executable_record_ratio"] == 0.0
    assert payload["jit_module_available_any"] is True
    assert payload["jit_enabled_any"] is True
    assert payload["compiled_function_count_max"] == 4
    assert payload["compiled_during_run"] is True
    assert payload["cinderx_module_not_found_count"] == 0
    assert payload["top_executables"] == []
    assert payload["static_loader_statuses"] == ["installed"]


def test_collect_pyperformance_jit_audit_normalizes_realpath_for_expected_executable(
    tmp_path: Path,
) -> None:
    audit_dir = tmp_path / "jit-audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    real_python = bin_dir / "python-real"
    real_python.write_text("#!/bin/sh\n", encoding="utf-8")
    expected_link = bin_dir / "python-link"
    expected_link.symlink_to(real_python)

    (audit_dir / "jit-audit-1.json").write_text(
        json.dumps(
            {
                "expected_executable": str(expected_link),
                "sys_executable": str(real_python),
                "jit_module_available": True,
                "jit_enabled": True,
                "compiled_function_count": 3,
                "static_loader_status": "installed",
            }
        ),
        encoding="utf-8",
    )
    (audit_dir / "jit-audit-2.json").write_text(
        json.dumps(
            {
                "expected_executable": str(expected_link),
                "sys_executable": str(real_python),
                "jit_module_available": False,
                "jit_enabled": False,
                "compiled_function_count": 0,
                "static_loader_status": "installed",
                "error": "cinderx module not found",
            }
        ),
        encoding="utf-8",
    )

    payload = runner._collect_pyperformance_jit_audit(audit_dir)
    assert payload["record_count"] == 2
    assert payload["expected_executable"] == str(real_python.resolve())
    assert payload["matching_expected_executable_record_count"] == 2
    assert payload["matching_expected_executable_record_ratio"] == 1.0
    assert payload["matching_expected_executable_module_not_found_count"] == 1
    assert payload["cinderx_module_not_found_count"] == 1
    assert payload["top_executables"] == [{"executable": str(real_python.resolve()), "count": 2}]


def test_resolve_pyperformance_bootstrap_rejects_profile_inline_conflict() -> None:
    try:
        runner._resolve_pyperformance_bootstrap_inline(
            inline_code="print('x')",
            profile="cinderx-init",
            jit_compile_after_n_calls=None,
        )
    except ValueError as exc:
        assert (
            "Choose either --pyperformance-bootstrap-inline or --pyperformance-bootstrap-profile"
        ) in str(exc)
    else:
        raise AssertionError("Expected bootstrap profile/inline conflict validation error")


def test_run_pyperformance_suite_records_bootstrap_profile_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")

    cpython_link = tmp_path / "cpython-runtime"
    cpython_link.symlink_to(Path(sys.executable))
    cinderx_link = tmp_path / "cpython-cinderx-runtime"
    cinderx_link.symlink_to(Path(sys.executable))

    monkeypatch.setattr(
        runner,
        "_resolve_pyperformance_launcher",
        lambda _python_hint: (["fake-pyperformance"], "v1"),
    )
    monkeypatch.setattr(runner, "_runtime_has_cinderx_support", lambda _executable: True)
    monkeypatch.setattr(runner, "_measure_startup", lambda _executable, samples: [0.01] * samples)
    monkeypatch.setattr(
        runner,
        "_python_runtime_details",
        lambda _executable: {"implementation": "CPython", "version": "3.14"},
    )
    monkeypatch.setattr(runner, "_version_line", lambda _executable: "Python 3.14")

    observed_env_by_runtime_key: dict[str, dict[str, str]] = {}
    original_run_command = runner._run_command

    def fake_run_command(
        args: list[str],
        *,
        timeout_s: int = 90,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if args and args[0] == "fake-pyperformance":
            if env:
                runtime_key = env.get("CXC_PYPERF_RUNTIME_KEY", "unknown")
                observed_env_by_runtime_key[runtime_key] = dict(env)
                audit_dir = env.get("CXC_PYPERF_JIT_AUDIT_DIR")
                if runtime_key == "cpython-cinderx" and audit_dir:
                    audit_payload = {
                        "jit_module_available": True,
                        "jit_enabled": True,
                        "compiled_function_count": 5,
                        "static_loader_status": "not-requested",
                    }
                    Path(audit_dir).mkdir(parents=True, exist_ok=True)
                    (Path(audit_dir) / "jit-audit-test.json").write_text(
                        json.dumps(audit_payload),
                        encoding="utf-8",
                    )
            runtime_arg = args[args.index("--python") + 1]
            output_arg = Path(args[args.index("--output") + 1])
            scale = 1.0 if "cpython-cinderx" in runtime_arg else 1.1
            payload = {
                "benchmarks": [
                    {
                        "metadata": {"name": "nbody"},
                        "runs": [
                            {"values": [0.30 * scale, 0.32 * scale], "warmups": [0.35 * scale]}
                        ],
                    }
                ]
            }
            output_arg.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        return original_run_command(args, timeout_s=timeout_s, env=env)

    monkeypatch.setattr(runner, "_run_command", fake_run_command)

    result = runner.run_pyperformance_suite(
        python=cpython_link,
        cpython_cinderx=cinderx_link,
        out_root=tmp_path / "runs",
        summary_root=tmp_path / "summary",
        machine="pyperformance-bootstrap-profile-test",
        ci_mode=True,
        require_cinderx_baseline=True,
        pyperformance_bootstrap_profile="cinderx-jit-compile-after-n-calls",
        pyperformance_bootstrap_jit_compile_after_n_calls=7,
    )

    summary = json.loads(Path(result.summary_path).read_text(encoding="utf-8"))
    run_config = summary["metadata"]["run_config"]
    assert run_config["pyperformance_bootstrap_inline_enabled"] is True
    assert run_config["pyperformance_bootstrap_profile"] == "cinderx-jit-compile-after-n-calls"
    assert run_config["pyperformance_bootstrap_profile_source"] == "explicit"
    assert run_config["pyperformance_bootstrap_jit_compile_after_n_calls"] == 7
    assert run_config["pyperformance_bootstrap_target_runtime_key"] == "cpython-cinderx"
    assert run_config["pyperformance_cinderx_jit_audit_required"] is True
    assert run_config["pyperformance_cinderx_static_loader_required"] is False
    assert run_config["pyperformance_bootstrap_inline_sha256"]
    assert summary["metadata"]["toolchain"]["pyperformance_bootstrap_mode"] == (
        "sitecustomize-profile"
    )
    assert observed_env_by_runtime_key["cpython"]["CXC_PYPERF_BOOTSTRAP_MODE"] == (
        "sitecustomize-profile"
    )
    assert observed_env_by_runtime_key["cpython-cinderx"]["CXC_PYPERF_BOOTSTRAP_MODE"] == (
        "sitecustomize-profile"
    )
    assert observed_env_by_runtime_key["cpython"]["SETUPTOOLS_USE_DISTUTILS"] == "local"
    assert observed_env_by_runtime_key["cpython-cinderx"]["SETUPTOOLS_USE_DISTUTILS"] == "local"
    assert observed_env_by_runtime_key["cpython"]["CXC_PYPERF_BOOTSTRAP_TARGET_RUNTIME_KEY"] == (
        "cpython-cinderx"
    )
    assert (
        observed_env_by_runtime_key["cpython-cinderx"]["CXC_PYPERF_BOOTSTRAP_TARGET_RUNTIME_KEY"]
        == "cpython-cinderx"
    )
    assert (
        "compile_after_n_calls(7)"
        in observed_env_by_runtime_key["cpython"]["CXC_PYPERF_BOOTSTRAP_INLINE"]
    )
    cinderx_runtime = next(
        item for item in summary["runtimes"] if item.get("runtime") == "cpython-cinderx"
    )
    assert cinderx_runtime["jit_audit"]["compiled_during_run"] is True


def test_preflight_pyperformance_uses_cinderx_runtime_with_auto_profile(
    tmp_path: Path, monkeypatch
) -> None:
    cpython_link = tmp_path / "cpython-runtime"
    cpython_link.symlink_to(Path(sys.executable))
    cinderx_link = tmp_path / "cpython-cinderx-runtime"
    cinderx_link.symlink_to(Path(sys.executable))

    monkeypatch.setattr(runner, "_runtime_has_cinderx_support", lambda _executable: True)

    observed_commands: list[list[str]] = []
    observed_env_by_command: list[dict[str, str]] = []
    original_run_command = runner._run_command

    def fake_run_command(
        args: list[str],
        *,
        timeout_s: int = 90,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if len(args) >= 3 and args[1] == "-m" and args[2] == "pyperformance":
            observed_commands.append(list(args))
            observed_env_by_command.append(dict(env or {}))
            audit_dir = (env or {}).get("CXC_PYPERF_JIT_AUDIT_DIR")
            if audit_dir:
                payload = {
                    "jit_module_available": True,
                    "jit_enabled": True,
                    "compiled_function_count": 2,
                    "static_loader_status": "not-requested",
                    "expected_executable": (env or {}).get("CXC_PYPERF_EXPECTED_EXECUTABLE"),
                    "sys_executable": (env or {}).get("CXC_PYPERF_EXPECTED_EXECUTABLE"),
                }
                Path(audit_dir).mkdir(parents=True, exist_ok=True)
                (Path(audit_dir) / f"jit-audit-{len(observed_commands)}.json").write_text(
                    json.dumps(payload),
                    encoding="utf-8",
                )
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")
        if len(args) >= 3 and args[1] == "-c" and "cinderx.jit" in args[2]:
            payload = {
                "available": True,
                "jit_module_available": True,
                "jit_enabled": True,
                "compile_after_n_calls": 0,
                "compiled": True,
                "compiled_count": 1,
                "used_is_jit_compiled": True,
                "error": None,
            }
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )
        return original_run_command(args, timeout_s=timeout_s, env=env)

    monkeypatch.setattr(runner, "_run_command", fake_run_command)

    result = runner.preflight_pyperformance_suite(
        python=cpython_link,
        cpython_cinderx=cinderx_link,
        require_cinderx_baseline=True,
        timeout_seconds=10,
    )

    assert result.runtime == "cpython-cinderx"
    assert result.bootstrap_profile == runner.AUTO_PYPERFORMANCE_BOOTSTRAP_PROFILE
    assert result.bootstrap_profile_source == "auto-default"
    assert result.bootstrap_target_runtime_key == "cpython-cinderx"
    assert any("--help" in command for command in observed_commands)
    assert any("run" in command for command in observed_commands)
    assert any("--debug-single-value" in command for command in observed_commands)
    assert any(
        "--benchmarks" in command
        and command[command.index("--benchmarks") + 1]
        == runner.PYPERFORMANCE_LEGACY_DISTUTILS_BENCHMARKS
        for command in observed_commands
    )
    assert all("--inherit-environ" in command for command in observed_commands)
    assert observed_env_by_command
    assert any(
        env.get("CXC_PYPERF_RUNTIME_KEY") == "cpython-cinderx" for env in observed_env_by_command
    )
    assert any(env.get("CXC_PYPERF_RUNTIME_KEY") == "cpython" for env in observed_env_by_command)
    assert all(env.get("SETUPTOOLS_USE_DISTUTILS") == "local" for env in observed_env_by_command)
    assert all(
        env.get("CXC_PYPERF_BOOTSTRAP_TARGET_RUNTIME_KEY") == "cpython-cinderx"
        for env in observed_env_by_command
    )
    assert any("JIT probe observed compiled function" in note for note in result.notes)


def test_preflight_pyperformance_fails_fast_on_launcher_error(tmp_path: Path, monkeypatch) -> None:
    cpython_link = tmp_path / "cpython-runtime"
    cpython_link.symlink_to(Path(sys.executable))
    cinderx_link = tmp_path / "cpython-cinderx-runtime"
    cinderx_link.symlink_to(Path(sys.executable))

    monkeypatch.setattr(runner, "_runtime_has_cinderx_support", lambda _executable: True)

    def fake_run_command(
        args: list[str],
        *,
        timeout_s: int = 90,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if len(args) >= 3 and args[1] == "-m" and args[2] == "pyperformance":
            raise ValueError("simulated pyperformance bootstrap break")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner, "_run_command", fake_run_command)

    try:
        runner.preflight_pyperformance_suite(
            python=cpython_link,
            cpython_cinderx=cinderx_link,
            require_cinderx_baseline=True,
            timeout_seconds=10,
        )
    except ValueError as exc:
        assert "Preflight failed for pyperformance bootstrap on runtime 'cpython-cinderx'" in str(
            exc
        )
    else:
        raise AssertionError("Expected pyperformance preflight failure")


def test_run_pyperformance_suite_without_cinderx_keeps_bootstrap_disabled(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")

    cpython_link = tmp_path / "cpython-runtime"
    cpython_link.symlink_to(Path(sys.executable))
    pypy_missing = tmp_path / "missing-pypy-runtime"

    monkeypatch.setattr(
        runner,
        "_resolve_pyperformance_launcher",
        lambda _python_hint: (["fake-pyperformance"], "v1"),
    )
    monkeypatch.setattr(runner, "_measure_startup", lambda _executable, samples: [0.01] * samples)
    monkeypatch.setattr(
        runner,
        "_python_runtime_details",
        lambda _executable: {"implementation": "CPython", "version": "3.14"},
    )
    monkeypatch.setattr(runner, "_version_line", lambda _executable: "Python 3.14")

    observed_env: dict[str, str] = {}
    original_run_command = runner._run_command

    def fake_run_command(
        args: list[str],
        *,
        timeout_s: int = 90,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if args and args[0] == "fake-pyperformance":
            if env:
                observed_env.update(env)
            output_arg = Path(args[args.index("--output") + 1])
            payload = {
                "benchmarks": [
                    {
                        "metadata": {"name": "nbody"},
                        "runs": [{"values": [0.30, 0.32], "warmups": [0.35]}],
                    }
                ]
            }
            output_arg.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        return original_run_command(args, timeout_s=timeout_s, env=env)

    monkeypatch.setattr(runner, "_run_command", fake_run_command)

    result = runner.run_pyperformance_suite(
        python=cpython_link,
        pypy=pypy_missing,
        out_root=tmp_path / "runs",
        summary_root=tmp_path / "summary",
        machine="pyperformance-no-cinderx-auto-bootstrap",
        ci_mode=True,
    )

    summary = json.loads(Path(result.summary_path).read_text(encoding="utf-8"))
    run_config = summary["metadata"]["run_config"]
    assert run_config["pyperformance_bootstrap_inline_enabled"] is False
    assert run_config["pyperformance_bootstrap_profile"] is None
    assert run_config["pyperformance_bootstrap_profile_source"] == "disabled"
    assert run_config["pyperformance_bootstrap_target_runtime_key"] is None
    assert "CXC_PYPERF_BOOTSTRAP_INLINE" not in observed_env


def test_run_pyperformance_suite_rejects_bootstrap_without_cinderx_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")
    cpython_link = tmp_path / "cpython-runtime"
    cpython_link.symlink_to(Path(sys.executable))
    monkeypatch.setattr(
        runner,
        "_resolve_pyperformance_launcher",
        lambda _python_hint: (["fake-pyperformance"], "v1"),
    )
    monkeypatch.setattr(runner, "_measure_startup", lambda _executable, samples: [0.01] * samples)
    monkeypatch.setattr(
        runner,
        "_python_runtime_details",
        lambda _executable: {"implementation": "CPython", "version": "3.14"},
    )
    monkeypatch.setattr(runner, "_version_line", lambda _executable: "Python 3.14")

    try:
        runner.run_pyperformance_suite(
            python=cpython_link,
            out_root=tmp_path / "runs",
            summary_root=tmp_path / "summary",
            machine="pyperformance-bootstrap-missing-runtime",
            ci_mode=True,
            require_cinderx_baseline=False,
            pyperformance_bootstrap_profile="cinderx-all-features",
        )
    except ValueError as exc:
        assert "Provide --cpython-cinderx /path/to/cinderx-python" in str(exc)
    else:
        raise AssertionError("Expected bootstrap target runtime validation failure")


def test_verify_publishable_summaries_rejects_non_cinderx_baseline(tmp_path: Path) -> None:
    summary_root = tmp_path / "summary"
    summary_root.mkdir(parents=True, exist_ok=True)

    smoke_payload = _publishable_summary_payload(suite=SMOKE_SUITE)
    smoke_payload["baseline_runtime"] = "cpython"
    (summary_root / "latest-smoke.json").write_text(json.dumps(smoke_payload), encoding="utf-8")
    _write_index(
        summary_root / "index.json",
        suites=[SMOKE_SUITE],
        latest_file_by_suite={SMOKE_SUITE: "latest-smoke.json"},
    )

    try:
        runner.verify_publishable_summaries(
            summary_root=summary_root,
            static_summary_root=None,
            suites=[SMOKE_SUITE],
        )
    except ValueError as exc:
        assert "baseline_runtime" in str(exc)
        assert "cpython-cinderx" in str(exc)
    else:
        raise AssertionError("Expected verify-publish baseline guard failure")


def test_verify_publishable_summaries_accepts_cinderx_published_payloads(tmp_path: Path) -> None:
    summary_root = tmp_path / "summary"
    static_root = tmp_path / "static-summary"
    summary_root.mkdir(parents=True, exist_ok=True)
    static_root.mkdir(parents=True, exist_ok=True)

    payloads = {
        SMOKE_SUITE: _publishable_summary_payload(suite=SMOKE_SUITE),
        PYPERFORMANCE_SUITE: _publishable_summary_payload(suite=PYPERFORMANCE_SUITE),
    }
    for suite, payload in payloads.items():
        latest_name = f"latest-{suite}.json"
        (summary_root / latest_name).write_text(json.dumps(payload), encoding="utf-8")
        (static_root / latest_name).write_text(json.dumps(payload), encoding="utf-8")

    _write_index(
        summary_root / "index.json",
        suites=[SMOKE_SUITE, PYPERFORMANCE_SUITE],
        latest_file_by_suite={
            SMOKE_SUITE: "latest-smoke.json",
            PYPERFORMANCE_SUITE: "latest-pyperformance.json",
        },
    )
    _write_index(
        static_root / "index.json",
        suites=[SMOKE_SUITE, PYPERFORMANCE_SUITE],
        latest_file_by_suite={
            SMOKE_SUITE: "latest-smoke.json",
            PYPERFORMANCE_SUITE: "latest-pyperformance.json",
        },
    )

    result = runner.verify_publishable_summaries(
        summary_root=summary_root,
        static_summary_root=static_root,
    )
    assert result.suites_checked == [SMOKE_SUITE, PYPERFORMANCE_SUITE]
    assert any("CinderX-baselined" in note for note in result.notes)


def test_verify_publishable_summaries_rejects_cross_suite_machine_mismatch(tmp_path: Path) -> None:
    summary_root = tmp_path / "summary"
    summary_root.mkdir(parents=True, exist_ok=True)

    smoke_payload = _publishable_summary_payload(suite=SMOKE_SUITE)
    pyperf_payload = _publishable_summary_payload(suite=PYPERFORMANCE_SUITE)
    pyperf_payload["machine"] = "other-host"

    (summary_root / "latest-smoke.json").write_text(json.dumps(smoke_payload), encoding="utf-8")
    (summary_root / "latest-pyperformance.json").write_text(
        json.dumps(pyperf_payload),
        encoding="utf-8",
    )
    _write_index(
        summary_root / "index.json",
        suites=[SMOKE_SUITE, PYPERFORMANCE_SUITE],
        latest_file_by_suite={
            SMOKE_SUITE: "latest-smoke.json",
            PYPERFORMANCE_SUITE: "latest-pyperformance.json",
        },
    )

    try:
        runner.verify_publishable_summaries(summary_root=summary_root)
    except ValueError as exc:
        assert "machine mismatch" in str(exc)
    else:
        raise AssertionError("Expected publish verification failure for suite machine mismatch")


def test_verify_publishable_summaries_rejects_unsupported_runtime_rows(tmp_path: Path) -> None:
    summary_root = tmp_path / "summary"
    summary_root.mkdir(parents=True, exist_ok=True)

    smoke_payload = _publishable_summary_payload(suite=SMOKE_SUITE)
    runtimes = smoke_payload.get("runtimes")
    assert isinstance(runtimes, list)
    runtimes.append(
        {
            "runtime": "unsupported-runtime",
            "runtime_label": "Unsupported runtime",
            "runtime_version": "0.0",
            "runtime_details": {},
            "executed": False,
        }
    )
    benchmarks = smoke_payload.get("benchmarks")
    assert isinstance(benchmarks, list)
    benchmarks.append(
        {
            "benchmark": "dynamic_dispatch",
            "runtime": "unsupported-runtime",
            "speedup_vs_baseline": None,
        }
    )

    (summary_root / "latest-smoke.json").write_text(json.dumps(smoke_payload), encoding="utf-8")
    _write_index(
        summary_root / "index.json",
        suites=[SMOKE_SUITE],
        latest_file_by_suite={SMOKE_SUITE: "latest-smoke.json"},
    )

    try:
        runner.verify_publishable_summaries(
            summary_root=summary_root,
            suites=[SMOKE_SUITE],
        )
    except ValueError as exc:
        assert "unsupported runtime key(s)" in str(exc)
    else:
        raise AssertionError("Expected publish verification failure for unsupported runtime rows")


def test_verify_publishable_summaries_rejects_missing_pyperformance_jit_audit(
    tmp_path: Path,
) -> None:
    summary_root = tmp_path / "summary"
    summary_root.mkdir(parents=True, exist_ok=True)

    pyperf_payload = _publishable_summary_payload(suite=PYPERFORMANCE_SUITE)
    runtimes = pyperf_payload.get("runtimes")
    assert isinstance(runtimes, list)
    assert runtimes
    runtime_row = runtimes[0]
    assert isinstance(runtime_row, dict)
    runtime_row.pop("jit_audit", None)

    (summary_root / "latest-pyperformance.json").write_text(
        json.dumps(pyperf_payload),
        encoding="utf-8",
    )
    _write_index(
        summary_root / "index.json",
        suites=[PYPERFORMANCE_SUITE],
        latest_file_by_suite={PYPERFORMANCE_SUITE: "latest-pyperformance.json"},
    )

    try:
        runner.verify_publishable_summaries(
            summary_root=summary_root,
            suites=[PYPERFORMANCE_SUITE],
        )
    except ValueError as exc:
        assert "jit_audit" in str(exc)
    else:
        raise AssertionError(
            "Expected publish verification failure for missing pyperformance jit_audit"
        )


def test_verify_publishable_summaries_allows_non_target_subprocess_import_failures(
    tmp_path: Path,
) -> None:
    summary_root = tmp_path / "summary"
    summary_root.mkdir(parents=True, exist_ok=True)

    pyperf_payload = _publishable_summary_payload(suite=PYPERFORMANCE_SUITE)
    runtimes = pyperf_payload.get("runtimes")
    assert isinstance(runtimes, list) and runtimes
    runtime_row = runtimes[0]
    assert isinstance(runtime_row, dict)
    jit_audit = runtime_row.get("jit_audit")
    assert isinstance(jit_audit, dict)
    jit_audit.update(
        {
            "expected_executable": "/tmp/cinderx-python",
            "matching_expected_executable_record_count": 3,
            "matching_expected_executable_module_not_found_count": 0,
            "matching_expected_executable_jit_module_available_any": True,
            "matching_expected_executable_jit_enabled_any": True,
            "matching_expected_executable_compiled_during_run": True,
            "cinderx_module_not_found_count": 9,
        }
    )

    (summary_root / "latest-pyperformance.json").write_text(
        json.dumps(pyperf_payload),
        encoding="utf-8",
    )
    _write_index(
        summary_root / "index.json",
        suites=[PYPERFORMANCE_SUITE],
        latest_file_by_suite={PYPERFORMANCE_SUITE: "latest-pyperformance.json"},
    )

    runner.verify_publishable_summaries(
        summary_root=summary_root,
        suites=[PYPERFORMANCE_SUITE],
    )


def test_verify_publishable_summaries_rejects_target_executable_import_failures(
    tmp_path: Path,
) -> None:
    summary_root = tmp_path / "summary"
    summary_root.mkdir(parents=True, exist_ok=True)

    pyperf_payload = _publishable_summary_payload(suite=PYPERFORMANCE_SUITE)
    runtimes = pyperf_payload.get("runtimes")
    assert isinstance(runtimes, list) and runtimes
    runtime_row = runtimes[0]
    assert isinstance(runtime_row, dict)
    jit_audit = runtime_row.get("jit_audit")
    assert isinstance(jit_audit, dict)
    jit_audit.update(
        {
            "expected_executable": "/tmp/cinderx-python",
            "matching_expected_executable_record_count": 3,
            "matching_expected_executable_module_not_found_count": 1,
            "matching_expected_executable_jit_module_available_any": True,
            "matching_expected_executable_jit_enabled_any": True,
            "matching_expected_executable_compiled_during_run": True,
            "cinderx_module_not_found_count": 1,
        }
    )

    (summary_root / "latest-pyperformance.json").write_text(
        json.dumps(pyperf_payload),
        encoding="utf-8",
    )
    _write_index(
        summary_root / "index.json",
        suites=[PYPERFORMANCE_SUITE],
        latest_file_by_suite={PYPERFORMANCE_SUITE: "latest-pyperformance.json"},
    )

    try:
        runner.verify_publishable_summaries(
            summary_root=summary_root,
            suites=[PYPERFORMANCE_SUITE],
        )
    except ValueError as exc:
        assert "on expected executable" in str(exc)
    else:
        raise AssertionError(
            "Expected publish verification failure for target-executable import failures"
        )


def test_verify_publishable_summaries_rejects_static_mismatch(tmp_path: Path) -> None:
    summary_root = tmp_path / "summary"
    static_root = tmp_path / "static-summary"
    summary_root.mkdir(parents=True, exist_ok=True)
    static_root.mkdir(parents=True, exist_ok=True)

    summary_payload = _publishable_summary_payload(suite=SMOKE_SUITE)
    static_payload = _publishable_summary_payload(suite=SMOKE_SUITE)
    static_payload["metadata"] = {"run_config": {"require_cinderx_baseline": False}}

    (summary_root / "latest-smoke.json").write_text(json.dumps(summary_payload), encoding="utf-8")
    (static_root / "latest-smoke.json").write_text(json.dumps(static_payload), encoding="utf-8")
    _write_index(
        summary_root / "index.json",
        suites=[SMOKE_SUITE],
        latest_file_by_suite={SMOKE_SUITE: "latest-smoke.json"},
    )
    _write_index(
        static_root / "index.json",
        suites=[SMOKE_SUITE],
        latest_file_by_suite={SMOKE_SUITE: "latest-smoke.json"},
    )

    try:
        runner.verify_publishable_summaries(
            summary_root=summary_root,
            static_summary_root=static_root,
            suites=[SMOKE_SUITE],
        )
    except ValueError as exc:
        assert "Summary/static mismatch" in str(exc) or "require_cinderx_baseline" in str(exc)
    else:
        raise AssertionError("Expected static mismatch publish verification failure")


def test_export_metadata_dossiers_writes_files(tmp_path: Path) -> None:
    summary_root = tmp_path / "summary"
    summary_root.mkdir(parents=True, exist_ok=True)

    smoke_payload = _publishable_summary_payload(suite=SMOKE_SUITE)
    pyperformance_payload = _publishable_summary_payload(suite=PYPERFORMANCE_SUITE)
    (summary_root / "latest-smoke.json").write_text(json.dumps(smoke_payload), encoding="utf-8")
    (summary_root / "latest-pyperformance.json").write_text(
        json.dumps(pyperformance_payload),
        encoding="utf-8",
    )

    result = runner.export_metadata_dossiers(summary_root=summary_root)
    assert result.suites_exported == [SMOKE_SUITE, PYPERFORMANCE_SUITE]
    assert len(result.output_files) == 2
    for file_path in result.output_files:
        assert Path(file_path).exists()
        payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
        assert "metadata" in payload


def test_export_metadata_dossiers_fails_for_missing_latest(tmp_path: Path) -> None:
    summary_root = tmp_path / "summary"
    summary_root.mkdir(parents=True, exist_ok=True)
    (summary_root / "latest-smoke.json").write_text(
        json.dumps(_publishable_summary_payload(suite=SMOKE_SUITE)),
        encoding="utf-8",
    )

    try:
        runner.export_metadata_dossiers(summary_root=summary_root)
    except ValueError as exc:
        assert "latest-pyperformance.json" in str(exc)
    else:
        raise AssertionError("Expected metadata dossier export failure for missing suite summary")
