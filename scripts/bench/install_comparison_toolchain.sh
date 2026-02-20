#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

python_bin="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
  echo "error: Python interpreter not found or not executable: $python_bin" >&2
  echo "hint: run 'make python-dev' first or set PYTHON_BIN=/path/to/python" >&2
  exit 2
fi

detect_first() {
  for name in "$@"; do
    if command -v "$name" >/dev/null 2>&1; then
      command -v "$name"
      return 0
    fi
  done
  return 1
}

echo "Installing required benchmark tools into: $python_bin"
uv pip install --python "$python_bin" pyperformance

pypy_python="${PYPY_PYTHON:-$(detect_first pypy3 pypy || true)}"

echo
echo "Detected comparator executables:"
echo "  pypy:   ${pypy_python:-missing}"

echo
echo "Usage examples:"
echo "  bash scripts/bench/run_quickstart_matrix.sh"
echo "  CINDERX_PYTHON=/path/to/cinderx-python bash scripts/bench/run_quickstart_matrix.sh"
if [[ -n "${pypy_python}" ]]; then
  echo "  PYPY_PYTHON=${pypy_python} bash scripts/bench/run_quickstart_matrix.sh"
fi
