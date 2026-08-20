#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  pwd
)"

CLUSTER_NAME="agentos-quickstart"
CONTEXT="kind-${CLUSTER_NAME}"
OPERATOR_IMAGE="enterprise-agent-operator:quickstart"
RUNTIME_IMAGE="enterprise-agent-runtime:quickstart"
NAMESPACE="agent-workloads"
OWNER_NAMESPACE="kube-system"
OWNER_CONFIGMAP="agentos-quickstart-owner"

cd "$ROOT_DIR"

require_command() {
  local command_name="$1"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $command_name" >&2
    exit 1
  fi
}

cluster_exists() {
  kind get clusters 2>/dev/null | grep -Fxq "$CLUSTER_NAME"
}

cluster_is_owned() {
  kubectl --context "$CONTEXT" \
    -n "$OWNER_NAMESPACE" \
    get configmap "$OWNER_CONFIGMAP" \
    -o jsonpath='{.data.managed-by}' 2>/dev/null \
    | grep -Fxq 'scripts/quickstart.sh'
}

require_owned_cluster() {
  if ! cluster_exists; then
    echo "ERROR: Quick Start cluster '$CLUSTER_NAME' does not exist." >&2
    echo "Run './scripts/quickstart.sh' first." >&2
    exit 1
  fi

  if ! cluster_is_owned; then
    echo "ERROR: cluster '$CLUSTER_NAME' has no Quick Start ownership marker." >&2
    echo "Refusing to modify or delete it; handle the cluster manually." >&2
    exit 1
  fi
}

preflight() {
  require_command docker
  require_command kubectl
  require_command kind

  if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker daemon is not available." >&2
    exit 1
  fi
}

print_cleanup_hint() {
  echo "Run './scripts/quickstart.sh cleanup' to delete the Quick Start cluster."
}

start() {
  local started_at
  local platform_ready_at
  local first_value_at
  local task_phase
  local task_attempts
  local task_result

  preflight

  if cluster_exists; then
    echo "ERROR: kind cluster '$CLUSTER_NAME' already exists." >&2
    echo "Refusing to modify it; preserve or handle it manually." >&2
    exit 1
  fi

  started_at="$(date +%s)"

  echo "==> Building Quick Start images"
  docker build \
    -f operator/Dockerfile \
    -t "$OPERATOR_IMAGE" \
    .
  docker build \
    -f runtime/Dockerfile \
    -t "$RUNTIME_IMAGE" \
    .

  echo "==> Creating dedicated cluster: $CLUSTER_NAME"
  kind create cluster \
    --name "$CLUSTER_NAME" \
    --wait 120s
  kubectl --context "$CONTEXT" \
    -n "$OWNER_NAMESPACE" \
    create configmap "$OWNER_CONFIGMAP" \
    --from-literal=managed-by=scripts/quickstart.sh

  echo "==> Loading local images"
  kind load docker-image \
    --name "$CLUSTER_NAME" \
    "$OPERATOR_IMAGE" \
    "$RUNTIME_IMAGE"

  echo "==> Installing the Agent Control Plane"
  kubectl --context "$CONTEXT" apply -f manifests/dev/namespaces.yaml
  kubectl --context "$CONTEXT" apply -f manifests/crd
  kubectl --context "$CONTEXT" apply -f manifests/operator/service-account.yaml
  kubectl --context "$CONTEXT" apply -f manifests/operator/rbac.yaml
  kubectl set image \
    -f manifests/operator/deployment.yaml \
    "operator=$OPERATOR_IMAGE" \
    --local \
    -o yaml \
    | kubectl --context "$CONTEXT" apply -f -
  kubectl --context "$CONTEXT" \
    -n agent-system \
    rollout status deployment/agent-operator \
    --timeout=120s

  platform_ready_at="$(date +%s)"
  echo "PLATFORM READY: $((platform_ready_at - started_at))s"

  echo "==> Creating the mock-backed Agent"
  kubectl patch \
    --local \
    -f manifests/agents/researcher.yaml \
    --type merge \
    -p "{\"spec\":{\"runtime\":{\"image\":\"$RUNTIME_IMAGE\"}}}" \
    -o yaml \
    | kubectl --context "$CONTEXT" apply -f -
  kubectl --context "$CONTEXT" \
    -n "$NAMESPACE" \
    wait \
    --for=jsonpath='{.status.phase}'=Running \
    agents.agentos.io/researcher-agent \
    --timeout=120s
  kubectl --context "$CONTEXT" \
    -n "$NAMESPACE" \
    rollout status deployment/researcher-agent \
    --timeout=120s

  echo "==> Running the first Agent Task"
  kubectl --context "$CONTEXT" apply -f manifests/tasks/example-task.yaml
  kubectl --context "$CONTEXT" \
    -n "$NAMESPACE" \
    wait \
    --for=jsonpath='{.status.phase}'=Succeeded \
    tasks.agentos.io/research-task \
    --timeout=120s

  task_phase="$(
    kubectl --context "$CONTEXT" \
      -n "$NAMESPACE" \
      get tasks.agentos.io/research-task \
      -o jsonpath='{.status.phase}'
  )"
  task_attempts="$(
    kubectl --context "$CONTEXT" \
      -n "$NAMESPACE" \
      get tasks.agentos.io/research-task \
      -o jsonpath='{.status.attempts}'
  )"
  task_result="$(
    kubectl --context "$CONTEXT" \
      -n "$NAMESPACE" \
      get tasks.agentos.io/research-task \
      -o jsonpath='{.status.result}'
  )"
  first_value_at="$(date +%s)"

  echo
  echo "FIRST VALUE: PASS"
  echo "Task:     research-task"
  echo "Phase:    $task_phase"
  echo "Attempts: $task_attempts"
  echo "Result:   $task_result"
  echo "TIME TO FIRST VALUE: $((first_value_at - started_at))s"
  echo
  echo "Next: ./scripts/quickstart.sh workflow"
  print_cleanup_hint
}

