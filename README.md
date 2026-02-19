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

When a claim is not fully validated by those sources, we mark it explicitly as TODO/hypothesis.

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
uv pip install --python .venv/bin/python -e ./python[dev]
uv add --project ./python --optional cinderx cinderx --no-sync
make dev      # run docs locally
make lint     # lint JS/TS + Python
make test     # run Python tests
make build    # produce static docs build
```

Docs live in `packages/site/docs` and the homepage lives in `packages/site/src/pages/index.tsx`.

## Upstream Tracking (Latest CinderX)

The Python CLI tracks upstream provenance and snapshots:
- Sync/clone upstream repo to local cache
- Pin provenance in `python/cinderx_community/pins.toml`
- Record commit snapshots over time in `.cache/upstream/history/`

Example:

```bash
uv python install 3.14
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -e ./python[dev]
cd python
../.venv/bin/cxc upstream clone --repo cinderx --dest .cache/upstream/cinderx
../.venv/bin/cxc upstream pin --repo cinderx --dest .cache/upstream/cinderx --tag phase-2
../.venv/bin/cxc upstream status
../.venv/bin/cxc upstream history --repo cinderx
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
  --nuitka "$(which nuitka)" \
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

Use additional runtime flags (for example `--pypy` and `--nuitka`) as optional comparators against
the CinderX baseline.
`--cpython-cinderx` is validated at runtime; if the interpreter does not expose CinderX
(`import cinderx`), the run fails to prevent mislabeled comparison baselines.
Install benchmark toolchain extras with:

```bash
uv pip install --python .venv/bin/python pyperformance nuitka
```

To install the optional package metadata path for CinderX in this project:

```bash
uv add --project ./python --optional cinderx cinderx --no-sync
uv pip install --python .venv/bin/python -e ./python[dev,cinderx]
```

Note: CinderX installation is platform/toolchain dependent; on macOS arm64, local source builds may
currently fail upstream without additional native build prerequisites.

Before trying CinderX-baselined runs, check environment readiness:

```bash
make cinderx-env-check
```

Attempt local CinderX install:

```bash
make cinderx-install-local
```

Convenience targets for local benchmark runs:

```bash
make bench-smoke-local
make bench-pyperformance-local
CINDERX_PYTHON=/path/to/cinderx-python make bench-smoke-local-cinderx
CINDERX_PYTHON=/path/to/cinderx-python make bench-pyperformance-local-cinderx
```

Before publishing benchmark artifacts, run the guard command:

```bash
cd python
../.venv/bin/cxc bench verify-publish \
  --summary-root ../data/summary \
  --static-summary-root ../packages/site/static/data/summary
```

Or run the wired target directly:

```bash
make bench-publish-check
```

You can run publishable benchmarks locally (no self-hosted CI required) as long as the run is
CinderX-baselined and metadata-rich. For smoke-only local publishes, scope the guard:

```bash
cd python
../.venv/bin/cxc bench verify-publish \
  --summary-root ../data/summary \
  --static-summary-root ../packages/site/static/data/summary \
  --require-suite smoke
```

To include configuration details in reports, export metadata snapshots:

```bash
jq '.metadata' data/summary/latest-smoke.json > data/summary/latest-smoke.metadata.json
jq '.metadata' data/summary/latest-pyperformance.json > data/summary/latest-pyperformance.metadata.json
```

Or use the wired dossier command/targets:

```bash
cd python
../.venv/bin/cxc bench export-dossier --summary-root ../data/summary --output-root ../data/summary/reports
make bench-dossier
```

## Development Notes

- This repo intentionally does **not** vendor the upstream CinderX source tree.
- Runnable benchmark suites are `smoke` and `pyperformance`; additional suites remain phased/TODO.
- Continuous benchmark automation is defined in `.github/workflows/benchmarks.yml` and now attempts
  hosted-runner CinderX installation automatically (with CI-shape fallback when unavailable).

## License

MIT (see `LICENSE`).
