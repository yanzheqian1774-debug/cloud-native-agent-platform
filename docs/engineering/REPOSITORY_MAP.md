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

Primary responsibility:

workflow-related implementation that is separated from operator
controller code.

Inspect source before assuming ownership of a particular workflow
behavior because some orchestration behavior may live in operator/.

Relevant tests are under:

workflow/tests/

when present.

### gateway/

Primary responsibility:

gateway/model-related integration owned by the current repository.

Inspect current source before assuming future Model Plane capabilities
exist.

Relevant tests are under:

gateway/tests/

when present.

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

Primary responsibility:

runnable examples and early Solution scenarios where present.

Examples must not be treated as production architecture unless
explicitly documented.

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
