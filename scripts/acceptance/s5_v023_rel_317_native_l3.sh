#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
artifact_dir="${1:-/Users/tristan/.codex/evidence/s5-v023-rel-317-trusted-native/native-l3}"
database_url="${REL_317_DATABASE_URL:?REL_317_DATABASE_URL_REQUIRED}"
cluster_database_url="${REL_317_CLUSTER_DATABASE_URL:?REL_317_CLUSTER_DATABASE_URL_REQUIRED}"
cluster="s5-v023-rel-317"
namespace="s5-v023-rel-317-native"
source_sha="$(git -C "$repo_root" rev-parse HEAD)"
source_tree="$(git -C "$repo_root" rev-parse HEAD^{tree})"
short_sha="${source_sha:0:12}"
worker_image="s5-v023-rel-317-worker:$short_sha"
runtime_image="s5-v023-rel-317-runtime:$short_sha"

mkdir -p "$artifact_dir"
if kind get clusters | grep -Fx "$cluster" >/dev/null; then
  echo "REL_317_CLUSTER_ALREADY_EXISTS" >&2
  exit 1
fi

git -C "$repo_root" ls-files \
  pyproject.toml uv.lock core gateway operator runtime console/backend \
  scripts/acceptance/s5_v023_rel_317_native_l3.py \
  | sort > "$artifact_dir/build-context-files.txt"
while IFS= read -r path; do
  sha256sum "$repo_root/$path"
done < "$artifact_dir/build-context-files.txt" > "$artifact_dir/build-context.sha256"
sha256sum "$artifact_dir/build-context.sha256" > "$artifact_dir/build-context-summary.sha256"
printf 'source_sha=%s\nsource_tree=%s\nworker_image=%s\nruntime_image=%s\n' \
  "$source_sha" "$source_tree" "$worker_image" "$runtime_image" \
  > "$artifact_dir/build-parameters.txt"

docker build -f runtime/Dockerfile -t "$runtime_image" "$repo_root" \
  > "$artifact_dir/runtime-build.log" 2>&1
docker build -f- -t "$worker_image" "$repo_root" \
  > "$artifact_dir/worker-build.log" 2>&1 <<'DOCKERFILE'
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/
ENV UV_NO_DEV=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/core/src:/app/gateway/src:/app/operator/src:/app/runtime/src:/app/console/backend/src
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY core ./core
COPY gateway ./gateway
COPY operator ./operator
COPY runtime ./runtime
COPY console/backend ./console/backend
COPY scripts/acceptance/s5_v023_rel_317_native_l3.py ./scripts/acceptance/s5_v023_rel_317_native_l3.py
CMD ["/app/.venv/bin/python", "/app/scripts/acceptance/s5_v023_rel_317_native_l3.py", "worker", "--artifact-dir", "/evidence"]
DOCKERFILE

docker image inspect "$worker_image" --format '{{.Id}} {{json .RepoDigests}}' > "$artifact_dir/worker-image-digest.txt"
docker image inspect "$runtime_image" --format '{{.Id}} {{json .RepoDigests}}' > "$artifact_dir/runtime-image-digest.txt"
kind create cluster --name "$cluster" --wait 120s > "$artifact_dir/kind-create.log" 2>&1
kind load docker-image --name "$cluster" "$worker_image" "$runtime_image" > "$artifact_dir/kind-load.log" 2>&1
kubectl --context "kind-$cluster" apply -f "$repo_root/manifests/crd/tasks.agentos.io.yaml" > "$artifact_dir/crd-apply.log"
kubectl --context "kind-$cluster" create namespace "$namespace"

PYTHONPATH="$repo_root/console/backend/src:$repo_root/core/src:$repo_root/operator/src:$repo_root/gateway/src:$repo_root/runtime/src" \
  uv run --directory "$repo_root" python "$repo_root/scripts/acceptance/s5_v023_rel_317_native_l3.py" seed \
  --database-url "$database_url" --cluster-database-url "$cluster_database_url" \
  --artifact-dir "$artifact_dir" > "$artifact_dir/seed-output.json"

kubectl --context "kind-$cluster" -n "$namespace" create configmap rel-317-authority \
  --from-file="$artifact_dir/authority" > "$artifact_dir/configmap-create.log"
kubectl --context "kind-$cluster" apply -f - <<YAML
apiVersion: v1
kind: ServiceAccount
metadata: {name: rel-317-worker, namespace: $namespace}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {name: rel-317-worker, namespace: $namespace}
rules:
- apiGroups: ["agentos.io"]
  resources: ["tasks"]
  verbs: ["create", "get"]
