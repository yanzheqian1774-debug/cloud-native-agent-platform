# S5 v0.2 Architecture Evidence Baseline

This directory is the durable architecture record integrated by S5-REL-001.
It preserves accepted architecture separately from current implementation.
Source code and tests remain authoritative for implemented behavior.

## Active architecture reviews

- [User Intervention, Preference, Feedback, and Governed Optimization Boundary v1](S5-ARCH-012-USER-INTERVENTION-PREFERENCE-FEEDBACK-GOVERNED-OPTIMIZATION-BOUNDARY-V1.md)
  defines the Human-approved-with-constraints Governed Successor and Cold
  Optimization Boundary. It preserves distinct typed authorities for correction,
  intervention, feedback, preferences/consent/deletion, candidates, evaluation,
  future publication/application, and rollback. v0.2 preference and candidate
  behavior is preview-only and `NOT_APPLIED`; governed publication is reserved for
  v0.3. This is architecture-only and changes no implementation, public API, CRD,
  Canonical Graph, dependency, Workflow, Knowledge, Runtime, Demo, or Release state.
  It is `REVIEW / AUTHORIZED / CHECKPOINT_A / PASS_WITH_CONSTRAINTS /
  READY_FOR_HUMAN_S5_ARCH_012_REVIEW_GATE`.
- [Product Intent, Dynamic Work, Role, and Knowledge Consumption Boundary v1](S5-ARCH-011-PRODUCT-INTENT-DYNAMIC-WORK-ROLE-KNOWLEDGE-CONSUMPTION-BOUNDARY-V1.md)
  defines the Human-approved-with-constraints bounded v0.2 authority and contract
  model from a business question to an immutable approved Workflow, deterministic
  authorization-first matching, declared Native placement, authorized read-only
  Knowledge retrieval and citations, execution Evidence, sibling Product/Technical
  projections, and immutable correction successors. It is architecture-only:
  implementation, public API/CRD/Graph changes, generated-role publication, general
  RAG/Knowledge operations, Runtime Manager, MCP Knowledge access, Golden Demo, and
  production claims remain unauthorized. Independent Checkpoint B added one bounded
  safety clarification for durable-architecture mapping, threat completeness, package
  gates, the separate Preference/Intervention/Optimization review, and rollback. It is
  `CLOSING / AUTHORIZED / PASS_WITH_CONSTRAINTS /
  READY_FOR_HUMAN_S5_ARCH_011_MERGE_GATE`.
- [Production Execution Evidence and Shared Read Model Boundary v1](S5-ARCH-010-PRODUCTION-EXECUTION-EVIDENCE-SHARED-READ-MODEL-BOUNDARY-V1.md)
  records the Human-approved Hybrid F authority model and bounded single-node
  SQLite persistence direction for a future v0.2 implementation slice.
  Kubernetes remains public control/current-state authority, the append-only
  internal repository owns detailed evidence, the Canonical Graph owns
  relationships, and one deterministic backend assembler owns the shared
  Product/Technical snapshot. It is architecture-only: implementation,
  production certification, multi-node persistence, public API/CRD changes,
  recovery, and exactly-once claims are not authorized. Independent Checkpoint
  B review is complete with one bounded safety clarification commit; the
  candidate is `CLOSING / READY_FOR_HUMAN_MERGE_GATE / NOT_DURABLE_MAIN`.
- [Product and Technical Graph Projection Scope Gate v1](S5-ARCH-009-PRODUCT-TECHNICAL-GRAPH-PROJECTION-SCOPE-GATE-V1.md)
  defines one internal canonical relationship graph, graph layers, node and
  relation semantics, cardinality, deterministic aggregation and grouping,
  Product/Technical projection policies, identity and plan-revision
  invariants, and architecture-only fixture expectations. It is
  `CLOSING / PASS_WITH_CONSTRAINTS / READY_TO_CLOSE`; Graph Projection is
  architecture-complete but remains `NOT_IMPLEMENTED`, internal, and unfrozen.
  Both views remain `NOT_STARTED`, and Human S5-ARCH-009 Close Confirmation is
  pending.
