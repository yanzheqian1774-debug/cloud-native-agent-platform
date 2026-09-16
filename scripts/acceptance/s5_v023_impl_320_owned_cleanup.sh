#!/usr/bin/env bash

# Cleanup is limited to process IDs started by the current 320 run. Databases,
# runtime files, logs, screenshots, and failed-run evidence are preserved.
s5_320_cleanup_owned_processes() {
  local pid
  for pid in "${server_pid:-}" "${mock_pid:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}

s5_320_exit_trap() {
  local exit_code=$?
  trap - EXIT INT TERM
  s5_320_cleanup_owned_processes
  exit "$exit_code"
}

s5_320_signal_trap() {
  local exit_code="$1"
  trap - EXIT INT TERM
  s5_320_cleanup_owned_processes
  exit "$exit_code"
}
