#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

history_branch="${BENCH_HISTORY_BRANCH:-bench-results}"
python_bin="${PYTHON_BIN:-}"

if [[ -z "$python_bin" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    python_bin=".venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    python_bin="$(command -v python3)"
  else
    echo "error: no usable Python found (.venv/bin/python or python3)." >&2
    exit 2
  fi
fi

echo "Fetching benchmark history branch: $history_branch"
git fetch --no-tags origin "$history_branch"

tmpdir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT

git archive --format=tar "origin/$history_branch" history/latest | tar -xf - -C "$tmpdir"

if [[ ! -f "$tmpdir/history/latest/index.json" ]]; then
  echo "error: missing history/latest/index.json on origin/$history_branch" >&2
  exit 1
fi

staged_root="$tmpdir/history/latest"

"$python_bin" - "$staged_root" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
index = json.loads((root / "index.json").read_text(encoding="utf-8"))
entries = index.get("entries", [])
if not isinstance(entries, list) or not entries:
    raise SystemExit("No benchmark entries found after sync.")

has_pyperf_entry = any(
    isinstance(entry, dict) and entry.get("suite") == "pyperformance"
    for entry in entries
)
if not has_pyperf_entry:
    raise SystemExit("Missing required pyperformance entry in synced index.json.")

latest_path = root / "latest-pyperformance.json"
if not latest_path.exists():
    raise SystemExit(f"Missing required summary file: {latest_path}")
payload = json.loads(latest_path.read_text(encoding="utf-8"))
if payload.get("suite") != "pyperformance":
    raise SystemExit(
        f"Suite mismatch for {latest_path.name}: "
        f"expected 'pyperformance', found '{payload.get('suite')}'."
    )

baseline = payload.get("baseline_runtime")
run_config = ((payload.get("metadata") or {}).get("run_config") or {})
runtimes = payload.get("runtimes") or []
has_cinderx_runtime = any(
    isinstance(item, dict)
    and item.get("runtime") == "cpython-cinderx"
    and item.get("executed") is True
    for item in runtimes
)
if baseline != "cpython-cinderx":
    raise SystemExit(
        f"{latest_path.name} is not CinderX-baselined (baseline_runtime={baseline!r})."
    )
if run_config.get("require_cinderx_baseline") is not True:
    raise SystemExit(
        f"{latest_path.name} was not generated with require_cinderx_baseline=true."
    )
if run_config.get("ci_mode") is True:
    raise SystemExit(f"{latest_path.name} is CI-mode and not publishable headline data.")
pyperf_mode = run_config.get("pyperformance_mode")
if pyperf_mode not in (None, "default"):
    raise SystemExit(f"{latest_path.name} uses non-full pyperformance mode ({pyperf_mode!r}).")
if not has_cinderx_runtime:
    raise SystemExit(
        f"{latest_path.name} has no executed cpython-cinderx runtime entry."
    )
allowed_runtimes = {"cpython", "cpython-cinderx", "pypy"}
runtime_keys = {
    str(item.get("runtime"))
    for item in runtimes
    if isinstance(item, dict)
}
unsupported_runtime_rows = sorted(runtime_keys - allowed_runtimes)
if unsupported_runtime_rows:
    raise SystemExit(
        f"{latest_path.name} includes unsupported runtime rows: "
        + ", ".join(unsupported_runtime_rows)
    )
benchmark_runtime_keys = {
    str(item.get("runtime"))
    for item in (payload.get("benchmarks") or [])
    if isinstance(item, dict)
}
unsupported_benchmark_rows = sorted(benchmark_runtime_keys - allowed_runtimes)
if unsupported_benchmark_rows:
    raise SystemExit(
        f"{latest_path.name} includes unsupported benchmark runtime rows: "
        + ", ".join(unsupported_benchmark_rows)
    )

print(f"synced_entries={len(entries)}")
print("required_latest_files=pyperformance")
print("publishable_cinderx_required=true")
PY

rm -rf packages/site/static/data/summary
mkdir -p packages/site/static/data/summary
cp -R "$staged_root/." packages/site/static/data/summary/

echo "Synced published benchmark summaries into packages/site/static/data/summary"
