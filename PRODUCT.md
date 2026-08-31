# Product North Star

## Mission

Make AI agents production-grade enterprise workloads.

## Product Vision

Build an open, cloud-native platform to produce, run, orchestrate,
govern, and operate enterprise AI agents.

## Product Category

Enterprise Agent Platform.

## Product Core

Enterprise Agent Lifecycle Platform.

## Technical Core

Kubernetes-native Agent Control Plane.

The Agent Control Plane is the technical kernel of the product.
It is not the entire product.

## North Star

Enterprises are moving from using large language models to operating
large numbers of AI agents in real business environments.

The platform exists to help enterprises:

- produce agents at scale;
- run agents reliably;
- compose agents into workflows;
- connect agents to enterprise capabilities;
- preserve agent state independently of runtime implementations;
- govern agent access and behavior;
- observe cost, quality, reliability, and business value;
- operate agents across enterprise infrastructure.

## Enterprise Agent Lifecycle

The primary product abstraction is the Enterprise Agent Lifecycle:

Discover
→ Define
→ Assemble
→ Evaluate
→ Publish
→ Instantiate
→ Run
→ Orchestrate
→ Observe
→ Govern
→ Optimize
→ Evolve

## Product Layers

The product is described at three levels.

### Enterprise Agent Platform

The complete enterprise product.

### Enterprise Agent Lifecycle Platform

The product core responsible for the lifecycle of enterprise agents.

### Agent Control Plane

The technical core responsible for declarative control, lifecycle,
scheduling, reconciliation, execution coordination, retry, and recovery.

## Core Product Principles

1. Platform is not the same as Control Plane.
2. Agent Definition is not the same as Agent Instance.
3. Agent is not the same as Runtime.
4. Agent is not the same as Model.
5. Runtime is not the same as State.
6. Capability is not embedded implementation detail.
7. Contracts precede replaceable implementations.
8. Reference implementations must remain replaceable.
9. Governance and Operations are cross-cutting concerns.
10. End-to-end solutions are product acceptance scenarios.

## Build Boundary

The platform MUST own:

- Agent contracts;
- Agent lifecycle semantics;
- Agent Instance model;
- Task and Workflow contracts;
- Agent Control Plane;
- Runtime Contract;
- Capability Contract;
- State Contract;
- Model abstraction;
- governance semantics;
- Platform API;
- core management experience.

The platform SHOULD provide replaceable reference implementations for:

- native runtime;
- state providers;
- model providers;
- capability providers;
- basic observability;
- basic user experience.

The platform SHOULD integrate rather than reinvent:

- foundation models;
- general-purpose agent harnesses;
- mature agent frameworks;
- Kubernetes;
- databases;
- vector databases;
- enterprise identity providers;
- observability backends;
- enterprise communication channels.

## Ecosystem Philosophy

The long-term platform should support:

- Bring Your Own Model;
- Bring Your Own Runtime;
- Bring Your Own Agent;
- Bring Your Own Capability;
- Bring Your Own MCP;
- Bring Your Own State Provider;
- Bring Your Own Cloud;
- Bring Your Own Kubernetes.

The platform provides unified lifecycle, control, governance,
observability, and operations across those ecosystems.

## Agent OS

"Agent OS" is treated as an industry narrative, not as the unique
first-level product identity.

The product category remains Enterprise Agent Platform.

## Kubernetes

Kubernetes is the technical foundation of the control plane.

Kubernetes-native is a technical differentiator, not the product's
ultimate purpose.

## Human-confirmed v0.2 product increments

The following bounded increments define how the current v0.2 objective grows
from a business question to a governed, evidence-backed outcome. They are
product definitions and acceptance boundaries, not claims of current
implementation, production readiness, certification, Contract freeze, or
release acceptance.

### v0.2.2 — Agent, Skill, MCP and Knowledge Factory

v0.2.2 combines the Agent, Skill, MCP and Knowledge Factory with an Enterprise
Resource Workbench and bounded Resource and Product Journey persistence. Its
managed resource lifecycle is:

```text
DRAFT
→ VALIDATED
→ TESTED
→ HUMAN_REVIEWED
→ PUBLISHED
→ MATCHABLE
→ DEPRECATED
```

The first future durable vertical slice must create an Agent Definition draft,
validate the exact revision, bind a test result and Human review to its exact
digest, publish an immutable revision, recover the same identity, revision and
digest after service restart, inspect it in the Resource Workbench, make that
exact published revision eligible for governed discovery and matching, and
deprecate it without deleting history. S5-IMPL-044 Accounting is a supporting
primitive; Accounting Technical Inspection does not replace the Factory and
Workbench product outcome.

### v0.2.3 — Runtime operations and closed-loop execution

v0.2.3 provides Native/OpenClaw Runtime Operations and Closed-Loop Execution.
Its required hierarchy is:

```text
Approved Plan → Workflow Run → Task Run → Attempt → Placement
→ Runtime Instance → Agent Instance → Resource Invocations
→ Events → Evidence → Outcome → Feedback
```

Session is execution context only. It does not replace Runtime, Agent, Task, or
persistent Knowledge identity.

### v0.2.4 — Enterprise model governance

v0.2.4 provides an Enterprise Model Catalog, Evaluation and Governed Selection:
Model Definition and immutable Revision; Provider, Endpoint and Profile
references; capability and compatibility declarations; evidence-backed health
and compatibility; bounded evaluation; policy evaluation; governed selection;
optional Human override; exact model binding; invocation Evidence; and explicit
evidence-backed fallback. S5-IMPL-043 provider adapters and Model Usage
Inventory are foundations or thin slices, not complete Model Governance.

All three increments require bounded product-continuity persistence. The
Human-selected direction is domain-owned typed repository ports with bounded
single-node SQLite adapters for v0.2, immutable revisions and append-only or
link-based histories, and replaceability of PostgreSQL behind those ports.
Qdrant remains vector storage while durable SQL stores Knowledge and index
snapshot identities and references. Secret values remain external. Runtime
observed state is reacquired and reconciled after restart, and Accounting is
derived from durable facts unless a separate high-water snapshot is approved.
Implementation requires a subsequent consolidated persistence G2; this product
definition grants no persistence implementation authority.

## Current Release Boundary

The latest published release is **v0.1.0-alpha**. It proves the Agent Control
Plane core.

It MUST focus on:

- installability;
- real execution;
- multi-agent workflow;
- failure and retry semantics;
- observability;
- documentation;
- reproducibility.

It MUST NOT expand into the complete Enterprise Agent Platform.

The current development objective is **v0.2 CONNECT — Digital Employee
Technical Preview**, classified as a `WORKING_RELEASE_OBJECTIVE`. v0.2 release
acceptance and production readiness are `NOT_GRANTED`.

For this objective, the platform governs Digital Employees as business-facing
projections over Agent Definitions, Agent Instances, Tasks, Workflows,
Capabilities, Runtime Providers, and enterprise control mechanisms. Digital
Employee is not a Core CRD. The final Demo scenario and final product brand
remain open Human decisions.

See the derived [current Project State](PROJECT_STATE.md) and authoritative
[Governance Registry](docs/governance/REGISTRY.md) for operational status.

## North Star Test

Every significant new capability must answer:

Does this capability help an enterprise better produce, run, compose,
govern, or operate AI agents?

If not, it should normally remain outside the product core.
