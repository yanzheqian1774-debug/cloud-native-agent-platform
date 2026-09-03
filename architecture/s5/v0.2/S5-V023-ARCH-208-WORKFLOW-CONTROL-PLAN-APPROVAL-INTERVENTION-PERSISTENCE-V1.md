# S5-V023-ARCH-208 — Workflow Control, Plan Approval and Intervention Persistence v1

## 1. Decision record

| Field | Value |
| --- | --- |
| Session | `S5-V023-ARCH-208` |
| Gate | `ARCH / G2 / CHECKPOINT_A_CANDIDATE` |
| Baseline | commit `090ff05beaaa2d44b77fa98efcc5b21fc149a153`; tree `27d9245674d5b97a1456e23c3fa18485602ef1ea`; CI `33727444881 / SUCCESS` |
| Authorities | ARCH-201/REL-202; ARCH-204/REL-206; IMPL-210/REL-205; IMPL-230/REL-207; migration `0008` |
| Decision status | `PROPOSED / READY_FOR_HUMAN_CHECKPOINT_A` |
| Implementation status | `NOT_STARTED`; IMPL-240 remains blocked pending durable schema integration |
| Contract status | Internal v0.2.3 persistence/repository contract; `NOT_FROZEN` |

Suffix `208` was unused before the explicit Human allocation of this Session. This
record defines but does not allocate a schema/repository task, likely
`S5-V023-IMPL-221`, or authorize resumption of `S5-V023-IMPL-240`. It changes no
public CRD, Kubernetes API group, Runtime effect, migration, product implementation
or IMPL-220 path. `MUST` applies only after Human approval and separate allocation.

## 2. Authority decision

PostgreSQL is the authoritative writer for Plan, approval, execution-control intent,
Intervention history, idempotency and Evidence/Outcome relationships. Kubernetes
remains authoritative for public Control Plane resources and observed workload
state; providers remain authoritative for native effects. A desired command proves
authorized intent, never observed effect.

Migration `0008` remains immutable. The extension MUST be additive migration `0009`.
SQLite/in-memory adapters MAY support focused conformance tests but are explicitly
non-authoritative and cannot satisfy deployment, transaction or restart acceptance.

Every key and relation below is scoped by `(namespace, security_domain)`. Scope is
immutable and present in every foreign/unique key. IDs are opaque, bounded, never
reused and never derived from provider identity.

## 3. Entity and relation matrix

| Entity | Identity / version | Enforced relations and immutability |
| --- | --- | --- |
| Plan | stable `plan_id`; immutable `(plan_id, plan_version)`; CAS `aggregate_version` guards pre-approval status only | exact Workflow Definition ID/revision/digest; optional predecessor version; canonical bytes/digest never update; correction inserts a successor |
| Approval decision | immutable `approval_decision_id`; ordinal per Plan version | exact Plan version/digest, actor and authority; append-only; one effective terminal decision |
| Workflow Run | existing `workflow_run_id`; new state and CAS version | Assignment and exact approved Plan; optional predecessor/correction Run; identity/links immutable |
| Task Run | existing `task_run_id`; new state and CAS version | parent Run plus stable Workflow node; retry does not replace it |
| Attempt | existing `attempt_id`; new state, ordinal and CAS version | parent Task Run and optional predecessor Attempt; retry inserts a new Attempt |
| Intervention | stable `intervention_id`; CAS current state/version | exactly one primary Run, Task Run or Attempt target; transitions stored separately |
| Control command | immutable `control_command_id` | Intervention transition and exact target; optional affected Attempt, successor Plan/Run and later Runtime command link |
| Evidence/Outcome link | ordinal per Intervention transition | scoped FK to exact transition and existing Evidence or Outcome; append-only |

### Plan and approval lifecycle

```text
DRAFT → PENDING_APPROVAL → APPROVED → INVALIDATED
  │            │              └────→ SUPERSEDED
  │            ├→ REJECTED
  └────────────┴→ CANCELLED
```

Approval requires an authorized `APPROVE` decision binding exact canonical Plan
bytes and SHA-256 digest. Approval/rejection history is append-only. Duplicate
decisions fail closed unless an idempotent replay returns the original result.
Revoked authority or dependency invalidation may mark an approved version
`INVALIDATED`; correction creates a successor version and marks the predecessor
`SUPERSEDED`. Neither operation changes approved content, digest or decision facts.

A Run MUST reference the composite key of an `APPROVED` Plan and copy its approved
digest. The repository checks status/digest in the creation transaction; no implicit
`latest` selection is permitted.

### Exactly-one Intervention target

`interventions` has nullable `workflow_run_id`, `task_run_id`, and `attempt_id`, each
with a scoped composite FK, plus:

