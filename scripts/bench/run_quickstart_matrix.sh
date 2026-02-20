#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

detect_first() {
  for name in "$@"; do
    if command -v "$name" >/dev/null 2>&1; then
      command -v "$name"
      return 0
    fi
  done
  return 1
}

cxc_bin="${CXC_BIN:-.venv/bin/cxc}"
python_bin="${PYTHON_BIN:-.venv/bin/python}"

if [[ ! -x "$cxc_bin" ]]; then
  echo "error: benchmark CLI not found: $cxc_bin" >&2
  echo "hint: run 'make python-dev' first" >&2
  exit 2
fi
if [[ ! -x "$python_bin" ]]; then
  echo "error: Python interpreter not found: $python_bin" >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required for summary inspection output." >&2
  exit 2
fi

cinderx_python="${CINDERX_PYTHON:-}"
pypy_python="${PYPY_PYTHON:-$(detect_first pypy3 pypy || true)}"

common_args=(
  --python "$python_bin"
  --ci-mode
  --out data/runs
  --summary-out data/summary
  --static-summary-out packages/site/static/data/summary
)

smoke_compare_args=()
if [[ -n "$cinderx_python" ]]; then
  smoke_compare_args+=(--cpython-cinderx "$cinderx_python")
fi
if [[ -n "$pypy_python" ]]; then
  smoke_compare_args+=(--pypy "$pypy_python")
fi

require_mode="${REQUIRE_CINDERX_BASELINE:-auto}"
if [[ "$require_mode" == "auto" && -n "$cinderx_python" ]]; then
  require_mode="true"
fi
if [[ "$require_mode" == "true" ]]; then
  smoke_compare_args+=(--require-cinderx-baseline)
fi

echo "Running smoke suite..."
if [[ ${#smoke_compare_args[@]} -gt 0 ]]; then
  "$cxc_bin" bench run --suite smoke "${common_args[@]}" "${smoke_compare_args[@]}"
else
  "$cxc_bin" bench run --suite smoke "${common_args[@]}"
fi

pyperf_compare_args=()
if [[ -n "$cinderx_python" ]]; then
  pyperf_compare_args+=(--cpython-cinderx "$cinderx_python")
fi
if [[ -n "$pypy_python" ]]; then
  pyperf_compare_args+=(--pypy "$pypy_python")
fi
if [[ "$require_mode" == "true" ]]; then
  pyperf_compare_args+=(--require-cinderx-baseline)
fi

echo "Running pyperformance suite..."
if [[ ${#pyperf_compare_args[@]} -gt 0 ]]; then
  "$cxc_bin" bench run --suite pyperformance "${common_args[@]}" "${pyperf_compare_args[@]}"
else
  "$cxc_bin" bench run --suite pyperformance "${common_args[@]}"
fi

echo "Exporting metadata dossier..."
"$cxc_bin" bench export-dossier --summary-root data/summary --output-root data/summary/reports

if [[ "$require_mode" == "true" ]]; then
  echo "Running publish verification..."
  "$cxc_bin" bench verify-publish \
    --summary-root data/summary \
    --static-summary-root packages/site/static/data/summary
fi

echo
echo "Latest smoke summary:"
jq '{suite,run_id,machine,baseline_runtime,runtimes:(.runtimes|map({runtime,executed})),skipped_runtimes}' data/summary/latest-smoke.json

echo
echo "Latest pyperformance summary:"
jq '{suite,run_id,machine,baseline_runtime,runtimes:(.runtimes|map({runtime,executed})),skipped_runtimes}' data/summary/latest-pyperformance.json

echo
echo "Interpreter comparator coverage: CPython, CinderX (when available), PyPy (when available)."
