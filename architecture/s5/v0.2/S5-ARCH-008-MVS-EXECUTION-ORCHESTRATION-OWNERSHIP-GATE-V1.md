# S5-ARCH-008 — MVS Execution & Orchestration Ownership Gate v1

## 1. Session and decision state

| Field | Value |
| --- | --- |
| ID | `S5-ARCH-008` |
| Type / version | `ARCH` / `v0.2 CONNECT — Digital Employee Technical Preview` |
| Lifecycle / authorization | `CLOSING` / `AUTHORIZED` |
| Status | `PASS_WITH_CONSTRAINTS` |
| Checkpoint | `B — FINAL_G2_CONVERGENCE_AND_S5_IMPL_008_HANDOFF` |
| Result | `READY_TO_CLOSE` |
| Authorized baseline | `f6309c163194ebc7f64a21661770a5a43252e3fc` |
| Selected option | `O1 — BOUNDED_OPERATOR_HOSTED_MVS_INTEGRATION` |
| Human G2 decision | `PASS_WITH_CONSTRAINTS` |
| S5-IMPL-008 | `ACTIVE / BLOCKED_UNTIL_ARCH_INTEGRATION` |
| Implementation started | `NO` |
| Next action | `WAIT_FOR_HUMAN_CLOSE_CONFIRMATION` |

Human G2 selected O1 with every constraint recorded here. This artifact does
not by itself authorize implementation, amend ADR-0003, freeze a Contract, or
grant release, Provider-certification, or production-readiness claims.

## 2. Provenance and scope

Preflight verified both `HEAD` and `origin/main` at the authorized baseline.
The Session ID was preflighted as unused by the dispatching task. This review
uses the accepted S5-PLAN-001 Portfolio, S5-ARCH-007, ADR-0003 and its index,
the current source, and the durable evidence from S5-IMPL-003, S5-IMPL-004/C1,
S5-IMPL-007, S5-REL-011, S5-REL-013, and S5-REL-015.

The source S5-IMPL-008 worktree is read-only provenance and was not mutated.
This Session changes no production code, tests, dependency, public API, CRD,
schema, Provider, Gateway, or Document/File behavior.

## 3. Current physical architecture

The current implementation places three materially different concerns in the
`operator` package/process boundary:

1. Agent infrastructure reconciliation constructs Kubernetes runtime
   resources.
2. `task_controller.py` watches Task creation, translates legacy Task and
   Agent resources into an internal execution envelope, writes a durable
   `Running` replay barrier, invokes the same-name Agent Service over HTTP,
   applies bounded retry classification, and projects the result into current
   Task status.
3. `workflow_controller.py` validates and sequences a DAG, creates
   Workflow-owned Task resources, observes their phases/results, propagates
   inputs, skips blocked nodes, and aggregates current Workflow status.

S5-IMPL-003 added the internal compatibility interpreter and deterministic
Platform Execution Identity without changing public Task or Workflow wire
shape. S5-IMPL-004 provides the independently testable Native Provider
boundary and normalized execution evidence. S5-IMPL-007 provides an internal
Capability Gateway with authorization-before-invocation, unchanged identity,
zero-call denial, and explicit ambiguous-effect semantics. Neither boundary is
currently consumed by the Task/Workflow controllers.

## 4. ADR-0003 intended architecture and exact drift

ADR-0003 is `Accepted / Partial`. It authorizes the Operator and
reconciliation pattern for Agent infrastructure lifecycle, requires runtime
implementation details behind an adapter, and explicitly excludes task
execution, workflow orchestration, model reasoning, and business logic from
the Operator. Its index records the present Task and Workflow controllers as
known architecture drift requiring a future architecture decision.

S5-IMPL-008 would deepen that drift: the Operator-hosted Task path would
coordinate the Native Provider, Capability Gateway, Platform identity, and
internal Outcome evidence, while the Operator-hosted Workflow path would
continue to own DAG progression. The requested integration is therefore a
Control Plane / Execution Plane and cross-plane ownership decision, even
though it requires no public wire change. Under the Architecture Gates this is
G2 and cannot be inferred from the Portfolio or current code.

## 5. Options

| Option | Delivery and compatibility | Architecture consequence | Disposition |
| --- | --- | --- | --- |
| O1 — bounded Operator-hosted MVS integration | Reuses tested controllers; no public API, CRD, schema, dependency, migration, or dual write | Explicit, temporary v0.2 exception; extraction seams and production blocker required | `SELECTED_PASS_WITH_CONSTRAINTS` |
| O2 — separate component now | Aligns physical ownership with ADR-0003 before integration | Broad process/package, lifecycle, deployment, reliability, and test design; premature for the bounded MVS | `NOT_RECOMMENDED_FOR_THIS_MVS` |
| O3 — amend/supersede ADR-0003 for permanent Operator ownership | Could legitimize current placement | Collapses reconciliation and business execution boundaries without production evidence | `REJECT_RECOMMENDATION` |
| O4 — defer S5-IMPL-008 | Avoids further drift | Blocks the vertical slice until permanent ownership is resolved | `FALLBACK_IF_O1_CONSTRAINTS_ARE_NOT_ACCEPTED` |

