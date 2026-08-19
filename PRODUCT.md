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

## Current Release Boundary

v0.1.0-alpha proves the Agent Control Plane core.

It MUST focus on:

- installability;
- real execution;
- multi-agent workflow;
- failure and retry semantics;
- observability;
- documentation;
- reproducibility.

It MUST NOT expand into the complete Enterprise Agent Platform.

## North Star Test

Every significant new capability must answer:

Does this capability help an enterprise better produce, run, compose,
govern, or operate AI agents?

If not, it should normally remain outside the product core.
