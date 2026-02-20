# cinderx_community (Python tooling)

CLI toolkit for:
- Upstream CinderX repository sync and provenance pinning
- Deterministic introspection extraction and generated docs
- Benchmark execution (smoke + pyperformance) plus planning for additional suites

## Install

```bash
uv python install 3.14
uv venv --python 3.14 ../.venv
uv pip install --python ../.venv/bin/python -e .[dev]
uv pip install --python ../.venv/bin/python pyperformance
uv add --optional cinderx cinderx --no-sync
uv pip install --python ../.venv/bin/python -e .[dev,cinderx]
```

Note: CinderX install/build depends on upstream wheel availability and native build prerequisites.
On macOS arm64, default source builds may fail in bundled `fmt` (`malloc` / `free` undeclared).
Use:

```bash
CXXFLAGS='-include cstdlib' CMAKE_ARGS='-DCMAKE_VERBOSE_MAKEFILE:BOOL=ON' uv pip install --python ../.venv/bin/python -v --no-cache-dir --reinstall cinderx
```

From repo root, you can validate local readiness before benchmark publication runs:

- `make cinderx-env-check`
- `make cinderx-install-local`
- `make cinderx-install-local-macos`

This package requires Python 3.14+.

## Commands

```bash
../.venv/bin/cxc --help
../.venv/bin/cxc upstream clone --repo cinderx --dest .cache/upstream/cinderx
../.venv/bin/cxc upstream pin --repo cinderx --dest .cache/upstream/cinderx --tag phase-2
../.venv/bin/cxc upstream status
../.venv/bin/cxc upstream history --repo cinderx
../.venv/bin/cxc bench list
../.venv/bin/cxc bench run --suite smoke --python ../.venv/bin/python --cpython-cinderx /path/to/cinderx-python --pypy /path/to/pypy3 --require-cinderx-baseline --out ../data/runs --summary-out ../data/summary --ci-mode
../.venv/bin/cxc bench run --suite pyperformance --python ../.venv/bin/python --cpython-cinderx /path/to/cinderx-python --pypy /path/to/pypy3 --require-cinderx-baseline --out ../data/runs --summary-out ../data/summary --ci-mode
../.venv/bin/cxc bench verify-publish --summary-root ../data/summary --static-summary-root ../packages/site/static/data/summary
../.venv/bin/cxc bench verify-publish --summary-root ../data/summary --static-summary-root ../packages/site/static/data/summary --require-suite smoke
../.venv/bin/cxc bench export-dossier --summary-root ../data/summary --output-root ../data/summary/reports
../.venv/bin/cxc bench export-dossier --summary-root ../data/summary --output-root ../data/summary/reports --require-suite smoke
../.venv/bin/cxc research extract --repo cinderx --repo-path .cache/upstream/cinderx --out ../data/introspection
../.venv/bin/cxc research render-docs --repo cinderx --data-root ../data/introspection --docs-out ../packages/site/docs/generated
```

`cxc upstream pin` writes provenance records to `cinderx_community/pins.toml`.
History snapshots are persisted in `.cache/upstream/history/`.

`cxc bench run --suite smoke` executes a lightweight reproducibility suite and emits:

- raw runtime artifacts in `data/runs/<date>/<machine>/<runtime>/...`
- normalized summary tables in `data/summary/*.json`
- optional static-site mirror (via `--static-summary-out`)

For CinderX-centric comparisons, provide `--cpython-cinderx /path/to/cinderx-python`.
Additional comparators are suite-specific:

- `--suite smoke`: optional `--pypy /path/to/pypy3` (or auto-detected `pypy3`/`pypy`)
- `--suite pyperformance`: interpreter comparators only (`cpython`, `cpython-cinderx`, `pypy`)
If `--cpython-cinderx` does not point to a CinderX-capable runtime (`import cinderx`), the run
fails to avoid publishing mislabeled baselines.
`cxc bench verify-publish` fails unless required latest summaries are truly CinderX-baselined and
policy-enforced.
It also validates rich run metadata (host/toolchain/guardrails) so local runs can still be
publishable if fully documented.
`cxc bench export-dossier` writes metadata dossier JSON files for latest suite summaries so
configuration details can be attached directly to reports.

For direct local execution without CI, wired `make` targets are available from repo root:

- `make bench-smoke-local`
- `make bench-pyperformance-local`
- `CINDERX_PYTHON=/path/to/cinderx-python make bench-smoke-local-cinderx`
- `CINDERX_PYTHON=/path/to/cinderx-python make bench-pyperformance-local-cinderx`
- `make bench-toolchain-compare`
- `make bench-run-quickstart-matrix`
- `make bench-sync-site-data`
