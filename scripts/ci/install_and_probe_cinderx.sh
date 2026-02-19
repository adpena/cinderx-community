#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage:
  install_and_probe_cinderx.sh --python <python_bin> [--mode <permissive|strict>] [--diagnostics-dir <dir>] [--output-file <path>]

Notes:
  - Writes step outputs to --output-file (or $GITHUB_OUTPUT when present).
  - Attempts staged install strategies and probes `import cinderx` after each.
EOF
}

PYTHON_BIN=""
MODE="permissive"
DIAGNOSTICS_DIR=".cache/cinderx-diagnostics"
OUTPUT_FILE="${GITHUB_OUTPUT:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
  --python)
    PYTHON_BIN="${2:-}"
    shift 2
    ;;
  --mode)
    MODE="${2:-}"
    shift 2
    ;;
  --diagnostics-dir)
    DIAGNOSTICS_DIR="${2:-}"
    shift 2
    ;;
  --output-file)
    OUTPUT_FILE="${2:-}"
    shift 2
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  *)
    echo "Unknown argument: $1" >&2
    usage >&2
    exit 2
    ;;
  esac
done

if [[ -z "$PYTHON_BIN" ]]; then
  echo "--python is required" >&2
  exit 2
fi
if [[ "$MODE" != "permissive" && "$MODE" != "strict" ]]; then
  echo "--mode must be one of: permissive, strict" >&2
  exit 2
fi
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "python executable not found or not executable: $PYTHON_BIN" >&2
  exit 2
fi
PYTHON_BIN="$("$PYTHON_BIN" - <<'PY'
import sys
print(sys.executable)
PY
)"

write_output() {
  local key="$1"
  local value="$2"
  if [[ -n "$OUTPUT_FILE" ]]; then
    {
      printf '%s<<__CXC_EOF__\n' "$key"
      printf '%s\n' "$value"
      printf '__CXC_EOF__\n'
    } >>"$OUTPUT_FILE"
  fi
}

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SESSION_DIR="${DIAGNOSTICS_DIR}/${TIMESTAMP}"
mkdir -p "$SESSION_DIR"

SUMMARY_LOG="$SESSION_DIR/summary.log"
touch "$SUMMARY_LOG"

log() {
  local msg="$1"
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$msg" | tee -a "$SUMMARY_LOG"
}

run_cmd_capture() {
  local outfile="$1"
  shift
  set +e
  "$@" >"$outfile" 2>&1
  local rc=$?
  set -e
  return "$rc"
}

collect_baseline_diagnostics() {
  log "Collecting baseline diagnostics into $SESSION_DIR"
  {
    echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "mode=$MODE"
    echo "python_bin=$PYTHON_BIN"
    echo "pwd=$(pwd)"
    uname -a || true
    if [[ -f /etc/os-release ]]; then
      cat /etc/os-release
    fi
  } >"$SESSION_DIR/environment.txt"

  run_cmd_capture "$SESSION_DIR/python-version.txt" "$PYTHON_BIN" -VV || true
  run_cmd_capture "$SESSION_DIR/python-platform.txt" "$PYTHON_BIN" - <<'PY' || true
import platform
import sys
import sysconfig

print(f"executable={sys.executable}")
print(f"version={sys.version}")
print(f"platform={platform.platform()}")
print(f"libc={platform.libc_ver()}")
print(f"implementation={platform.python_implementation()}")
print(f"soabi={sysconfig.get_config_var('SOABI')}")
print(f"cc={sysconfig.get_config_var('CC')}")
print(f"cflags={sysconfig.get_config_var('CFLAGS')}")
print(f"ldflags={sysconfig.get_config_var('LDFLAGS')}")
PY
  run_cmd_capture "$SESSION_DIR/uv-version.txt" uv --version || true
}

collect_shared_object_diagnostics() {
  local phase="$1"
  local so_list_file="$SESSION_DIR/${phase}-cinderx-so-files.txt"
  find .venv -type f \( -name 'cinderx*.so' -o -name '_cinderx*.so' \) 2>/dev/null | sort >"$so_list_file" || true
  if [[ ! -s "$so_list_file" ]]; then
    log "No cinderx shared objects found during $phase"
    return 0
  fi

  while IFS= read -r so_file; do
    [[ -z "$so_file" ]] && continue
    local base
    base="$(basename "$so_file")"
    run_cmd_capture "$SESSION_DIR/${phase}-${base}.file.txt" file "$so_file" || true
    run_cmd_capture "$SESSION_DIR/${phase}-${base}.ldd.txt" ldd "$so_file" || true
    run_cmd_capture "$SESSION_DIR/${phase}-${base}.readelf-dynamic.txt" readelf -d "$so_file" || true
    run_cmd_capture "$SESSION_DIR/${phase}-${base}.readelf-symbols.txt" readelf -Ws "$so_file" || true
  done <"$so_list_file"
}

