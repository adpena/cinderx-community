"""Source-backed introspection extraction and generated-doc rendering."""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    "build",
    "dist",
    "node_modules",
}

PYTHON_SUFFIXES = {".py"}
C_CPP_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp"}
MAX_FILE_BYTES = 2_000_000
MAX_ROWS_PER_DOC_TABLE = 120

FLAG_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("cmake-option", re.compile(r"\boption\(\s*([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)),
    (
        "cmake-set-bool",
        re.compile(
            r"\bset\(\s*([A-Za-z_][A-Za-z0-9_]*)\s+(ON|OFF|TRUE|FALSE)\b",
            re.IGNORECASE,
        ),
    ),
    ("compile-definition", re.compile(r"(?:^|\s)-D([A-Za-z_][A-Za-z0-9_]*)")),
    ("ifdef", re.compile(r"^\s*#\s*(?:ifn?def)\s+([A-Za-z_][A-Za-z0-9_]*)")),
    ("if-defined", re.compile(r"defined\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)")),
]

RUNTIME_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("linux", re.compile(r"\blinux\b", re.IGNORECASE)),
    ("macos", re.compile(r"\b(macos|darwin)\b", re.IGNORECASE)),
    ("windows", re.compile(r"\b(win32|windows)\b", re.IGNORECASE)),
    ("x86_64", re.compile(r"\b(x86_64|amd64)\b", re.IGNORECASE)),
    ("arm", re.compile(r"\b(aarch64|arm64|arm)\b", re.IGNORECASE)),
    ("asan", re.compile(r"\basan\b", re.IGNORECASE)),
    ("jit", re.compile(r"\bjit\b", re.IGNORECASE)),
    ("free-threading", re.compile(r"(free-thread|gil[_ -]?disabled)", re.IGNORECASE)),
]

MARKER_PATTERN = re.compile(r"@(?:pytest\.)?mark\.([A-Za-z_][A-Za-z0-9_]*)")
PASS_MARKERS = {
    "passIf": re.compile(r"@passIf\b"),
    "passUnless": re.compile(r"@passUnless\b"),
    "skip": re.compile(r"@(?:unittest\.)?skip(?:If|Unless)?\b"),
}
FLAKY_PATTERN = re.compile(
    r"\b(xfail|flaky|unstable|nondeterministic|intermittent)\b",
    re.IGNORECASE,
)

C_EXPORT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("pyapi", re.compile(r"\bPyAPI_(?:FUNC|DATA)\s*\([^)]*\)\s*([A-Za-z_][A-Za-z0-9_]*)")),
    ("module-init", re.compile(r"\bPyMODINIT_FUNC\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")),
    (
        "export-macro",
        re.compile(
            r"\b(?:CINDERX?_EXPORT|CI_EXPORT|JIT_EXPORT)\b[^{;]*\b([A-Za-z_][A-Za-z0-9_]*)\s*\("
        ),
    ),
]
C_FUNCTION_PATTERN = re.compile(
    r"^\s*(?P<prefix>[A-Za-z_][A-Za-z0-9_\s\*\:&<>]*)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{"
)


@dataclass(slots=True)
class ExtractedMetadata:
    repo: str
    repo_path: str
    repo_url: str
    commit_sha: str
    output_dir: str
    generated_files: list[str]
    notes: list[str]


@dataclass(slots=True)
class RenderedDocs:
    repo: str
    commit_sha: str
    source_dir: str
    docs_dir: str
    generated_pages: list[str]


def _git(args: list[str], cwd: Path) -> str:
    command = ["git", *args]
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise ValueError("git is required for introspection but is not available") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or "(no stderr)"
        raise ValueError(f"git command failed: {' '.join(command)}\n{stderr}") from exc
    return completed.stdout.strip()


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _iter_files(root: Path, suffixes: set[str] | None = None) -> list[Path]:
    results: list[Path] = []
    for current_root, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".git"))
        for name in sorted(files):
            path = Path(current_root, name)
            if suffixes is not None and path.suffix not in suffixes:
                continue
            if "gen_cached" in name or "generated_cases" in name:
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            results.append(path)
    return results


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _module_name(relative: Path) -> str:
    parts = list(relative.parts)
    if not parts:
        return ""
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(parts[-1]).stem
    return ".".join(parts)


