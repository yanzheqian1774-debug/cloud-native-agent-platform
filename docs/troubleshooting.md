# Troubleshooting

These checks cover observed first-user failures in the current local Alpha
workflow. Run commands from the repository root unless noted otherwise.

## A prerequisite is missing

The Quick Start requires `docker`, `kubectl`, and `kind`:

```bash
docker --version
docker info
kubectl version --client
kind version
```

If `docker info` fails, start the Docker daemon before retrying. Repository
development additionally requires Python 3.12 and `uv`.

## Frontend validation reports an unsupported Node version

Repository CI uses Node 24. Current locked frontend dependencies also permit
compatible Node 20.19+ and 22.13+ releases. Check the active version before
running frontend validation:

```bash
node --version
npm --version
```

Then run `npm ci`, `npm run lint`, and `npm run build` from
`console/frontend`.

## An image or package download fails

Uncached builds retrieve base images and locked Python artifacts from external
registries and package services. Preserve the exact failing URL and error,
verify Docker and outbound network access, and retry only after identifying a
specific transient cause. Do not substitute an older local application image
as fresh-build evidence.

## The Agent is not ready

Do not create a Task until the Agent reports `Running` and its Deployment is
available:

```bash
kubectl --context kind-agentos-dev -n agent-workloads wait \
  --for=jsonpath='{.status.phase}'=Running \
  agents.agentos.io/researcher-agent --timeout=120s
kubectl --context kind-agentos-dev -n agent-workloads rollout status \
  deployment/researcher-agent --timeout=120s
```

Inspect the Agent, Deployment, Pod, and Operator logs if readiness times out:

```bash
kubectl --context kind-agentos-dev -n agent-workloads get agent,deployment,pod
kubectl --context kind-agentos-dev -n agent-system logs deployment/agent-operator
```

## The Quick Start refuses an existing cluster

The script intentionally refuses to modify an existing
`agentos-quickstart` cluster. It also refuses workflow or cleanup operations if
the cluster lacks the Quick Start ownership marker. Preserve or handle an
unrelated same-name cluster manually; do not bypass the ownership check.

List local kind clusters with:

```bash
kind get clusters
```

## Cleanup

For a cluster created by the Quick Start:

```bash
./scripts/quickstart.sh cleanup
```

For the dedicated cluster created by the detailed installation guide:

```bash
kind delete cluster --name agentos-dev
```

Only delete a cluster when you have confirmed that it belongs to your current
guide or task. Quick Start cleanup retains its two local image tags as build
caches.
