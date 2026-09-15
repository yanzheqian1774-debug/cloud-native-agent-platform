#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
artifact_dir="${1:-$(mktemp -d /tmp/s5-v023-rel-317.XXXXXX)}"
database_url="${REL_317_DATABASE_URL:?REL_317_DATABASE_URL_REQUIRED}"
public_port="${REL_317_PUBLIC_PORT:-18427}"
control_port="${REL_317_CONTROL_PORT:-18428}"
runtime_dir="$artifact_dir/runtime"
cert_path="$artifact_dir/rel-317.crt"
key_path="$artifact_dir/rel-317.key"
token_path="$artifact_dir/control-token"
server_log="$artifact_dir/server.log"
startup_status="$artifact_dir/startup.json"
raw_report="$artifact_dir/playwright.json"
output_dir="$artifact_dir/playwright-output"

mkdir -p "$artifact_dir"
applicant_credential="$(openssl rand -hex 32)"
admin_credential="$(openssl rand -hex 32)"
list_credential="$(openssl rand -hex 32)"
wrong_scope_credential="$(openssl rand -hex 32)"
wrong_grant_credential="$(openssl rand -hex 32)"
control_token="$(openssl rand -hex 32)"
printf '%s' "$control_token" > "$token_path"
chmod 600 "$token_path"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -keyout "$key_path" -out "$cert_path" -subj '/CN=127.0.0.1' \
  -addext 'subjectAltName=IP:127.0.0.1' >/dev/null 2>&1

digest() {
  printf '%s' "$1" | openssl dgst -sha256 -r | awk '{print $1}'
}

cd "$repo_root"
PYTHONPATH=console/backend/src:core/src uv run python \
  console/backend/tests/s5_v023_impl_310_real_browser_server.py \
  --rel-317 \
  --database-url "$database_url" \
  --runtime-dir "$runtime_dir" \
  --dist console/frontend/dist \
  --public-port "$public_port" \
  --control-port "$control_port" \
  --cert "$cert_path" \
  --key "$key_path" \
  --control-token-file "$token_path" \
  --startup-status "$startup_status" \
  --full-credential-sha256 "$(digest "$applicant_credential")" \
  --admin-credential-sha256 "$(digest "$admin_credential")" \
  --list-credential-sha256 "$(digest "$list_credential")" \
  --wrong-scope-credential-sha256 "$(digest "$wrong_scope_credential")" \
  --wrong-grant-credential-sha256 "$(digest "$wrong_grant_credential")" \
  >"$server_log" 2>&1 &
server_pid=$!

cleanup() {
  if kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  rm -f "$token_path" "$cert_path" "$key_path"
  rm -rf "$runtime_dir"
}
trap cleanup EXIT INT TERM

ready=false
for _ in $(seq 1 120); do
  if curl --insecure --fail --silent \
      "https://127.0.0.1:$public_port/api/workbench/v1/login" >/dev/null \
    && curl --fail --silent "http://127.0.0.1:$control_port/ready" >/dev/null; then
    ready=true
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    break
  fi
  sleep 0.25
done
if [ "$ready" != true ]; then
  echo "REL_317_HARNESS_START_FAILED artifact_dir=$artifact_dir" >&2
  exit 1
fi

cd "$repo_root/console/frontend"
REL_317_WORKBENCH_URL="https://127.0.0.1:$public_port" \
REL_317_APPLICANT_CREDENTIAL="$applicant_credential" \
REL_317_ADMIN_CREDENTIAL="$admin_credential" \
PLAYWRIGHT_OUTPUT_DIR="$output_dir" \
npx playwright test \
  --config playwright.rel-317.config.ts \
  --workers=1 --retries=0 --forbid-only --reporter=json >"$raw_report"

echo "REL_317_ACCEPTANCE_PASSED artifact_dir=$artifact_dir"