def _extract_all_literal(node: ast.Assign | ast.AnnAssign) -> list[str] | None:
    value = node.value if isinstance(node, ast.Assign) else node.value
    if value is None or not isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        return None
    names: list[str] = []
    for element in value.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            names.append(element.value)
        else:
            return None
    return names


def _extract_python_symbols(repo_path: Path) -> dict[str, object]:
    python_files = _iter_files(repo_path, PYTHON_SUFFIXES)
    modules: list[dict[str, object]] = []
    classes: list[dict[str, object]] = []
    functions: list[dict[str, object]] = []
    exports: list[dict[str, object]] = []
    parse_errors: list[dict[str, object]] = []

    for path in python_files:
        relative = path.relative_to(repo_path)
        module = _module_name(relative)
        source = _safe_read_text(path)
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            parse_errors.append(
                {
                    "path": _relative(path, repo_path),
                    "line": exc.lineno or 1,
                    "message": str(exc),
                }
            )
            continue

        modules.append({"module": module, "path": _relative(path, repo_path)})
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                classes.append(
                    {
                        "name": node.name,
                        "module": module,
                        "path": _relative(path, repo_path),
                        "line": node.lineno,
                    }
                )
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                kind = "async-function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                functions.append(
                    {
                        "name": node.name,
                        "kind": kind,
                        "module": module,
                        "path": _relative(path, repo_path),
                        "line": node.lineno,
                    }
                )
            elif isinstance(node, ast.Assign):
                target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if "__all__" in target_names:
                    names = _extract_all_literal(node)
                    if names is not None:
                        exports.append(
                            {
                                "module": module,
                                "path": _relative(path, repo_path),
                                "line": node.lineno,
                                "names": sorted(names),
                            }
                        )
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == "__all__":
                    names = _extract_all_literal(node)
                    if names is not None:
                        exports.append(
                            {
                                "module": module,
                                "path": _relative(path, repo_path),
                                "line": node.lineno,
                                "names": sorted(names),
                            }
                        )

    modules.sort(key=lambda row: (str(row["module"]), str(row["path"])))
    classes.sort(key=lambda row: (str(row["name"]), str(row["module"]), int(row["line"])))
    functions.sort(key=lambda row: (str(row["name"]), str(row["module"]), int(row["line"])))
    exports.sort(key=lambda row: (str(row["module"]), str(row["path"]), int(row["line"])))
    parse_errors.sort(key=lambda row: (str(row["path"]), int(row["line"])))

    return {
        "files_scanned": len(python_files),
        "modules": modules,
        "classes": classes,
        "functions": functions,
        "exports": exports,
        "parse_errors": parse_errors,
    }


def _storage_class(prefix: str) -> str:
    prefix_lower = prefix.lower()
    if "static " in prefix_lower or prefix_lower.startswith("static"):
        return "static"
    if "extern " in prefix_lower or prefix_lower.startswith("extern"):
        return "extern"
    return "public"


