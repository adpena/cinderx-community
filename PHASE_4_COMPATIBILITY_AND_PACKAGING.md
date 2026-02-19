# Phase 4 — Compatibility, Packaging, and “C Extensions Reality Check”

## Objectives
Help users answer:
- “Will my project run on CinderX?”
- “What changes do I need?”
- “How do native extensions behave?”
- “How do I ship this in production?”

## Deliverables
1) **Compatibility matrix**
   - OS/arch support (source-backed)
   - Python versions supported (source-backed)
   - Toolchain requirements (source-backed)
   - Runtime feature availability by platform (e.g., macOS “builds but features disabled”)
   - Windows status (source-backed)

2) **C extension guide**
   - Explain the CPython C-API landscape:
     - per-version ABI (most wheels)
     - Limited API / Stable ABI (`abi3` wheels) and what it does/doesn’t guarantee
     - Why other runtimes (e.g., PyPy) differ
   - Provide a checklist for package maintainers:
     - do you use the Limited API?
     - do you rely on CPython internals?
     - do you use `PyFrameObject` / tracing hooks?
     - do you ship manylinux wheels?
   - Provide guidance for diagnosing crashes:
     - symbol mismatches
     - `manylinux` tags
     - audit of ABI usage (consider tooling like abi3audit)

3) **Packaging & deployment recipes**
   - Dockerfiles (baseline images)
   - Building from source on Linux x86_64
   - Pinning CinderX version
   - CI matrix suggestions for projects adopting CinderX

4) **Test strategy**
   - “How to test your project under CinderX”:
     - unit tests
     - integration tests
     - perf smoke tests
   - When to disable JIT (if applicable) for determinism (only if validated by docs/tests)

## Acceptance criteria
- The website has a “Compatibility” section that answers the top 20 FAQs.
- A short “Production checklist” page exists.
- Any claims about CinderX-specific C-extension behavior are backed by:
  - upstream code/tests, or
  - reproduced experiments published in Phase 3 results.

## Nice-to-haves
- A “known packages” page with:
  - verified green list (tested)
  - unknown list
  - known issues list with links

## Implementation Status (2026-02-19)

Phase 4 deliverables are implemented with source-backed docs and deployment/testing guidance pages.

- Compatibility docs set:
  - landing page: `packages/site/docs/compatibility.md`
  - setup/verification: `packages/site/docs/compatibility/cinderx-runtime-setup.md`
  - matrix: `packages/site/docs/compatibility/matrix.mdx`
  - platform support: `packages/site/docs/compatibility/platform-support.md`
  - C-extension/ABI guide: `packages/site/docs/compatibility/c-extensions-and-abi.md`
  - packaging/deployment recipes: `packages/site/docs/compatibility/packaging-and-deployment.md`
  - test strategy: `packages/site/docs/compatibility/test-strategy.md`
  - production checklist: `packages/site/docs/compatibility/production-checklist.md`
  - known packages tracker scaffold: `packages/site/docs/compatibility/known-packages.md`
- Tooling support for setup/configuration:
  - `make cinderx-env-check`
  - `make cinderx-install-local`

Remaining operational caveat:

- As of 2026-02-19 in this workspace (macOS arm64), local upstream `cinderx` source build still
  fails in bundled `fmt` C++ compilation (`malloc` / `free` undeclared), so CinderX-baselined
  publishable benchmark runs remain blocked until upstream/runtime artifact resolution.
