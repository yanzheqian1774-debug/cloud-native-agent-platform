#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../.."
  pwd
)"

cd "$ROOT_DIR"

NAMESPACE="${NAMESPACE:-agent-workloads}"
SUCCESS_WORKFLOW="${SUCCESS_WORKFLOW:-engineering-s4-009-004}"
FAILED_WORKFLOW="${FAILED_WORKFLOW:-engineering-s4-009-001}"
CONSOLE_URL="${CONSOLE_URL:-http://127.0.0.1:8000}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "============================================================"
echo "CONSOLE REAL WORKFLOW E2E"
echo "============================================================"

echo
echo "Namespace:        $NAMESPACE"
echo "Success workflow: $SUCCESS_WORKFLOW"
echo "Failed workflow:  $FAILED_WORKFLOW"
echo "Console URL:      $CONSOLE_URL"

echo
echo "===== PRECHECK ====="

kubectl config current-context

curl -fsS "$CONSOLE_URL/healthz" >/dev/null

kubectl get workflow \
  "$SUCCESS_WORKFLOW" \
  -n "$NAMESPACE" \
  >/dev/null

kubectl get workflow \
  "$FAILED_WORKFLOW" \
  -n "$NAMESPACE" \
  >/dev/null

echo "Precheck PASS"

snapshot() {
  local phase="$1"

  kubectl get workflow \
    "$SUCCESS_WORKFLOW" \
    -n "$NAMESPACE" \
    -o json \
    > "$TMP_DIR/success-workflow-$phase.json"

  kubectl get tasks.agentos.io \
    -n "$NAMESPACE" \
    -l "agentos.io/workflow=$SUCCESS_WORKFLOW" \
    -o json \
    > "$TMP_DIR/success-tasks-$phase.json"

  kubectl get workflow \
    "$FAILED_WORKFLOW" \
    -n "$NAMESPACE" \
    -o json \
    > "$TMP_DIR/failed-workflow-$phase.json"

  kubectl get tasks.agentos.io \
    -n "$NAMESPACE" \
    -l "agentos.io/workflow=$FAILED_WORKFLOW" \
    -o json \
    > "$TMP_DIR/failed-tasks-$phase.json"
}

echo
echo "===== SNAPSHOT BEFORE ====="

snapshot before

echo "Snapshot PASS"

echo
echo "===== CONSOLE READ ====="

curl -fsS \
  "$CONSOLE_URL/api/v1/workflows" \
  > "$TMP_DIR/workflow-list.json"

curl -fsS \
  "$CONSOLE_URL/api/v1/workflows/$NAMESPACE/$SUCCESS_WORKFLOW" \
  > "$TMP_DIR/success-api.json"

curl -fsS \
  "$CONSOLE_URL/api/v1/workflows/$NAMESPACE/$FAILED_WORKFLOW" \
  > "$TMP_DIR/failed-api.json"

echo "Console read PASS"

echo
echo "===== SNAPSHOT AFTER ====="

snapshot after

echo "Snapshot PASS"

echo
echo "===== VALIDATION ====="

python3 \
  scripts/e2e/console_real_workflow.py \
  "$TMP_DIR"

echo
echo "============================================================"
echo "CONSOLE REAL WORKFLOW E2E COMPLETE"
echo "============================================================"
