# Phase 3 — Benchmarking Suite & Methodology (Real-world, credible, reproducible)

## Objectives
Design and implement a benchmark suite that community members and Meta engineers will consider:
- fair
- reproducible
- representative of real workloads
- transparent about methodology and limitations

We want *both* microbenchmarks (to reason about mechanisms) and macrobenchmarks (to represent
actual application behavior).

## Key reference suites (to integrate, not reinvent)
- **pyperformance**: “authoritative” Python benchmark suite with real-world focus.
- **Nuitka** benchmarking patterns: AOT compile/run workflows, compile-time accounting, and runtime measurement.
- **numba/numba-benchmark**: ASV-based suite for Numba.
- **speed.pypy.org benchmarks**: Unladen Swallow-derived suite, plus their reporting patterns.

## Deliverables
1) **Benchmark taxonomy**
   - Document workload classes:
     - interpreter-heavy / dynamic dispatch heavy
     - compute-bound numeric
     - I/O-bound (filesystem, networking)
     - serialization-heavy (json/msgpack/pickle)
     - web framework workload (Django dummy app + k6)
     - “C-extension dominated” workloads (NumPy/Pandas/etc.) to illustrate ceilings
   - Include *why each class matters* for CinderX features.

2) **Harness (single entrypoint, multi-runtime)**
   - `cxc bench run` supports:
     - CPython + CinderX (primary baseline for comparison publishing)
     - CPython 3.14 (reference runtime, not the primary comparison baseline)
     - PyPy (optional comparator)
     - Nuitka (optional comparator with compile-time reporting)
     - Cython, Numba, Codon (workload-dependent; some are compilers/tools)
   - Use adapters per runtime/tool with consistent output format.
   - Enforce CinderX-first comparison policy for publishable comparisons (for example `--require-cinderx-baseline`).
   - Use a standard “run metadata” blob:
     - OS, kernel, CPU model, RAM
     - Python version/build flags
     - tool versions
     - git SHAs for benchmark suite + upstream toolchain
     - run timestamp, warmup strategy, iteration counts

3) **Result format + storage**
   - Store raw outputs (e.g., pyperf JSON) under `data/runs/<date>/<machine>/<runtime>/...`
   - Provide a normalized “summary table” JSON for website charts:
     - mean, stdev, p-values (when available)
     - speedup vs baseline
     - memory RSS (optional)
     - compile time / startup time (as relevant)

4) **Reproducibility guardrails**
   - Document and optionally enforce:
     - CPU pinning
     - turbo/boost notes
     - thermal state warnings
     - background process checks
   - Provide “CI mode” that runs only quick sanity benchmarks, not performance claims.

5) **Publishing**
   - A static “Benchmarks” section on the website that:
     - reads `data/summary/*.json`
     - renders interactive charts (per suite, per workload class)
     - includes methodology and machine metadata
   - “Latest results” should include commit SHAs and dates.

6) **Continuous benchmarking strategy**
   - Recommended: scheduled runs on a dedicated self-hosted runner (or GitHub-hosted if small).
   - Store results in git (small) or in a separate `results` branch with LFS if needed.
   - Generate a “performance regression” report for changes in *this* repo (site/tools).

## Methodology expectations
- Use statistical benchmarking tools where possible (`pyperf`/`pyperformance`).
- Separate:
  - startup time
  - steady-state runtime
  - compilation time (AOT tools)
- Be explicit about when a tool cannot run a workload (e.g., Codon subset limitations).

## Acceptance criteria
- One command can run a small “smoke suite” and produce parsable results:
  - `cxc bench run --suite smoke --python <...> --out data/...`
- Charts render from produced summary JSON.
- Docs clearly state limitations and avoid misleading comparisons.

## Implementation Status (2026-02-19)

Phase 3 deliverables are implemented with runnable harnesses, published summaries, and CI/scheduled
benchmark workflow wiring.

- Deliverable 1 (benchmark taxonomy): implemented
  - Taxonomy doc: `packages/site/docs/benchmarks/taxonomy.md`
  - Taxonomy embedded in summary JSON (`workload_taxonomy` field)
- Deliverable 2 (harness): implemented
  - Runnable commands:
    - `cxc bench run --suite smoke ...`
    - `cxc bench run --suite pyperformance ...`
  - Multi-runtime adapters:
    - implemented baseline: CPython + CinderX (`--cpython-cinderx`) as primary comparison baseline
    - implemented comparators: CPython, PyPy (explicit `--pypy` or auto-detected `pypy3`/`pypy`), Nuitka (explicit `--nuitka` or auto-detected `nuitka`)
    - declared/TODO: Cython, Numba, Codon workload-specific adapters
  - Baseline policy:
    - `--require-cinderx-baseline` blocks comparison runs that would otherwise fall back to CPython-only baselines
    - `--cpython-cinderx` is validated as CinderX-capable (`import cinderx`/runtime branding); non-CinderX executables are rejected to avoid mislabeled baselines
  - Run metadata includes OS/kernel/CPU/RAM/runtime details, timestamps, guardrails, and pinned CinderX SHA
