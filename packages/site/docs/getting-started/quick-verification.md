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

:::caution TODO
Feature-level verification is tracked as future work and will be backed by source reading and differential tests.
:::
