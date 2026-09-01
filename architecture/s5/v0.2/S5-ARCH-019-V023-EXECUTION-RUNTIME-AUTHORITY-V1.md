# S5-ARCH-019 — v0.2.3 Execution and Runtime Authority v1

## 1. Decision record

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-019` |
| Type / checkpoint | `ARCH / G2`; terminal reconciliation after Checkpoint A |
| Authorized baseline | `c06c5d8da89e1df960e64f48036c9dea2f8166a5` |
| Decision status | `CLOSED / COMPLETED / SESSION_CLOSED / DURABLY_INTEGRATED / BINDING` |
| Durable integration | PR #106; main `4200bd33c489bd544c04c3209f58b5b84c80bd14`; CI `33467767800 / SUCCESS` |
| Implementation status | `NOT_STARTED / NOT_ALLOCATED`; authority `NONE` pending separate Human allocation |
| Contract status | internal v0.2.3 architecture; `NOT_FROZEN` |
| Supersession | specializes S5-ARCH-018 for v0.2.3; does not reopen or supersede it |

This binding decision establishes the smallest authority boundary needed for later
v0.2.3 closed-loop execution. It changes no public CRD or Kubernetes API group,
creates no migration, implements no Runtime adapter, and allocates no implementation
Session. Separate Human implementation allocations remain required. S5-ARCH-019 and
its integrating S5-REL-060 Session are closed and may not be reopened.

## 2. Decision

PostgreSQL owns stable Product execution identity, intent, history and normalized
facts. Kubernetes owns actual CRD and workload state. Runtime providers own their
native effects and identifiers. A typed reconciler compares versioned PostgreSQL
desired commands with timestamped Kubernetes/provider observations and appends the
result; observation never directly rewrites Product authority.

The existing Native Runtime, Task/Workflow controllers, coordinator and execution
envelope are reused through an internal translator. OpenClaw follows only after the
Native boundary is stable and is limited to a real, exact-version, bounded adapter.
Execution Evidence moves from transitional SQLite to PostgreSQL by one verified
single-writer cutover before v0.2.3 closed-loop completion.

## 3. Canonical identity model

Every Platform identity is opaque, stable, scoped by `(namespace, security_domain)`,
and independent of storage row IDs and external identifiers.

| Concept | Identity and relation | Binding invariant |
| --- | --- | --- |
| Digital Employee Definition/Template | immutable revision of business role/composition | definition is not a running employee |
| Digital Employee Instance | instance of one exact approved definition revision | owns assignments; not an Agent or Runtime Instance |
| Agent Definition | immutable published agent revision | definition is not an Agent Instance |
| Agent Instance | execution participant bound to exact Agent Definition and Runtime Instance | may span Attempts; is not a Runtime or Pod |
| Workflow Definition | immutable executable graph/plan revision | definition is not a Workflow Run |
| Workflow Run | one execution of one exact approved Workflow Definition/Plan | rerun creates a successor Run |
| Task Definition | immutable task node semantics within a Workflow Definition | definition is not a Task Run |
| Task Run | one task occurrence within one Workflow Run | retry does not create another Task Run |
| Attempt | one authorized execution try under one Task Run | retry creates a new Attempt; Pod restart does not |
| Assignment | durable binding of work to a Digital Employee Instance and approved inputs | routing consumes it; it is not Placement |
| Runtime Profile | immutable/selected runtime requirements and configuration references | profile is not a Runtime Instance |
| Runtime Instance | Platform lifecycle identity for a runtime realization | external runtime, Pod and Service IDs are correlations |
| Placement | immutable decision binding an Attempt/Agent Instance to a Runtime Instance | decision is not the runtime realization |
| Session | execution-context identity, optionally affinity-bearing | never substitutes for Run, Task, Agent or Runtime identity |
| State/Memory Reference | typed reference to separately owned state | no State Plane authority is created here |
| Evidence | immutable, ordered execution fact with canonical bytes and digest | Evidence is not business Outcome |
| Outcome | immutable business/technical assessment referencing Runs and Evidence | never inferred from Pod phase alone |
| Feedback | append-only assessment of an Outcome; may supersede prior Feedback | never rewrites Evidence or Outcome |
| Intervention | append-only requested/applied/observed Human or policy action facts | action is not silently inferred from external state |

Platform identity must never equal or derive authority from Pod name/UID, CRD UID,
provider session, native invocation ID or database sequence. Native identifiers are
opaque correlations. Exact approved revision/digest bindings are immutable per
Attempt. A correction creates an approved successor definition or plan and a
successor Workflow Run; it never edits the prior Run.

## 4. Authority matrix

### 4.1 PostgreSQL authority

PostgreSQL is authoritative for Digital Employee Instance, Agent Instance, Runtime
Instance, Assignment, Workflow Run, Task Run, Attempt, Placement, desired Runtime
commands and versions, authorization/compatibility/policy decision references,
Intervention, Outcome, Feedback, post-cutover immutable Execution Evidence, and
append-only reconciliation facts. It also stores exact approved Plan/resource
bindings, idempotency keys, generations, correlations, observation timestamps and
high-water marks.

### 4.2 Kubernetes authority

Kubernetes is authoritative for actual CRD and workload state; Deployment, Service
and Pod existence/state; observed readiness and health; termination; owner references;
and technical status. Existing public Agent, Task and Workflow CRDs remain unchanged.
Kubernetes objects cannot mint Product identities or declare business success.

### 4.3 Provider authority

A provider is authoritative only for its native accepted/running/terminal effects,
health observations and opaque handles. Those facts become Platform-visible only
through normalized, timestamped observations and Evidence. Provider identity never
replaces Platform identity, and provider observation cannot authorize work.

No fact has two authorities. PostgreSQL records correlations and observations about
Kubernetes/provider facts without becoming their live-state authority.

## 5. Desired and observed reconciliation

A desired-state command is an immutable typed request containing command ID, Runtime
Instance ID, action, desired-state version, reconciliation generation, scope,
authorization/compatibility/policy references, idempotency key and creation time.
Permitted initial actions are an allowlisted adapter set such as `START`, `STOP`,
`CANCEL`, `REPLACE` and `OBSERVE`; adapters may support only a subset.

An observed-state fact contains observation ID, Runtime Instance ID, generation,
source kind, opaque resource correlations, normalized state, health, readiness,
observation time, ingestion time, freshness threshold, source version and Evidence
references. `health` is whether the realization can operate; `readiness` is whether
it may accept assigned work. Neither implies business success.

The reconciler processes `(runtime_instance_id, generation)` idempotently:

1. load authorized desired command and last observations;
2. reject stale, mismatched-scope or unapproved commands;
3. observe before issuing an external effect when replay or ambiguity is possible;
4. issue only a fixed typed adapter operation with its durable idempotency key;
5. append accepted/applied/observed or uncertainty facts;
6. converge only when the observation matches the desired generation.

State is `UNKNOWN` when no trustworthy current observation exists, `STALE` when the
freshness threshold is exceeded, and `RECOVERY_REQUIRED` when safe convergence needs
Human action or cannot prove whether a destructive/external effect occurred. Process
restart marks cached liveness stale, re-observes external authority and never blindly
reissues an ambiguous action. Missing or replaced Kubernetes objects are correlated
by typed labels/owner references and observed UID, never by business-selected name.

Graceful stop first persists the authorized desired command, stops new assignment,
requests the adapter's bounded drain/stop, then observes termination. Failure
replacement creates a new realization correlation under the same Runtime Instance
generation or a successor generation according to policy; it never creates an
Attempt unless an explicit retry decision does so. Destructive ambiguity fails to
`RECOVERY_REQUIRED`.

Claims are limited to replayable desired commands, append-only observations and
bounded reconciliation. Exactly-once effects, uninterrupted continuity, automatic
recovery, HA, failover and portable runtime State are explicitly unsupported.

## 6. Kubernetes safety boundary

| Prohibited | Controlled alternative |
| --- | --- |
| arbitrary Pod creation or YAML editing | typed, allowlisted Runtime command |
| business-selected Pod name | Platform-generated opaque correlation |
| frontend Pod deletion | authorized cancel/stop command persisted before adapter action |
| Pod UID as business identity | opaque observed-resource correlation |
| Pod `Running` as business success | terminal Attempt/Outcome supported by Evidence |
| restart count as Attempt | explicit PostgreSQL Attempt identity |
| arbitrary exec | fixed adapter operation set |
| raw Secret or environment exposure | typed Secret Reference and redacted status |
| unsanitized logs | allowlisted structured Event/Evidence |
| Kubernetes observation mutating Product authority | append observation, then reconcile through typed policy |

Authorization, compatibility and policy decisions occur before Placement and every
invocation. Free-form environment, commands, YAML, logs and provider payloads are
rejected or strictly normalized; secret values never enter commands, Evidence,
status, logs or frontend projections.

## 7. Execution Evidence PostgreSQL cutover

The accepted S5-ARCH-010 append-only semantics and S5-ARCH-018 PostgreSQL direction
remain binding. The PostgreSQL adapter must preserve exact record ID, canonical
bytes, canonical digest, schema/digest version, namespace/security domain, aggregate
identity, ordinal, event and recorded timestamps, supersession and typed references.
Conformance includes insert, exact replay, conflicting replay, scoped reads,
deterministic order, high-water reads and failure mapping.

SQLite import order is its deterministic storage sequence, with record identity as
a stable tie-breaker if required by the accepted repository. The importer records a
resumable checkpoint containing source backup identity/digest, last imported storage
sequence and record ID, target high-water, importer version and verification status.
Resume revalidates both stores and the checkpoint before appending.

Cutover procedure:

1. stop the sole Evidence writer and prove writer quiescence;
2. create verified SQLite and PostgreSQL backups;
3. establish source row count, high-water, ordered record IDs and digests;
4. import deterministically with exact replay semantics and resumable checkpoints;
5. verify schema versions, scopes, canonical bytes/digests, references, ordinals,
   timestamps, row count, order and high-water marks;
6. atomically configure PostgreSQL as the sole writer and restart it only after all
   checks pass;
7. retain SQLite and both backups as bounded read-only rollback material.

There is one cutover and exactly one authoritative Evidence writer at any time. Dual
write, shadow write, silent fallback, partial-store rollback and identity/digest
rewriting are prohibited. Rollback stops writers, restores the complete verified
pre-cutover storage/configuration, verifies it, then starts the SQLite writer; records
written only after PostgreSQL cutover require a separately reviewed complete-store
reconciliation and cannot be discarded silently.

STOP if writer quiescence, backup verification, canonical-byte reproduction, scope,
ID/digest/order/reference/high-water parity, checkpoint integrity or exclusive-writer
configuration cannot be proven. Corrupt, unknown-version or conflicting records also
STOP cutover and require recovery; no incomplete store may serve as complete.

## 8. Migration `0008`

Migration number `0008` is `FUTURE_RESERVED_FOR_V0.2.3_EXECUTION_AUTHORITY /
NOT_IMPLEMENTED / NOT_ALLOCATED` for the first separately authorized v0.2.3
Execution Authority/PostgreSQL Evidence implementation. Future Track A is its sole
writer if separately allocated. One transactionally applied
migration should introduce the mutually constrained execution identities, Runtime
Instance/reconciliation facts, PostgreSQL Execution Evidence and Intervention/Outcome
relations together, because splitting them would permit invalid intermediate schemas.
If PostgreSQL DDL or import mechanics require non-transactional steps, `0008` remains
the schema owner while the data cutover is a separately checkpointed startup barrier.

Future Track B supplies schema requirements and compatibility fixtures before `0008` is
frozen, but cannot edit a migration or own a competing migration. This proposal does
not create `0008`, freeze its physical schema or authorize a dependency. The v0.2.2
migration chain remains `0001` through `0007`; Wave 3B requires no migration. Any
Wave 3B requirement for `0008` or another migration is `STOP / G2` and requires new
Human authority.

## 9. Native Runtime reuse

The first executable increment uses Native only. It preserves public v0.1 CRDs and
reuses compatible Task/Workflow controllers, execution coordinator, Native provider
and execution envelope. An internal translator maps PostgreSQL Workflow Run, Task
Run, Attempt, Placement, Runtime Instance and Agent Instance identities into the
existing envelope and passes stable Attempt/Platform identity through invocation.

The translator records the Kubernetes UID and native invocation ID only as observed
correlations. Normalized Events, Evidence and Outcome persist in PostgreSQL. Runtime
and Agent Instance reconciliation wraps existing workload behavior without making
PostgreSQL the actual Kubernetes-state authority. Rebuilding or replacing Native
Runtime requires separate evidence and review.

## 10. Bounded OpenClaw boundary

After Native contract stabilization, a separately allocated Track B may implement an
explicit `OpenClaw` Runtime type and exact-version adapter supporting multiple Platform
Runtime Instances, manual desired replicas, Assignment routing, declared session
affinity, explicit stateful/stateless mode, separate health/readiness, graceful stop,
bounded failure replacement, exact Run/Task/Attempt/Agent/Workflow linkage, opaque
native identifiers and normalized Evidence.

The adapter must exercise real accepted and terminal execution; fixtures cannot be
represented as execution proof. Automatic elasticity, HA, automatic failover,
multi-cluster/region, state migration, rolling upgrade, generalized certification
and production-readiness claims are excluded. A stateful declaration does not create
State portability or migration authority.

## 11. Intervention, retry, rerun and Outcome

- Cancel appends distinct `requested`, adapter `applied` and externally `observed`
  facts. Unknown application remains explicit; cancel does not erase an Attempt.
- Retry appends a decision and creates a new Attempt under the same Task Run. It
  references the failed/ambiguous predecessor Attempt and uses a new idempotency key.
- Rerun creates a successor Workflow Run referencing its predecessor and the same or
  successor approved Plan as applicable. It does not reuse Attempt identity.
- Correction references prior Evidence and Outcome, creates an approved successor
  definition/plan with a new digest, and executes a successor Workflow Run.
- Approval binds the exact successor revision and digest before Placement/invocation.
- Outcome is immutable and cites exact Runs, Attempts and Evidence. Feedback may
  supersede Feedback but never rewrites Outcome or Evidence.
- Comparable Outcomes preserve predecessor/successor Runs, Evidence sets, comparison
  method/version and explicit missing or `NOT_MEASURABLE` values.

## 12. Later implementation tracks

### Track A — Execution Authority and PostgreSQL Evidence Continuity

Owns canonical execution identity schemas, typed repository ports, PostgreSQL
adapters, migration `0008`, Evidence import/cutover, Intervention/Outcome persistence,
and conformance/recovery tests. Preferred paths are:

- `console/backend/src/agent_console/execution/`
- `console/backend/src/agent_console/execution_postgres.py`
- `core/src/agent_core/execution_evidence/postgres.py`
- `console/backend/tests/execution/`
- `core/tests/test_postgres_evidence_repository.py`
- `console/backend/migrations/0008_execution_runtime_authority.sql`

### Track B — Runtime Manager Core and Native/OpenClaw Adapters

Owns runtime-control domain, Runtime Instance desired/observed reconciliation,
Native reuse, OpenClaw adapter, Placement consumption, observed-state normalization,
Runtime tests and separately authorized bounded fixtures/manifests. Preferred paths:

- `core/src/agent_core/runtime_control/`
- `operator/src/agent_operator/runtime_manager/`
- `runtime/src/agent_runtime/providers/openclaw/`
- `operator/tests/runtime_manager/`
- `runtime/tests/openclaw/`
- `runtime/tests/native_runtime_manager/`

Track A must establish identity/port/schema candidates and stabilize the Native
execution handoff before Track B's first executable increment. Track B may provide
requirements and contract tests in parallel but OpenClaw execution follows Native.
Neither track is allocated by this decision.

Evidence ports/domain, internal execution envelope, coordinator, operator bootstrap,
deployment manifests, backend composition, end-to-end tests and Product/Technical
frontend integration are shared integration paths. They are serialized through a
later Human assembly Gate after S5-IMPL-053 releases protected paths.

## 13. S5-IMPL-053 parallelism and compatibility

This architecture Session modifies documentation only and may run beside S5-IMPL-053.
It does not modify `app.py`, frontend shell/routes/styles, Wave 3 modules/journey or
`CURRENT_IMPLEMENTATION.md`. Later Tracks A and B must not touch those protected paths
until a Human assembly Gate assigns them.

No public CRD/API, Kubernetes group, frozen Contract, existing v0.1 behavior or
S5-ARCH-018 authority changes. S5-ARCH-002's earlier Candidate deliberately omitted a
universal Runtime Instance; this proposal adds an internal v0.2.3 Product lifecycle
identity without freezing the Runtime Contract or requiring external providers to
expose the same native object.

## 14. Limitations and next gate

This decision provides no implementation, migration, deployment, track allocation,
public Contract freeze, CRD change, State/Model/Tenant/IAM architecture, HA, recovery,
exactly-once, certification, production readiness, v0.2.3 completion, release or
automatic downstream authority. OpenClaw remains unsupported until separately
implemented and proven.

S5-ARCH-019 and S5-REL-060 are closed, durably integrated and may not be reopened.
The only future gate is a separate Human allocation decision for bounded Tracks A
and B and their G1 implementation plans; none is allocated by this decision.