- [MVS Execution & Orchestration Ownership Gate v1](S5-ARCH-008-MVS-EXECUTION-ORCHESTRATION-OWNERSHIP-GATE-V1.md)
  records the Human-selected O1 bounded exception, temporary authority map,
  mandatory extraction seams, final G2 dispositions, production blocker, and
  constrained S5-IMPL-008 handoff. It is `CLOSING / READY_TO_CLOSE` with Human
  Close Confirmation pending; it does not itself authorize implementation or
  amend ADR-0003.

## Accepted architecture

- [Core Representation & API Gate v1](S5-ARCH-007-CORE-REPRESENTATION-API-GATE-V1.md)
  inventories the current physical APIs and records the Human-accepted R3
  internal-first, compatibility-preserving representation for the bounded A1
  prototype. G2-01–G2-12 are dispositioned with constraints; S5-ARCH-007 is
  `CLOSING / READY_TO_CLOSE` with Human Close Confirmation pending. It changes
  no public API, CRD, schema, production source, or freeze state and does not
  authorize S5-IMPL-001.
- [Digital Employee Golden Demo Scope and Acceptance Candidate v1](../../../S5-ARCH-006-DIGITAL-EMPLOYEE-GOLDEN-DEMO-V1.md)
  defines the S5-ARCH-006 Product Demo scope, layered acceptance contract,
  implementation gap map, and portfolio handoff. Its Human Golden Demo Scope
  Gate passed with constraints, including G07's independently versioned
  Runtime Provider support policy and G08's platform-managed-primary/hybrid
  placement and enterprise asset boundary. The Session is
  `CLOSED / COMPLETED / PASS / SESSION_CLOSED`; it authorizes no implementation
  or freeze. Integration remains separately governed.
- [Runtime Provider Architecture v1](baselines/s5-arch-002-runtime-provider-architecture-v1.md)
  defines the accepted Runtime Provider model. Its acceptance does not freeze the
  Runtime Contract or certify a Provider.
- [Core Contract Convergence v1](baselines/s5-arch-003-core-contract-convergence-v1.md)
  records the reasoning for D30–D36 and AP-S5-001/AP-S5-010/AP-S5-011.
- [S5-ARCH-003 Closeout](closeouts/s5-arch-003-closeout.md) records the final
  human decisions: D30–D36 accepted, D32 Option C, and AP-S5-001/AP-S5-010/
  AP-S5-011 accepted.

## History and closeouts

- [Historical D1–D16 reconciliation](history/s5-arch-001-baseline-reconciliation-v1.md)
  preserves `HISTORICAL_FORMAL_EXECUTION: NOT_VERIFIED`, architecture continuity
  `CONTINUOUS_WITH_REFINEMENTS`, and a passed retroactive-fiction check.
- [S5-ARCH-001 Closeout](closeouts/s5-arch-001-closeout.md)
- [S5-ARCH-002 Closeout](closeouts/s5-arch-002-closeout.md)

## Contract and certification state

- Runtime Contract: `NOT FROZEN`.
- Capability Contract: `NOT FROZEN`.
- `G-S5-RUNTIME-FREEZE-01`: `FAIL / UNCHANGED`.
- Native Runtime: reference / Golden Path candidate.
- OpenClaw: heterogeneous Runtime / shared-Gateway proof candidate.
- Hermes: experimental Managed Runtime candidate, not currently certifiable,
  and not a v0.2 Golden Demo blocker.

Supporting success, failure, and debt evidence is indexed under
[S5 evidence](../../../docs/evidence/s5/README.md). Artifact-level source
provenance is recorded in the
[S5-REL-001 integration manifest](../../../S5-REL-001-INTEGRATION-MANIFEST.md).
