# Current Implementation Boundary

## Purpose

This document tells humans and Coding Agents what is actually
implemented in the repository today.

It exists to prevent roadmap or architecture documents from being
mistaken for current product capabilities.

The source code and tests remain the final authority for implementation
details.

## Current Release Planning Context

The current planning baseline targets:

v0.1.0-alpha

Planning phase:

S4.5 — Alpha Release Hardening.

This is planning metadata, not an implementation capability claim.

The current goal is to make the existing Agent Control Plane core:

- installable;
- runnable;
- observable;
- documented;
- reproducible;
- safe to publish as an Alpha.

## Implemented Core

The repository currently contains implementation for the following
core concepts.

### Kubernetes Resources

Implemented custom resources include:

- Agent;
- Task;
- Workflow.

These resources belong primarily to the Agent Control Plane.

### Operator

The repository contains Kubernetes operator/controller behavior for
managing current Agent, Task, and Workflow lifecycle behavior.

### Native Runtime

The repository contains a native Agent runtime implementation.

This is the current runtime implementation.

It must not be interpreted as the final or only runtime architecture.

### Model Integration

The current runtime supports real model execution through the
repository's provider/model integration.

Current provider behavior should be verified from source and
configuration before making provider-specific assumptions.

### Workflow

Current workflow capabilities include tested behavior for areas such as:

- DAG execution;
- dependency handling;
- parallel execution;
- fan-in behavior;
- failure handling;
- retry behavior;
- skip semantics;
- timeout-related behavior where implemented.

Always verify exact semantics from source and tests before changing
workflow behavior.

### Console

The current Console provides a basic workflow execution viewing and
projection experience.

The current Console is not a complete enterprise management portal.

Do not assume that it currently provides:

- Agent Factory;
- enterprise administration;
- tenant management;
- full RBAC;
- policy management;
- Capability Marketplace;
- Runtime Marketplace.

### Kubernetes Source of Truth

Current architecture treats Kubernetes resources as the source of
truth for the implemented Control Plane behavior.

Do not introduce a Console-owned source of truth or persistent Console
database without an approved architecture decision.

## Implemented Quality Baseline

The repository currently uses automated quality checks including:

- Ruff;
- pytest;
- pre-commit;
- make check.

The exact current test count is intentionally not frozen in this
document because it changes over time.

Use the current test suite as the source of truth.

## Not Implemented Yet

The following concepts appear in Product Architecture or Roadmap
documents but must NOT be treated as current capabilities unless source
code proves otherwise:

- Agent Instance as a first-class platform model;
- Agent Factory;
- Agent Catalog;
- Runtime Contract as a stable public contract;
- Runtime Adapter SDK;
- Hermes adapter;
- OpenClaw adapter;
- LangGraph adapter;
- Capability Registry;
- complete MCP management plane;
- State Plane;
- enterprise Memory service;
- Persona service;
- Preference service;
- enterprise Workspace state service;
- multi-tenancy;
- enterprise SSO;
- enterprise RBAC;
- policy engine;
- approval workflows;
- Agent FinOps;
- full Model Registry;
- heterogeneous resource scheduling;
- GPU-aware Agent placement;
- multi-cluster control;
- hybrid-cloud control plane;
- mature Solution Gallery.

These are roadmap or architecture concepts.

Do not implement them unless they are explicitly part of the assigned
task.

## Current Alpha Boundary

v0.1.0-alpha should prove the existing Control Plane core.

Alpha work should prioritize:

- release engineering;
- clean installation;
- Quick Start;
- security hygiene;
- configuration correctness;
- documentation;
- Golden Demo;
- cross-platform validation;
- packaging.

Alpha work should NOT opportunistically introduce v0.2+ platform
architecture.

## Important Compatibility Boundaries

Treat the following as architecture-sensitive:

- public CRD schemas;
- Kubernetes API group;
- Agent lifecycle semantics;
- Task lifecycle semantics;
- Workflow lifecycle semantics;
- Runtime lifecycle behavior;
- Kubernetes source-of-truth model.

Changes to these areas must follow the Architecture Gates.

## Rule for Coding Agents

Architecture and Roadmap documents describe intended direction.

They do not authorize implementation.

For every task:

1. start from the explicit task scope;
2. inspect current source and tests;
3. use this document to distinguish current from planned behavior;
4. stop if the task requires an unapproved architecture change.