```sql
CHECK (num_nonnulls(workflow_run_id, task_run_id, attempt_id) = 1)
```

Target kind is derived from the populated FK. If projected as a column, a check MUST
make it agree. Assignment, Digital Employee Instance, Placement and Runtime Instance
may be validated scope-matching context only; they never replace the primary target.

### Intervention history

The stable row records action, bounded reason, requester/actor, expected target
version, current state/version and timestamps. It stores neither arbitrary messages
nor overwritable decisions. `intervention_transitions` uses immutable
`(intervention_id, ordinal)` rows and unique `transition_id` values.

| From | To | Meaning |
| --- | --- | --- |
| none | `REQUESTED` | request durably accepted |
| `REQUESTED` | `AUTHORIZED`, `REJECTED`, `EXPIRED`, `CANCELLED` | decision/withdrawal/timeout |
| `AUTHORIZED` | `APPLICATION_PENDING`, `CANCELLED`, `EXPIRED` | command creation or pre-application termination |
| `APPLICATION_PENDING` | `APPLIED`, `FAILED` | guarded Product mutation committed or failed |
| `APPLIED` | `OBSERVED`, `FAILED` | later effect observation |

`REJECTED`, `EXPIRED`, `CANCELLED`, `FAILED` and `OBSERVED` are terminal.
Cancellation is valid only before `APPLIED`; cancellation of execution is a new
`CANCEL`/`STOP` Intervention. Each transition appends history and increments CAS.

## 4. Closed control state machines

| Aggregate | States | Guarded transitions |
| --- | --- | --- |
| Run | `PENDING`, `RUNNING`, `PAUSE_REQUESTED`, `PAUSE_PENDING`, `PAUSED`, `RESUME_REQUESTED`, `CANCELLATION_PENDING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `RECOVERY_REQUIRED` | pending→running; running→pause-requested→pause-pending→paused; paused→resume-requested→running; nonterminal→cancellation-pending→cancelled; active→terminal/recovery |
| Task Run | `PENDING`, `READY`, `RUNNING`, `BLOCKED`, `CANCELLATION_PENDING`, `SUCCEEDED`, `FAILED`, `SKIPPED`, `CANCELLED` | dependency-controlled forward transitions; nonterminal→cancellation-pending→cancelled |
| Attempt | `PENDING`, `PLACED`, `RUNNING`, `CANCELLATION_PENDING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `UNKNOWN`, `RECOVERY_REQUIRED` | forward execution; active→cancellation-pending→cancelled; explicit uncertainty/recovery |

These are internal Product persistence states; they do not reinterpret CRD states.

| Action | Preconditions | Atomic Product result | Observed-effect boundary |
| --- | --- | --- | --- |
| `PAUSE` | running Run; safe-point support | `PAUSE_REQUESTED` plus command | observer later records pending/paused; never OS process pause |
| `APPROVE_AND_CONTINUE` | exact pending Plan/approval request | exact approval and optional resume intent | execution cannot precede approval commit |
| `PROVIDE_HUMAN_INPUT` | requested bounded schema | sanitized reference/digest plus command | arbitrary input is not audit Evidence |
| `RESUME` | paused Run | `RESUME_REQUESTED` plus command | running only after observation |
| `RETRY_ATTEMPT` | failed Attempt; eligible Task | new next-ordinal Attempt linked to predecessor | old Attempt remains unchanged |
| `RERUN_APPROVED_PLAN` | approved, valid exact Plan | new linked Run using same Plan | no Run/Task/Attempt ID reuse |
| `CORRECT_BUSINESS_INTENT` | valid source and corrected content | successor Plan requiring approval; predecessor superseded | no rewrite or automatic execution |
| `CANCEL` | eligible nonterminal exact target | cancellation-pending plus command | terminal state follows observation |
| `STOP` | eligible Run with active execution | block new work; cancellation-pending plus command | adapter owns bounded drain/stop |
| `REQUEST_RUNTIME_REPLACEMENT` | affected Attempt has eligible Placement context | replacement-request command linked to Attempt | no Placement edit, Kubernetes/provider call |

Retry, rerun, correction, compensation, rollback, cancellation, stop and replacement
remain distinct. Unsafe/unsupported pause produces a terminal rejection and no
target mutation or desired command.

## 5. Optimistic concurrency

Plan, Run, Task Run, Attempt and Intervention have positive `aggregate_version`.
Existing execution rows are backfilled to `1`; new aggregates start at `1`. Mutation
requires explicit expected version and compare-and-swap:

```sql
UPDATE ... SET ..., aggregate_version = aggregate_version + 1
WHERE namespace=? AND security_domain=? AND id=? AND aggregate_version=?
RETURNING aggregate_version;
```

