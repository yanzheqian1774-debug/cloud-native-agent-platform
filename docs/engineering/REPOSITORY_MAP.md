# Repository Map

## Purpose

This document provides a fast navigation map for humans and Coding
Agents.

It is not a substitute for reading the relevant source code.

## Primary Areas

### operator/

Primary responsibility:

Agent Control Plane controller/operator behavior.

Inspect this area for:

- reconciliation;
- resource lifecycle;
- controller behavior;
- retry/failure behavior;
- Kubernetes resource management.

Relevant tests are under:

operator/tests/

### runtime/

Primary responsibility:

current Native Runtime and model/provider execution behavior.

Inspect this area for:

- Agent execution;
- runtime lifecycle;
- provider integration;
- model invocation.

Relevant tests are under:

runtime/tests/

### workflow/

Current status:

Placeholder / reserved subsystem directory.

The directory does not currently own production workflow
orchestration.

Current workflow orchestration is primarily implemented under:

- operator/src/agent_operator/workflow_controller.py;
- related modules under operator/src/agent_operator/.

Current workflow behavior is primarily validated by:

- operator/tests/;
- tests/test_workflow_crd.py.

Do not infer implementation ownership from the existence of the
workflow/ directory.

### gateway/

Current status:

Placeholder / reserved subsystem directory.

The directory does not currently implement the future Model Gateway.

Current model/provider execution integration is primarily implemented
under:

- runtime/.

Current provider behavior is primarily validated under:

- runtime/tests/.

The Model Gateway and broader Model Plane described in
ARCHITECTURE.md are future architecture unless current source proves
otherwise.

### console/backend/

Primary responsibility:

Console backend API, repository/projection, schemas, and service logic.

Relevant tests are under:

console/backend/tests/

### console/frontend/

Primary responsibility:

Console frontend.

Frontend changes must use the frontend's repository-defined lint and
build commands.

### tests/

Primary responsibility:

repository-level tests including project and CRD validation.

### manifests/

Primary responsibility:

Kubernetes deployment and resource manifests where present.

Inspect this area for:

- CRDs;
- deployment resources;
- configuration;
- example Kubernetes resources.

### examples/

Current status:

Placeholder / documentation-oriented area unless current contents prove
otherwise.

Current executable Kubernetes examples are primarily found under:

- manifests/.

Do not assume examples/ contains runnable Solution Gallery scenarios
until such examples are explicitly added.

### adr/

Primary responsibility:

Architecture Decision Records.

Architecture-sensitive changes should consult existing ADRs before
introducing new decisions.

### architecture/

Primary responsibility:

architecture documentation where present.

### docs/

Primary responsibility:

project documentation, engineering rules, guides, and future execution
plans.

## Strategic Documents

Repository-level product and architecture direction:

- PRODUCT.md
- ARCHITECTURE.md
- ROADMAP.md

Coding Agent control documents:

- AGENTS.md
- docs/engineering/CODEX_WORKFLOW.md
- docs/engineering/CURRENT_IMPLEMENTATION.md
- docs/engineering/REPOSITORY_MAP.md
- docs/engineering/TASK_TEMPLATE.md
- docs/engineering/DEFINITION_OF_DONE.md
- docs/engineering/ARCHITECTURE_GATES.md
- docs/engineering/DECISION_STATUS.md
- docs/engineering/BRANCH_WORKTREE.md

## Navigation Rule

Before editing:

1. identify the task's owning subsystem;
2. inspect that subsystem's source;
3. inspect its tests;
4. inspect related ADRs;
5. inspect cross-module dependencies;
6. only then propose implementation changes.

Do not infer current implementation solely from directory names or
Roadmap documents.
