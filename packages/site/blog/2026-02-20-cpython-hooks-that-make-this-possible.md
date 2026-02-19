---
slug: cpython-hooks-that-make-this-possible
title: CPython hooks that make this possible
authors: [community]
tags: [cpython, cinderx, internals]
---

CinderX's extension model depends on upstream CPython hooks and compatibility work, especially
across recent Python versions.

This post frames the "why" behind our source-citation rule: we only claim mechanisms we can trace
to upstream docs/code.

<!-- truncate -->

Primary references:

- [Meta engineering note on CPython 3.12 hooks](https://engineering.fb.com/2023/10/05/developer-tools/python-312-meta-new-features/)
- [CinderX README](https://github.com/facebookincubator/cinderx)