def _extract_c_symbols(repo_path: Path) -> dict[str, object]:
    files = _iter_files(repo_path, C_CPP_SUFFIXES)
    exported_symbols: list[dict[str, object]] = []
    function_symbols: list[dict[str, object]] = []
    seen: set[tuple[str, str, int, str]] = set()

    for path in files:
        source = _safe_read_text(path)
        lines = source.splitlines()
        rel = _relative(path, repo_path)
        for index, line in enumerate(lines, start=1):
            for kind, pattern in C_EXPORT_PATTERNS:
                match = pattern.search(line)
                if match is None:
                    continue
                name = match.group(1)
                key = (name, rel, index, kind)
                if key in seen:
                    continue
                seen.add(key)
                exported_symbols.append(
                    {
                        "name": name,
                        "kind": kind,
                        "path": rel,
                        "line": index,
                    }
                )

            match = C_FUNCTION_PATTERN.match(line)
            if match is None:
                continue
            name = match.group("name")
            if name in {"if", "for", "while", "switch"}:
                continue
            key = (name, rel, index, "function")
            if key in seen:
                continue
            seen.add(key)
            function_symbols.append(
                {
                    "name": name,
                    "path": rel,
                    "line": index,
                    "storage": _storage_class(match.group("prefix")),
                }
            )

    exported_symbols.sort(key=lambda row: (str(row["name"]), str(row["path"]), int(row["line"])))
    function_symbols.sort(key=lambda row: (str(row["name"]), str(row["path"]), int(row["line"])))
    return {
        "files_scanned": len(files),
        "exported_symbols": exported_symbols,
        "function_definitions": function_symbols,
        "limitations": [
            "C/C++ extraction uses regex fallbacks, not a full Clang AST pipeline.",
            "Generated files like *gen_cached* and *generated_cases* are skipped.",
        ],
    }


def _is_relevant_flag(name: str) -> bool:
    upper = name.upper()
    return (
        upper.startswith(("ENABLE_", "CINDER", "CI_", "PY_"))
        or "JIT" in upper
        or "STATIC" in upper
        or "STRICT" in upper
        or "GIL" in upper
        or "PARALLEL_GC" in upper
    )


def _build_flag_candidate(path: Path) -> bool:
    if path.name in {"CMakeLists.txt", "Makefile", "setup.py", "pyproject.toml"}:
        return True
    return path.suffix in {".cmake", ".mk", ".py", ".toml", ".h", ".hpp", ".c", ".cpp"}


def _extract_build_flags(repo_path: Path) -> dict[str, object]:
    all_files = _iter_files(repo_path)
    flag_records: dict[str, dict[str, object]] = {}

    for path in all_files:
        if not _build_flag_candidate(path):
            continue
        text = _safe_read_text(path)
        rel = _relative(path, repo_path)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for kind, pattern in FLAG_PATTERNS:
                match = pattern.search(line)
                if match is None:
                    continue
                name = match.group(1)
                if not _is_relevant_flag(name):
                    continue
                existing = flag_records.get(name)
                if existing is not None:
                    continue
                flag_records[name] = {
                    "name": name,
                    "kind": kind,
                    "path": rel,
                    "line": line_no,
                    "snippet": line.strip(),
                }

    flags = sorted(flag_records.values(), key=lambda row: (str(row["name"]), str(row["path"])))
    return {
        "flags": flags,
        "limitations": [
            "Build options are discovered heuristically from source text.",
            "Not every conditional compilation branch is guaranteed to be surfaced.",
        ],
    }


def _is_test_file(relative: Path) -> bool:
    suffix = relative.suffix.lower()
    if suffix not in {".py", ".cpp", ".cc", ".c", ".h"}:
        return False
    lower_parts = [part.lower() for part in relative.parts]
    name = relative.name.lower()
    if "testscripts" in lower_parts:
        return True
    if name.startswith("test_"):
        return True
    if name.endswith(("_test.py", "_test.cpp", "_test.cc", "_test.c")):
        return True
    return any(part.startswith("test") or part.endswith("tests") for part in lower_parts)


def _group_for_test(relative: Path) -> str:
    parts = relative.parts
    if "RuntimeTests" in parts:
        return "RuntimeTests"
    if "TestScripts" in parts:
        return "TestScripts"
    if "PythonLib" in parts and "test_cinderx" in parts:
        return "PythonLib/test_cinderx"
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return parts[0] if parts else "unknown"


