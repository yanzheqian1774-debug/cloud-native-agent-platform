# Product Architecture V2

## Architecture Objective

The platform is an Enterprise Agent Platform built around the
Enterprise Agent Lifecycle.

Its technical kernel is a Kubernetes-native Agent Control Plane.

The architecture intentionally separates agent definitions, instances,
runtime implementations, state, models, and capabilities.

## Architecture Model

The product is organized into eight product planes plus two
cross-cutting systems.

### P8 — Experience Plane

Responsibilities:

- Portal;
- Chat;
- IDE;
- API;
- Event;
- enterprise applications;
- channel integration;
- invocation experience.

The platform provides common invocation and routing contracts without
requiring enterprises to use a single user interface.

### P7 — Agent Production Plane

Responsibilities:

- Agent Factory;
- templates;
- Agent Catalog;
- Workflow Studio;
- evaluation;
- publishing;
- release lifecycle.

This plane turns enterprise requirements into managed Agent
Definitions.

### P6 — Capability Plane

Responsibilities:

- MCP;
- Skills;
- Tools;
- Knowledge;
- Prompts;
- Capability Registry.

Capabilities are reusable enterprise AI assets and must not be tightly
bound to one runtime implementation.

### P5 — State Plane

Responsibilities:

- Session;
- Memory;
- Persona;
- Preference;
- Workspace;
- Context;
- Checkpoint.

Enterprise-owned state should remain portable across compatible
runtime implementations.

### P4 — Agent Control Plane

This is the technical core.

Responsibilities:

- Agent;
- future Agent Instance;
- Task;
- Workflow;
- Desired State;
- lifecycle;
- scheduling;
- reconciliation;
- retry;
- recovery;
- execution coordination.

The Control Plane manages runtimes. It does not become the runtime.

### P3 — Runtime Plane

Responsibilities:

- Native Runtime;
- external runtime adapters;
- runtime lifecycle;
- execution;
- health;
- status;
- result;
- failure;
- checkpoint integration.

Future external runtime integrations may include systems such as
Hermes, OpenClaw, LangGraph, and custom enterprise runtimes.

These integrations are ecosystem targets, not current implementation
claims.

### P2 — Model Plane

Responsibilities:

- model abstraction;
- model providers;
- gateway;
- routing;
- evaluation;
- admission;
- deployment integration.

Agents must not be permanently coupled to one model provider.

### P1 — Resource Plane

Responsibilities:

- Kubernetes;
- compute;
- GPU;
- storage;
- network;
- cloud;
- on-premises infrastructure;
- future resource-aware placement.

The platform should reuse Kubernetes and infrastructure ecosystems
rather than recreate generic schedulers.

## Cross-Cutting — Governance

Responsibilities may include:

- Identity;
- Tenant;
- RBAC;
- Policy;
- Secret;
- Audit;
- Approval;
- data policy.

Governance applies across users, agents, capabilities, state, runtimes,
models, and resources.

Most enterprise governance capabilities are roadmap items and are not
part of the current Alpha implementation.

## Cross-Cutting — Operations

Responsibilities may include:

- usage;
- latency;
- success rate;
- failures;
- token consumption;
- model cost;
- capability usage;
- workflow SLA;
- traces;
- Agent FinOps;
- business value.

## Core Domain Separation

The architecture follows this invariant:

Agent Definition
!= Agent Instance
!= Agent Runtime
!= Agent State
!= Model
!= Capability

These concepts may reference each other but must not collapse into one
implementation object.

## Agent Definition

A future Agent Definition may describe:

- identity;
- instructions;
- runtime requirements;
- model requirements;
- capabilities;
- state policy;
- resource policy;
- governance policy.

It describes what an Agent is, not its concrete running state.

## Agent Instance

Agent Instance is a future first-class lifecycle concept.

Conceptually:

Agent Definition
→ instantiate
→ Agent Instance
→ execute
→ Task
→ participate in
→ Workflow

An Agent Instance may eventually bind:

- Runtime;
- State;
- Owner;
- Workspace;
- Policy;
- Credentials;
- Resources;
- lifecycle state.

Agent Instance is NOT part of the v0.1 Alpha scope.

## Strategic Contracts

The long-term architecture is expected to define:

1. Agent Contract;
2. Runtime Contract;
3. Capability Contract;
4. State Contract;
5. Model Contract.

Governance Contract may become an additional formal contract later.

These contracts are strategic architecture targets. They are not all
implemented today.

## Runtime Architecture

Future direction:

Agent Control Plane
→ Runtime Contract
→ Runtime Adapter
→ Runtime Implementation

A first Runtime Contract should focus only on control-plane concerns
such as:

- start;
- execute;
- cancel;
- status;
- health;
- result;
- error;
- checkpoint;
- metadata.

Runtime-specific configuration may remain opaque where appropriate.

## Reference Implementation Principle

For extensible subsystems:

Contract
→ Reference Implementation
→ Replaceable Ecosystem Provider

The platform should not hard-code one external ecosystem into the
Control Plane.

## Solution Architecture

A Solution is an end-to-end product composition.

Conceptually:

Solution
=
Experience
+ Agents
+ Workflow
+ Capabilities
+ State
+ Runtime
+ Model
+ Governance
+ Example Data
+ Documentation

Solution Gallery is part of the product strategy, not merely a
collection of YAML examples.

## Current Code Mapping

Current repository capabilities map approximately as follows:

- Agent CRD → Agent / Control Plane;
- Task CRD → execution contract / Control Plane;
- Workflow CRD → orchestration contract / Control Plane;
- operator/ → Control Plane;
- workflow/ → currently a placeholder/reserved subsystem directory;
- runtime/ → Native Runtime and current model/provider integration;
- gateway/ → currently a placeholder/reserved subsystem directory;
- console/ → Experience and basic Operations;
- manifests → deployment / Resource Plane;
- engineering workflow example → early Solution Gallery seed.

This mapping does not imply that future planes are already
implemented.

## Architecture Rule

The existing v0.1 implementation should not be strategically
refactored merely to make the future architecture appear complete.

New planes are introduced incrementally through the roadmap.
