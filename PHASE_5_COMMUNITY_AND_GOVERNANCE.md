# Phase 5 — Community Features, Governance, and “Understated Genius” Polish

## Objectives
Turn the site into the *community hub* for using and understanding CinderX:
- welcoming to newcomers
- credible to experts
- easy to contribute to
- transparent about what’s known vs unknown

## Deliverables
1) **Community structure**
   - Add a lightweight governance doc:
     - roles (maintainers, reviewers)
     - decision process
     - code of conduct enforcement path
   - CONTRIBUTING improvements:
     - “good first issue” guide
     - docs style guide (citations, no speculation, code snippets)
     - how to add a benchmark

2) **Content strategy**
   - Blog series:
     - “CinderX 101”
     - “CPython hooks that make this possible”
     - “Interpreters vs AOT compilers: fair comparisons”
   - Tutorials:
     - “Enabling CinderX in a Django service (dummy app)”
     - “Measuring your app’s speedup (without lying to yourself)”

3) **Website polish**
   - Great IA and cross-linking
   - “Glossary” for JIT terms, ABI terms, CPython internals
   - “FAQ” driven by issues/discussions
   - Social preview image + favicon set + OpenGraph metadata

4) **Repository hygiene**
   - Renovate or Dependabot
   - Release automation (optional) for the site/tooling package
   - Spellcheck/lint for docs (vale or cspell)

## Acceptance criteria
- A newcomer can land on the homepage and get to:
  - install instructions
  - compatibility notes
  - at least one hands-on tutorial
  in < 2 minutes.
- Contributors can add a doc page or benchmark with clear instructions and CI feedback.

## Implementation Status (2026-02-19)

Phase 5 deliverables are implemented with governance docs, onboarding docs, site IA additions, and
automation hygiene improvements.

- Community structure:
  - governance: `GOVERNANCE.md`
  - code of conduct/enforcement path: `CODE_OF_CONDUCT.md`, `SECURITY.md`
  - contributor workflow docs:
    - `packages/site/docs/contributing/good-first-issues.md`
    - `packages/site/docs/contributing/how-to-add-benchmark.md`
- Content strategy seeds:
  - blog series starters:
    - `packages/site/blog/2026-02-20-cinderx-101.md`
    - `packages/site/blog/2026-02-20-cpython-hooks-that-make-this-possible.md`
    - `packages/site/blog/2026-02-20-interpreters-vs-aot-fair-comparisons.md`
  - tutorial starters:
    - `packages/site/docs/tutorials/django-dummy-service.md`
    - `packages/site/docs/tutorials/measure-speedups.md`
- Website polish:
  - glossary: `packages/site/docs/glossary.md`
  - FAQ: `packages/site/docs/faq.md`
  - navbar/sidebar cross-linking updates in `packages/site/docusaurus.config.ts` and
    `packages/site/sidebars.ts`
  - social preview and favicon remain in `packages/site/static/img/social-card.svg` and
    `packages/site/static/img/favicon.svg`
- Repository hygiene:
  - dependency automation: `.github/dependabot.yml`
  - docs spellcheck in site lint flow via `cspell` (`packages/site/package.json`,
    `packages/site/.cspell.json`)
  - release automation workflow:
    - `.github/workflows/release.yml` builds Python package artifacts + site bundle and publishes
      GitHub Releases on tag push or manual dispatch.
