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

### v0.2.2 — Core Resource Management and Composition

v0.2.2 combines Agent, Skill, MCP and Knowledge foundation with Digital Employee
Definition and composition, Runtime Provider/Profile binding, an Enterprise
Resource Catalog and domain Workbenches, PostgreSQL product-continuity
persistence and a real resource-composition browser journey. Its managed
resource lifecycle is:

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

### v0.2.3 — Digital Employee Execution and Runtime Closure

v0.2.3 provides Assignment, Digital Employee Instance, Native/OpenClaw Runtime
Operations and Closed-Loop Execution. It reuses and productizes the v0.1
Kubernetes-native Runtime rather than reimplementing it. OpenClaw is one
mandatory bounded real execution vertical slice. Its required hierarchy is:

```text
Approved Plan → Workflow Run → Task Run → Attempt → Placement
→ Runtime Instance → Agent Instance → Resource Invocations
→ Events → Evidence → Outcome → Feedback
```

Session is execution context only. It does not replace Runtime, Agent, Task, or
persistent Knowledge identity.

### v0.2.4 — Model and Capability Composition

v0.2.4 provides an Enterprise Model Catalog, Evaluation and Governed Selection:
Model Definition and immutable Revision; Provider, Endpoint and Profile
references; capability and compatibility declarations; evidence-backed health
and compatibility; bounded evaluation; policy evaluation; governed selection;
optional Human override; exact Agent/Digital Employee/Knowledge model binding;
invocation Evidence; usage and latency; token and cost when measurable;
explicit `NOT_MEASURABLE`; and evidence-backed fallback. S5-IMPL-043 provider
adapters and Model Usage Inventory are foundations or thin slices, not complete
Model Governance.

All three increments require bounded product-continuity persistence. The
Human-selected direction is domain-owned typed repository ports with PostgreSQL
as the primary deployment adapter for new product-continuity domains. Existing
Execution Evidence SQLite remains transitional, and SQLite/in-memory adapters
are limited to focused local development and conformance tests. Revisions are
immutable and histories append-only or link-based. Qdrant remains a derived
vector index while durable SQL stores authoritative Knowledge and index
snapshot identities and references. Secret values remain external. Runtime
observed state is reacquired and reconciled after restart, and Accounting is
derived from durable facts unless a separate high-water snapshot is approved.
S5-ARCH-018 is the governing persistence authority; this product definition
does not expand its implementation authority.

The complete Runtime Manager, Tenant and Organization, centralized Policy and
Authorization, Marketplace, FinOps, HA/autoscaling/failover, certification,
generalized Recovery, governed optimization and ecosystem operations remain
v0.3.x boundaries.

Minimum v0.2.x governance remains mandatory: Identity, Revision, digest, Human
Review, publication, authorization, isolation, Secret Reference, Evidence,
audit, impact analysis, deletion protection and fail-closed behavior.

Backend-only, API-only, architecture-only, mock-only, generic-table-only,
fixture-only or browserless delivery does not satisfy a v0.2.x capability.
Acceptance requires a real user entry, real frontend operation, backend
authority, required durable persistence, real composition or consumption,
version-required execution, Evidence/Outcome, real-browser acceptance against
real services and explicit limitations.

### Binding Workbench continuity

The v0.2.2–v0.2.4 product direction preserves five related experiences over
canonical backend-owned objects and identities:

1. **Business Workbench:** problem, plan, approval, progress, Evidence-backed
   result, correction, Outcome, and feedback.
2. **Enterprise Resource Workbench:** Digital Employee, Agent, Skill, MCP,
   Knowledge, Capability, and their relationships.
3. **Runtime Operations Workbench:** Workflow Run, Task Run, Attempt, Runtime
   Instance, Agent Instance, interventions, Events, Evidence, and Outcome.
4. **Model Governance Workbench:** Model Catalog, Provider/Endpoint/Profile,
   Evaluation, Selection, optional Human override, exact Binding, Usage, and
   Invocation Evidence.
5. **Technical Inspection:** canonical identities, authorization, provenance,
   Accounting, limitations, and `NOT_MEASURABLE` classifications.

Each independently managed resource should progressively provide, where the
resource's governance semantics apply:

```text
Dashboard
→ Catalog/List
→ Detail
→ Draft/Authoring
→ Validation/Test
→ Human Review
→ Publication
→ immutable Revision History
→ Relationships/Consumers
→ Invocation/Retrieval History
→ Deprecation
```

Workbench does not mean a single generic table or a view-only dashboard. It
includes the governed lifecycle actions appropriate to each resource while
preserving backend authority and immutable history.

Product View and Technical View are sibling projections over the same canonical
objects and identities. Product View presents business meaning, important
decisions, progress, Evidence, limitations, correction, and Outcome. Technical
View presents revisions, matching, placement, Runtime, Provider/model, policy,
authorization, provenance, and Accounting. Neither frontend view becomes
lifecycle, planning, execution, or Evidence authority.

The first v0.2.2 Agent Definition vertical slice is the first implementation of
this Workbench pattern. It does not reduce or supersede the planned Skill, MCP,
Knowledge, Digital Employee, Runtime Operations, or Model Governance
workbenches.

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
