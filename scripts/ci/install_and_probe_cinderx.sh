#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage:
  install_and_probe_cinderx.sh --python <python_bin> [--mode <permissive|strict>] [--require-static-loader] [--diagnostics-dir <dir>] [--output-file <path>]

Notes:
  - Writes step outputs to --output-file (or $GITHUB_OUTPUT when present).
  - Attempts staged install strategies and probes `import cinderx` after each.
EOF
}

PYTHON_BIN=""
MODE="permissive"
REQUIRE_STATIC_LOADER="false"
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
  --require-static-loader)
    REQUIRE_STATIC_LOADER="true"
    shift 1
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
    echo "require_static_loader=$REQUIRE_STATIC_LOADER"
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

resolve_installed_strict_stubs_path() {
  local report_file="$SESSION_DIR/strict-stubs-installed.txt"
  if ! run_cmd_capture "$report_file" "$PYTHON_BIN" - <<'PY'; then
import pathlib

import cinderx

cinderx_file = getattr(cinderx, "__file__", "")
candidate = ""
exists = 0
if cinderx_file:
    candidate_path = pathlib.Path(cinderx_file).resolve().parent / "compiler" / "strict" / "stubs"
    candidate = str(candidate_path)
    exists = int(candidate_path.is_dir())
print(f"STRICT_STUBS_CANDIDATE={candidate}")
print(f"STRICT_STUBS_EXISTS={exists}")
PY
    log "Failed to inspect installed strict stubs path; see $report_file"
    return 1
  fi

  local candidate
  candidate="$(sed -n 's/^STRICT_STUBS_CANDIDATE=//p' "$report_file" | tail -n 1)"
  local exists
  exists="$(sed -n 's/^STRICT_STUBS_EXISTS=//p' "$report_file" | tail -n 1)"
  if [[ "$exists" == "1" && -n "$candidate" ]]; then
    STRICT_STUBS_PATH="$candidate"
    STRICT_STUBS_SOURCE="site-packages"
    log "Found strict stubs in installed cinderx package: $STRICT_STUBS_PATH"
    return 0
  fi

  if [[ -n "$candidate" ]]; then
    log "Installed cinderx strict stubs candidate is missing: $candidate"
  else
    log "Installed cinderx strict stubs candidate could not be determined."
  fi
  return 1
}

recover_strict_stubs_from_upstream_sparse() {
  local repo_dir="$SESSION_DIR/upstream-cinderx-stubs"
  local recover_log="$SESSION_DIR/strict-stubs-upstream-recover.txt"

  log "Attempting strict stubs recovery via sparse upstream clone"
  set +e
  git clone --filter=blob:none --depth 1 --sparse https://github.com/facebookincubator/cinderx.git "$repo_dir" >"$recover_log" 2>&1
  local clone_rc=$?
  set -e
  if [[ "$clone_rc" -ne 0 ]]; then
    log "Sparse clone for strict stubs recovery failed (rc=$clone_rc); see $recover_log"
    return 1
  fi

  set +e
  git -C "$repo_dir" sparse-checkout set cinderx/PythonLib/cinderx/compiler/strict/stubs >>"$recover_log" 2>&1
  local sparse_rc=$?
  set -e
  if [[ "$sparse_rc" -ne 0 ]]; then
    log "Sparse checkout for strict stubs recovery failed (rc=$sparse_rc); see $recover_log"
    return 1
  fi

  local candidate="$repo_dir/cinderx/PythonLib/cinderx/compiler/strict/stubs"
  if [[ -d "$candidate" ]]; then
    STRICT_STUBS_PATH="$candidate"
    STRICT_STUBS_SOURCE="upstream-sparse"
    log "Recovered strict stubs from upstream sparse checkout: $STRICT_STUBS_PATH"
    return 0
  fi

  log "Upstream sparse checkout did not produce strict stubs directory at $candidate"
  return 1
}

