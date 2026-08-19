# Architecture Decision Records

This directory records significant architecture decisions for the
Cloud Native Agent Platform.

Architecture approval and implementation progress are separate.

See:

- `docs/engineering/DECISION_STATUS.md`

for the authoritative interpretation rules.

## ADR Index

| ADR | Decision Status | Implementation Status | Decision |
| --- | --- | --- | --- |
| ADR-0001 | Accepted | Implemented | Use Kubernetes as the Agent Platform Control Plane |
| ADR-0002 | Accepted | Partial | Model Agent as a Declarative Enterprise Resource |
| ADR-0003 | Accepted | Partial | Use the Operator and Reconciliation Pattern for Agent Lifecycle |
| ADR-0004 | Accepted | Partial | Introduce a Pluggable Agent Runtime Architecture |
| ADR-0005 | Accepted | Partial | Introduce Model Provider, Model Policy, and Model Gateway Abstractions |
| ADR-0006 | Accepted | Implemented | Introduce a Read-Only Workflow Execution Console |

## Important Interpretation Rule

`Accepted` does not mean `Implemented`.

Decision Status answers:

> Has this architecture decision been approved?

Implementation Status answers:

> How much of this decision is reflected in current source?

For current behavior, inspect source and tests.

For approved architecture, inspect the relevant Accepted ADR.

If current source and an Accepted ADR materially disagree in an area
relevant to the assigned task:

STOP and report architecture/implementation drift.

Do not silently rewrite the implementation or the architecture.

## Known Architecture Drift

### ADR-0003

ADR-0003 defines the Operator primarily around Agent infrastructure
reconciliation and states that lifecycle management does not include
task or workflow execution.

Current implementation also contains Task and Workflow controllers
under `operator/`.

This is intentionally recorded as known architecture drift.

Do not resolve this drift as incidental refactoring.

A future architecture decision must determine the intended long-term
boundary between:

- Agent infrastructure reconciliation;
- Task execution control;
- Workflow orchestration;
- the Kubernetes Operator process/package boundary.

Until then, current source defines current behavior and ADR-0003
continues to define the accepted original architecture decision.

### ADR-0004

ADR-0004 defines runtime selection through `runtimeClass`, a Runtime
Resolver, and a stable Runtime Adapter boundary.

Current Agent configuration instead embeds runtime type/image
information, and the current Operator directly constructs runtime
infrastructure.

The Native Runtime is implemented, but the accepted runtime abstraction
boundary is not.

This is intentionally recorded as known architecture drift.

Do not introduce RuntimeClass or refactor runtime lifecycle boundaries
as incidental work. That requires an architecture-approved task.

### ADR-0005

ADR-0005 defines platform-level ModelProvider, ModelPolicy, and
ModelGateway abstractions and states that Agents should reference a
ModelPolicy rather than directly owning provider-specific model
configuration.

Current Agent configuration embeds model provider/name information and
passes those values toward the runtime.

The runtime also contains a runtime-local `ModelProvider` interface with
mock and OpenAI-compatible implementations. That interface must not be
confused with the broader platform-level ModelProvider architecture
described by ADR-0005.

This is intentionally recorded as known architecture drift.

Do not introduce ModelPolicy, ModelGateway, or rewrite Agent model
configuration as incidental work. That requires an architecture-approved
task.

## Updating ADR Status

When implementation materially advances an ADR:

1. inspect the accepted decision;
2. inspect current source and tests;
3. update `Implementation Status` only when evidence supports it;
4. update this index;
5. do not change `Decision Status` merely because implementation
   differs.

Changing an Accepted decision to Superseded requires a new or
explicitly identified superseding architecture decision.
