---
title: Packaging and deployment
---

# Packaging and deployment

This page provides baseline deployment recipes for teams adopting CinderX carefully.

## 1) Pin CinderX in project metadata

In this repository:

```bash
uv add --project ./python --optional cinderx cinderx --no-sync
```

For reproducible app environments, pin exact versions in your lock process and keep benchmark
artifacts linked to the same runtime version.

## 2) Linux x86_64 baseline container recipe

Upstream says Linux x86_64 is the primary supported target.

Source: [facebookincubator/cinderx README](https://github.com/facebookincubator/cinderx)

Example baseline Dockerfile:

```dockerfile
FROM python:3.14-slim

RUN python -m pip install --upgrade pip setuptools wheel
RUN python -m pip install cinderx

WORKDIR /app
COPY . /app
RUN python -m pip install -e .[prod]

CMD ["python", "-m", "your_service"]
```

## 3) Build-from-source notes

If binary wheels are not available for your exact platform/toolchain:

- ensure compiler/toolchain floors meet upstream requirements,
- build in a controlled CI/container environment,
- validate with full tests and representative workload smoke benchmarks.

## 4) CI matrix suggestion for adopters

Use a staged matrix:

- `cpython-3.14` mandatory gate (unit + integration),
- `cinderx` canary gate (unit + integration + smoke benchmark),
- optional nightly CinderX benchmark run with metadata dossier export.

## 5) Deployment policy recommendation

- Require CinderX runtime import check in startup diagnostics.
- Keep a fast rollback path to stock CPython.
- Publish benchmark claims only when CinderX baseline validation passes.