- apiGroups: ["agentos.io"]
  resources: ["tasks/status"]
  verbs: ["patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: rel-317-worker, namespace: $namespace}
subjects:
- {kind: ServiceAccount, name: rel-317-worker, namespace: $namespace}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: Role, name: rel-317-worker}
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: researcher-agent, namespace: $namespace}
spec:
  replicas: 1
  selector: {matchLabels: {app: researcher-agent}}
  template:
    metadata: {labels: {app: researcher-agent}}
    spec:
      containers:
      - name: runtime
        image: $runtime_image
        imagePullPolicy: Never
        env:
        - {name: AGENT_NAME, value: researcher-agent}
        - {name: AGENT_NAMESPACE, value: $namespace}
        - {name: MODEL_PROVIDER, value: mock}
        - {name: MODEL_NAME, value: rel-317-mock}
        ports: [{containerPort: 8080}]
---
apiVersion: v1
kind: Service
metadata: {name: researcher-agent, namespace: $namespace}
spec:
  selector: {app: researcher-agent}
  ports: [{port: 8080, targetPort: 8080}]
---
apiVersion: batch/v1
kind: Job
metadata: {name: rel-317-native-worker, namespace: $namespace}
spec:
  backoffLimit: 0
  template:
    spec:
      serviceAccountName: rel-317-worker
      restartPolicy: Never
      initContainers:
      - name: authority-copy
        image: $worker_image
        imagePullPolicy: Never
        command: ["/bin/sh", "-c"]
        args: ["cp /config/* /authority/ && chmod 600 /authority/*"]
        volumeMounts:
        - {name: config, mountPath: /config}
        - {name: authority, mountPath: /authority}
      containers:
      - name: worker
        image: $worker_image
        imagePullPolicy: Never
        env:
        - {name: NATIVE_DISPATCH_DATABASE_URL, value: "$cluster_database_url"}
        - {name: NATIVE_DISPATCH_AUTHORITY_CONFIGURATION, value: /authority/runtime.json}
        - {name: NATIVE_DISPATCH_EXECUTION_MIGRATION, value: /app/console/backend/migrations/0008_execution_runtime_authority.sql}
        - {name: NATIVE_DISPATCH_SCHEMA_MIGRATION, value: /app/console/backend/migrations/0022_native_execution_dispatch.sql}
        - {name: NATIVE_DISPATCH_WORKER_ID, value: rel-317-worker-stable}
        - {name: NATIVE_DISPATCH_TASK_PREFIX, value: rel-317-native}
        volumeMounts:
        - {name: authority, mountPath: /authority}
      volumes:
      - {name: config, configMap: {name: rel-317-authority}}
      - {name: authority, emptyDir: {}}
YAML

kubectl --context "kind-$cluster" -n "$namespace" rollout status deployment/researcher-agent --timeout=120s
kubectl --context "kind-$cluster" -n "$namespace" wait --for=condition=complete job/rel-317-native-worker --timeout=180s
kubectl --context "kind-$cluster" -n "$namespace" logs job/rel-317-native-worker > "$artifact_dir/worker.log"
kubectl --context "kind-$cluster" -n "$namespace" logs deployment/researcher-agent > "$artifact_dir/runtime.log"
kubectl --context "kind-$cluster" -n "$namespace" get task -o json > "$artifact_dir/task.json"
kubectl --context "kind-$cluster" -n "$namespace" get pods -o json > "$artifact_dir/pods.json"
PYTHONPATH="$repo_root/console/backend/src:$repo_root/core/src" \
  uv run --directory "$repo_root" python "$repo_root/scripts/acceptance/s5_v023_rel_317_native_l3.py" readback \
  --database-url "$database_url" --artifact-dir "$artifact_dir" > "$artifact_dir/readback-output.json"

runtime_calls="$(grep -c 'POST /v1/invoke HTTP/1.1.*200' "$artifact_dir/runtime.log")"
if [ "$runtime_calls" != 1 ]; then
  echo "REL_317_RUNTIME_CALL_COUNT_${runtime_calls}" >&2
  exit 1
fi
printf 'runtime_post_invoke_200=%s\n' "$runtime_calls" > "$artifact_dir/runtime-call-count.txt"
find "$artifact_dir" -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "$artifact_dir/SHA256SUMS"
echo "REL_317_NATIVE_L3_PASSED artifact_dir=$artifact_dir source=$source_sha tree=$source_tree"
