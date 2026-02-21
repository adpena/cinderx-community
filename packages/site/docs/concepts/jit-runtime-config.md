---
title: JIT Runtime Config
---

# JIT Runtime Config

This page is the source-backed reference for CinderX JIT controls and how this repo wires them.

## Benchmark default in this repo

For pyperformance runs with `--cpython-cinderx`, our default bootstrap profile is
`cinderx-all-features`, and that profile now configures eager JIT (`jit-all` behavior) by calling:

```python
cinderx.jit.compile_after_n_calls(0)
```

This is deliberate for constrained benchmark environments where waiting for warmup thresholds can
hide JIT impact.

## Harness bootstrap profiles

- `cinderx-init`: import + initialize CinderX only.
- `cinderx-all-features`: JIT all + static loader install (`enable_patching=True` when stubs exist).
- `cinderx-jit-all`: JIT all only.
- `cinderx-jit-auto`: default auto threshold.
- `cinderx-jit-compile-after-n-calls`: configurable threshold.
- `cinderx-jit-disable`: disable JIT.
- `cinderx-static-loader`: strict/static loader only.
- `cinderx-static-loader-patching`: strict/static loader with patching enabled.

## Python API knobs

Primary runtime controls are exposed in `cinderx.jit`:

- `auto()`
- `compile_after_n_calls(n)`
- `enable()` / `disable()`
- `is_enabled()`
- `is_jit_compiled(func)`
- `force_compile(func)` / `lazy_compile(func)`
- `precompile_all(workers=...)`
- `set_max_code_size(bytes)`
- inliner/opcode/type-guard toggles

## Exhaustive `-X` and env option catalog

As of the pinned upstream revision, JIT flags are registered in
`cinderx/Jit/pyjit.cpp` via the `FlagProcessor`.

