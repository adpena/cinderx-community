---
title: Quick verification
---

# Quick verification

Use a minimal import check as a first smoke test:

```bash
python - <<'PY'
import cinderx
print('loaded:', cinderx.__file__)
PY
```

This verifies package import only. It does not confirm specific JIT/static features.

To inspect JIT/static-related runtime capabilities:

```bash
.venv/bin/python scripts/tutorials/runtime_identity_report.py
```

To test project-style bootstrap actions:

```bash
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode all
.venv/bin/python scripts/tutorials/cinderx_project_bootstrap.py --jit-mode auto
```

For end-to-end app integration, use:

- [CPython project quickstart](../tutorials/cpython-project-quickstart)

:::caution Validation scope
Feature-level verification should use the compatibility guides and benchmark verification commands,
not this import-only smoke check.
:::
