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

## Install on a local Kubernetes cluster

The current Alpha installation uses Docker, `kubectl`, and `kind`. Follow the
[local Kubernetes installation guide](manifests/README.md) to build the current
Operator and Native Runtime images, install the CRDs and Operator, run the mock
Agent/Task/Workflow examples, and inspect the result through Kubernetes or the
read-only Console API.

## License

This project is licensed under the Apache License 2.0. See
[LICENSE](LICENSE) for the complete license text.












