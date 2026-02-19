# Contributing

Thanks for helping build CinderX Community.

## Local Setup

1. Install Node.js 22+, Python 3.14+, and `uv`.
2. Enable Corepack: `corepack enable`
3. Install docs dependencies: `pnpm -C packages/site install`
4. Create a virtualenv: `uv venv --python 3.14 .venv`
5. Install Python tooling: `uv pip install --python .venv/bin/python -e ./python[dev]`
6. Optional CinderX metadata extra: `uv add --project ./python --optional cinderx cinderx --no-sync`

## Common Commands

- `make dev`: run local docs website
- `make fmt`: format JS/TS/MD(X) + Python
- `make lint`: lint JS/TS/MD(X) + Python
- `make test`: run Python tests
- `make build`: create static docs site

## Pull Request Expectations

- Keep changes focused and well-described.
- Add or update tests where appropriate.
- Run `make lint test build` before opening a PR.
- For docs claims about CinderX behavior, include source links.
- Follow `GOVERNANCE.md` for role/decision/escalation policy.

## Docs Writing Rules

- Treat upstream README/blog/docs as source of truth.
- Do not present unverified assumptions as facts.
- Mark unverified technical details with a TODO callout.

## Benchmarks Policy (Bootstrap Phase)

- Do not commit ad-hoc benchmark claims without reproducible methodology.
- Keep benchmark execution out of CI unless explicitly lightweight and deterministic.