run_static_loader_probe() {
  local strict_stubs_path="$1"
  local probe_out="$SESSION_DIR/probe-static-loader.txt"

  set +e
  PYTHONSTRICTMODULESTUBSPATH="$strict_stubs_path" "$PYTHON_BIN" -X faulthandler - <<'PY' >"$probe_out" 2>&1
import importlib
import json
import os
import pathlib
import sys
import tempfile

payload = {
    "python_executable": sys.executable,
    "strict_stubs_path": os.environ.get("PYTHONSTRICTMODULESTUBSPATH", ""),
}

import cinderx
payload["cinderx_file"] = getattr(cinderx, "__file__", None)
if hasattr(cinderx, "init"):
    cinderx.init()

strict_loader = importlib.import_module("cinderx.compiler.strict.loader")
strict_loader.install()

with tempfile.TemporaryDirectory(prefix="cxc-static-probe-") as raw_temp:
    temp_root = pathlib.Path(raw_temp)
    module_name = "cxc_static_probe_module"
    module_path = temp_root / f"{module_name}.py"
    module_path.write_text(
        "import __static__\n\n"
        "def add(x: int, y: int) -> int:\n"
        "    return x + y\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(temp_root))
    module = importlib.import_module(module_name)
    payload["probe_module"] = module_name
    payload["probe_result"] = module.add(2, 3)
    try:
        static_api = importlib.import_module("cinderx.static")
    except Exception:
        static_api = None
    if static_api is not None and hasattr(static_api, "is_static_module"):
        payload["is_static_module"] = bool(static_api.is_static_module(module))

print(json.dumps(payload, sort_keys=True))
PY
  local probe_rc=$?

  if [[ "$probe_rc" -eq 0 ]]; then
    log "Strict/static loader probe succeeded (stubs: $strict_stubs_path)"
  else
    log "Strict/static loader probe failed with exit code $probe_rc (stubs: $strict_stubs_path); see $probe_out"
  fi
  return "$probe_rc"
}

ATTEMPT_INDEX=0
SUCCESS="false"
SUCCESS_ATTEMPT=""
LAST_INSTALL_RC=0
LAST_PROBE_RC=0
STRICT_STUBS_PATH=""
STRICT_STUBS_SOURCE="none"
STRICT_LOADER_READY="false"
STATIC_PROBE_READY="false"

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

if [[ "$SUCCESS" == "true" ]]; then
  resolve_installed_strict_stubs_path || true
  if [[ -z "$STRICT_STUBS_PATH" || ! -d "$STRICT_STUBS_PATH" ]]; then
    recover_strict_stubs_from_upstream_sparse || true
  fi

  if [[ -n "$STRICT_STUBS_PATH" && -d "$STRICT_STUBS_PATH" ]]; then
    set +e
    run_static_loader_probe "$STRICT_STUBS_PATH"
    static_probe_rc=$?
    set -e
    if [[ "$static_probe_rc" -eq 0 ]]; then
      STRICT_LOADER_READY="true"
      STATIC_PROBE_READY="true"
    fi
  else
    log "No strict stubs path was resolved; static loader probe skipped."
  fi
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
write_output "strict_stubs_path" "$STRICT_STUBS_PATH"
write_output "strict_stubs_source" "$STRICT_STUBS_SOURCE"
write_output "strict_loader_ready" "$STRICT_LOADER_READY"
write_output "static_probe_ready" "$STATIC_PROBE_READY"
write_output "require_static_loader" "$REQUIRE_STATIC_LOADER"

if [[ "$SUCCESS" == "true" ]]; then
  if [[ "$REQUIRE_STATIC_LOADER" == "true" && "$STATIC_PROBE_READY" != "true" ]]; then
    log "CinderX install succeeded, but static loader requirement failed."
    if [[ -z "$STRICT_STUBS_PATH" ]]; then
      log "No strict stubs path was available."
    else
      log "Static probe did not pass with strict stubs path: $STRICT_STUBS_PATH"
    fi
    exit 1
  fi
  log "CinderX install+probe succeeded via attempt '${SUCCESS_ATTEMPT}'"
  exit 0
fi

log "CinderX install+probe failed across all attempts"
if [[ "$MODE" == "strict" ]]; then
  exit 1
fi
exit 0
