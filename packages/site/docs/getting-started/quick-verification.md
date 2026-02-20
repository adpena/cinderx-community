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

:::caution Validation scope
Feature-level verification should use the compatibility guides and benchmark verification commands,
not this import-only smoke check.
:::
