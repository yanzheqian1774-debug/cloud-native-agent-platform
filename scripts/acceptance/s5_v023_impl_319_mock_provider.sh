#!/usr/bin/env bash
set -euo pipefail

# Task-owned S5-V023-IMPL-319 acceptance runner. It expects an existing,
# caller-owned PostgreSQL database and never creates, drops, or cleans one.
repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repository_root"
repository_pythonpath="conformance_harness/src:core/src:gateway/src:operator/src:runtime/src:console/backend/src:console/backend/tests:experiments/s5-spike-005-runtime-target-manifest:experiments/s5-spike-007-capability-rest-fixtures"
export PYTHONPATH="$repository_pythonpath${PYTHONPATH:+:$PYTHONPATH}"

: "${ACCEPTANCE_DATABASE_URL:?ACCEPTANCE_DATABASE_URL is required}"
evidence_root="${S5_319_EVIDENCE_DIR:-${RUNNER_TEMP:?RUNNER_TEMP or S5_319_EVIDENCE_DIR is required}}"
export S5_319_EVIDENCE_DIR="$evidence_root"
public_port="${S5_319_PUBLIC_PORT:-19443}"
control_port="${S5_319_CONTROL_PORT:-19444}"
mock_port="${S5_319_MOCK_PORT:-19445}"
runtime_dir="$evidence_root/s5-v023-impl-319-runtime"
cert="$evidence_root/s5-v023-impl-319.crt"
key="$evidence_root/s5-v023-impl-319.key"
control_token_file="$evidence_root/s5-v023-impl-319-control-token"
credential_file="$evidence_root/s5-v023-impl-319-fake-provider-key"
startup="$evidence_root/s5-v023-impl-319-startup.json"
browser_report="$evidence_root/s5-v023-impl-319-playwright.json"
browser_stderr="$evidence_root/s5-v023-impl-319-playwright.stderr.log"
browser_exit="$evidence_root/s5-v023-impl-319-playwright.exit"
output_dir="$evidence_root/s5-v023-impl-319-playwright"
mock_log="$evidence_root/s5-v023-impl-319-mock.log"
server_log="$evidence_root/s5-v023-impl-319-server.log"
readiness="$evidence_root/s5-v023-impl-319-readiness.txt"
build_mode="$evidence_root/s5-v023-impl-319-build-mode.txt"
mock_pid=""
server_pid=""

source scripts/acceptance/s5_v023_impl_319_owned_cleanup.sh
trap s5_319_exit_trap EXIT
trap 's5_319_signal_trap 130' INT
trap 's5_319_signal_trap 143' TERM

mkdir -p "$runtime_dir" "$output_dir"

# Fail before any server or browser starts if Vite produced only the shell route
# or omitted the Draft Assistance feature branch.
BUILD_MODE_FILE="$build_mode" python3 - <<'PY'
import os
from pathlib import Path

assets = [item.read_bytes() for item in Path("console/frontend/dist").rglob("*") if item.is_file()]
results = []
for marker in ("新建对话", "AI 问题理解与草稿辅助"):
    results.append((marker, any(marker.encode("utf-8") in payload for payload in assets)))
Path(os.environ["BUILD_MODE_FILE"]).write_text(
    "".join(f"{marker}={str(found).lower()}\n" for marker, found in results),
    encoding="utf-8",
)
missing = [marker for marker, found in results if not found]
if missing:
    raise SystemExit(f"FRONTEND_BUILD_MODE_INVALID:{','.join(missing)}")
PY

openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -keyout "$key" -out "$cert" -subj "/CN=127.0.0.1" \
  -addext "subjectAltName=IP:127.0.0.1" >/dev/null 2>&1
printf '%s' 'local-mock-key-319' > "$credential_file"
chmod 600 "$credential_file"
control_token="$(openssl rand -hex 32)"
applicant="$(openssl rand -hex 32)"
administrator="$(openssl rand -hex 32)"
unused_list="$(openssl rand -hex 32)"
unused_scope="$(openssl rand -hex 32)"
unused_grant="$(openssl rand -hex 32)"
for value in "$control_token" "$applicant" "$administrator" "$unused_list" "$unused_scope" "$unused_grant"; do
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "::add-mask::$value"
  fi
done
printf '%s' "$control_token" > "$control_token_file"
digest() { printf '%s' "$1" | sha256sum | cut -d ' ' -f 1; }

