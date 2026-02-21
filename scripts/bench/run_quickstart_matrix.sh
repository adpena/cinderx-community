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
pyperf_bootstrap_inline="${PYPERF_BOOTSTRAP_INLINE:-}"
pyperf_bootstrap_profile="${PYPERF_BOOTSTRAP_PROFILE:-}"
pyperf_bootstrap_profiles_csv="${PYPERF_BOOTSTRAP_PROFILES:-}"
pyperf_bootstrap_jit_compile_after_n_calls="${PYPERF_BOOTSTRAP_JIT_COMPILE_AFTER_N_CALLS:-}"

if [[ -n "$pyperf_bootstrap_inline" && ( -n "$pyperf_bootstrap_profile" || -n "$pyperf_bootstrap_profiles_csv" ) ]]; then
  echo "error: set only one of PYPERF_BOOTSTRAP_INLINE or PYPERF_BOOTSTRAP_PROFILE(S)" >&2
  exit 2
fi
if [[ -n "$pyperf_bootstrap_profile" && -n "$pyperf_bootstrap_profiles_csv" ]]; then
  echo "error: set either PYPERF_BOOTSTRAP_PROFILE or PYPERF_BOOTSTRAP_PROFILES, not both" >&2
  exit 2
fi
if [[ -n "$pyperf_bootstrap_jit_compile_after_n_calls" ]]; then
  allow_threshold=false
  if [[ "$pyperf_bootstrap_profile" == "cinderx-jit-compile-after-n-calls" ]]; then
    allow_threshold=true
  fi
  if [[ -n "$pyperf_bootstrap_profiles_csv" && "$pyperf_bootstrap_profiles_csv" == *"cinderx-jit-compile-after-n-calls"* ]]; then
    allow_threshold=true
  fi
  if [[ "$allow_threshold" != "true" ]]; then
    echo "error: PYPERF_BOOTSTRAP_JIT_COMPILE_AFTER_N_CALLS requires compile-after profile in PYPERF_BOOTSTRAP_PROFILE(S)" >&2
    exit 2
  fi
fi
if [[ -n "$pyperf_bootstrap_profiles_csv" && -z "$cinderx_python" ]]; then
  echo "error: PYPERF_BOOTSTRAP_PROFILES requires CINDERX_PYTHON so profile matrix can target cpython-cinderx lane." >&2
  exit 2
fi

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
if [[ -n "$pyperf_bootstrap_profiles_csv" ]]; then
  IFS=',' read -r -a pyperf_bootstrap_profiles <<< "$pyperf_bootstrap_profiles_csv"
  for raw_profile in "${pyperf_bootstrap_profiles[@]}"; do
    profile="${raw_profile#"${raw_profile%%[![:space:]]*}"}"
    profile="${profile%"${profile##*[![:space:]]}"}"
    if [[ -z "$profile" ]]; then
      continue
    fi
    profile_args=("${pyperf_compare_args[@]}" --pyperformance-bootstrap-profile "$profile")
    if [[ -n "$pyperf_bootstrap_jit_compile_after_n_calls" && "$profile" == "cinderx-jit-compile-after-n-calls" ]]; then
      profile_args+=(
        --pyperformance-bootstrap-jit-compile-after-n-calls
        "$pyperf_bootstrap_jit_compile_after_n_calls"
      )
    fi
    echo "  -> profile: $profile"
    "$cxc_bin" bench run --suite pyperformance "${common_args[@]}" "${profile_args[@]}"
  done
else
  if [[ -n "$pyperf_bootstrap_inline" ]]; then
    pyperf_compare_args+=(--pyperformance-bootstrap-inline "$pyperf_bootstrap_inline")
  fi
  if [[ -n "$pyperf_bootstrap_profile" ]]; then
    pyperf_compare_args+=(--pyperformance-bootstrap-profile "$pyperf_bootstrap_profile")
  fi
  if [[ -n "$pyperf_bootstrap_jit_compile_after_n_calls" ]]; then
    pyperf_compare_args+=(
      --pyperformance-bootstrap-jit-compile-after-n-calls
      "$pyperf_bootstrap_jit_compile_after_n_calls"
    )
  fi
  if [[ ${#pyperf_compare_args[@]} -gt 0 ]]; then
    "$cxc_bin" bench run --suite pyperformance "${common_args[@]}" "${pyperf_compare_args[@]}"
  else
    "$cxc_bin" bench run --suite pyperformance "${common_args[@]}"
  fi
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
if [[ -n "$pyperf_bootstrap_profile" ]]; then
  echo "Pyperformance bootstrap profile: $pyperf_bootstrap_profile"
elif [[ -n "$pyperf_bootstrap_profiles_csv" ]]; then
  echo "Pyperformance bootstrap profile matrix: $pyperf_bootstrap_profiles_csv"
elif [[ -n "$pyperf_bootstrap_inline" ]]; then
  echo "Pyperformance bootstrap mode: custom inline"
elif [[ -n "$cinderx_python" ]]; then
  echo "Pyperformance bootstrap profile: auto-default (cinderx-all-features = JIT all + static loader on cpython-cinderx lane only)"
fi
