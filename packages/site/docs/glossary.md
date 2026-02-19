---
title: Glossary
slug: /glossary
---

# Glossary

- **CinderX**: A CPython extension from Meta focused on Python runtime performance improvements.
- **Cinder**: Meta's historical CPython fork preceding extension-based CinderX.
- **JIT**: Just-in-time compilation from bytecode to native code during execution.
- **Static Python**: A stricter Python subset/form used for stronger analysis and optimization paths.
- **Baseline runtime**: Runtime used as denominator for speedup values in a benchmark summary.
- **CinderX-first policy**: This repo's publication rule requiring CinderX baseline for headline
  runtime comparisons.
- **CI-shape run**: Fast, non-claim benchmark run used for output/automation validation.
- **Publishable run**: Benchmark run that passes strict CinderX baseline and metadata guardrails.
- **`abi3`**: CPython stable ABI subset for extension compatibility across CPython minor versions.
- **Manylinux tag**: Linux wheel compatibility tag indicating glibc baseline expectations.
