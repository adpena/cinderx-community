---
title: FAQ
slug: /faq
---

# FAQ

## Is this project affiliated with Meta?

No. This is a community-run repository focused on source-grounded documentation and tooling around
CinderX.

## Why are benchmark claims so strict here?

To avoid misleading comparisons. Published comparison runs must be CinderX-baselined and pass
metadata/policy verification.

## Can I publish CPython-vs-PyPy headline results from this repo?

Not as primary claims. This repository's policy frames publishable runtime comparisons against
CinderX baseline.

## Why does `make bench-publish-check` fail locally?

Most commonly because latest summaries are not CinderX-baselined (`--cpython-cinderx` not executed,
or runtime is not truly CinderX-capable).

## What if CinderX does not build on my machine?

Use CI-shape mode locally for harness validation and keep results non-publishable. Track platform
constraints and upstream build issues in compatibility docs.

## Where should I start as a contributor?

Start with:

- [Local dev setup](./contributing/local-dev-setup)
- [Good first issues](./contributing/good-first-issues)
- [How to add a benchmark](./contributing/how-to-add-benchmark)