## 6. Selected decision: O1 bounded exception

Human G2 authorizes O1 only for the v0.2 Minimum Vertical Slice. This is
a temporary physical co-location exception, not permanent Operator ownership.
It preserves the logical boundaries already introduced by the internal Core,
Native Provider, and Capability Gateway packages while deferring a premature
production-grade process split.

O1 does **not** amend or supersede ADR-0003. ADR-0003 already records the
intended separation and the index records current drift. This decision adds a
time-bounded, Human-approved exception with an explicit extraction obligation;
it neither rewrites nor weakens the accepted long-term decision. If Human G2
instead chooses O3 or grants permanent Operator ownership, a separately owned
ADR amendment or superseding ADR and later REL integration are required before
S5-IMPL-008 may resume.

## 7. Temporary authority map

| Concern | Temporary v0.2 owner | Authority and limit |
| --- | --- | --- |
| Kubernetes event/status adaptation | Task/Workflow controllers | Interpret existing resources and project existing statuses only |
| Task execution coordination | Internal Task execution coordinator service/port, physically Operator-hosted | Own bounded use-case sequencing; controller calls it but does not absorb its semantics |
| Workflow DAG coordination | Workflow controller, physically Operator-hosted | Preserve current DAG/task-resource behavior only; no general process engine |
| Platform Execution Identity | Existing Core/compatibility interpreter | Consume unchanged; controllers and Providers must not mint competing identities |
| Runtime execution | Native Provider port/implementation | Consume only; controller must not redefine Provider configuration or lifecycle semantics |
| Capability authorization/invocation | Capability Gateway port/implementation | Consume only; preserve authorization-before-call, zero-call denial, identity, and ambiguity semantics |
| Outcome normalization | Internal, domain-specific normalization boundary | Task, Capability, Runtime, and Workflow evidence remain distinct; vocabulary/version unfrozen |
| Public desired/observed state | Existing Kubernetes Task and Workflow resources | Kubernetes remains source of truth; wire shape and lifecycle semantics remain unchanged |
| Document/File | No owner in initial MVS integration | Explicitly excluded and deferred |

## 8. Controller responsibilities and prohibitions

`task_controller.py` may interpret Kubernetes events, enforce existing
terminal and `Running` replay barriers, construct bounded internal execution
inputs, call the internal coordinator, and translate its result into the
existing Task status. It must not directly own permanent business execution
semantics, redefine Runtime Provider behavior or Capability authorization,
mint an identity, add real HTTP transport to the new Provider/Gateway path, or
change retry/lifecycle semantics.

`workflow_controller.py` may preserve current DAG validation and sequencing,
create and observe current Task resources, propagate current Task results, and
map terminal Task evidence into existing Workflow behavior. It must not become
a general-purpose process engine, redefine public Workflow contracts, bypass
Task execution identity, directly invoke Providers or capabilities, or
silently retry an execution whose effect is ambiguous.

## 9. Mandatory extraction seams

O1 is valid only if S5-IMPL-008 supplies all of these internal seams:

- a Task execution coordinator port/service independent of Kopf handlers;
- consumption of the existing Runtime invocation boundary, without redefining
  Provider configuration or lifecycle semantics;
- consumption of the existing Capability invocation boundary, preserving its
  authorization and ambiguity invariants;
- an internal Outcome normalization boundary that keeps domain outcomes
  distinct and unfrozen;
- an explicit execution context carrying the unchanged Platform Execution
  Identity end to end;
- deterministic, controller-independent component tests for the coordinator;
- collaborators supplied explicitly (Provider, Gateway, repositories,
  selectors, identity minters, and clocks), with no new globals; and
- no new public resource representation.

Physical co-location inside the Operator repository or process is permitted
for this slice; logical dependency direction must allow the coordinator and
its tests to move without importing Kubernetes controller behavior.

## 10. Public compatibility boundary

The decision authorizes no public API, CRD, status schema, Kubernetes API
group, Runtime HTTP wire, Console DTO, Contract freeze, dependency, database,
migration, or dual write. Existing Task and Workflow lifecycle meanings,
replay barriers, retry rules, names, owner references, DAG behavior, and
status projections must remain compatible.

Outcome is internal, domain-specific, version-unfrozen evidence. It is not a
new universal Outcome contract and must not be serialized into unapproved
public fields. Platform identity is consumed unchanged. Native Provider and
Capability Gateway behavior is consumed, not redefined. Document/File remains
outside the initial MVS integration.

If implementation discovers that any public or frozen boundary must change,
or that lifecycle semantics cannot be preserved, S5-IMPL-008 must stop at a
new G2 rather than treating this decision as broader authority.

## 11. Rollback

Because this Session creates documentation only, rollback is removal of this
artifact and its index link. If O1 is later approved and implemented, rollback
must remove the internal controller-to-coordinator integration and restore the
pre-S5-IMPL-008 controller path without data migration, schema rollback, or
dual-write reconciliation. Existing Kubernetes resources and their statuses
remain the compatibility boundary.

