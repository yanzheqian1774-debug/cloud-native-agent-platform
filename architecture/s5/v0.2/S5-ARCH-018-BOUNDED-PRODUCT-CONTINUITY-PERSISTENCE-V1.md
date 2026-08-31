# S5-ARCH-018 — Bounded Product Continuity Persistence Architecture v1

## 1. Decision record

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-018` |
| Type / checkpoint | `ARCH / G2`; `A — ARCHITECTURE_DECISION_AND_VALIDATION` |
| Authorized baseline | `a6ec463a365b5f12e8fb64b0b84772a3beb0ae15` |
| Decision status | `FINAL_RECONCILED_PROPOSAL / READY_FOR_HUMAN_ARCHITECTURE_REVIEW` |
| Implementation status | `NOT_STARTED` |
| Contract status | internal v0.2 architecture; `NOT_FROZEN`; no public API or CRD change |
| Selected direction | domain-owned typed repository ports with PostgreSQL as the primary deployment adapter; bounded SQLite transition/test role |

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
typed repository ports expressed only in domain values. PostgreSQL is the primary
deployment adapter for every newly implemented v0.2.2–v0.2.4 product-continuity
domain. Existing SQLite Execution Evidence remains supported during a bounded
transition, and SQLite or in-memory adapters may support focused local development
and repository conformance tests. SQL statements, PostgreSQL sequences/row IDs,
driver objects, database URLs, PostgreSQL-specific JSON representations, SQLite
paths/types, connection details and migration mechanics stay behind adapters.

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

### 3.2 Governed resource management and deletion

Agent, Skill, MCP, Knowledge and Capability resources, plus applicable Digital
Employee projections, expose one backend-governed management contract. PostgreSQL
persists every authoritative lifecycle mutation and decision. A Workbench or other
projection may request an action but cannot apply, infer or simulate authority.

Applicable management operations are:

```text
create Draft -> edit Draft -> validate/test -> submit for Human review
-> approve or reject exact Revision digest -> publish immutable Revision
-> create successor Revision -> inspect history/relationships/consumers
-> enable/disable where applicable -> deprecate -> archive
-> request deletion -> analyze impact -> purge only when permitted
```

Every operation requires trusted scope, authorization, expected aggregate/revision
version, exact digest where a revision is involved, stable decision identity and a
non-sensitive reason/provenance record. Enable/disable affects only the resource's
declared availability boundary; it cannot silently unpublish, delete history, revoke
unrelated authorization or claim control over an external system.

Deletion is a governed request and decision, not generic repository CRUD:

- An unpublished, unreferenced Draft may be hard-deleted only after authorization,
  an exact-scope reference/consumer check and an atomic decision. The minimum
  non-sensitive deletion tombstone remains so the identity cannot be silently reused.
- A published Revision cannot normally be hard-deleted. Normal removal uses
  deprecation, removal from future matchability, disablement where applicable and
  archival. A successor never overwrites or erases its predecessor.
- Any authorized reference, consumer, binding, Run, Evidence, Outcome, approval,
  relationship or unresolved ingestion dependency makes deletion fail closed. Impact
  analysis runs before mutation, is scope-isolated, records the checked high-water
  marks, and cannot disclose foreign identities or counts.
- Archive removes an object from ordinary active views while preserving authorized
  history, references and audit access. Archive is not purge or deletion.
- Historical Evidence, Outcome, approval, review, publication, selection, binding and
  rollback facts are never rewritten to make a deletion appear to have always existed.

Knowledge compliance purge is a separately authorized exceptional path. It removes
applicable prohibited source content, document/chunk payloads, derived Qdrant vectors
and derived caches, and appends a scope-bound purge decision. It preserves only the
minimum non-sensitive tombstone/audit facts necessary to prove identity, affected
revision/digest, authority, time, reason classification and completion state; it must
not preserve prohibited content in the tombstone, logs, Evidence or backups. SQL and
Qdrant/cache cleanup is resumable and explicitly reports partial or
`RECOVERY_REQUIRED`; no cross-store atomicity is claimed. Exact retention, legal hold,
backup expiry and regulatory authority still require the applicable governance gate.

MCP deprecation, archival or purge removes only the Platform-managed MCP Definition,
Revision, credentials references, bindings and derived caches within authorized scope.
It makes no claim that an external MCP server, its data or its operator-owned logs
were deleted. External cleanup requires separately verified authority and Evidence.

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
hidden mutation. If an operation needs atomic writes across PostgreSQL-owned domains,
it must use one explicitly defined application transaction. A transitional operation
that links PostgreSQL to SQLite Execution Evidence uses append-first resumable
orchestration with a durable idempotency key and explicit partial/uncertain state;
it has no cross-store atomicity and may not use silent dual writes.

## 5. PostgreSQL v0.2 deployment contract

### 5.1 Instance, database and ownership

The bounded v0.2 deployment uses one PostgreSQL instance and one logical database
for new Product Journey, Enterprise Resource, Execution and Model Governance
domains. Each domain owns an explicit schema or equivalently explicit migration
namespace and grants no schema ownership to frontend or projection code. Additional
databases, cross-database transactions, replicas, sharding or distributed ownership
require a later G2.

Connection configuration is supplied by the deployment boundary. Credentials are
resolved only through external typed Secret references; they are absent from domain
objects, logs, Evidence, migrations and frontend configuration. TLS and private
network transport are required where the deployment environment supports them;
an implementation must document any local exception without claiming production
security.

### 5.2 Transactions, locking and concurrency

- Empty-database initialization and each migration are atomic where PostgreSQL DDL
  semantics permit; any non-transactional operation requires a separately reviewed
  resumable step and startup barrier.
- Immutable insert plus its required append-only acceptance fact is one transaction.
- Head advancement uses compare-and-set in the same transaction as the advancing fact.
- Append uses a unique semantic identity and ordinal/version constraint.
- Unique and foreign-key constraints enforce scoped semantic identity and typed
  relationships in addition to domain validation.
- Updates use optimistic concurrency through expected revision/high-water values;
  digest or version conflicts fail without partial writes.
- The adapter uses explicit isolation levels, bounded statement/lock/transaction
  timeouts and fail-closed error mapping. Deadlock or serialization failure may be
  retried only through a bounded idempotent operation.
- The application connection pool has explicit per-process minimum/maximum size,
  acquisition timeout, idle/lifetime limits and a deployment-wide connection budget.
  Exhaustion returns unavailable; callers do not spin forever.
- No HA, replica-read consistency, multi-region, distributed transaction,
  horizontal-scale or production-certification claim is made.

### 5.3 Schema and startup

The PostgreSQL product-continuity store begins at logical schema version `1`. A metadata table
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
complete. The system never falls back to memory, SQLite, fixtures or a new empty
database. Errors
expose stable codes only, not paths, SQL, records, counts or foreign existence.

A bounded backup uses a PostgreSQL-consistent logical or physical backup appropriate
to the deployment. Before first implementation acceptance, backup and restore must be
rehearsed into an isolated database and verified by schema, constraint, row/digest,
scope and repository-conformance checks. Restore is whole-database, coordinated with
stopped writers and scope-preserving. Reset is destructive, explicit, separately
authorized, never automatic, and makes no retention/legal-erasure guarantee.

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
Hybrid F authority are preserved. During v0.2.2, existing Execution Evidence SQLite
remains unchanged while new Product Journey and Enterprise Resource authority is in
PostgreSQL. Cross-store links contain canonical identities, exact digests and scope;
there is no cross-store transaction, atomic commit, referential constraint or
exactly-once claim. Health and Technical Inspection must label the split authority
and independently report either store as unavailable or stale.

Before v0.2.3 closed-loop execution is complete, add a PostgreSQL Execution Evidence
adapter behind the existing typed port. Run the same repository conformance suite
against SQLite and PostgreSQL, preserving Evidence identities, digests, append-only
behavior, ordering, authorization-first reads and disclosure-safe errors. Define and
validate an explicit migration/import and cutover procedure:

1. freeze or high-water-bound SQLite Evidence writes;
2. verify source integrity, schema and scoped record counts/digests;
3. import idempotently into PostgreSQL without minting identities or rewriting time;
4. compare all identities/digests/ordinals and authorization behavior;
5. switch the injected adapter through configuration only;
6. retain a rollback window with no dual authority; and
7. archive or retire SQLite only through a separately authorized retention decision.

Dual-write is prohibited unless a later G2 defines conflict authority and recovery.
New closed-loop execution must not depend indefinitely on split authoritative stores.
Failure to prove import, cutover, rollback and conformance blocks v0.2.3 completion.

PostgreSQL and SQLite adapters replace storage mechanics, not ports or domain objects.
Database-generated keys may exist internally for performance but never escape,
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

Add typed Agent Definition/revision/lifecycle repositories and a PostgreSQL deployment
adapter behind the domain boundary. In-memory or SQLite adapters may be used only for
focused test/local-development conformance and are never deployed product authority.
The Agent Definition application service is the sole lifecycle
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

The accepted AI management-platform prototype is a non-authoritative product-design
reference. Implementations may preserve its unified platform shell, left navigation,
global search, business-first Golden Demo entry, Dashboard/List/Detail patterns,
Enterprise Resource Catalog, Factory/Runtime separation, monitoring/security/domain-
application entries and restrained enterprise visual style. Prototype data, simulated
actions, metrics, model names, cost values, frontend state and mock responses are never
authority or acceptance Evidence. All lifecycle and mutation actions remain
backend-governed and PostgreSQL-persisted.

The versioned Workbench delivery mapping is:

- v0.2.2: Business/Resource Workbench, Agent/Skill/MCP/Knowledge Factory and
  PostgreSQL product-continuity persistence;
- v0.2.3: Runtime Operations, Runs, Instances, Intervention, Evidence and Outcome,
  including completion of the PostgreSQL Execution Evidence migration gate; and
- v0.2.4: Model Catalog, Evaluation, Selection, exact Binding and evidence-backed
  usage/cost, with missing facts still `NOT_MEASURABLE`.

### Expected implementation paths

Expected paths are bounded to a new or existing domain package under
`console/backend/src/agent_console/`, matching tests under
`console/backend/tests/`, a PostgreSQL adapter/migration package, explicit
startup/configuration wiring, deployment Secret/reference and PostgreSQL prerequisite
manifests, and narrowly required internal Workbench frontend paths. Reuse/move of
`definition_authority.py` must preserve current semantics and compatibility tests.
`operator/`, `runtime/`, CRDs, public API, gateway, Qdrant and model-provider behavior
remain out of scope. Any deployment-manifest path must be exact and may provision only
the approved bounded PostgreSQL dependency; S5-DEPLOY-003 remains prohibited.

### Required tests

- port conformance against PostgreSQL and focused in-memory/SQLite adapters using
  identical cases and domain results;
- same ID/same digest replay and same ID/different digest/scope/provenance conflict;
- exact digest canonicalization and secret-shaped input rejection;
- full lifecycle happy path and every skipped, stale, duplicate or invalid transition;
- immutable published revision and successor/predecessor/correction history;
- publication versus derived scoped `MATCHABLE` separation and deprecation retention;
- complete governed management-operation transition coverage, including enable/
  disable and archive where applicable;
- unpublished/unreferenced Draft authorized hard delete with retained non-sensitive
  tombstone; published Revision hard-delete rejection and identity non-reuse;
- reference/consumer/binding/Run/Evidence/Outcome/approval impact checks that fail
  closed before mutation and disclose no foreign identity or count;
- Knowledge purge success, partial failure/resume and retry across SQL, Qdrant and
  caches; prohibited-content absence from tombstone/log/Evidence/backup fixtures;
- MCP removal tests proving Platform records are affected without claiming or issuing
  external MCP server deletion;
- immutable historical Evidence/Outcome/approval facts across deprecation, archive,
  deletion request and purge;
- authorization-before-lookup, foreign identity/count/existence nondisclosure, scoped
  pagination/aggregation and cache-key isolation;
- atomic head/fact update; optimistic-concurrency, unique/FK, deadlock/serialization,
  pool-exhaustion, timeout, unavailable and incompatible-schema failures; bounded
  idempotent retry and no in-memory/SQLite deployment fallback;
- empty-database v1 initialization, supported forward migration fixture, newer/partial/
  checksum-mismatch rejection and prior-binary compatibility declaration;
- external Secret-reference-only connection configuration; database URL/credential,
  driver, SQL, sequence ID and PostgreSQL JSON representation non-leakage;
- TLS/private-network configuration where applicable and stable non-disclosing
  database-unavailable errors;
- PostgreSQL backup/restore rehearsal with exact identity, digest, scope, history and
  constraint verification;
- service restart recovers the identical definition ID, revision ID, digest, facts,
  derived eligibility and history from the configured database;
- Workbench sibling projections retain identical canonical identity and provenance;
- explicit SQLite Execution Evidence coexistence with cross-store canonical identity/
  digest linkage and no cross-store atomicity claim;
- PostgreSQL Execution Evidence adapter conformance plus verified import/cutover/
  rollback fixtures before v0.2.3 completion; and full repository regression validation.

### STOP conditions and gate

The implementation is `G1` only after Human acceptance and Durable Integration of
this amended G2, because it adds an internal adapter/service/Workbench capability
behind approved ports. The first implementation requires a PostgreSQL driver/client
dependency if none is already present, an externally supplied Secret reference,
bounded connection-pool configuration, an available PostgreSQL database, ordered
migration execution and backup/restore rehearsal. Dependency/lockfile and deployment
prerequisite changes require exact G1 planning and security review; they are not
implemented by this decision. STOP and return to `G2` for public API/CRD or Kubernetes
authority changes, more than the approved PostgreSQL database plus transitional
Evidence SQLite arrangement, SQLite shared-filesystem/multi-node use, PostgreSQL HA,
replication or multi-region operation, enterprise Tenant/IAM/retention architecture,
general State Plane, destructive migration/down-migration, cross-domain atomicity not
covered here, another persistent dependency, changed S5-ARCH-010/013 semantics, or a need
to persist secret values. Frontend scope or a new endpoint requires a written G1 plan.

## 13. Decision consequences and limitations

This amended decision gives v0.2 a truthful PostgreSQL deployment seam and preserves
SQLite only for bounded transition/local conformance. It intentionally accepts an
explicit v0.2.2 dual-store transition without cross-store atomicity, ordered migrations
and coordinated whole-database backup/restore. It does not establish production
readiness, certification, availability/SLA, multi-node safety, complete Tenant or
authorization architecture, retention/deletion compliance, distributed transactions,
exactly-once effects, complete recovery, or release acceptance.

## 14. Human gate

Human Architecture Review must either accept, amend or reject this Proposed decision.
Only acceptance may change Decision Status to `Accepted`. Implementation remains
`Not Started` and requires a separately allocated task, G1 plan, exact paths, tests,
review, PR and Human Durable Integration decision.