- Deliverable 3 (result format + storage): implemented for smoke + pyperformance normalization
  - Raw artifacts: `data/runs/<date>/<machine>/<runtime>/...`
  - Normalized summaries: `data/summary/*.json` + `index.json` + `latest-smoke.json` + `latest-pyperformance.json`
  - Statistical fields in normalized summaries: `p_value` plus optional `memory_rss_bytes` and `compile_time_seconds` when adapters expose them
- Deliverable 4 (repro guardrails): implemented
  - Guardrail checks recorded in metadata (CPU affinity visibility, background load, turbo/thermal notes)
  - `--enforce-guardrails` can fail noisy runs
  - `--ci-mode` enables fast smoke settings and labels non-claim mode
- Deliverable 5 (publishing): implemented
  - Static-site mirror: `packages/site/static/data/summary/*.json`
  - Interactive dashboard page: `packages/site/docs/benchmarks/results-placeholder.mdx`
  - Dashboard component: `packages/site/src/components/BenchSummaryDashboard.tsx` (includes CinderX comparison mode and statistical metrics table)
  - Publish guard command: `cxc bench verify-publish` fails if latest required summaries are not truly CinderX-baselined/policy-enforced
  - Metadata dossier export command: `cxc bench export-dossier` emits report-ready configuration snapshots from latest summaries
- Deliverable 6 (continuous strategy): implemented
  - Workflow: `.github/workflows/benchmarks.yml` (manual + scheduled benchmark runs with a dual-job strategy:
    - `benchmark` on `ubuntu-latest` is diagnostics-only CI-shape validation and gracefully falls back when hosted CinderX probe crashes/fails
    - `benchmark_pinned_publishable` on pinned `ubuntu-22.04` + pinned CPython `3.14.0` (via `actions/setup-python`) is the canonical publishable lane for strict CinderX-baselined comparisons and uploads publishable artifacts)
  - `CINDERX_PYTHON` override is supported for external CinderX runtimes
  - CinderX-enabled runs execute `cxc bench verify-publish` before uploading publishable artifacts
  - diagnostics lane uploads are explicitly non-publishable `ci-shape` artifacts only
  - publishable summary history is persisted by CI to the `bench-results` branch (`history/index.json`, `history/latest/`, per-run snapshots under `history/runs/...`)
  - metadata dossiers are exported automatically
  - Local-free execution path is wired through make targets: `make bench-smoke-local`, `make bench-pyperformance-local`, `make bench-smoke-local-cinderx`, `make bench-pyperformance-local-cinderx`
  - Project metadata includes optional `cinderx` dependency managed via `uv` (`uv add --project ./python --optional cinderx cinderx --no-sync`)

Validation in this workspace:

- `make lint` ✅
- `make test` ✅
- `make build` ✅
- `cxc bench run --suite smoke --python .venv/bin/python --cpython-cinderx .venv/bin/python --require-cinderx-baseline --ci-mode` ❌ (expected strict-policy failure: provided `--cpython-cinderx` does not expose `cinderx`)
- `cxc bench run --suite smoke --python .venv/bin/python --ci-mode --out data/runs --summary-out data/summary --static-summary-out packages/site/static/data/summary` ✅ (CI-shape, non-comparison)
- `cxc bench run --suite pyperformance --python .venv/bin/python --ci-mode --out data/runs --summary-out data/summary --static-summary-out packages/site/static/data/summary` ✅ (CI-shape, non-comparison)

Validation caveat:

- GitHub-hosted `ubuntu-latest` + `uv python install 3.14` still reproduces a CinderX import-probe crash (`exit 139`) after successful install, so that lane remains CI-shape fallback by design.
- Pinned lane (`ubuntu-22.04` + `actions/setup-python@v6` with CPython `3.14.0`) now produces publishable CinderX-baselined runs and passes `cxc bench verify-publish`.
- A runtime-path bug in the harness (resolving `.venv/bin/python` symlinks to the base interpreter and losing venv site-packages) was fixed; this removed false negative `ModuleNotFoundError: No module named 'cinderx'` probe failures in strict publishable runs.
- Local publishable comparisons still require a real local CinderX-enabled runtime (`--cpython-cinderx` or `CINDERX_PYTHON`).

Re-validation snapshot (2026-02-19):

- `make bench-smoke-local` ✅ (run id `20260219T184031Z`)
- `make bench-pyperformance-local` ✅ (run id `20260219T184031Z`)
- `make bench-dossier` ✅
- `make bench-publish-check` ❌ expected (fails by design until a real CinderX baseline runtime is executed with `--require-cinderx-baseline`)
- GitHub Actions run `22196870445` ✅ (smoke-only dispatch; fallback CI-shape + pinned publishable both green)
- GitHub Actions run `22196955889` ✅ (smoke + pyperformance dispatch; fallback CI-shape + pinned publishable both green)
