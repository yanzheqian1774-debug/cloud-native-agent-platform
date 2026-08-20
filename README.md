# Enterprise Agent Platform

**Run agents like cloud-native workloads.**

This repository implements the current Alpha core of an Enterprise Agent
Platform: a Kubernetes-native Agent Control Plane for declaring agents,
executing tasks, coordinating workflows, and observing execution state.

The project exists to move AI agents beyond isolated applications toward
manageable cloud-native workloads. Kubernetes resources are the source of
truth, and the Operator reconciles the current Agent, Task, and Workflow
lifecycle.

## v0.1.0-alpha scope

The current implementation includes:

- `Agent`, `Task`, and `Workflow` Kubernetes custom resources;
- Operator reconciliation for their current lifecycle behavior;
- a Native Runtime with deterministic mock and implemented model-provider
  execution paths;
- workflow dependencies, parallel execution, result propagation, retry,
  failure, skip, and timeout behavior where implemented; and
- a stateless, read-only Console for Workflow and Task execution visibility.

This Alpha is **not production-ready**. It does not currently provide the full
Enterprise Agent Platform described by the product roadmap. Agent Factory,
Agent Instance, external runtime adapters, State Plane, registries,
multi-tenancy, enterprise RBAC and policy, cost governance, autoscaling, and
managed Kubernetes qualification remain future direction.

The `agentos.io` Kubernetes API group is the current technical API. “Agent OS”
is an industry narrative, not a finalized first-level product brand.

## Quick Start

The Quick Start is the shortest supported path to a deterministic first Agent
result. It requires Git, a running Docker daemon, `kubectl`, and `kind`, plus
outbound access for uncached image and Python artifact downloads. It does not
require an external model account or API key.

```bash
./scripts/quickstart.sh
```

The script builds the current Operator and Native Runtime images, creates the
dedicated `agentos-quickstart` kind cluster, installs the control plane, starts
the mock-backed `researcher-agent`, and executes `research-task`.

Success ends with output like:

```text
FIRST VALUE: PASS
Phase:    Succeeded
Attempts: 1
Result:   mock response: Analyze the architecture of Kubernetes-native Agent runtimes.
```

Explore Workflow dependencies and result propagation, then clean up:

```bash
./scripts/quickstart.sh workflow
./scripts/quickstart.sh cleanup
```

The script refuses to modify or delete a same-name cluster without its
ownership marker. Cleanup deletes the Quick Start cluster and retains the two
local `:quickstart` image tags as build caches.

Qualified-fresh Ubuntu 24.04 Linux AMD64 validation reached First Value in 136
seconds. The Alpha target is no more than 15 minutes under the documented
prerequisites; 136 seconds is qualification evidence, not a universal runtime
guarantee.

## Golden Engineering Demo

The [Golden Engineering Demo](examples/golden-engineering-demo/README.md) is
the deeper validation path. Unlike the Quick Start’s fastest First Value path,
it demonstrates successful orchestration, dependency result propagation, a
real retryable network failure, dependency skipping, and read-only Console
inspection.

## Architecture and product direction

Use the documents according to their role:

- [Current Implementation](docs/engineering/CURRENT_IMPLEMENTATION.md)
  summarizes what source and tests implement today.
- [Architecture](ARCHITECTURE.md) describes accepted target architecture and
  explicitly includes future concepts.
- [Architecture decisions](adr/README.md) record accepted decisions and known
  implementation drift, including ADR-0003, ADR-0004, and ADR-0005.
- [Product](PRODUCT.md) and [Roadmap](ROADMAP.md) describe product intent and
  planned sequencing; they do not claim that future capabilities exist today.

Accepted architecture is not automatically implemented. Source and tests
remain the authority for current behavior.

## Compatibility and qualification

Validated Alpha paths are bounded to:

- a macOS ARM64 development path; and
- Ubuntu 24.04 on native/cloud-virtualized Linux AMD64, including fresh source
  builds, local kind installation, Agent/Task/Workflow execution, and the
  qualified-fresh Quick Start.

This evidence does not establish Windows, every Linux distribution, Linux
ARM64, managed Kubernetes, production deployment, or multi-architecture
release-artifact compatibility. Fresh builds remain dependent on external
registries and package services.

## Install, troubleshoot, and develop

- [Detailed local Kubernetes installation](manifests/README.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Documentation index](docs/README.md)
- [Examples index](examples/README.md)

For repository development, install Python 3.12, `uv`, and Git, then run:

```bash
make setup
make check
```

Frontend contributors should also follow the validation commands in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for issue routing, development workflow,
validation, commits, and pull-request expectations.

Report suspected vulnerabilities privately as described in
[SECURITY.md](SECURITY.md). Do not disclose suspected vulnerabilities through
public issues or pull requests.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).
