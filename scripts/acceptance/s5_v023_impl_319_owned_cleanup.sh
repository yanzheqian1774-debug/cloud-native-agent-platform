#!/usr/bin/env bash

# Cleanup is intentionally limited to process IDs started by the current 319 run.
# It does not remove databases, runtime files, logs, screenshots, or other evidence.
s5_319_cleanup_owned_processes() {
  local pid
  for pid in "${server_pid:-}" "${mock_pid:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}

s5_319_exit_trap() {
  local exit_code=$?
  trap - EXIT INT TERM
  s5_319_cleanup_owned_processes
  exit "$exit_code"
}

s5_319_signal_trap() {
  local exit_code="$1"
  trap - EXIT INT TERM
  s5_319_cleanup_owned_processes
  exit "$exit_code"
}
