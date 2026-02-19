---
title: Measuring your app's speedup responsibly
---

# Measuring your app's speedup responsibly

This tutorial is a short playbook for reproducible, CinderX-first speed measurements.

## 1) Define workload and claim boundary

- Identify exact workload (endpoint mix, input shape, concurrency, warmup behavior).
- Decide whether you are making an internal engineering decision or a public claim.

## 2) Verify runtime identity

```bash
$CINDERX_PYTHON -c "import cinderx,sys; print(sys.executable); print(cinderx.__file__)"
```

If this check fails, do not label results as CinderX-based.

## 3) Run baseline and comparator fairly

- Same machine profile
- Same dependency lock
- Same dataset and workload generator
- Same run duration and warmup strategy

## 4) Capture complete metadata

- OS/kernel/CPU/RAM
- runtime versions
- command lines
- timestamps

In this repository, use:

```bash
make bench-dossier
```

## 5) Enforce publish guard before sharing

```bash
make bench-publish-check
```

If guard fails, treat results as non-publishable diagnostics, not headline comparisons.