run_import_probe() {
  local label="$1"
  local probe_out="$SESSION_DIR/probe-${label}.txt"

  set +e
  "$PYTHON_BIN" -X faulthandler - <<'PY' >"$probe_out" 2>&1
import importlib.util
import platform
import sys

print(f"python_executable={sys.executable}")
print(f"python_version={sys.version}")
print(f"platform={platform.platform()}")
print(f"libc={platform.libc_ver()}")
spec = importlib.util.find_spec("cinderx")
print(f"cinderx_spec={getattr(spec, 'origin', None)}")

import cinderx
print(f"cinderx_file={cinderx.__file__}")
print("probe_status=ok")
PY
  local probe_rc=$?
  set -e

  if [[ "$probe_rc" -eq 0 ]]; then
    log "Import probe succeeded for attempt '$label'"
  else
    log "Import probe failed for attempt '$label' with exit code $probe_rc"
    if [[ "$probe_rc" -eq 139 || "$probe_rc" -eq 134 ]]; then
      log "Probe appears to have crashed (segfault/abort). Capturing gdb trace when available."
      if command -v gdb >/dev/null 2>&1; then
        run_cmd_capture "$SESSION_DIR/gdb-${label}.txt" gdb -batch -q -ex run -ex bt --args "$PYTHON_BIN" -X faulthandler -c "import cinderx" || true
      fi
    fi
  fi

  return "$probe_rc"
}

ATTEMPT_INDEX=0
SUCCESS="false"
SUCCESS_ATTEMPT=""
LAST_INSTALL_RC=0
LAST_PROBE_RC=0

attempt_install_and_probe() {
  local label="$1"
  shift
  ATTEMPT_INDEX=$((ATTEMPT_INDEX + 1))
  local install_log="$SESSION_DIR/install-${ATTEMPT_INDEX}-${label}.txt"

  log "Starting install attempt ${ATTEMPT_INDEX} (${label})"
  set +e
  "$@" >"$install_log" 2>&1
  local install_rc=$?
  set -e
  LAST_INSTALL_RC="$install_rc"
  write_output "attempt_${ATTEMPT_INDEX}_label" "$label"
  write_output "attempt_${ATTEMPT_INDEX}_install_log" "$install_log"

  if [[ "$install_rc" -ne 0 ]]; then
    log "Install attempt '${label}' failed with exit code $install_rc"
    LAST_PROBE_RC=0
    return 1
  fi

  collect_shared_object_diagnostics "attempt-${ATTEMPT_INDEX}-${label}"
  set +e
  run_import_probe "$label"
  local probe_rc=$?
  set -e
  if [[ "$probe_rc" -eq 0 ]]; then
    SUCCESS="true"
    SUCCESS_ATTEMPT="$label"
    LAST_PROBE_RC=0
    return 0
  fi

  LAST_PROBE_RC="$probe_rc"
  return 1
}

collect_baseline_diagnostics

# Attempt 1: default installer path (wheel if available).
attempt_install_and_probe "default-wheel" uv pip install --python "$PYTHON_BIN" cinderx || true

if [[ "$SUCCESS" != "true" ]]; then
  # Attempt 2: rebuild from source distribution.
  attempt_install_and_probe "source-rebuild" uv pip install --python "$PYTHON_BIN" --no-binary cinderx --reinstall cinderx || true
fi

if [[ "$SUCCESS" != "true" ]]; then
  # Attempt 3: fmt workaround for source compile issues (primarily observed on macOS).
  attempt_install_and_probe "source-rebuild-fmt-workaround" env CXXFLAGS='-include cstdlib' CMAKE_ARGS='-DCMAKE_VERBOSE_MAKEFILE:BOOL=ON' uv pip install --python "$PYTHON_BIN" -v --no-cache-dir --no-binary cinderx --reinstall cinderx || true
fi

write_output "installed" "$SUCCESS"
write_output "python_bin" "$PYTHON_BIN"
if [[ "$SUCCESS" == "true" ]]; then
  write_output "cinderx_bin" "$PYTHON_BIN"
  write_output "selected_attempt" "$SUCCESS_ATTEMPT"
else
  write_output "cinderx_bin" ""
  write_output "selected_attempt" ""
fi
write_output "last_install_exit" "$LAST_INSTALL_RC"
write_output "last_probe_exit" "$LAST_PROBE_RC"
write_output "diagnostics_dir" "$SESSION_DIR"

if [[ "$SUCCESS" == "true" ]]; then
  log "CinderX install+probe succeeded via attempt '${SUCCESS_ATTEMPT}'"
  exit 0
fi

log "CinderX install+probe failed across all attempts"
if [[ "$MODE" == "strict" ]]; then
  exit 1
fi
exit 0
