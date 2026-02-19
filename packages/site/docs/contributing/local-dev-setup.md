---
title: Local dev setup
---

# Local dev setup

## Requirements

- Node.js 22+
- Python 3.14+
- `uv`
- Corepack enabled (`corepack enable`)

## Commands

```bash
pnpm -C packages/site install
uv python install 3.14
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -e ./python[dev]
make dev
```

Docs source location: `packages/site/docs`.
