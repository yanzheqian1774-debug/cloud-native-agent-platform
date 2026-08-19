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
