# Product Roadmap

## Roadmap Authority

This document is the current forward-looking product release roadmap.

An earlier repository roadmap used v0.1-v0.6 labels for bootstrap and
learning milestones such as project setup, Kubernetes, Operator,
Runtime, Multi-Agent, and cloud deployment.

Those historical milestone labels are superseded by this roadmap and
must not be interpreted as the current product release sequence.

Git history remains the source for the earlier roadmap.

## Roadmap Principle

Versions are organized around product hypotheses, not feature volume.

RUN
→ CONNECT
→ BUILD
→ GOVERN
→ SCALE
→ TRUST

## v0.1 — CORE / RUN

Question:

Can Agent workloads run reliably?

Goal:

Prove the Kubernetes-native Agent Control Plane core.

Primary scope:

- Agent;
- Task;
- Workflow;
- Operator;
- Native Runtime;
- workflow DAG;
- parallel execution;
- retry;
- failure;
- skip;
- timeout;
- real model execution;
- basic Console execution visibility.

Release focus:

- clean install;
- Quick Start;
- security hygiene;
- documentation;
- reproducible Golden Demo;
- Linux AMD64 validation;
- release packaging.

Explicitly out of scope:

- Agent Builder;
- external Runtime adapters;
- full multi-tenancy;
- enterprise RBAC;
- Memory platform;
- Capability Marketplace;
- full Model Registry;
- GPU scheduler.

## v0.2 — OPEN / CONNECT

Question:

Can different Agent ecosystems plug into the platform?

Goal:

Establish open Contracts and validate runtime portability.

Expected scope:

- Runtime Contract v0.1;
- Runtime Adapter SDK;
- Native Runtime implementation of the contract;
- at least one external runtime integration;
- second distinct runtime/framework validation where practical;
- Capability Contract foundation;
- MCP integration;
- minimal State Contract;
- cross-runtime workflow validation.

External integrations are selected through technical spikes and are
not hard-coded roadmap promises.

Potential candidates include:

- Hermes;
- OpenClaw;
- LangGraph.

### Current v0.2 working objective

CONNECT is the current active development stage. Its working release objective
is **v0.2 CONNECT — Digital Employee Technical Preview**. This objective does
not grant release acceptance, production readiness, Provider certification, or
Contract/Schema freeze.

The final Digital Employee Demo scenario and its acceptance criteria require a
separate Human Product/Architecture Gate. The alternative simplified sequence
`v0.1 -> v0.2 -> v0.5 -> v0.9 -> v1.0` is `NOT_APPROVED / OPEN`; it does not
replace the approved RUN / CONNECT / BUILD / GOVERN / SCALE / TRUST roadmap.

Current operational status is summarized in [PROJECT_STATE.md](PROJECT_STATE.md)
and governed through the [Governance Registry](docs/governance/REGISTRY.md).

### Human-confirmed v0.2 increment sequence

The current exact sequence is:

```text
v0.2.1 → v0.2.2 → v0.2.3 → v0.2.4 → v0.3.0
```

There is no v0.2.5 in this Human-confirmed sequence. Each increment depends on
the durable identities and governed outcomes of the preceding increment; none
inherits production, certification, public Contract, deployment, release, or
implementation authority merely by appearing here.

#### v0.2.2 — Factory, Workbench and product continuity