Zero rows is `STALE_AGGREGATE_VERSION`, never an implicit retry. Locks are acquired
Plan → Run → Task Run → Attempt → Intervention. Serialization retries repeat the
whole transaction only with the identical idempotency claim/digest.

| Race | Result |
| --- | --- |
| two Intervention decisions | one commits; one stale/conflict |
| duplicate Plan approval | unique effective decision; replay original or conflict |
| two retries | one successor ordinal/edge; other stale/conflict |
| resume versus cancel | one CAS wins; loser stale/conflict |
| target changes after request | application rolls back; no false `APPLIED` |

## 6. Idempotency and replay

Every application command requires an idempotency key scoped by `(namespace,
security_domain, actor_id, command_type, idempotency_key)`. The claim stores SHA-256
of versioned canonical command bytes, `IN_PROGRESS/COMPLETED`, original Intervention,
command and result identities, timestamps and retention deadline. Actor is immutable
authenticated audit identity, not display name.

| Lookup | Result |
| --- | --- |
| absent | insert `IN_PROGRESS` inside the command transaction |
| same digest and completed | return original deterministic result; no append/effect |
| same digest and in progress | `COMMAND_IN_PROGRESS`; no duplicate |
| different digest | `IDEMPOTENCY_PAYLOAD_MISMATCH`; no mutation/effect |
| other scope/actor/type | independent key space; authorization still precedes lookup |

Claims survive restart. Retention MUST cover the supported retry/audit/recovery
window; policy deletion cannot occur while referenced or erase immutable audit.
Exactly-once external effects are not claimed.

## 7. Evidence, Outcome and command relations

Use explicit joins, never JSON-only references:

- `intervention_evidence_links(intervention_id, transition_ordinal, ordinal,
  evidence_record_id)`;
- `intervention_outcome_links(intervention_id, transition_ordinal, ordinal,
  outcome_id)`;
- command FKs for successor Plan/version, successor Run, affected Attempt and
  optional later Runtime command.

Every link key/FK includes scope. `0009` adds scoped uniqueness to
`execution_evidence`; `outcomes` already has a scoped key. Readback orders by
transition ordinal, link ordinal, then storage identity.

Evidence contains only bounded categories, digests, identities, timestamps,
outcomes and limitations. It MUST NOT contain arbitrary messages, prompts,
credentials, secrets, or model/provider payloads. Separately retained Human input
uses an access-controlled content authority; audit contains only reference/digest.

## 8. Atomic Unit of Work

One `WorkflowControlUnitOfWork` owns one PostgreSQL transaction at `SERIALIZABLE` or
proven equivalent. It authorizes before disclosure; locks and validates targets;
claims idempotency; checks digest/CAS; appends request/decision; transitions target;
creates successors; persists the Product desired command; appends Evidence/Outcome
and links; increments versions; completes the claim; and reads back deterministically.
No Kubernetes, provider or Runtime call occurs inside it.

| Failure | Complete rollback requirement |
| --- | --- |
| replay mismatch/in-progress | no aggregate, history or command write |
| authorization/scope/target/CAS | no disclosure and no partial write |
| invalid transition/duplicate decision | no target/version/history change |
| successor insert constraint | request, decision, links and command roll back |
| command insert | target mutation and all facts roll back |
| Evidence/Outcome/link | entire command rolls back |
| deterministic readback | transaction rolls back; never report success |
| later Runtime effect | append later failure/observation; never rewrite intent |

Committed commands may be consumed at least once (for example with `SKIP LOCKED`),
but consumers are idempotent and observation remains distinct.

## 9. Migration `0009`

`0009` is mandatory and owned only by the separately authorized schema/repository
task. It MUST NOT edit `0008`.

### New tables and exact constraints/indexes

| Table | Required columns/checks | Keys/indexes |
| --- | --- | --- |
| `plans` | scope, Plan ID/version, predecessor, exact Workflow Definition ID/revision/digest, checked status, CAS, 64-char digest, canonical bytes, timestamps | composite PK; unique successor per predecessor; predecessor/workflow FKs; status/digest indexes |
| `plan_approval_decisions` | scoped decision ID, exact Plan/digest, positive ordinal, `APPROVE/REJECT`, actor, bounded authority/reason, time/digest | scoped PK; unique Plan+ordinal; partial unique effective decision; Plan-order index |
| `intervention_transitions` | scope, Intervention, positive ordinal, transition ID, checked from/to, actor/authority/reason, digest/time | PK Intervention+ordinal; unique transition ID; ordered index |
| `idempotency_claims` | scope, actor, command type/key, payload digest, state, original identities, retention/completion | composite PK; digest/state checks; retention index |
| `control_commands` | scope, ID/type, Intervention transition, exactly one target, expected version, optional successor/Attempt/Runtime command, digest/canonical record/time | scoped PK; unique transition; scoped target/successor FKs; pending-order index |
| Evidence links | Intervention/transition, positive ordinal, Evidence ID | PK transition+ordinal; scoped FKs/traversal index |
| Outcome links | Intervention/transition, positive ordinal, Outcome ID | PK transition+ordinal; scoped FKs/traversal index |

