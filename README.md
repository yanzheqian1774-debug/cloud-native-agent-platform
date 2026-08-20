# Enterprise Agent Platform

An open, cloud-native platform for making AI agents production-grade
enterprise workloads. Its technical core is a Kubernetes-native Agent Control
Plane.

The current v0.1.0-alpha implementation focuses on the control-plane core. It
includes:

- `Agent`, `Task`, and `Workflow` Kubernetes custom resources;
- a Kubernetes operator for their current lifecycle behavior;
- a native agent runtime with model-provider integration;
- workflow DAG execution, including dependency, parallel, retry, failure,
  skip, and timeout behavior where implemented; and
- a basic Console for workflow execution visibility.

Broader Enterprise Agent Platform capabilities described in the product,
architecture, and roadmap documents are future direction unless the source and
tests show that they are implemented.

## Repository guide

- [PRODUCT.md](PRODUCT.md) defines product intent and boundaries.
- [ARCHITECTURE.md](ARCHITECTURE.md) describes the target architecture.
- [ROADMAP.md](ROADMAP.md) describes planned release sequencing.
- [CURRENT_IMPLEMENTATION.md](docs/engineering/CURRENT_IMPLEMENTATION.md)
  records the current implementation boundary.

## Local development

### Prerequisites

- Python 3.12
- uv
- Git

### Setup

```bash
make setup
```

Run the repository checks with:

```bash
make check
```

## Quick Start

Get a deterministic first Agent result on a new local Kubernetes cluster. This
path requires Git, a running Docker daemon, `kubectl`, and `kind`; it does not
require an external model account or API key. An uncached image build also
requires outbound access to the base-image registry and Python package
artifacts. The current sub-15-minute validation is qualified-warm; the known
INSTALL-001 external artifact-transfer blocker for fresh Operator builds is not
closed by this path.

The command builds the current Operator and Native Runtime images, creates a
dedicated kind cluster named `agentos-quickstart`, installs the CRDs and
Operator, creates the mock-backed `researcher-agent`, and runs `research-task`.
It stops with an error rather than modifying a cluster that already has that
name.

```bash
./scripts/quickstart.sh
```

Success ends with `FIRST VALUE: PASS`, a successful Task phase, and its
deterministic `mock response`. To see Workflow dependencies and result
propagation after First Value:

```bash
./scripts/quickstart.sh workflow
```

Delete only the Quick Start cluster when finished:

```bash
./scripts/quickstart.sh cleanup
```

The two local `:quickstart` image tags are retained as a build cache. See the
[installation guide](manifests/README.md) for the expanded installation path
and the [Golden Engineering Demo](examples/golden-engineering-demo/README.md)
for failure/retry and Console observability.

## Install on a local Kubernetes cluster

The current Alpha installation uses Docker, `kubectl`, and `kind`. Follow the
[local Kubernetes installation guide](manifests/README.md) to build the current
Operator and Native Runtime images, install the CRDs and Operator, run the mock
Agent/Task/Workflow examples, and inspect the result through Kubernetes or the
read-only Console API.

## Golden Engineering Demo

The [Golden Engineering Demo](examples/golden-engineering-demo/README.md) uses
the deterministic mock provider to demonstrate successful orchestration,
dependency result propagation, real failure/retry behavior, and read-only
execution observability.

## License

This project is licensed under the Apache License 2.0. See
[LICENSE](LICENSE) for the complete license text.









