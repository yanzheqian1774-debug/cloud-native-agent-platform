# Local Kubernetes installation

This guide installs the current `v0.1.0-alpha` control-plane core from source
into a local [kind](https://kind.sigs.k8s.io/) cluster. The example Agent uses
the built-in deterministic mock model provider, so no external model account or
credential is required.

## Prerequisites

- Docker with a running daemon;
- `kubectl`;
- `kind`;
- Python 3.12 and `uv` for repository validation and the optional Console; and
- Node.js 24 (used by repository CI), or a compatible 20.19+/22.13+ release,
  plus npm, for the Console frontend.

Run all commands from the repository root. The commands below create and use a
dedicated kind cluster named `agentos-dev`. If an existing `agentos-dev` cluster
is unrelated or must be preserved, do not run this guide as written against it.

## Build and install

Install the locked Python dependencies and build the locked frontend
dependencies:

```bash
uv sync --frozen
cd console/frontend
npm ci
npm run build
cd ../..
```

Build the Operator and Native Runtime images used by the checked-in manifests:

```bash
docker build -f operator/Dockerfile -t enterprise-agent-operator:v0.1-dev .
docker build -f runtime/Dockerfile -t enterprise-agent-runtime:v0.1-dev .
```

Create the cluster, load those local images, and install the namespaces, CRDs,
RBAC, and Operator:

```bash
kind create cluster --config manifests/dev/kind-cluster.yaml --wait 120s
kind load docker-image --name agentos-dev \
  enterprise-agent-operator:v0.1-dev \
  enterprise-agent-runtime:v0.1-dev

kubectl --context kind-agentos-dev apply -f manifests/dev/namespaces.yaml
kubectl --context kind-agentos-dev apply -f manifests/crd
kubectl --context kind-agentos-dev apply -f manifests/operator/service-account.yaml
kubectl --context kind-agentos-dev apply -f manifests/operator/rbac.yaml
kubectl --context kind-agentos-dev apply -f manifests/operator/deployment.yaml
kubectl --context kind-agentos-dev -n agent-system rollout status \
  deployment/agent-operator --timeout=120s
```

## Run the mock examples

Create the mock-backed Agent and wait for its runtime to become ready:

```bash
kubectl --context kind-agentos-dev apply -f manifests/agents/researcher.yaml
kubectl --context kind-agentos-dev -n agent-workloads wait \
  --for=jsonpath='{.status.phase}'=Running \
  agents.agentos.io/researcher-agent --timeout=120s
kubectl --context kind-agentos-dev -n agent-workloads rollout status \
  deployment/researcher-agent --timeout=120s
kubectl --context kind-agentos-dev -n agent-workloads get \
  agents.agentos.io/researcher-agent
```

Create a standalone Task and confirm that it succeeds:

```bash
kubectl --context kind-agentos-dev apply -f manifests/tasks/example-task.yaml
kubectl --context kind-agentos-dev -n agent-workloads wait \
  --for=jsonpath='{.status.phase}'=Succeeded \
  tasks.agentos.io/research-task --timeout=120s
kubectl --context kind-agentos-dev -n agent-workloads get \
  tasks.agentos.io/research-task -o yaml
```

Create the example workflow and confirm that all four mock-backed nodes reach
a successful terminal state:

```bash
kubectl --context kind-agentos-dev apply -f manifests/workflows/example-workflow.yaml
kubectl --context kind-agentos-dev -n agent-workloads wait \
  --for=jsonpath='{.status.phase}'=Succeeded \
  workflows.agentos.io/research-workflow --timeout=180s
kubectl --context kind-agentos-dev -n agent-workloads get \
  workflows.agentos.io/research-workflow -o yaml
kubectl --context kind-agentos-dev -n agent-workloads get tasks.agentos.io \
  -l agentos.io/workflow=research-workflow
```

## Inspect through the Console

The current Console backend is a read-only projection of the Kubernetes
Workflow and Task resources. Ensure `kind-agentos-dev` is the current context,
then start the backend from the repository root:

```bash
kubectl config use-context kind-agentos-dev
uv run uvicorn agent_console.app:app \
  --app-dir console/backend/src \
  --host 127.0.0.1 \
  --port 8000
```

In another terminal, verify the API:

```bash
curl --fail http://127.0.0.1:8000/healthz
curl --fail http://127.0.0.1:8000/api/v1/workflows
curl --fail \
  http://127.0.0.1:8000/api/v1/workflows/agent-workloads/research-workflow
```

To run the browser frontend, start its repository-defined development server
from a third terminal:

```bash
cd console/frontend
npm run dev
```

Open `http://127.0.0.1:5173`. The development server proxies `/api` and
`/healthz` to the backend at `http://127.0.0.1:8000`.

## Cleanup

Delete only the cluster created by this guide:

```bash
kind delete cluster --name agentos-dev
```
