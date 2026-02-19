# Phase 2 — Codebase & Test Introspection (“Tell the full story”)

## Objectives
Build *trustworthy, source-backed* documentation about how CinderX works by performing structured
introspection of:
- the CinderX source tree (C/C++/Python)
- its tests
- the relevant CPython upstream hooks and extension points

Deliver the kind of “how it works” story that engineering readers expect: diagrams, callouts, traced
code paths, and links back to the exact file/line in upstream repos.

## Non-goals (Phase 2)
- No authoritative performance claims beyond what we can reproduce in Phase 3.
- No mass “copying” of upstream code into the site. Prefer excerpts, summaries, and deep links.

## Inputs / Sources
Primary:
- `facebookincubator/cinderx` (CinderX extension) — source and tests
- CPython 3.14+ sources and relevant PEPs/issue discussions for hooks used by JIT/extensions

Secondary:
- Meta engineering blog posts about upstreaming hooks (e.g., frame evaluation / perf hooks)
- Existing talks/posts by maintainers (when available)

## Deliverables
1) **Upstream pinning & provenance**
   - Add `cxc upstream clone` + `cxc upstream pin` commands
   - Store pins in `python/cinderx_community/pins.toml`:
     - repo URL
     - commit SHA
     - clone timestamp
     - optional tags/releases
   - Add “provenance banner” on generated docs (“Built from CinderX @ <SHA>”).

2) **Introspection pipeline (repeatable)**
   - Create `cxc research extract` that generates:
     - symbol inventories (modules, classes, exported C symbols)
     - feature flags / build-time options (where discoverable)
     - test taxonomy (group tests by folder/marker, runtime requirements, flakiness tags if any)
   - Output should be structured JSON under `data/introspection/<repo>/<sha>/...`.

3) **Docs generation**
   - A small generator that takes introspection JSON and renders MDX pages under the site:
     - `docs/generated/...`
   - Generated pages should always include links back to upstream paths.

4) **“How it works” narrative docs (handwritten + cited)**
   - `Architecture overview`
   - `JIT pipeline (high-level → deep dive)`
   - `Static Python overview + how it affects runtime behavior`
   - `Runtime hooks and CPython extension points used`
   - `Debugging & observability` (what breaks tracing/profiling, what’s supported)

5) **Diagramming**
   - Prefer lightweight diagrams embedded as SVG:
     - Mermaid (if you accept it) or hand-authored SVG
   - A single canonical diagram per major subsystem.

## Suggested technical approach
- Use *tree-sitter* for Python and C/C++ parsing where it helps.
- For C/C++ symbol extraction:
  - `clang` tooling (libclang or `clang -Xclang -ast-dump=json`) on supported platforms
  - fallback: `ctags`/regex extraction (document limitations)
- For Python API surface:
  - import-time inspection where possible, but keep it optional (CinderX needs CPython 3.14+)

## Quality bar / acceptance criteria
- One command generates fresh introspection artifacts deterministically:
  - `cxc research extract --repo cinderx --out data/...`
- Generated docs build successfully (no broken MDX)
- Every non-trivial claim has a link to upstream code, test, or primary source
- Clear separation between:
  - “confirmed by code/test”
  - “inferred / hypothesis”
  - “unknown yet” (TODO)

## Risks & mitigations
- **Tooling portability**: clang tooling may vary. Provide graceful fallbacks.
- **Doc drift**: generated docs should include the upstream commit SHA and be re-generatable.

## Implementation Status (2026-02-19)

Phase 2 deliverables are implemented and validated in this workspace.

- Upstream pinning/provenance:
  - `cxc upstream clone`, `cxc upstream pin`, `cxc upstream status`, `cxc upstream history`
  - Pin metadata persisted in `python/cinderx_community/pins.toml` (`repo_url`, `commit_sha`, `clone_timestamp_utc`, `destination`, `tags`)
  - Provenance banner rendered in generated docs (for example `packages/site/docs/generated/introspection-overview.mdx`)
- Introspection extraction pipeline:
  - `cxc research extract` writes `summary.json`, `symbols.json`, `build_flags.json`, `tests.json`
  - Output path: `data/introspection/<repo>/<sha>/...`
- Generated docs:
  - `cxc research render-docs` (or `--render-docs` on extract) renders MDX under `packages/site/docs/generated/`
  - Generated pages link to upstream file/line references
- Narrative docs and diagrams:
  - `packages/site/docs/architecture/overview.mdx`
  - `packages/site/docs/architecture/jit-pipeline.mdx`
  - `packages/site/docs/architecture/static-python-runtime.mdx`
  - `packages/site/docs/architecture/runtime-hooks-cpython.mdx`
  - `packages/site/docs/architecture/debugging-observability.mdx`
  - Each includes clear `confirmed` / `inferred` / `unknown` separation and an embedded SVG subsystem diagram

Validation run in this workspace:

- `make lint` ✅
- `make test` ✅
- `make build` ✅
- `cxc research extract --repo cinderx --repo-path .cache/upstream/cinderx --out data/introspection --render-docs --docs-out packages/site/docs/generated` ✅
- Automated checks in `python/cinderx_community/tests/test_phase2_tools.py` validate provenance + upstream source links in generated docs ✅

Re-validation snapshot (2026-02-19):

- `.venv/bin/cxc research extract --repo cinderx --repo-path .cache/upstream/cinderx --out data/introspection --render-docs --docs-out packages/site/docs/generated` ✅
  - upstream commit extracted/rendered: `31bca9f3156b78cca3c6b36000c42c48f5ddf037`
  - regenerated files under `data/introspection/cinderx/<sha>/...` and `packages/site/docs/generated/*.mdx`