## 12. Evidence Debt and extraction trigger

Operator-hosted execution/orchestration remains a bounded v0.2 transitional
implementation. The permanent Execution and Orchestration Component boundary,
deployment topology, durability model, crash recovery, concurrency control,
horizontal scaling, tenancy, and operational ownership remain unresolved.
Current `Running` barriers and framework serialization are not exactly-once
proof. Internal Outcome vocabulary and Provider/Gateway contracts remain
unfrozen; certification and production readiness are not granted.

This debt is not a Technical Preview release blocker. It is a production
blocker until resolved. A new Human architecture decision and extraction are
required before any production-readiness or Provider-certification claim,
release acceptance beyond Technical Preview, broad Workflow intervention,
durable retry/recovery, horizontal execution scaling, production multi-tenancy,
or multi-process/distributed execution—whichever occurs first.

## 13. S5-IMPL-008 handoff and resume conditions

S5-IMPL-008 remains blocked. It may resume only after Human Close Confirmation,
S5-ARCH-008 Session closure, durable REL integration of Draft PR #54 and this
exact architecture artifact, and a separate S5-IMPL-008 Resume Authorization.
The implementing Session must start from that authorized durable baseline,
retain its existing isolated ownership, and revalidate predecessor handoffs
and overlap.

Initial resumed scope is limited to Task/Workflow consumption of the Native
Provider and Capability Gateway plus internal Outcome evidence. Document/File
requires a later, separately authorized boundary. No REL Session starts
automatically, and this architecture Session does not resume or mutate the
blocked implementation worktree.

## 14. Future Product Architecture Handoff

The following direction is preserved for future planning only. It is
`RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED`, is not part of S5-IMPL-008,
and requires a future Human architecture gate:

- synchronized Digital Employee Product and Technical Operations views;
- AI-assisted Job and Agent Definition drafts with Human approval of duties,
  permitted capabilities, and explicit prohibitions;
- problem-driven Work Requests and Work Plans, approved Agent Definition
  matching, and multi-role Dynamic Digital Workforce planning;
- elastic Agent Instance allocation and Runtime Realization scale-up and
  scale-to-zero governed by workload, capacity, cost, and budget policy;
- Skill and MCP Control Plane plus Platform-owned Job, Memory, and State Plane;
  and
- OpenClaw and Hermes only as Runtime/Workspace Adapters, with any proposed
  v0.3 through v1.0 roadmap separately owned and approved.

## 15. G2 decision ledger

| Decision | Human disposition | Binding constraint |
| --- | --- | --- |
| G2-EO-01 — select O1/O2/O3/O4 | `PASS` — O1 selected | Bounded Operator-hosted MVS integration only |
| G2-EO-02 — ADR-0003 treatment | `PASS_WITH_CONSTRAINTS` | No amendment or supersession; explicit time-limited exception; permanent ownership not granted |
| G2-EO-03 — temporary Task ownership | `PASS_WITH_CONSTRAINTS` | Current Operator Task path is a thin adapter, replay-barrier coordinator, and coordinator consumer |
| G2-EO-04 — temporary Workflow ownership | `PASS_WITH_CONSTRAINTS` | Current Operator Workflow path is a thin DAG/Task lifecycle coordinator, not a general process engine |
| G2-EO-05 — extraction seams | `PASS` | Every Section 9 seam is mandatory; no global repository, selector, minter, or clock |
| G2-EO-06 — public compatibility | `PASS` | No public API, CRD, schema, or existing-wire change |
| G2-EO-07 — Outcome | `PASS_WITH_CONSTRAINTS` | Internal, domain-specific, version-unfrozen, non-public, non-normative; no universal Status/Outcome |
| G2-EO-08 — extraction/production blocker | `PASS` | Section 12 trigger; not a Technical Preview blocker; production blocked until resolved |
| G2-EO-09 — Document/File | `PASS` | Prohibited from initial MVS; post-MVS, recommended only, inactive, unauthorized |
| G2-EO-10 — resume conditions | `PASS` | Closure, durable PR #54 REL integration, and separate Resume Authorization required |

```text
SESSION: S5-ARCH-008
LIFECYCLE: CLOSING
STATUS: PASS_WITH_CONSTRAINTS
CHECKPOINT: B — FINAL_G2_CONVERGENCE_AND_S5_IMPL_008_HANDOFF
RESULT: READY_TO_CLOSE
HUMAN_MVS_EXECUTION_ORCHESTRATION_G2_GATE: PASS_WITH_CONSTRAINTS
S5_IMPL_008: ACTIVE / BLOCKED_UNTIL_ARCH_INTEGRATION
IMPLEMENTATION_STARTED: NO
SESSION_CLOSED: NO
NEXT_ACTION: WAIT_FOR_HUMAN_CLOSE_CONFIRMATION
NEXT_GATE: Human S5-ARCH-008 Close Confirmation
```