def _extract_test_taxonomy(repo_path: Path) -> dict[str, object]:
    test_files = [
        path for path in _iter_files(repo_path) if _is_test_file(path.relative_to(repo_path))
    ]
    entries: list[dict[str, object]] = []
    group_counts: dict[str, int] = {}
    marker_counts: dict[str, int] = {}
    runtime_counts: dict[str, int] = {}

    for path in test_files:
        rel = path.relative_to(repo_path)
        rel_text = _relative(path, repo_path)
        group = _group_for_test(rel)
        text = _safe_read_text(path)
        lines = text.splitlines()

        markers = set(MARKER_PATTERN.findall(text))
        for marker_name, pattern in PASS_MARKERS.items():
            if pattern.search(text):
                markers.add(marker_name)

        runtime_requirements: set[str] = set()
        for label, pattern in RUNTIME_PATTERNS:
            if pattern.search(text):
                runtime_requirements.add(label)

        flakiness_tags: set[str] = set()
        for match in FLAKY_PATTERN.findall(text):
            flakiness_tags.add(match.lower())
        if "skipif" in text:
            flakiness_tags.add("skipif")

        for marker in markers:
            marker_counts[marker] = marker_counts.get(marker, 0) + 1
        for requirement in runtime_requirements:
            runtime_counts[requirement] = runtime_counts.get(requirement, 0) + 1
        group_counts[group] = group_counts.get(group, 0) + 1

        entries.append(
            {
                "path": rel_text,
                "group": group,
                "line_count": len(lines),
                "markers": sorted(markers),
                "runtime_requirements": sorted(runtime_requirements),
                "flakiness_tags": sorted(flakiness_tags),
                "line": 1,
            }
        )

    entries.sort(key=lambda row: str(row["path"]))
    sorted_groups = sorted(group_counts.items(), key=lambda row: row[0])
    sorted_markers = sorted(marker_counts.items(), key=lambda row: row[0])
    sorted_runtime = sorted(runtime_counts.items(), key=lambda row: row[0])
    flaky_file_count = sum(1 for row in entries if row["flakiness_tags"])

    return {
        "counts": {
            "files": len(entries),
            "flaky_or_skipif_files": flaky_file_count,
        },
        "groups": [{"group": group, "count": count} for group, count in sorted_groups],
        "marker_frequency": [
            {"marker": marker, "count": count} for marker, count in sorted_markers
        ],
        "runtime_requirements_frequency": [
            {"requirement": requirement, "count": count} for requirement, count in sorted_runtime
        ],
        "files": entries,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def extract_metadata(repo: str, repo_path: Path, out_root: Path) -> ExtractedMetadata:
    path = repo_path.expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Repository path does not exist: {path}")

    commit_sha = _git(["rev-parse", "HEAD"], cwd=path)
    repo_url = _git(["config", "--get", "remote.origin.url"], cwd=path)
    output_dir = out_root.expanduser().resolve() / repo / commit_sha
    output_dir.mkdir(parents=True, exist_ok=True)

    python_symbols = _extract_python_symbols(path)
    c_symbols = _extract_c_symbols(path)
    build_flags = _extract_build_flags(path)
    tests = _extract_test_taxonomy(path)

    summary = {
        "repo": repo,
        "repo_url": repo_url,
        "commit_sha": commit_sha,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "repo_path": str(path),
        "output_dir": str(output_dir),
        "provenance_banner": f"Built from {repo} @ {commit_sha}",
        "counts": {
            "python_files_scanned": python_symbols["files_scanned"],
            "c_cpp_files_scanned": c_symbols["files_scanned"],
            "flags_discovered": len(build_flags["flags"]),
            "test_files_classified": tests["counts"]["files"],
        },
        "limitations": [
            "Python and C/C++ inventories are static analysis outputs.",
            "C/C++ symbol extraction uses regex fallback rather than full Clang AST parsing.",
            "Test runtime requirements are inferred from textual patterns.",
        ],
    }

    symbols_payload = {
        "repo": repo,
        "commit_sha": commit_sha,
        "generated_at_utc": summary["generated_at_utc"],
        "python": python_symbols,
        "c_cpp": c_symbols,
    }
    build_flags_payload = {
        "repo": repo,
        "commit_sha": commit_sha,
        "generated_at_utc": summary["generated_at_utc"],
        **build_flags,
    }
    tests_payload = {
        "repo": repo,
        "commit_sha": commit_sha,
        "generated_at_utc": summary["generated_at_utc"],
        **tests,
    }

    summary_path = output_dir / "summary.json"
    symbols_path = output_dir / "symbols.json"
    build_flags_path = output_dir / "build_flags.json"
    tests_path = output_dir / "tests.json"

    _write_json(summary_path, summary)
    _write_json(symbols_path, symbols_payload)
    _write_json(build_flags_path, build_flags_payload)
    _write_json(tests_path, tests_payload)

    generated_files = [
        str(summary_path),
        str(symbols_path),
        str(build_flags_path),
        str(tests_path),
    ]
    return ExtractedMetadata(
        repo=repo,
        repo_path=str(path),
        repo_url=repo_url,
        commit_sha=commit_sha,
        output_dir=str(output_dir),
        generated_files=generated_files,
        notes=summary["limitations"],
    )


def _repo_web_url(repo_url: str) -> str:
    if repo_url.startswith("git@github.com:"):
        converted = repo_url.removeprefix("git@github.com:")
        repo_url = f"https://github.com/{converted}"
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]
    return repo_url


