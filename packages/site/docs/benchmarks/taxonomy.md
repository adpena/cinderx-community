---
title: Workload taxonomy
---

# Workload taxonomy

Phase 3 classifies workloads so results are interpretable and not over-generalized.

## Classes we track

- `interpreter-heavy-dynamic-dispatch`: call/attribute/frame overhead where evaluator/JIT behavior is most visible.
- `compute-bound-numeric`: loop-heavy numeric execution where optimization quality dominates.
- `io-bound`: filesystem/network latency where VM speedups can be capped by system calls.
- `serialization-heavy`: JSON/msgpack/pickle style payload handling used in APIs and services.
- `web-framework`: end-to-end request handling with framework and middleware overhead.
- `c-extension-dominated`: native extension workloads (NumPy/Pandas/etc.) that show speedup ceilings.

## Why this matters for CinderX

CinderX combines frame-evaluator hooks, JIT compilation, and static-runtime behavior. Different workload
classes expose different ceilings and tradeoffs:

- dispatch-heavy workloads can benefit from evaluator/JIT behavior
- compute loops show steady-state throughput characteristics
- I/O and extension-dominated workloads prevent misleading speedup expectations

## Smoke suite coverage

Current runnable smoke coverage includes:

- dispatch-heavy (`dynamic_dispatch`)
- compute-bound (`compute_numeric`)
- serialization-heavy (`serialization_json`)
- I/O-bound (`io_tempfile`)
- C-extension dominated (`hashlib_sha256`)

Web-framework and networking-heavy macro workloads are intentionally deferred to dedicated suite adapters.