uv run python console/backend/tests/s5_v023_impl_319_mock_responses_server.py \
  --port "$mock_port" --cert "$cert" --key "$key" >"$mock_log" 2>&1 &
mock_pid=$!
export S5_319_DRAFT_ASSISTANCE=1
export S5_319_MOCK_RESPONSES_URL="https://127.0.0.1:$mock_port/v1/responses"
S5_319_MOCK_CA_FILE="$cert" \
S5_319_MOCK_CREDENTIAL_FILE="$credential_file" \
uv run python console/backend/tests/s5_v023_impl_310_real_browser_server.py \
  --database-url "$ACCEPTANCE_DATABASE_URL" \
  --runtime-dir "$runtime_dir" \
  --dist console/frontend/dist \
  --public-port "$public_port" --control-port "$control_port" \
  --cert "$cert" --key "$key" \
  --control-token-file "$control_token_file" \
  --startup-status "$startup" \
  --full-credential-sha256 "$(digest "$applicant")" \
  --admin-credential-sha256 "$(digest "$administrator")" \
  --list-credential-sha256 "$(digest "$unused_list")" \
  --wrong-scope-credential-sha256 "$(digest "$unused_scope")" \
  --wrong-grant-credential-sha256 "$(digest "$unused_grant")" \
  --rel-316 >"$server_log" 2>&1 &
server_pid=$!

listener_ready=false
for _ in $(seq 1 120); do
  if curl --insecure --fail --silent "https://127.0.0.1:$mock_port/ready" >/dev/null \
    && curl --insecure --fail --silent "https://127.0.0.1:$public_port/api/workbench/v1/login" >/dev/null \
    && curl --fail --silent "http://127.0.0.1:$control_port/ready" >/dev/null; then
    listener_ready=true
    break
  fi
  if ! kill -0 "$mock_pid" 2>/dev/null || ! kill -0 "$server_pid" 2>/dev/null; then
    break
  fi
  sleep 0.25
done
printf 'ready=%s\n' "$listener_ready" > "$readiness"
test "$listener_ready" = true

browser_status=0
if (
  cd console/frontend
  S5_319_WORKBENCH_URL="https://127.0.0.1:$public_port" \
  S5_319_APPLICANT_CREDENTIAL="$applicant" \
  S5_319_ADMIN_CREDENTIAL="$administrator" \
  PLAYWRIGHT_OUTPUT_DIR="$output_dir" \
  npx playwright test --config playwright.s5-319.config.ts \
    --workers=1 --retries=0 --forbid-only --reporter=json \
    >"$browser_report" 2>"$browser_stderr"
); then
  browser_status=0
else
  browser_status=$?
fi
printf '%s\n' "$browser_status" > "$browser_exit"
if (( browser_status != 0 )); then
  exit "$browser_status"
fi

SOURCE_SHA="$(git rev-parse HEAD)" TREE_SHA="$(git rev-parse 'HEAD^{tree}')" \
BUILD_SHA="$(find console/frontend/dist -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d ' ' -f 1)" \
OUTPUT_DIR="$output_dir" STARTUP="$startup" REPORT="$browser_report" \
python3 - <<'PY'
import glob
import hashlib
import json
import os

files = {}
for artifact in sorted(glob.glob(os.environ["OUTPUT_DIR"] + "/**/*", recursive=True)):
    if os.path.isfile(artifact):
        with open(artifact, "rb") as stream:
            files[os.path.relpath(artifact, os.environ["OUTPUT_DIR"])] = hashlib.sha256(stream.read()).hexdigest()
with open(os.environ["STARTUP"], encoding="utf-8") as stream:
    startup_document = json.load(stream)
with open(os.environ["REPORT"], encoding="utf-8") as stream:
    report_document = json.load(stream)
evidence = {
    "schemaVersion": "s5-v023-impl-319-mock-provider-acceptance.v1",
    "source": os.environ["SOURCE_SHA"],
    "tree": os.environ["TREE_SHA"],
    "frontendBuildDigest": os.environ["BUILD_SHA"],
    "provider": "LOCAL_HTTPS_OPENAI_RESPONSES_MOCK",
    "realProviderCalls": 0,
    "startup": startup_document,
    "playwrightStats": report_document.get("stats"),
    "artifactSha256": files,
}
with open(os.environ["S5_319_EVIDENCE_DIR"] + "/s5-v023-impl-319-evidence.json", "w", encoding="utf-8") as stream:
    json.dump(evidence, stream, sort_keys=True, indent=2)
PY
