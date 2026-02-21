# CinderX Community

Community-run monorepo for documentation, compatibility guidance, and benchmarking scaffolding around [Meta's CinderX](https://github.com/facebookincubator/cinderx).

Project owner: Alejandro Pena (GitHub: [@adpena](https://github.com/adpena)).

This repository is intentionally scoped for open collaboration:

- A polished docs website (Docusaurus, static, GitHub Pages ready)
- Python CLI for upstream pinning, introspection extraction, and benchmark orchestration
- Contributor-first automation (lint, tests, CI, issue templates)

## Scope and Source Policy

Documentation in this repo is grounded in these sources:

- CinderX README: https://github.com/facebookincubator/cinderx
- Meta engineering post on CPython 3.12 hooks: https://engineering.fb.com/2023/10/05/developer-tools/python-312-meta-new-features/
- pyperformance docs: https://pyperformance.readthedocs.io/

When a claim is not fully validated by those sources, we mark it explicitly as an open
question/hypothesis.

## Monorepo Layout

```text
.
├── packages/site/        # Docusaurus docs + blog
└── python/               # cinderx_community CLI tooling
```

## Quickstart

Requirements:

- Node.js 22+
- Python 3.14+
- `uv` (Python/runtime/package manager)
- `corepack` enabled (ships with modern Node)

```bash
uv python install 3.14
uv venv --python 3.14 .venv
corepack enable
pnpm -C packages/site install
make python-dev  # install Python tooling into .venv
uv add --project ./python --optional cinderx cinderx --no-sync
make dev      # run docs locally
make fmt      # format JS/TS/MD(X) + Python
make lint     # lint JS/TS + Python
make test     # run Python tests
make build    # produce static docs build
```

Docs live in `packages/site/docs` and the homepage lives in `packages/site/src/pages/index.tsx`.

Python/runtime dependency management in this repo is `uv`-only (`uv python`, `uv venv`, `uv add`,
`uv pip install`).

## Common Make Targets

- `make python-dev`: provision `.venv` and install `python[dev]`
- `make python-dev-cinderx`: install `python[dev,cinderx]` into `.venv`
- `make dev`: run the docs site locally on port `3000`
- `make fmt`: format web/docs files and Python
- `make lint`: TypeScript/Prettier/cspell + Ruff checks
- `make test`: run `pytest` under `python/cinderx_community/tests`
- `make build`: create the static docs site (`packages/site/build`)
- `make clean`: remove local build/cache/venv artifacts

## Upstream Tracking (Latest CinderX)

The Python CLI tracks upstream provenance and snapshots:

- Sync/clone upstream repo to local cache
- Pin provenance in `python/cinderx_community/pins.toml`
- Record commit snapshots over time in `.cache/upstream/history/`

Example:

```bash
uv python install 3.14
uv venv --python 3.14 .venv
make python-dev
.venv/bin/cxc upstream clone --repo cinderx --dest .cache/upstream/cinderx
.venv/bin/cxc upstream pin --repo cinderx --dest .cache/upstream/cinderx --tag phase-2
.venv/bin/cxc upstream status --dest .cache/upstream/cinderx
.venv/bin/cxc upstream history --repo cinderx
```

## Phase 2 Introspection Pipeline

Generate deterministic source inventories:

```bash
cd python
../.venv/bin/cxc research extract \
  --repo cinderx \
  --repo-path ../.cache/upstream/cinderx \
  --out ../data/introspection
```

Generate MDX docs from those inventories:

```bash
cd python
../.venv/bin/cxc research render-docs \
  --repo cinderx \
  --data-root ../data/introspection \
  --docs-out ../packages/site/docs/generated
```

Or run extraction + generated docs in one command:

```bash
cd python
../.venv/bin/cxc research extract \
  --repo cinderx \
  --repo-path ../.cache/upstream/cinderx \
  --out ../data/introspection \
  --render-docs \
  --docs-out ../packages/site/docs/generated
```

## Phase 3 Benchmark Smoke Harness

Run a reproducibility-focused smoke suite and publish summary JSON:

```bash
cd python
../.venv/bin/cxc bench run \
  --suite smoke \
  --python ../.venv/bin/python \
  --cpython-cinderx /path/to/cinderx-python \
  --pypy "$(which pypy3)" \
  --require-cinderx-baseline \
  --out ../data/runs \
  --summary-out ../data/summary \
  --static-summary-out ../packages/site/static/data/summary \
  --ci-mode
```

This writes:

- raw per-runtime artifacts under `data/runs/<date>/<machine>/<runtime>/...`
- normalized summary JSON under `data/summary/`
- static-site summary mirror under `packages/site/static/data/summary/`

Use additional runtime flags (for example `--pypy`) as optional comparators against the CinderX
baseline in `smoke`.
`pyperformance` comparisons are interpreter-runtime only (`cpython`, `cpython-cinderx`, `pypy`).
`--cpython-cinderx` is validated at runtime; if the interpreter does not expose CinderX
(`import cinderx`), the run fails to prevent mislabeled comparison baselines.
Install benchmark toolchain extras with:

```bash
make bench-toolchain
```

To install the optional package metadata path for CinderX in this project:

```bash
uv add --project ./python --optional cinderx cinderx --no-sync
uv pip install --python .venv/bin/python -e ./python[dev,cinderx]
```

Note: CinderX installation is platform/toolchain dependent; on macOS arm64, default local source
builds may fail in bundled `fmt` (`malloc` / `free` undeclared).
Even when install succeeds, `get_import_error()` can still report `_cinderx.so` missing symbols on
some macOS setups; verify with `scripts/tutorials/runtime_identity_report.py` before benchmark
claims.

Before trying CinderX-baselined runs, check environment readiness:

```bash
make cinderx-env-check
```

Attempt local CinderX install:

```bash
make cinderx-install-local
```

If you hit the macOS arm64 `fmt` compile failure, use the workaround path:

```bash
make cinderx-install-local-macos
```

For CI-parity staged install + import probe diagnostics:

```bash
bash scripts/ci/install_and_probe_cinderx.sh --python .venv/bin/python --mode permissive
```

For strict/static-loader readiness (Linux publish gate), run:

```bash
bash scripts/ci/install_and_probe_cinderx.sh --python .venv/bin/python --mode strict --require-static-loader
```

If strict loader reports missing stubs, use the script's `strict_stubs_path` output as:

```bash
export PYTHONSTRICTMODULESTUBSPATH=/path/to/strict/stubs
```

Equivalent direct command:

```bash
CXXFLAGS='-include cstdlib' CMAKE_ARGS='-DCMAKE_VERBOSE_MAKEFILE:BOOL=ON' uv pip install --python .venv/bin/python -v --no-cache-dir --reinstall cinderx
```

Convenience targets for local benchmark runs:

```bash
make bench-smoke-local
make bench-pyperformance-local
CINDERX_PYTHON=/path/to/cinderx-python make bench-smoke-local-cinderx
CINDERX_PYTHON=/path/to/cinderx-python make bench-pyperformance-local-cinderx
```

`bench-pyperformance-local*` targets run full pyperformance by default. For fast debug-only subsets:

```bash
make bench-pyperformance-local-ci
CINDERX_PYTHON=/path/to/cinderx-python make bench-pyperformance-local-cinderx-ci
```

Script-first helpers are also available:

```bash
bash scripts/bench/install_comparison_toolchain.sh
bash scripts/bench/run_quickstart_matrix.sh
bash scripts/bench/sync_site_data_from_bench_results.sh
.venv/bin/python scripts/tutorials/runtime_identity_report.py
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode all
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode auto
.venv/bin/python scripts/tutorials/json_hot_path.py --iterations 4000 --payload-size 512
```

Equivalent wrapper targets:

```bash
make bench-toolchain
make bench-toolchain-compare
make bench-run-quickstart-matrix
make bench-sync-site-data
```

Before publishing benchmark artifacts, run the guard command:

```bash
cd python
../.venv/bin/cxc bench verify-publish \
  --summary-root ../data/summary \
  --static-summary-root ../packages/site/static/data/summary \
  --require-suite pyperformance
```

Or run the wired target directly:

```bash
make bench-publish-check
```

Pyperformance CinderX bootstrap policy:

```bash
cd python
../.venv/bin/cxc bench run \
  --suite pyperformance \
  --python ../.venv/bin/python \
  --cpython-cinderx /path/to/cinderx-python \
  --require-cinderx-baseline
```

- With `--cpython-cinderx`, the harness auto-applies profile `cinderx-all-features` to the
  `cpython-cinderx` lane (`JIT all` + static loader when strict stubs are available).
- Plain `cpython` remains the control lane (no bootstrap execution).
- Override the default profile with `--pyperformance-bootstrap-profile <name>`, or use
  `--pyperformance-bootstrap-inline` for custom experiments.

Available profile options:

- `cinderx-init`
- `cinderx-all-features`
- `cinderx-jit-all`
- `cinderx-jit-auto`
- `cinderx-jit-compile-after-n-calls` (plus
  `--pyperformance-bootstrap-jit-compile-after-n-calls <N>`)
- `cinderx-jit-disable`
- `cinderx-static-loader`
- `cinderx-static-loader-patching`

You can run publishable benchmarks locally (no self-hosted CI required) as long as the run is
CinderX-baselined, metadata-rich, and full pyperformance (non-`ci_mode`):

```bash
cd python
../.venv/bin/cxc bench verify-publish \
  --summary-root ../data/summary \
  --static-summary-root ../packages/site/static/data/summary \
  --require-suite pyperformance
```

Optional smoke-only guard (debug validation):

```bash
make bench-publish-check-smoke
```

To include configuration details in reports, export metadata snapshots:

```bash
jq '.metadata' data/summary/latest-pyperformance.json > data/summary/latest-pyperformance.metadata.json
```

Or use the wired dossier command/targets:

```bash
cd python
../.venv/bin/cxc bench export-dossier --summary-root ../data/summary --output-root ../data/summary/reports --require-suite pyperformance
make bench-dossier
make bench-dossier-smoke
```

## Development Notes

- This repo intentionally does **not** vendor the upstream CinderX source tree.
- Runnable benchmark suites are `smoke` and `pyperformance`; additional suites remain roadmap-scoped.
- Continuous benchmark automation is defined in `.github/workflows/benchmarks.yml` and now attempts
  hosted-runner CinderX installation automatically.
- Smoke runs are debug-only diagnostics; canonical published results are full pyperformance.

## License

MIT (see `LICENSE`).