- `-X jit-dump-hir-stats` / `PYTHONJITDUMPHIRSTATS`
- `-X jit-all` / `PYTHONJITALL`
- `-X jit-auto` / `PYTHONJITAUTO`
- `-X jit-debug` / `PYTHONJITDEBUG`
- `-X jit-log-file` / `PYTHONJITLOGFILE`
- `-X jit-asm-syntax` / `PYTHONJITASMSYNTAX`
- `-X jit-debug-refcount` / `PYTHONJITDEBUGREFCOUNT`
- `-X jit-debug-regalloc` / `PYTHONJITDEBUGREGALLOC`
- `-X jit-debug-inliner` / `PYTHONJITDEBUGINLINER`
- `-X jit-dump-hir` / `PYTHONJITDUMPHIR`
- `-X jit-dump-hir-passes` / `PYTHONJITDUMPHIRPASSES`
- `-X jit-dump-final-hir` / `PYTHONJITDUMPFINALHIR`
- `-X jit-dump-lir` / `PYTHONJITDUMPLIR`
- `-X jit-dump-lir-origin` / `PYTHONJITDUMPLIRORIGIN`
- `-X jit-symbolize` / `PYTHONJITSYMBOLIZE`
- `-X jit-dump-asm` / `PYTHONJITDUMPASM`
- `-X jit-enable-inline-cache-stats-collection` / `PYTHONJITCOLLECTINLINECACHESTATS`
- `-X jit-gdb-support` / `PYTHONJITGDBSUPPORT`
- `-X jit-gdb-write-elf` / `PYTHONJITGDBWRITEELF`
- `-X jit-dump-stats` / `PYTHONJITDUMPSTATS`
- `-X jit-huge-pages` / `PYTHONJITHUGEPAGES`
- `-X jit-enable-jit-list-wildcards` / `PYTHONJITENABLEJITLISTWILDCARDS`
- `-X jit-all-static-functions` / `PYTHONJITALLSTATICFUNCTIONS`
- `-X jit-list-file` / `PYTHONJITLISTFILE`
- `-X jit-list-fail-on-parse-error` / `PYTHONJITLISTFAILONPARSEERROR`
- `-X jit-disable` / `PYTHONJITDISABLE`
- `-X jit-shadow-frame` / `PYTHONJITSHADOWFRAME`
- `-X jit-lightweight-frame` / `PYTHONJITLIGHTWEIGHTFRAME`
- `-X jit-stable-frame` / `PYTHONJITSTABLEFRAME`
- `-X jit-preload-dependent-limit` / `PYTHONJITPRELOADDEPENDENTLIMIT`
- `-X jit-begin-inlined-function-elim` / `PYTHONJITBEGININLINEDFUNCTIONELIM`
- `-X jit-builtin-load-method-elim` / `PYTHONJITBUILTINLOADMETHODELIM`
- `-X jit-clean-cfg` / `PYTHONJITCLEANCFG`
- `-X jit-dead-code-elim` / `PYTHONJITDEADCODEELIM`
- `-X jit-dynamic-comparison-elim` / `PYTHONJITDYNAMICCOMPARISIONELIM`
- `-X jit-guard-type-removal` / `PYTHONJITGUARDTYPEREMOVAL`
- `-X jit-enable-hir-inliner` / `PYTHONJITENABLEHIRINLINER`
- `-X jit-phi-elim` / `PYTHONJITPHIELIM`
- `-X jit-simplify` / `PYTHONJITSIMPLIFY`
- `-X jit-simplify-iteration-limit` / `PYTHONJITSIMPLIFYITERATIONLIMIT`
- `-X jit-simplify-new-block-limit` / `PYTHONJITSIMPLIFYNEWBLOCKLIMIT`
- `-X jit-hir-inliner-cost-limit` / `PYTHONJITHIRINLINERCOSTLIMIT`
- `-X jit-lir-inliner` / `PYTHONJITLIRINLINER`
- `-X jit-batch-compile-workers` / `PYTHONJITBATCHCOMPILEWORKERS`
- `-X jit-multithreaded-compile-test` / `PYTHONJITMULTITHREADEDCOMPILETEST`
- `-X jit-list-match-line-numbers` / `PYTHONJITLISTMATCHLINENUMBERS`
- `-X jit-time` / `(none)`
- `-X jit-multiple-code-sections` / `PYTHONJITMULTIPLECODESECTIONS`
- `-X jit-hot-code-section-size` / `PYTHONJITHOTCODESECTIONSIZE`
- `-X jit-cold-code-section-size` / `PYTHONJITCOLDCODESECTIONSIZE`
- `-X jit-attr-caches` / `PYTHONJITATTRCACHES`
- `-X jit-attr-cache-size` / `PYTHONJITATTRCACHESIZE`
- `-X jit-refine-static-python` / `PYTHONJITREFINESTATICPYTHON`
- `-X jit-perfmap` / `JIT_PERFMAP`
- `-X jit-perf-dumpdir` / `JIT_DUMPDIR`
- `-X jit-help` / `(none)`
- `-X perf-trampoline-prefork-compilation` / `PERFTRAMPOLINEPREFORKCOMPILATION`
- `-X jit-max-code-size` / `PYTHONJITMAXCODESIZE`
- `-X jit-emit-type-annotation-guards` / `PYTHONJITTYPEANNOTATIONGUARDS`
- `-X jit-specialized-opcodes` / `PYTHONJITSPECIALIZEDOPCODES`
- `-X jit-support-instrumentation` / `PYTHONJITSUPPORTINSTRUMENTATION`

## Practical recommendation for benchmarking

For reproducible CinderX-vs-CPython comparisons in this repo:

1. Keep plain `cpython` lane unmodified.
2. Keep `cpython-cinderx` lane on eager JIT (`cinderx-all-features` or `cinderx-jit-all`).
3. Run preflight before full pyperformance to prove JIT compilation is actually occurring.

## Sources

- [cinderx/PythonLib/cinderx/jit.py](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/PythonLib/cinderx/jit.py)
- [cinderx/Jit/pyjit.cpp](https://github.com/facebookincubator/cinderx/blob/31bca9f3156b78cca3c6b36000c42c48f5ddf037/cinderx/Jit/pyjit.cpp)
- [cinderx_community benchmark harness](https://github.com/adpena/cinderx-community/blob/main/python/cinderx_community/bench/runner.py)