Product outcome: Agent, Skill, MCP and Knowledge Factory plus Enterprise
Resource Workbench, with the exact lifecycle and first durable Agent Definition
vertical slice defined in [PRODUCT.md](PRODUCT.md#v022--agent-skill-mcp-and-knowledge-factory).

Required future package order:

```text
persistence G2
→ typed repository ports and migration/replay contract
→ durable Agent Definition revision lifecycle
→ exact-digest test and Human-review binding
→ immutable publication and governed matchability
→ restart recovery and Resource Workbench inspection
→ history-preserving deprecation
```

This increment excludes Runtime Manager, HA, distributed lifecycle,
Marketplace, production certification and release acceptance. S5-IMPL-044 is a
supporting Accounting primitive and cannot substitute for the main outcome.

#### v0.2.3 — Digital Employee execution and Runtime closure

Product outcome: Native/OpenClaw Runtime Operations and Closed-Loop Execution
over the hierarchy recorded in
[PRODUCT.md](PRODUCT.md#v023--digital-employee-execution-and-runtime-closure).

Required future package order:

```text
Run identity and Approved Plan binding
→ Workflow Run and Task Run
→ Attempt and Placement
→ Runtime Instance and Agent Instance reconciliation
→ governed Resource Invocations, Events and Evidence
→ Outcome and Feedback closure
```

It depends on v0.2.2 durable definitions and histories. Session remains context,
not a substitute identity. This increment excludes HA, multi-cluster or
distributed Runtime lifecycle, generalized Recovery, certification and
production-readiness claims.

#### v0.2.4 — Model catalog, evaluation and selection

Product outcome: the bounded Enterprise Model Catalog, Evaluation and Governed
Selection scope defined in [PRODUCT.md](PRODUCT.md#v024--enterprise-model-governance).

Required future package order:

```text
Model Definition and immutable Revision catalog
→ Provider/Endpoint/Profile references and compatibility declarations
→ evidence-backed health and bounded evaluation
→ policy evaluation and governed selection
→ optional Human override and exact model binding
→ invocation Evidence and explicit evidence-backed fallback
```

It depends on v0.2.2 product continuity and v0.2.3 durable execution Evidence.
It excludes model training, GPU orchestration, Billing, Provider certification,
production readiness and release acceptance. S5-IMPL-043 is a foundation or
thin slice only and does not establish complete Model Governance.

The shared persistence direction for v0.2.2–v0.2.4 is governed by merged
S5-ARCH-018: PostgreSQL is primary deployment persistence for new
product-continuity domains, existing Execution Evidence SQLite is transitional,
SQLite/in-memory are focused local/test adapters, and Qdrant is a derived
Knowledge vector index. Implementations remain bounded by that decision and
their separately allocated tasks.

The delivery order after the durably integrated Agent Definition slice is:
Skill/MCP lifecycle and Workbench; Knowledge Operations and Workbench; shared
Product Shell and Resource Workbench assembly; Digital Employee Definition and
composition; complete v0.2.2 real-browser acceptance/release gate; v0.2.3
Runtime execution closure; then v0.2.4 Model and capability composition.

After the S5-GOV-004 charter is durable, Skill/MCP and Knowledge may proceed as
two isolated implementation tracks. One owner must control shared frontend
shell, route, dependency, migration and CI paths, with at most two concurrent
heavy implementation writers. The charter does not allocate those tasks.

### Workbench continuity across increments

The [binding Workbench pattern](PRODUCT.md#binding-workbench-continuity) spans
the Business, Enterprise Resource, Runtime Operations, Model Governance, and
Technical Inspection experiences. Delivery must preserve Product View and
Technical View as sibling projections over the same canonical objects and
identities, with backend lifecycle, planning, execution, authorization, and
Evidence authority unchanged.

The first v0.2.2 Agent Definition vertical slice proves the pattern first; it
does not collapse Workbench into a generic list/dashboard or remove the later
Skill, MCP, Knowledge, Digital Employee, Runtime Operations, or Model Governance
workbenches from scope. Subsequent resource packages progressively add the
applicable authoring, validation/test, Human review, publication, immutable
revision history, relationship/consumer, invocation/retrieval history, and
deprecation actions rather than creating frontend-owned authority.

## v0.3 — BUILD

Question:

Can enterprises produce and manage Agents?

Goal:

Introduce Enterprise Agent Lifecycle capabilities.

Expected scope:

- Agent Definition;
- Agent Version;
- Agent Instance;
- Agent Factory;
- Agent Catalog;
- evaluation;
- publish lifecycle;
- Capability Registry;
- State Plane foundation;
- Memory;
- Persona;
- Workspace;
- lifecycle management.

Target product milestone:

Product Preview.

## v0.4 — ENTERPRISE / GOVERN

Question:

Can an enterprise safely operate Agents in production environments?

Expected scope:

- Tenant;
- Identity;
- SSO integration;
- RBAC;
- Policy;
- Secret integration;
- Audit;
- Approval;
- quota;
- usage;
- cost;
- SLA;
- Agent Operations Center.

Focus on Agent-specific governance rather than recreating generic IAM.

## v0.5 — SCALE

Question:

Can Agents operate across large and heterogeneous enterprise
infrastructure?

Expected scope:

- high availability;
- distributed control;
- runtime scheduling;
- autoscaling;
- resource awareness;
- placement policy;
- hybrid cloud;
- multi-cluster;
- model/resource awareness.

The platform should integrate with Kubernetes scheduling ecosystems
rather than recreate generic infrastructure schedulers.

## v1.0 — PLATFORM / TRUST

Question:

Can enterprises depend on the platform?

Primary focus:

- stability;
- compatibility;
- security;
- upgrades;
- migration;
- performance;
- scale;
- documentation;
- ecosystem maturity;
- supportability;
- stable contracts;
- stable APIs;
- Solution Gallery.

## Solution Track

Solutions evolve in parallel with the platform.

Suggested progression:

v0.1:
- Engineering Team.

v0.2:
- Multi-Runtime;
- Research.

v0.3:
- Enterprise Assistant.

v0.4:
- Customer Service.

v0.5:
- Hybrid AI / infrastructure scenario.

v1.0:
- mature Solution Gallery.

## Engineering Tracks

From v0.2 onward, work should be organized across four tracks:

### CORE

Contracts, lifecycle, Control Plane, APIs.

### ECO

Runtime, Model, Capability, State, and enterprise integrations.

### PRODUCT

Console, Factory, Catalog, Operations experience.

### SOLUTION

Golden scenarios and end-to-end validation.

## Release Principle

A version is not complete only because Core code is complete.

Where applicable, release readiness requires:

- Core acceptance;
- integration acceptance;
- Solution acceptance;
- documentation;
- reproducibility;
- quality gates.

## Development Strategy

Use:

Contract-first
+ AI-native engineering
+ parallel tracks
+ solution-driven development.

Human ownership:

- North Star;
- product decisions;
- architecture;
- contract approval;
- risk;
- release gates.

Coding Agent ownership may include:

- implementation;
- tests;
- refactoring;
- documentation;
- examples;
- CI fixes;
- bounded integration work.

## Planning Targets

Current planning targets are directional and must be recalibrated using
actual repository delivery data.

Target milestones:

- v0.1 Alpha: near-term release hardening;
- v0.3 Product Preview: approximately 2–3 months under an effective
  Codex-native workflow;
- v1.0 Enterprise Proof: approximately 4–6 months under sustained
  parallel execution and strong quality gates.

These are planning targets, not release commitments.