def _blob_link(repo_url: str, commit_sha: str, path: str, line: int | None = None) -> str:
    web_url = _repo_web_url(repo_url)
    suffix = f"#L{line}" if line is not None else ""
    return f"{web_url}/blob/{commit_sha}/{path}{suffix}"


def _provenance_banner(summary: dict[str, object]) -> str:
    repo = str(summary["repo"])
    sha = str(summary["commit_sha"])
    generated = str(summary["generated_at_utc"])
    repo_url = str(summary["repo_url"])
    return (
        ":::info Provenance\n"
        f"Built from `{repo}` @ `{sha}` on `{generated}`.\n\n"
        f"Source: [{_repo_web_url(repo_url)}]({_repo_web_url(repo_url)})\n"
        ":::\n"
    )


def _table(headers: list[str], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    if not rows:
        rows = [["(none)", *([""] * (len(headers) - 1))]]
    body = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join([header, separator, body])


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _select_latest_sha(repo_root: Path) -> str:
    dirs = sorted([path for path in repo_root.iterdir() if path.is_dir()])
    if not dirs:
        raise ValueError(f"No introspection snapshots found under {repo_root}")
    latest = max(dirs, key=lambda path: path.stat().st_mtime)
    return latest.name


def _write_doc(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"---\ntitle: {title}\n---\n\n{body.strip()}\n"
    path.write_text(text, encoding="utf-8")


def _render_overview_doc(
    summary: dict[str, object],
    symbols: dict[str, object],
    build_flags: dict[str, object],
    tests: dict[str, object],
) -> str:
    counts = summary["counts"]
    rows = [
        ["Python files scanned", str(counts["python_files_scanned"])],
        ["C/C++ files scanned", str(counts["c_cpp_files_scanned"])],
        ["Flags discovered", str(counts["flags_discovered"])],
        ["Test files classified", str(counts["test_files_classified"])],
        ["Python modules", str(len(symbols["python"]["modules"]))],
        ["Python classes", str(len(symbols["python"]["classes"]))],
        ["Python functions", str(len(symbols["python"]["functions"]))],
        ["Exported C symbols", str(len(symbols["c_cpp"]["exported_symbols"]))],
        ["Test groups", str(len(tests["groups"]))],
    ]
    limitations = "\n".join(f"- `{item}`" for item in summary["limitations"])
    return (
        "# Introspection Overview\n\n"
        f"{_provenance_banner(summary)}\n"
        "## Inventory Counts\n\n"
        f"{_table(['Metric', 'Value'], rows)}\n\n"
        "## Classification\n\n"
        "- `confirmed`: Values directly extracted from source files and tests.\n"
        "- `inferred`: Runtime requirements inferred from textual heuristics.\n"
        "- `unknown`: Build/runtime behavior requiring execution-time validation.\n\n"
        "## Limitations\n\n"
        f"{limitations}\n\n"
        "## Related Generated Pages\n\n"
        "- `generated/symbol-inventory`\n"
        "- `generated/build-options`\n"
        "- `generated/test-taxonomy`\n"
    )


def _render_symbol_doc(summary: dict[str, object], symbols: dict[str, object]) -> str:
    repo_url = str(summary["repo_url"])
    sha = str(summary["commit_sha"])
    rows: list[list[str]] = []

    for item in symbols["python"]["classes"][:MAX_ROWS_PER_DOC_TABLE]:
        path = str(item["path"])
        line = int(item["line"])
        link = _blob_link(repo_url, sha, path, line)
        rows.append(
            [
                "Python class",
                f"`{item['name']}`",
                f"`{item['module']}`",
                f"[{path}:{line}]({link})",
            ]
        )
    for item in symbols["python"]["functions"][:MAX_ROWS_PER_DOC_TABLE]:
        path = str(item["path"])
        line = int(item["line"])
        link = _blob_link(repo_url, sha, path, line)
        rows.append(
            [
                "Python function",
                f"`{item['name']}`",
                f"`{item['module']}`",
                f"[{path}:{line}]({link})",
            ]
        )
    for item in symbols["c_cpp"]["exported_symbols"][:MAX_ROWS_PER_DOC_TABLE]:
        path = str(item["path"])
        line = int(item["line"])
        link = _blob_link(repo_url, sha, path, line)
        rows.append(
            [
                f"C/C++ ({item['kind']})",
                f"`{item['name']}`",
                "`native`",
                f"[{path}:{line}]({link})",
            ]
        )

    return (
        "# Symbol Inventory\n\n"
        f"{_provenance_banner(summary)}\n"
        "## Source-Linked Inventory\n\n"
        f"{_table(['Kind', 'Symbol', 'Module/Area', 'Source'], rows)}\n\n"
        "## Notes\n\n"
        "- `confirmed`: Symbol names and line locations are extracted from files.\n"
        "- `inferred`: Symbol role beyond the recorded kind is not inferred.\n"
        "- `unknown`: Runtime reachability of symbols is not measured in this phase.\n"
    )


def _render_build_options_doc(summary: dict[str, object], build_flags: dict[str, object]) -> str:
    repo_url = str(summary["repo_url"])
    sha = str(summary["commit_sha"])
    rows: list[list[str]] = []
    for item in build_flags["flags"][:MAX_ROWS_PER_DOC_TABLE]:
        path = str(item["path"])
        line = int(item["line"])
        link = _blob_link(repo_url, sha, path, line)
        rows.append(
            [
                f"`{item['name']}`",
                str(item["kind"]),
                f"[{path}:{line}]({link})",
                f"`{item['snippet']}`",
            ]
        )

    return (
        "# Build Flags And Options\n\n"
        f"{_provenance_banner(summary)}\n"
        "## Discoverable Build-Time Controls\n\n"
        f"{_table(['Flag/Option', 'Kind', 'Source', 'Snippet'], rows)}\n\n"
        "## Notes\n\n"
        "- `confirmed`: Option/flag tokens and first-seen source locations.\n"
        "- `inferred`: Semantic impact of each flag may require build-time execution.\n"
        "- `unknown`: Platform-specific compile effects are not validated in Phase 2.\n"
    )


def _render_test_taxonomy_doc(summary: dict[str, object], tests: dict[str, object]) -> str:
    repo_url = str(summary["repo_url"])
    sha = str(summary["commit_sha"])

    group_rows = [[str(item["group"]), str(item["count"])] for item in tests["groups"]]
    marker_rows = [[str(item["marker"]), str(item["count"])] for item in tests["marker_frequency"]][
        :MAX_ROWS_PER_DOC_TABLE
    ]
    runtime_rows = [
        [str(item["requirement"]), str(item["count"])]
        for item in tests["runtime_requirements_frequency"]
    ][:MAX_ROWS_PER_DOC_TABLE]

    file_rows: list[list[str]] = []
    for item in tests["files"][:MAX_ROWS_PER_DOC_TABLE]:
        path = str(item["path"])
        line = int(item["line"])
        link = _blob_link(repo_url, sha, path, line)
        file_rows.append(
            [
                f"[{path}]({link})",
                str(item["group"]),
                ", ".join(str(marker) for marker in item["markers"]) or "-",
                ", ".join(str(req) for req in item["runtime_requirements"]) or "-",
                ", ".join(str(tag) for tag in item["flakiness_tags"]) or "-",
            ]
        )

    test_file_table = _table(
        ["File", "Group", "Markers", "Runtime Requirements", "Flakiness Tags"],
        file_rows,
    )
    return (
        "# Test Taxonomy\n\n"
        f"{_provenance_banner(summary)}\n"
        "## Groups\n\n"
        f"{_table(['Group', 'File Count'], group_rows)}\n\n"
        "## Marker Frequency\n\n"
        f"{_table(['Marker', 'File Count'], marker_rows)}\n\n"
        "## Runtime Requirement Frequency\n\n"
        f"{_table(['Requirement', 'File Count'], runtime_rows)}\n\n"
        "## Source-Linked Test Files\n\n"
        f"{test_file_table}\n\n"
        "## Notes\n\n"
        "- `confirmed`: Test file paths and marker tokens.\n"
        "- `inferred`: Runtime requirements are heuristic matches in source text.\n"
        "- `unknown`: Actual flaky behavior requires repeated test execution.\n"
    )


def render_docs_from_introspection(
    repo: str,
    data_root: Path,
    docs_root: Path,
    commit_sha: str | None = None,
) -> RenderedDocs:
    repo_root = data_root.expanduser().resolve() / repo
    if not repo_root.exists():
        raise ValueError(f"Introspection root not found: {repo_root}")
    selected_sha = commit_sha or _select_latest_sha(repo_root)
    source_dir = repo_root / selected_sha
    if not source_dir.exists():
        raise ValueError(f"Introspection snapshot not found: {source_dir}")

    summary = _load_json(source_dir / "summary.json")
    symbols = _load_json(source_dir / "symbols.json")
    build_flags = _load_json(source_dir / "build_flags.json")
    tests = _load_json(source_dir / "tests.json")

    docs_dir = docs_root.expanduser().resolve()
    overview_path = docs_dir / "introspection-overview.mdx"
    symbols_path = docs_dir / "symbol-inventory.mdx"
    build_options_path = docs_dir / "build-options.mdx"
    tests_path = docs_dir / "test-taxonomy.mdx"

    _write_doc(
        overview_path,
        "Introspection Overview",
        _render_overview_doc(summary, symbols, build_flags, tests),
    )
    _write_doc(symbols_path, "Symbol Inventory", _render_symbol_doc(summary, symbols))
    _write_doc(
        build_options_path,
        "Build Flags And Options",
        _render_build_options_doc(summary, build_flags),
    )
    _write_doc(tests_path, "Test Taxonomy", _render_test_taxonomy_doc(summary, tests))

    return RenderedDocs(
        repo=repo,
        commit_sha=str(summary["commit_sha"]),
        source_dir=str(source_dir),
        docs_dir=str(docs_dir),
        generated_pages=[
            str(overview_path),
            str(symbols_path),
            str(build_options_path),
            str(tests_path),
        ],
    )


def to_json(payload: ExtractedMetadata | RenderedDocs) -> str:
    return json.dumps(asdict(payload), indent=2, sort_keys=True)