### Additive changes to `0008` tables

| Table | Change | Populated-database rule |
| --- | --- | --- |
| `workflow_runs` | CAS, checked state, exact Plan ID/version/digest FK | version 1; legacy remains readable as `LEGACY_UNBOUND`; new writes require Plan |
| `task_runs` | CAS, checked state, stable Workflow node ID | version 1; explicit `LEGACY_IMPORTED`, never inferred success |
| `attempts` | CAS, checked state, positive ordinal unique per Task | version 1; derive ordinal only if deterministic, else abort `RECOVERY_REQUIRED` |
| `interventions` | action/reason/actor/expected target/current state/CAS/time and exact target FKs/check | preserve as `LEGACY_CONTEXT_ONLY`; never fabricate target/decision |
| `execution_evidence` | unique scope+Evidence ID | no content rewrite; enables scoped FK |

A staged companion legacy table/view MAY replace nullable columns if enforcement is
stronger. New authoritative writes MUST use the complete model. No Plan approval,
target, actor, success or relation may be fabricated from JSON.

Empty databases apply `0001`–`0009`. Populated databases validate all backfills
before transactional constraints; ambiguity aborts with no partial DDL or destructive
reinterpretation. Existing IDs, records and digests remain stable.

Rollback is Human/operator-owned: stop writers, capture verified backup/high-water,
then roll code back only if no `0009` authoritative fact exists. Otherwise forward
repair or explicit export/reconciliation is required. Dropping `0009` data is not an
accepted rollback; there is no automatic destructive down migration.

## 10. Repository contract

| Protocol | Required behavior |
| --- | --- |
| `PlanRepository` | exact-version scoped read; immutable insert; CAS status; append/read decisions; lineage traversal |
| `ExecutionControlRepository` | guarded Run/Task/Attempt reads/CAS; atomic successor Run/Attempt; no implicit latest |
| `InterventionRepository` | scoped request; CAS summary; append-only transitions; exact target traversal |
| `IdempotencyRepository` | claim/lookup/complete by full scope and digest |
| `ControlCommandRepository` | immutable desired command; deterministic pending/readback; effect link without effect ownership |
| `EvidenceOutcomeRepository` | append/traverse scoped, ordered transition links |
| `WorkflowControlUnitOfWork` | one connection/transaction for the complete command; commit only after readback |

PostgreSQL 15 integration, restart, conflict and rollback fault-injection tests are
mandatory. Generic per-row ports cannot substitute for atomic commands. Database
errors map to stable typed errors without SQL or protected-existence disclosure.
Recovery reads claims/commands, reacquires external observation and appends
`RECOVERY_REQUIRED` on ambiguity; it never blindly replays an effect.

## 11. Security and compatibility

- authorization precedes lookup, idempotency disclosure and effect;
- scoped keys prevent cross-tenant/domain linkage;
- actor and authority basis are immutable audit fields;
- action/state/reason are bounded vocabularies, not arbitrary text;
- audit excludes secrets, prompts, payloads and private messages;
- denial performs zero downstream calls and reveals no protected existence;
- retention/deletion cannot orphan lineage, transitions, links or audit identity.

| Boundary | Preserved invariant |
| --- | --- |
| REL-205 | existing Run/Task/Attempt identities remain; retry/rerun add linked IDs |
| IMPL-220 | Instance/Assignment/Placement ownership unchanged; context FK only; no Placement edit |
| REL-207 | Product command ends at intent; provider adapters own effects/observations; no fallback |
| Kubernetes | no CRD/API group or Runtime lifecycle change; desired and observed stay separate |
| Views | scoped IDs, digests, ordinals and lineage support Product/Technical/Evidence projections |
| Restart | PostgreSQL preserves facts; external state is re-observed, not cache-promoted |

## 12. Routing and result

Define, do not allocate: likely `S5-V023-IMPL-221` owns migration `0009`, typed ports,
PostgreSQL adapters and persistence tests. Only after its durable integration may the
already allocated `S5-V023-IMPL-240` resume application behavior. Neither task may
claim Workflow completion, Preview, Formal Release, production readiness,
certification or exactly-once external effects.

`PASS / WORKFLOW_CONTROL_PERSISTENCE_G2_DECIDED / READY_FOR_HUMAN_CHECKPOINT_A`

This is a Human-review candidate only. Implementation, allocation, integration,
deployment and release remain separately governed.
