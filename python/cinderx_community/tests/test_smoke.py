from typer.testing import CliRunner

from cinderx_community import upstream
from cinderx_community.cli import app


def test_cli_help_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "CinderX Community CLI" in result.stdout


def test_bench_list_mentions_pyperformance() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["bench", "list"])
    assert result.exit_code == 0
    assert "pyperformance" in result.stdout


def test_upstream_status_uninitialized(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")
    monkeypatch.setattr(upstream, "HISTORY_ROOT", tmp_path / "history")
    monkeypatch.setattr(upstream, "LEGACY_PIN_ROOT", tmp_path / "legacy")
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["upstream", "status", "--repo", "cinderx", "--dest", ".cache/upstream/does-not-exist"],
        )
    assert result.exit_code == 0
    assert "uninitialized" in result.stdout
