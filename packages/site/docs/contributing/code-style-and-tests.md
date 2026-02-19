---
title: Code style, lint, test
---

# Code style, lint, test

From repository root:

```bash
make fmt
make lint
make test
make build
```

Tooling includes:

- Site: TypeScript + Prettier
- Site docs: `cspell` (wired into `pnpm -C packages/site lint`)
- Python: Ruff + Pytest
