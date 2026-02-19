from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from cinderx_community import upstream
from cinderx_community.bench import runner
from cinderx_community.bench.runner import PYPERFORMANCE_SUITE, SMOKE_SUITE, build_plan, list_suites


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


def test_run_smoke_suite_executes_nuitka_adapter_when_provided(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")

    fake_nuitka = tmp_path / "fake-nuitka"
    fake_nuitka.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_nuitka.chmod(0o755)

    original_run_command = runner._run_command

    def fake_run_command(
        args: list[str], *, timeout_s: int = 90
    ) -> subprocess.CompletedProcess[str]:
        if args and args[0] == str(fake_nuitka):
            output_dir_arg = next(
                (item for item in args if item.startswith("--output-dir=")),
                None,
            )
            if output_dir_arg is None:
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="Nuitka 4.0.1",
                    stderr="",
                )
            output_dir = Path(output_dir_arg.split("=", maxsplit=1)[1])
            compiled = output_dir / "smoke-worker"
            compiled.write_text("#!/bin/sh\n", encoding="utf-8")
            compiled.chmod(0o755)
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        if args and args[0].endswith("smoke-worker"):
            payload = {"warmups": [], "samples": [0.01], "rss_max_bytes": 4096}
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )
        return original_run_command(args, timeout_s=timeout_s)

    monkeypatch.setattr(runner, "_run_command", fake_run_command)

    result = runner.run_smoke_suite(
        python=Path(sys.executable),
        nuitka=fake_nuitka,
        out_root=tmp_path / "runs",
        summary_root=tmp_path / "summary",
        machine="nuitka-adapter-test",
        ci_mode=True,
        sample_count=1,
        warmup_count=0,
    )

    summary = json.loads(Path(result.summary_path).read_text(encoding="utf-8"))
    nuitka_rows = [row for row in summary["benchmarks"] if row["runtime"] == "nuitka"]
    assert nuitka_rows
    assert all(row["compile_time_seconds"] is not None for row in nuitka_rows)


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

    original_run_command = runner._run_command

    def fake_run_command(
        args: list[str], *, timeout_s: int = 90
    ) -> subprocess.CompletedProcess[str]:
        if args and args[0] == "fake-pyperformance":
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
        return original_run_command(args, timeout_s=timeout_s)

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
    assert summary["benchmarks"]
    assert any(row["runtime"] == "pypy" for row in summary["benchmarks"])
    assert any(
        row["p_value"] is not None for row in summary["benchmarks"] if row["runtime"] == "pypy"
    )
    assert any(row["memory_rss_bytes"] is not None for row in summary["benchmarks"])
    assert any(row["compile_time_seconds"] is not None for row in summary["benchmarks"])


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
