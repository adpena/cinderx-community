# Repository Guidelines

## Project Structure & Module Organization
This monorepo has two active workstreams:
- `packages/site/`: Docusaurus docs site. Content lives in `packages/site/docs/`, blog posts in `packages/site/blog/`, React UI in `packages/site/src/`, and assets in `packages/site/static/`.
- `python/`: `cinderx_community` tooling package. CLI entrypoint is `python/cinderx_community/cli.py`; upstream tracking is in `python/cinderx_community/upstream.py`; benchmark/research stubs are in `python/cinderx_community/bench/` and `python/cinderx_community/research/`; tests are in `python/cinderx_community/tests/`.

Repo-level governance and automation live in `.github/`, `README.md`, `CONTRIBUTING.md`, and `SECURITY.md`.

## Build, Test, and Development Commands
- `make dev`: install site deps and run docs locally on port `3000`.
- `make fmt`: format JS/TS/MD(X)/CSS/JSON/YAML and Python.
- `make lint`: TypeScript + Prettier checks for site, Ruff checks for Python.
- `make test`: run `pytest` for Python tooling.
- `make build`: produce static site output in `packages/site/build`.
- `make clean`: remove local build/cache/venv artifacts.
- `make python-dev-cinderx`: install Python tooling with optional `cinderx` extra metadata.
- `make cinderx-env-check`: print local CinderX runtime/toolchain readiness diagnostics.
- `make cinderx-install-local`: attempt local CinderX install into `.venv` (`--no-build-isolation`).
- `make cinderx-install-local-macos`: macOS arm64 fallback install path for upstream `fmt` header failures during local `cinderx` source build.
- `bash scripts/ci/install_and_probe_cinderx.sh --python .venv/bin/python --mode permissive`: staged CinderX install + import probe + diagnostics capture (CI parity path).
- `bash scripts/ci/install_and_probe_cinderx.sh --python .venv/bin/python --mode strict --require-static-loader`: strict CI gate that also validates strict/static loader viability and resolves `strict/stubs` fallback path when wheel packaging omits it.
- `make bench-toolchain`: install local benchmark dependencies (`pyperformance`).
- `make bench-smoke-local`: run local smoke suite in CI-shape mode.
- `make bench-pyperformance-local`: run local full pyperformance suite.
- `make bench-smoke-local-cinderx`: run local smoke suite with required CinderX baseline (`CINDERX_PYTHON=...`).
- `make bench-pyperformance-local-cinderx`: run local full pyperformance suite with required CinderX baseline (`CINDERX_PYTHON=...`).
- `make bench-pyperformance-local-ci`: run local pyperformance CI-shape debug subset.
- `make bench-pyperformance-local-cinderx-ci`: run local pyperformance CI-shape debug subset with required CinderX baseline.
- `make bench-publish-check`: enforce CinderX-baselined publish guard for latest benchmark summaries.
- `make bench-dossier`: export benchmark metadata dossier JSON under `data/summary/reports/`.
- `CINDERX_PYTHON=/path/to/cinderx-python bash scripts/bench/run_quickstart_matrix.sh`: run quickstart matrix with default pyperformance CinderX bootstrap (`cpython` plain control + auto-bootstrap on `cpython-cinderx` lane only; default profile is `cinderx-jit-all`).
- `CINDERX_PYTHON=/path/to/cinderx-python PYPERF_BOOTSTRAP_PROFILES=cinderx-jit-all,cinderx-jit-auto,cinderx-jit-compile-after-n-calls bash scripts/bench/run_quickstart_matrix.sh`: run a profile matrix for JIT behavior checks.
- `.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode all`: apply project-style CinderX bootstrap actions (eager JIT/static-loader path) for local verification.
- Python environments and package installs are managed with `uv` (see setup below).

First-time setup:
```bash
uv python install 3.14
uv venv --python 3.14 .venv
corepack enable
pnpm -C packages/site install
uv pip install --python .venv/bin/python -e ./python[dev]
uv add --project ./python --optional cinderx cinderx --no-sync
uv pip install --python .venv/bin/python pyperformance
```

## Python Package Management (uv-only)
- Use `uv` for all Python runtime and dependency operations in this repo.
- Add/update dependencies in `python/` with `uv add --project ./python ...` (use `--optional <extra>` for optional groups).
- Install into the workspace venv with `uv pip install --python .venv/bin/python ...`.
- Use `uv python install` and `uv venv` for interpreter and virtualenv lifecycle.
- Do not use `pip`, `python -m pip`, `poetry`, or `pipenv` for project dependency management here.
- If adding optional `cinderx` metadata without syncing native build, use:
  - `uv add --project ./python --optional cinderx cinderx --no-sync`
- macOS arm64 local install caveat:
  - If `uv pip install cinderx` fails with bundled `fmt` compile errors (`malloc` / `free` undeclared), use:
    - `make cinderx-install-local-macos`
  - Equivalent direct command:
    - `CXXFLAGS='-include cstdlib' CMAKE_ARGS='-DCMAKE_VERBOSE_MAKEFILE:BOOL=ON' uv pip install --python .venv/bin/python -v --no-cache-dir --reinstall cinderx`
  - `PYTHONPATH=src` does not affect this native build failure mode.
  - Runtime caveat:
    - If `import cinderx` succeeds but `get_import_error()` reports missing symbol `__ZNSt3__113__hash_memoryEPKvm`, treat the runtime as non-CinderX-capable for JIT/static benchmarking and gather diagnostics with `bash scripts/ci/install_and_probe_cinderx.sh --python .venv/bin/python --mode permissive`.
  - Linux/static loader caveat:
    - Some CinderX wheels can omit `cinderx/compiler/strict/stubs`, which causes `Strict module stubs path does not exist` when strict/static loader is installed.
    - Use `scripts/ci/install_and_probe_cinderx.sh` to resolve a fallback stubs path and export `strict_stubs_path`; benchmark steps should pass it via `PYTHONSTRICTMODULESTUBSPATH`.
    - In benchmark bootstrap profiles that request static loader (`cinderx-all-features`, `cinderx-static-loader*`), missing stubs are now fail-fast (no silent fallback).

## Coding Style & Naming Conventions
- Follow `.editorconfig`: UTF-8, LF, trailing whitespace trimmed, final newline.
- Indentation: 2 spaces by default, 4 for `*.py`, tabs in `Makefile`.
- Python: Ruff is the source of truth (`line-length = 100`, `target-version = py314`).
- Web/docs: Prettier formatting; keep docs filenames kebab-case, React components PascalCase, Python functions/modules snake_case.

## Testing Guidelines
- Framework: `pytest`.
- Test files: `test_*.py` under `python/cinderx_community/tests/`.
- Keep tests deterministic and quick; do not add heavyweight benchmark execution to CI in bootstrap phases.

## Commit & Pull Request Guidelines
Local workspace snapshot may not include `.git` metadata; use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`) moving forward.
- Keep PRs focused and reviewable.
- Before opening PRs, run `make lint test build`.
- Update docs for behavior changes and cite sources for CinderX claims (or label claims as hypothesis/inference until validated).
- Do not commit secrets or generated site build artifacts.

## Security & Configuration Tips
- Follow `SECURITY.md` for vulnerability reporting.
- Do not vendor the upstream CinderX repo; use `cxc upstream ...` commands and local cache paths under `.cache/upstream/`.
