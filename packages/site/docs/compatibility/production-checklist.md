---
title: Production checklist
---

# Production checklist

Use this checklist before claiming production readiness with CinderX.

- [ ] Runtime identity is explicit (`CINDERX_PYTHON` pinned and verified via `import cinderx`).
- [ ] Platform/toolchain matches upstream-supported constraints.
- [ ] Unit and integration suites pass under the CinderX runtime targeted for deployment.
- [ ] CPython 3.14 compatibility checks pass for rollback/fallback readiness.
- [ ] Extension-heavy dependencies were import-tested and integration-tested under CinderX runtime.
- [ ] CinderX vs comparator benchmarks were run with `--require-cinderx-baseline`.
- [ ] `cxc bench verify-publish` passes for summary artifacts intended for publication.
- [ ] Metadata dossier exported and attached to benchmark/report artifacts.
- [ ] Rollback path to stock CPython is tested and documented.
- [ ] Unknowns and open questions are called out explicitly in public claims.

Source baseline: [facebookincubator/cinderx README](https://github.com/facebookincubator/cinderx).
