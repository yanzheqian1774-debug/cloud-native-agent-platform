# Golden Engineering Demo

This demo proves the current `v0.1.0-alpha` product claim:

> AI agents can be managed as production-style cloud-native workloads through
> a Kubernetes-native Agent Control Plane.

It uses the built-in deterministic mock model provider and requires no external
model account or credential. The demo covers three paths:

1. a successful Agent, standalone Task, and four-node Workflow;
2. a real retryable execution failure with an independent successful sibling
   and a skipped dependent node; and
3. read-only inspection through Kubernetes resources and the Console API.

## Prerequisite

Complete the [local Kubernetes installation](../../manifests/README.md) through
Operator readiness. The commands below expect its dedicated `agentos-dev`
cluster and `kind-agentos-dev` context.

Run all commands from the repository root.

## 1. Happy path

Create the mock-backed Agent and wait for its Native Runtime:

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

Run the standalone Task:

```bash
kubectl --context kind-agentos-dev apply -f manifests/tasks/example-task.yaml
kubectl --context kind-agentos-dev -n agent-workloads wait \
  --for=jsonpath='{.status.phase}'=Succeeded \
  tasks.agentos.io/research-task --timeout=120s
kubectl --context kind-agentos-dev -n agent-workloads get \
  tasks.agentos.io/research-task \
  -o jsonpath='{.status.phase}{" attempts="}{.status.attempts}{"\n"}{.status.result}{"\n"}'
```

Run the four-node Workflow:

```bash
kubectl --context kind-agentos-dev apply -f manifests/workflows/example-workflow.yaml
kubectl --context kind-agentos-dev -n agent-workloads wait \
  --for=jsonpath='{.status.phase}'=Succeeded \
  workflows.agentos.io/research-workflow --timeout=180s
kubectl --context kind-agentos-dev -n agent-workloads get \
  workflows.agentos.io/research-workflow
kubectl --context kind-agentos-dev -n agent-workloads get tasks.agentos.io \
  -l agentos.io/workflow=research-workflow
```

Expected outcome:

- the Agent reports `Running` with one ready replica;
- the standalone Task reports `Succeeded` with one attempt;
- the Workflow reports `Succeeded` with four Tasks; and
- the `market`, `technology`, and `report` Task inputs contain the results of
  their declared upstream Tasks.

Inspect one resolved downstream input:

```bash
kubectl --context kind-agentos-dev -n agent-workloads get \
  tasks.agentos.io/research-workflow-market \
  -o jsonpath='{.spec.input.prompt}{"\n"}'
```

The output includes a `Previous task results` section containing the
`research` result.

## 2. Failure and retry path

Apply the failure Workflow:

```bash
kubectl --context kind-agentos-dev apply \
  -f examples/golden-engineering-demo/failure-workflow.yaml
kubectl --context kind-agentos-dev -n agent-workloads wait \
  --for=jsonpath='{.status.phase}'=Failed \
  workflows.agentos.io/golden-demo-failure --timeout=120s
```

The `unavailable` node targets an intentionally nonexistent Agent Service.
That produces a real retryable `NetworkError`; no status is manually edited.
The Task controller owns execution retry and makes at most three attempts with
one-second and two-second backoffs. After the third failure:

- `unavailable` is `Failed` with `attempts: 3` and `reason: NetworkError`;
- `independent` is `Succeeded`, proving an unrelated sibling can continue;
- `blocked` is `Skipped` because its required dependency failed;
- no Task resource is created for the skipped `blocked` node; and
- the Workflow reaches terminal phase `Failed`.

Verify those outcomes:

```bash
kubectl --context kind-agentos-dev -n agent-workloads get \
  tasks.agentos.io/golden-demo-failure-unavailable \
  -o jsonpath='{.status.phase}{" attempts="}{.status.attempts}{" reason="}{.status.reason}{"\n"}'
kubectl --context kind-agentos-dev -n agent-workloads get \
  tasks.agentos.io/golden-demo-failure-independent \
  -o jsonpath='{.status.phase}{" attempts="}{.status.attempts}{"\n"}'
kubectl --context kind-agentos-dev -n agent-workloads get \
  workflows.agentos.io/golden-demo-failure -o yaml
kubectl --context kind-agentos-dev -n agent-workloads get tasks.agentos.io \
  -l agentos.io/workflow=golden-demo-failure
```

## 3. Observability path

Kubernetes resources are the source of truth. The Console backend is a
stateless, read-only projection of Workflow and Task state.

Ensure the demo context is current, then start the backend:

```bash
kubectl config use-context kind-agentos-dev
uv run uvicorn agent_console.app:app \
  --app-dir console/backend/src \
  --host 127.0.0.1 \
  --port 8000
```

In another terminal, inspect both Workflow projections:

```bash
curl --fail \
  http://127.0.0.1:8000/api/v1/workflows/agent-workloads/research-workflow
curl --fail \
  http://127.0.0.1:8000/api/v1/workflows/agent-workloads/golden-demo-failure
```

The successful projection exposes DAG dependencies, resolved inputs, upstream
results, outputs, attempts, and timing. The failure projection exposes the
failed node's attempts and reason, the independent success, and the skipped
dependent node. The Console does not mutate these resources or provide
authentication, policy, tracing, cost, or historical-storage capabilities.

## Cleanup

Delete only resources created by this demo:

```bash
kubectl --context kind-agentos-dev delete \
  -f examples/golden-engineering-demo/failure-workflow.yaml
kubectl --context kind-agentos-dev delete -f manifests/workflows/example-workflow.yaml
kubectl --context kind-agentos-dev delete -f manifests/tasks/example-task.yaml
kubectl --context kind-agentos-dev delete -f manifests/agents/researcher.yaml
```
