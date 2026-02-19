from __future__ import annotations

import json
import subprocess
from pathlib import Path

from cinderx_community import upstream
from cinderx_community.research.extract import extract_metadata, render_docs_from_introspection


def _run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _init_repo(path: Path, *, remote_url: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _run_git(path, "init")
    _run_git(path, "config", "user.name", "Test User")
    _run_git(path, "config", "user.email", "test@example.com")
    _run_git(path, "remote", "add", "origin", remote_url)
    return path


def _commit_all(repo: Path, message: str) -> None:
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-m", message)


def test_upstream_pin_writes_pins_toml(tmp_path: Path, monkeypatch) -> None:
    remote_repo = _init_repo(
        tmp_path / "remote",
        remote_url="https://github.com/example/demo.git",
    )
    (remote_repo / "README.md").write_text("demo\n", encoding="utf-8")
    _commit_all(remote_repo, "init")

    monkeypatch.setitem(upstream.DEFAULT_REPOS, "demo", str(remote_repo))
    monkeypatch.setattr(upstream, "PINS_FILE", tmp_path / "pins.toml")
    monkeypatch.setattr(upstream, "HISTORY_ROOT", tmp_path / "history")
    monkeypatch.setattr(upstream, "LEGACY_PIN_ROOT", tmp_path / "legacy")

    status = upstream.pin_upstream(
        repo="demo",
        destination=remote_repo,
        tags=["phase-2", "introspection"],
    )

    expected = _run_git(remote_repo, "rev-parse", "HEAD")
    assert status.pinned_commit == expected

    pins_text = (tmp_path / "pins.toml").read_text(encoding="utf-8")
    assert "[repos.demo]" in pins_text
    assert expected in pins_text
    assert "phase-2" in pins_text

    history_text = (tmp_path / "history" / "demo.jsonl").read_text(encoding="utf-8")
    assert "manual-pin" in history_text


def test_extract_and_render_docs(tmp_path: Path) -> None:
    repo = _init_repo(
        tmp_path / "demo-repo",
        remote_url="https://github.com/example/demo.git",
    )
    (repo / "pkg").mkdir()
    (repo / "native").mkdir()
    (repo / "tests").mkdir()

    (repo / "pkg" / "__init__.py").write_text(
        "__all__ = ['Demo']\n\nclass Demo:\n    pass\n\ndef helper() -> int:\n    return 1\n",
        encoding="utf-8",
    )
    (repo / "native" / "module.c").write_text(
        "PyMODINIT_FUNC PyInit_demo(void) {\n  return NULL;\n}\n",
        encoding="utf-8",
    )
    (repo / "CMakeLists.txt").write_text(
        'option(ENABLE_DEMO "demo flag" ON)\nadd_definitions(-DENABLE_DEMO)\n',
        encoding="utf-8",
    )
    (repo / "tests" / "test_basic.py").write_text(
        "import pytest\n\n@pytest.mark.slow\ndef test_basic() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    _commit_all(repo, "seed")

    extracted = extract_metadata(repo="demo", repo_path=repo, out_root=tmp_path / "data")
    assert Path(extracted.output_dir).exists()

    summary = json.loads((Path(extracted.output_dir) / "summary.json").read_text(encoding="utf-8"))
    symbols = json.loads((Path(extracted.output_dir) / "symbols.json").read_text(encoding="utf-8"))
    build_flags = json.loads(
        (Path(extracted.output_dir) / "build_flags.json").read_text(encoding="utf-8")
    )
    tests = json.loads((Path(extracted.output_dir) / "tests.json").read_text(encoding="utf-8"))

    assert summary["repo"] == "demo"
    assert any(item["name"] == "Demo" for item in symbols["python"]["classes"])
    assert any(item["name"] == "ENABLE_DEMO" for item in build_flags["flags"])
    assert any(item["marker"] == "slow" for item in tests["marker_frequency"])

    rendered = render_docs_from_introspection(
        repo="demo",
        data_root=tmp_path / "data",
        docs_root=tmp_path / "docs",
        commit_sha=extracted.commit_sha,
    )
    assert len(rendered.generated_pages) == 4

    overview = Path(rendered.docs_dir) / "introspection-overview.mdx"
    assert overview.exists()
    text = overview.read_text(encoding="utf-8")
    assert "Provenance" in text
    assert "Built from `demo`" in text

    symbols_doc = Path(rendered.docs_dir) / "symbol-inventory.mdx"
    build_doc = Path(rendered.docs_dir) / "build-options.mdx"
    tests_doc = Path(rendered.docs_dir) / "test-taxonomy.mdx"

    for doc in (symbols_doc, build_doc, tests_doc):
        rendered_text = doc.read_text(encoding="utf-8")
        assert "https://github.com/example/demo/blob/" in rendered_text
        assert "#L" in rendered_text