workflow() {
  local started_at
  local workflow_phase
  local workflow_tasks
  local downstream_input

  preflight

  require_owned_cluster

  started_at="$(date +%s)"

  echo "==> Running the four-node Workflow"
  kubectl --context "$CONTEXT" apply -f manifests/workflows/example-workflow.yaml
  kubectl --context "$CONTEXT" \
    -n "$NAMESPACE" \
    wait \
    --for=jsonpath='{.status.phase}'=Succeeded \
    workflows.agentos.io/research-workflow \
    --timeout=180s

  workflow_phase="$(
    kubectl --context "$CONTEXT" \
      -n "$NAMESPACE" \
      get workflows.agentos.io/research-workflow \
      -o jsonpath='{.status.phase}'
  )"
  workflow_tasks="$(
    kubectl --context "$CONTEXT" \
      -n "$NAMESPACE" \
      get workflows.agentos.io/research-workflow \
      -o jsonpath='{.status.taskCount}'
  )"
  downstream_input="$(
    kubectl --context "$CONTEXT" \
      -n "$NAMESPACE" \
      get tasks.agentos.io/research-workflow-market \
      -o jsonpath='{.spec.input.prompt}'
  )"

  echo
  echo "PRODUCT UNDERSTANDING: PASS"
  echo "Workflow: research-workflow"
  echo "Phase:    $workflow_phase"
  echo "Tasks:    $workflow_tasks"
  echo "Elapsed:  $(($(date +%s) - started_at))s"
  echo
  echo "Resolved downstream input:"
  echo "$downstream_input"
  echo
  print_cleanup_hint
}

cleanup() {
  require_command kind
  require_command kubectl

  if ! cluster_exists; then
    echo "Quick Start cluster '$CLUSTER_NAME' does not exist; nothing to delete."
    return
  fi

  require_owned_cluster

  kind delete cluster --name "$CLUSTER_NAME"
  echo "Deleted Quick Start cluster '$CLUSTER_NAME'."
  echo "Local images '$OPERATOR_IMAGE' and '$RUNTIME_IMAGE' were retained."
}

usage() {
  echo "Usage: $0 [start|workflow|cleanup]"
}

case "${1:-start}" in
  start)
    start
    ;;
  workflow)
    workflow
    ;;
  cleanup)
    cleanup
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
