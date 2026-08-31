# S5-ARCH-018 — Bounded Product Continuity Persistence Architecture v1

## 1. Decision record

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-018` |
| Type / checkpoint | `ARCH / G2`; `A — ARCHITECTURE_DECISION_AND_VALIDATION` |
| Authorized baseline | `a6ec463a365b5f12e8fb64b0b84772a3beb0ae15` |
| Decision status | `PROPOSED / READY_FOR_HUMAN_ARCHITECTURE_REVIEW` |
| Implementation status | `NOT_STARTED` |
| Contract status | internal v0.2 architecture; `NOT_FROZEN`; no public API or CRD change |
| Selected direction | domain-owned typed repository ports with bounded single-node SQLite adapters |

This G2 proposes the consolidated persistence architecture for v0.2.2 through
v0.2.4. It authorizes no implementation until Human acceptance and a separately
allocated implementation Session. It does not supersede Kubernetes as authority
for the implemented Workflow/Task desired and current control state, and it does
not create a generalized State Plane, enterprise Tenant architecture, public
Contract, Runtime Manager, Model Gateway, billing authority, HA, distributed
recovery, or exactly-once guarantee.

## 2. Decision

Bounded product continuity is stored as domain-owned canonical aggregates,
immutable revisions, and append-only decisions/facts. Domain services depend on
typed repository ports expressed only in domain values. A v0.2 adapter may store
these records in one configured local SQLite database on one node. SQL, SQLite
types, row identifiers, connection details, pragmas, database paths, and migration
mechanics stay behind adapters. A later PostgreSQL adapter must preserve the same
domain identities, digests, repository behavior, ordering, and conflict semantics.

Product, Technical, Business, Resource, Runtime Operations, and Model Governance
views are authorized projections over the same canonical identities. They never
mint, repair, overwrite, publish, execute, authorize, or persist canonical facts.

## 3. Domain authority matrix

All identities below are Platform identities scoped by `(namespace,
security_domain)`. An immutable revision identity is never a storage row ID.

| Domain | Canonical roots and stable identity | Immutable identity / digest boundary | Mutable or append-only facts | Lifecycle and repository owner | Allowed links; prohibited mutation |
| --- | --- | --- | --- | --- | --- |
| Product Journey | `ProductJourney(journey_id)`; child `BusinessProblem(problem_id)` | `IntentRevision(intent_revision_id)` and `PlanningProposalRevision(proposal_revision_id)`; digest covers normalized semantic content, scope, schema/digest-contract version, predecessor and source identities | journey pointer/status may advance by compare-and-set; approvals, corrections and transitions append | Product Journey domain service and repositories | may reference exact resource/run/outcome identities; cannot mutate Resource, Execution or Model records |
| Enterprise Resources | `AgentDefinition(definition_id)`, `SkillDefinition(skill_id)`, `MCPDefinition(mcp_id)`, `KnowledgeDefinition(knowledge_id)`, and `DigitalEmployee(digital_employee_id)` | each has a domain-specific `revision_id`; digest covers every lifecycle/matching/invocation-affecting field, scope, schema and declared relationships; secrets excluded | draft head may advance; validation, test, review, publication, deprecation and relationship facts append; published revision immutable | owning resource package and its typed repositories | typed references only; consumers cannot edit referenced resources; one resource repository cannot mutate another aggregate |
| Execution | `WorkflowRun(workflow_run_id)`, `TaskRun(task_run_id)`, `Attempt(attempt_id)`, `RuntimeInstance(runtime_instance_id)`, `AgentInstance(agent_instance_id)` | approved-plan binding and exact resource/model bindings are immutable per Attempt; Evidence record has independent immutable identity/digest | commands, interventions, Events, Evidence, Outcomes and Feedback append; last-recorded instance observation may advance but is not liveness proof | Execution domain; existing Kubernetes resources remain implemented Workflow/Task control authority; Execution Evidence retains its S5-ARCH-010 owner | references exact Journey/Resource/Model revisions; cannot publish resources, alter plans, or overwrite Kubernetes control state |
| Model Governance | `ModelDefinition(model_id)` | `ModelRevision(model_revision_id)` and exact evaluation/selection/binding identities; digest covers capability, compatibility and invocation-affecting semantics, not secret values | evaluations, policy decisions, selection, override, fallback, binding, invocation Evidence, change and rollback facts append | Model Governance domain and repositories | execution may consume exact binding; it cannot edit catalog, evaluation, policy, override, fallback or rollback history |

Definitions and Instances, Runtime and State, Model and Agent, and Capability and
implementation remain distinct. Capability declarations are immutable revision
content; observed availability is separate timestamped Evidence.

### 3.1 History invariants

- Published resource revisions are immutable. Changed semantic content creates a
  successor revision with an explicit predecessor link and a new digest.
- Validation, test, Human review, approval, publication, deprecation, policy,
  selection, override, fallback, rollback, command, Event and Evidence records are
  append-only.
- Deprecation changes future eligibility; it never deletes or rewrites history.
- Correction names the exact superseded object and digest and creates a successor.
- Run and Attempt history is retained. A retry is a new Attempt under the same
  logical run unless a separately authorized correction creates a successor run.
- A current pointer is a convenience index updated transactionally with the fact
  that advances it; the history, not the pointer alone, is authority.

## 4. Repository port contract

Each domain defines narrow typed ports. Names are architecture-level candidates;
implementation locations remain subject to the first implementation gate.

```text
ProductJourneyRepository
AgentDefinitionRepository / AgentRevisionRepository
ResourceLifecycleFactRepository
RelationshipFactRepository
ExecutionRunRepository / ExecutionObservationRepository
ExecutionEvidenceRepository (existing boundary retained)
ModelDefinitionRepository / ModelGovernanceFactRepository
KnowledgeIndexSnapshotRepository
```

Ports accept a trusted `Scope(namespace, security_domain)` before identity and
never accept unscoped lookup. Minimum behavior is:

- `add_immutable(record)`: insert, exact replay, or digest conflict;
- `get(scope, typed_id)`: authorized record or disclosure-safe not-found;
- `list(scope, query, page)`: deterministic order and bounded page;
- `append_fact(fact)`: atomic append with aggregate identity, ordinal/version and
  digest;
- `advance_head(expected_revision, successor)`: compare-and-set in one transaction;
- `read_history(scope, aggregate_id, high_water)`: stable ordered history;
- `health/compatibility`: bounded readiness without paths, SQL or raw diagnostics.

Same typed identity plus the same canonical digest and canonical bytes is an
idempotent replay and returns the existing semantic result. Same identity with a
different digest, bytes, scope, provenance, or ownership is a typed conflict and
adds nothing. Digest equality never authorizes a different identity or scope.

Domain services own lifecycle rules and transaction intent. Adapters own atomic
storage execution, not business decisions. Ports expose neither SQL transactions
nor generic CRUD/session objects. Cross-domain workflows use an application
coordinator and explicit typed references; no repository performs cross-domain
hidden mutation. If an operation needs atomic writes across domains, it must either
use one explicitly defined application transaction over the single configured
store or use append-first resumable orchestration with a durable idempotency key;
it may not use silent dual writes.

## 5. Bounded SQLite v0.2 contract

### 5.1 Location and ownership

The v0.2 reference uses one explicitly configured database location for all new
product-continuity domains and the existing Execution Evidence tables. Bounded
separation is allowed only after a later G2 explains atomicity, backup, migration,
availability, and identity consequences. No default current-working-directory,
temporary, repository, or frontend-owned database is allowed.

The service account owns the database directory and database/WAL/SHM files with
least privilege. Startup rejects symlinks, non-regular targets, unsafe ownership
or permissions, unwritable parent directories, and locations inside Git. Secret
values and credentials never determine or appear in a file name.

### 5.2 Transactions, locking and concurrency

- Empty-store initialization and each migration are atomic.
- Immutable insert plus its required append-only acceptance fact is one transaction.
- Head advancement uses compare-and-set in the same transaction as the advancing fact.
- Append uses a unique semantic identity and ordinal/version constraint.
- The adapter uses bounded busy timeout, WAL, `synchronous=FULL`, foreign-key
  enforcement, explicit transactions, and fail-closed error mapping.
- A process may use multiple readers and bounded serialized writers on one host.
  Persistent lock contention returns unavailable/busy; callers do not spin forever.
- WAL does not grant shared-filesystem, NFS, multi-host, multi-node, HA, horizontal
  scaling, or production-durability claims.

### 5.3 Schema and startup

The consolidated store begins at logical schema version `1`. A metadata table
records schema version, adapter marker and migration history with checksums. Startup
checks application-supported minimum/maximum version, required tables/indexes,
constraints and adapter marker before serving reads or writes. Empty storage may be
initialized. Partial, unknown, newer, checksum-mismatched or corrupt schemas fail
closed with stable non-disclosing errors.

Forward migrations are ordered, checksum-bound, reviewed application artifacts.
Migration ownership belongs to the persistence adapter package, while each domain
owns its semantic mapping and compatibility fixtures. Upgrade order is: stop writers,
make a verified bounded backup, run compatibility check, apply one forward migration
transaction at a time, recheck, then start readers/writers. Online mixed-schema
operation is not claimed.

Rollback of application binaries is permitted only while the prior binary declares
the resulting schema readable. Destructive down-migration is not promised. Otherwise
restore the whole verified pre-upgrade database while writers are stopped; never
partially restore a domain or delete newly unknown rows.

### 5.4 Failure, backup and reset

Unavailable, corrupt, incompatible, permission-denied or persistently locked storage
prevents authoritative lifecycle writes and any read that would otherwise be claimed
complete. The system never falls back to memory, fixtures or a new empty file. Errors
expose stable codes only, not paths, SQL, records, counts or foreign existence.

A bounded backup is an operator action using SQLite's safe backup mechanism or a
stopped-service copy of database plus required sidecars. Success requires integrity
and schema checks. Restore is whole-store, stopped-writer and scope-preserving. Reset
is destructive, explicit, separately authorized, never automatic, and makes no
retention/legal-erasure guarantee.

## 6. Security, scope and nondisclosure

`namespace` and `security_domain` are mandatory on every root, revision, fact,
reference, unique constraint, query and cache key. They are tenant-ready safety
discriminators, not a complete Tenant/IAM/RBAC architecture.

Authorization resolves trusted scope before repository lookup, join, aggregation,
count, pagination, snapshot construction or serialization. Missing, contradictory or
untrusted scope denies. A caller cannot distinguish foreign identity, existence,
count, digest, conflict, high-water mark, relationship, timing or deletion state.
Domain services enforce business authorization; repository ports enforce scoped data
access as defense in depth. Frontends never supply authoritative scope.

Cross-scope relationships, joins, aggregates, learning, evaluation reuse and model
selection are prohibited. Explicit future sharing requires a separate G2 and typed
authorization record. Retention periods, legal hold, subject erasure, backup expiry
and cryptographic deletion remain unresolved; no implementation may claim compliance
or hard deletion until those policies are approved.

## 7. Secret boundary

Only typed secret references plus non-sensitive presence/status, reference version,
rotation state and last-verified time may persist. Persisting or digesting API keys,
tokens, passwords, Authorization headers, cookies, frontend credentials, raw provider
sensitive payloads, raw prompts carrying secrets, environment dumps, or migration/log
diagnostics containing values is prohibited. Evidence, logs, exception strings,
backups, fixtures and migration history follow the same rule. Unknown free-form maps
are rejected or strictly allowlisted before persistence.

## 8. Qdrant and Knowledge boundary

Qdrant remains a replaceable derived vector index. SQL authority stores Knowledge
Definition/Revision, document and chunk identities/digests, ingestion identity,
embedding Model Revision, collection/index snapshot identity, Qdrant reference,
authorization scope and ingestion Evidence. Vector bytes may live in Qdrant, but
Qdrant existence, collection state or retrieval success cannot publish Knowledge or
repair missing SQL authority. Rebuild consumes an exact authorized snapshot and
produces a new index-snapshot fact; it does not mutate Knowledge history.

## 9. Runtime reconciliation

Persisted Runtime Instance and Agent Instance observations are last-recorded facts,
not proof of current liveness. On restart, the execution owner first marks prior
observations `STALE` or `UNKNOWN`, reacquires authorized observed state from the
runtime/Kubernetes authority, and reconciles desired, recorded and observed identities.
Ambiguity or missing external authority becomes `RECOVERY_REQUIRED`; it never becomes
continued running, success, Evidence or Outcome.

Durable command and effect idempotency keys prevent blind reissue. If the system
cannot prove whether an external effect occurred, it records uncertainty and requires
reconciliation or Human intervention. Persistence proves replayable facts, not
exactly-once effects, workload recovery, distributed failover or portable State.

## 10. Accounting boundary

Accounting remains a deterministic read model over authorized durable execution,
binding, usage and outcome facts. It has no independent truth and requires no
snapshot persistence in this decision. Missing token, cost or latency inputs remain
`NOT_MEASURABLE`, never zero or inferred. A future performance high-water snapshot
must name its source high-water marks, derivation version and rebuild path and requires
a separate gate if it creates new authority or infrastructure.

## 11. Compatibility and coexistence

The existing `ExecutionEvidenceRepository` semantics, evidence identities and S5-ARCH-010
Hybrid F authority are preserved. Its SQLite schema becomes a versioned domain-owned
part of the one configured store through a forward migration or, if migration cannot
be proven safe, a separately approved stopped-service import. No copy-and-switch,
dual-write or silent re-identification is authorized.

PostgreSQL adoption replaces adapters, not ports or domain objects. Conformance tests
must run unchanged against in-memory test doubles, SQLite and future PostgreSQL for
identity, scope, replay, conflict, ordering, transactions, history and failure mapping.
Database-generated integer keys may exist internally for performance but never escape,
participate in canonical digests, or replace Platform identities.

## 12. First implementation entry — v0.2.2 Durable Agent Definition Lifecycle

This is the copy-ready bounded entry for a separately allocated implementation task.

### Scope and identities

Implement only `AgentDefinition(definition_id)`, immutable
`AgentDefinitionRevision(revision_id, definition_id, predecessor_revision_id,
canonical_digest)`, and append-only `ValidationFact`, `TestFact`, `HumanReviewFact`,
`PublicationFact`, `MatchAuthorizationFact`, and `DeprecationFact`, all scoped by
namespace/security domain. Reuse S5-ARCH-013 publication/matchability semantics;
`MATCHABLE` is derived, not an independently mutable lifecycle state.

Lifecycle acceptance is:

```text
DRAFT -> VALIDATED -> TESTED -> HUMAN_REVIEWED -> PUBLISHED
PUBLISHED + effective scoped match grant -> derived MATCHABLE
PUBLISHED/MATCHABLE -> DEPRECATED (history retained)
```

Every transition binds the exact revision ID and digest. Failed or stale facts do not
advance lifecycle. Published bytes never change. Draft editing creates successor
revisions; deprecation changes eligibility and appends history.

### Ports and writers

Add typed Agent Definition/revision/lifecycle repositories and a SQLite adapter behind
the domain boundary. The Agent Definition application service is the sole lifecycle
writer. Validation/test/review services return typed facts; only the application
service appends them after scope/digest verification. Publication and match authority
remain logically separate as required by S5-ARCH-013. Workbench endpoints and views
invoke services and read projections only; frontend, projection, matcher, fixture,
Kubernetes Agent CRD and caches are prohibited writers.

### Workbench and projections

The Resource Workbench must support authorized catalog/list, detail, draft authoring,
validation, test binding, Human review, publication, immutable revision history,
relationships/consumers, derived match eligibility and deprecation. Product and
Technical views receive the same definition/revision/digest and lifecycle high-water
provenance. No public API/CRD change is implied; any new internal endpoint is a G1 plan.

### Expected implementation paths

Expected paths are bounded to a new or existing domain package under
`console/backend/src/agent_console/`, matching tests under
`console/backend/tests/`, explicit startup/configuration wiring, and narrowly required
internal Workbench frontend paths. Reuse/move of `definition_authority.py` must preserve
current semantics and compatibility tests. `operator/`, `runtime/`, CRDs, public API,
gateway, Qdrant and model-provider paths are out of scope.

### Required tests

- port conformance against in-memory and SQLite adapters;
- same ID/same digest replay and same ID/different digest/scope/provenance conflict;
- exact digest canonicalization and secret-shaped input rejection;
- full lifecycle happy path and every skipped, stale, duplicate or invalid transition;
- immutable published revision and successor/predecessor/correction history;
- publication versus derived scoped `MATCHABLE` separation and deprecation retention;
- authorization-before-lookup, foreign identity/count/existence nondisclosure, scoped
  pagination/aggregation and cache-key isolation;
- atomic head/fact update, injected crash/lock/unavailable/corrupt/incompatible-schema
  failures and no in-memory fallback;
- empty-store v1 initialization, supported forward migration fixture, newer/partial/
  checksum-mismatch rejection and prior-binary compatibility declaration;
- service restart recovers the identical definition ID, revision ID, digest, facts,
  derived eligibility and history from the configured database;
- Workbench sibling projections retain identical canonical identity and provenance;
- existing Execution Evidence coexistence and full repository regression validation.

### STOP conditions and gate

The implementation is `G1` only after Human acceptance of this G2, because it adds
an internal adapter/service/Workbench capability behind approved ports. STOP and
return to `G2` for public API/CRD or Kubernetes authority changes, a second database,
multi-node/shared-filesystem operation, enterprise Tenant/IAM/retention architecture,
general State Plane, destructive migration/down-migration, cross-domain atomicity not
covered here, new persistent dependency, changed S5-ARCH-010/013 semantics, or a need
to persist secret values. Frontend scope or a new endpoint requires a written G1 plan.

## 13. Decision consequences and limitations

This decision gives v0.2 a truthful restart-continuity seam and preserves future
PostgreSQL replacement. It intentionally accepts bounded single-writer contention,
offline migrations and whole-store backup/restore. It does not establish production
readiness, certification, availability/SLA, multi-node safety, complete Tenant or
authorization architecture, retention/deletion compliance, distributed transactions,
exactly-once effects, complete recovery, or release acceptance.

## 14. Human gate

Human Architecture Review must either accept, amend or reject this Proposed decision.
Only acceptance may change Decision Status to `Accepted`. Implementation remains
`Not Started` and requires a separately allocated task, G1 plan, exact paths, tests,
review, PR and Human Durable Integration decision.
