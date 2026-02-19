---
title: Known packages
---

# Known packages

This page tracks compatibility observations for commonly requested packages.

Legend:

- `green`: reproduced working in this repository with evidence
- `unknown`: not validated yet
- `known-issue`: reproducible issue exists, linked below

## Registry

| Package         | Status               | Runtime                       | Evidence                                             | Notes                                                                                                                                            |
| --------------- | -------------------- | ----------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `cinderx`       | known-issue          | macOS arm64 local build       | Local install attempts on 2026-02-19                 | Default build path fails in bundled `fmt`; workaround install using `CXXFLAGS='-include cstdlib'` + `CMAKE_ARGS` is validated in this workspace. |
| `cinderx`       | green                | GitHub `ubuntu-latest` runner | Actions run `22202746458`                            | Install and direct import probe succeeded via staged installer script (`default-wheel`).                                                         |
| `pyperformance` | green                | CPython 3.14                  | Local Phase 3 harness runs                           | Runnable adapter and normalized ingestion are active.                                                                                            |
| `nuitka`        | green (adapter path) | CPython toolchain             | Local smoke adapter execution path                   | Compare against CinderX baseline when runtime is available.                                                                                      |
| `pypy`          | unknown              | N/A                           | No validated CinderX-baselined run in this workspace | Optional comparator path exists.                                                                                                                 |

## Contribution format

When adding entries, include:

- exact runtime and version,
- command used,
- artifact link or issue link,
- classification (`green`, `unknown`, `known-issue`).
