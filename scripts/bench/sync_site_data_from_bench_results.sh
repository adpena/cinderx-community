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
from datetime import datetime
from pathlib import Path
import sys

root = Path(sys.argv[1])
index = json.loads((root / "index.json").read_text(encoding="utf-8"))
entries = index.get("entries", [])
if not isinstance(entries, list) or not entries:
    raise SystemExit("No benchmark entries found after sync.")

required_suites = ("smoke", "pyperformance")
entry_by_suite: dict[str, str] = {}
for entry in entries:
    if not isinstance(entry, dict):
        continue
    suite = entry.get("suite")
    file_name = entry.get("file")
    if isinstance(suite, str) and isinstance(file_name, str) and suite not in entry_by_suite:
        entry_by_suite[suite] = file_name

missing_entries = [suite for suite in required_suites if suite not in entry_by_suite]
if missing_entries:
    raise SystemExit(
        "Missing required suite entries in synced index.json: " + ", ".join(missing_entries)
    )


def validate_latest(suite: str) -> dict:
    latest_path = root / f"latest-{suite}.json"
    if not latest_path.exists():
        raise SystemExit(f"Missing required summary file: {latest_path}")
    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    if payload.get("suite") != suite:
        raise SystemExit(
            f"Suite mismatch for {latest_path.name}: "
            f"expected '{suite}', found '{payload.get('suite')}'."
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
    return payload


payload_by_suite = {suite: validate_latest(suite) for suite in required_suites}
run_ids = {str(payload.get("run_id", "")).strip() for payload in payload_by_suite.values()}
if any(not value for value in run_ids):
    detail = ", ".join(
        f"{suite}={payload_by_suite[suite].get('run_id')!r}" for suite in required_suites
    )
    raise SystemExit(f"Cross-suite coherence failure: run_id missing ({detail}).")

machines = {str(payload.get("machine", "")).strip() for payload in payload_by_suite.values()}
if len(machines) != 1:
    detail = ", ".join(
        f"{suite}={payload_by_suite[suite].get('machine')!r}" for suite in required_suites
    )
    raise SystemExit(f"Cross-suite coherence failure: machine mismatch ({detail}).")

repo_shas = {
    str(
        (
            ((payload.get("metadata") or {}).get("toolchain") or {}).get("benchmark_repo_sha")
            or ""
        )
    ).strip()
    for payload in payload_by_suite.values()
}
if len(repo_shas) != 1:
    detail = ", ".join(
        f"{suite}={((payload_by_suite[suite].get('metadata') or {}).get('toolchain') or {}).get('benchmark_repo_sha')!r}"
        for suite in required_suites
    )
    raise SystemExit(f"Cross-suite coherence failure: benchmark_repo_sha mismatch ({detail}).")

generated_times = {}
for suite in required_suites:
    raw = payload_by_suite[suite].get("generated_at_utc")
    if not isinstance(raw, str) or not raw.strip():
        raise SystemExit(f"Cross-suite coherence failure: missing generated_at_utc for {suite}.")
    normalized = raw.replace("Z", "+00:00")
    try:
        generated_times[suite] = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SystemExit(
            f"Cross-suite coherence failure: invalid generated_at_utc for {suite}: {raw!r}"
        ) from exc

skew_seconds = (max(generated_times.values()) - min(generated_times.values())).total_seconds()
if skew_seconds > 3600:
    detail = ", ".join(
        f"{suite}={payload_by_suite[suite].get('generated_at_utc')!r}"
        for suite in required_suites
    )
    raise SystemExit(
        f"Cross-suite coherence failure: generated_at_utc skew {skew_seconds:.1f}s exceeds 3600s ({detail})."
    )

print(f"synced_entries={len(entries)}")
print("required_suites=smoke,pyperformance")
print("publishable_cinderx_required=true")
PY

rm -rf packages/site/static/data/summary
mkdir -p packages/site/static/data/summary
cp -R "$staged_root/." packages/site/static/data/summary/

echo "Synced published benchmark summaries into packages/site/static/data/summary"
