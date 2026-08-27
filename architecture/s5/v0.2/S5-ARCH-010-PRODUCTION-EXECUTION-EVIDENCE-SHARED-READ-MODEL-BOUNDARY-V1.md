# S5-ARCH-010 — Production Execution Evidence and Shared Read Model Boundary v1

## 1. Session and decision state

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-010` |
| Type / version | `ARCH` / `v0.2 CONNECT — Digital Employee Technical Preview` |
| Lifecycle / checkpoint | `REVIEW` / `A — ARCHITECTURE_DECISION_AND_G2_BOUNDARY` |
| Authorized baseline | `4d5da13e519627ba40cfdc632e3662f5cf965626` |
| Human architecture decision | `PASS_WITH_CONSTRAINTS` |
| Human G2 decision | `APPROVED_FOR_BOUNDED_V0_2_ARCHITECTURE_ONLY` |
| Selected architecture | `HYBRID_F` |
| v0.2 persistence direction | `SQLITE_BACKED_APPEND_ONLY_INTERNAL_EVIDENCE_REPOSITORY` |
| Persistence classification | `BOUNDED_SINGLE_NODE_V0_2_PERSISTENCE / NOT_PRODUCTION_CERTIFIED / NOT_MULTI_NODE` |
| Implementation authorization | `NOT_GRANTED` |
| Publication state | `CANDIDATE / NOT_DURABLE_MAIN / HUMAN_REVIEW_PENDING` |

This decision defines an internal architecture boundary. It does not implement
or freeze a database schema, migration, API, DTO, Runtime Contract, Capability
Contract, public resource, or external contract. It grants no production
certification, Provider certification, Golden Demo readiness, release
acceptance, recovery guarantee, or exactly-once claim.

## 2. Authority model

Hybrid F has one owner for each kind of authority:

| Concern | Authority | Constraint |
| --- | --- | --- |
| Public desired, control, and current state | Existing Kubernetes Workflow and Task resources | Existing CRDs, status schemas, lifecycle meanings, resource identities, and Kubernetes source-of-truth behavior remain unchanged. |
| Detailed execution facts | Internal append-only Execution Evidence Repository | Owns normalized detailed evidence only; it cannot drive or overwrite public control state. |
| Relationships | Existing Canonical Graph projection | Consumes authorized inputs; it remains the sole relationship authority. |
| Shared execution read model | Deterministic shared snapshot assembler | Reproduces a snapshot from named authoritative inputs and owns shared snapshot identity. |
| View-specific presentation | Sibling backend Product and Technical projections | Filter and format the same snapshot; neither projection is an authority or independent assembler. |
| User experience | Frontend | Non-authoritative presentation only; it cannot persist authoritative business or execution state. |

No component may dual-write, reinterpret, or compete with another authority.
Evidence cannot become a second Task/Workflow state machine. Kubernetes status
cannot silently become the detailed evidence journal. Product, Technical, and
frontend code cannot reconstruct or mint execution or Graph authority.

## 3. Internal Execution Evidence Record

An Execution Evidence Record is immutable, versioned, internal, and contains
only normalized allowlisted facts. Its candidate semantic fields are:

- `evidence_record_id` and `schema_version`;
- `namespace` and `security_domain`;
- Platform Execution Identity;
- Workflow identity and Task identity;
- attempt ordinal, event ordinal, event type;
- `occurred_at` and `recorded_at`;
- payload digest;
- normalized Runtime classification;
- selected Platform Instance identity;
- Capability identity;
- authorization decision and reason code;
- Provider correlation ID and Provider-call count;
- normalized Outcome reference;
- Evidence and Citation references where available;
- limitation or failure code; and
- `supersedes_record_id` where applicable.

These are semantic requirements, not a frozen database or wire schema.
Storage-only fields, indexes, SQL types, table layout, and implementation
metadata remain implementation-gate decisions.

The repository must never persist prompts, secrets, tokens, credentials, raw
capability or other invocation arguments, raw Provider request or response
bodies, stack traces, unrestricted diagnostics, or host paths. Allowlisting and
redaction fail closed: an unknown field, unsafe value, or value that cannot be
normalized is rejected rather than persisted. Diagnostics must be mapped to
bounded reason or limitation codes before append. References must not embed
the referenced sensitive content.

## 4. Identity, attempts, ordering, and idempotency

One Platform Execution Identity identifies one logical Task execution. Attempts
are positive, ordered children of that execution. A retry reuses the logical
execution identity and does not silently mint another execution. A correction
or explicit re-execution may create a successor Platform Execution Identity
when its semantics are a new logical execution; the successor relationship
must be explicit evidence rather than inferred from time or naming.

Record append behavior is:

- same record ID plus the same payload digest: idempotent duplicate;
- same record ID plus a different digest: fail closed and append nothing;
- event ordinal gaps: detectable and surfaced as partial evidence;
- duplicate ordinals with different identities: detectable conflict;
- late or out-of-order arrival: retained with both occurrence and record time,
  and deterministically ordered without rewriting history.

The evidence stream provides detectable and replayable facts, not an
exactly-once execution guarantee. Existing replay barriers and transactional
append do not prove exactly-once effects.

## 5. Immutability, correction, retention, and deletion

Evidence records are immutable. Correction appends a new record that names the
superseded record; the prior record remains auditable. Historical records are
never updated in place.

Retention and deletion are policy-governed by namespace/security domain.
Auditable tombstone or erasure records must preserve the fact and authority of
the operation without preserving prohibited data. Exact retention durations,
legal-hold behavior, and tenant-level policy remain downstream governance
decisions. No controller, adapter, rollback, or application shutdown may
implicitly delete evidence.

## 6. Bounded SQLite adapter decision

Human G2 approves a future first-slice SQLite adapter only as bounded
single-node v0.2 persistence:

- local/single-node use only;
- database file location supplied by bounded configuration;
- database files and sidecar files excluded from Git;
- transactional append and unique record identity;
- digest mismatch fails closed;
- WAL, locking, crash behavior, file permissions, backup, and corruption
  behavior evaluated at the persistence/security implementation gate;
- no shared multi-node file or network-filesystem use;
- no production certification;
- persistence accessed only through a replaceable Evidence Repository port;
- PostgreSQL or an event journal/materialized read model remains downstream.

This architecture task creates no table, SQL schema, database file, migration,
dependency, adapter, or configuration.

## 7. Security-domain and namespace boundary

Every record carries both namespace and security domain. Query authorization
must occur before evidence is loaded. Field filtering must occur before Graph
construction and before DTO serialization. Cross-domain queries, joins,
aggregates, cache keys, and snapshot assembly are prohibited. Missing,
unknown, contradictory, or unauthorized domain context defaults to deny.

Raw diagnostics are never exposed. Provider, Runtime, Capability, Evidence,
and Citation fields are independently allowlisted. The v0.2 discriminator is
tenant-ready safety metadata, not a claim that the downstream tenant model or
enterprise authorization architecture is implemented.

## 8. Canonical Graph input

The Graph consumes an authorized Kubernetes control snapshot plus authorized
Evidence Records. Security filtering precedes Graph construction. The Graph
snapshot records at least:

- Workflow and Task resource identity/resourceVersion inputs;
- the evidence high-water mark included by the assembler; and
- `graph_snapshot_id`.

Product and Technical projections receive the same Graph snapshot. They cannot
mint, reverse, substitute, infer, or reconstruct canonical relations. This
decision makes no Canonical Graph semantic, cardinality, direction,
aggregation, visibility, or identity change.

## 9. Deterministic shared snapshot assembler

Assembler inputs are:

1. authorized Kubernetes Workflow/Task identities and resourceVersions;
2. authorized Evidence Records through a named high-water mark;
3. one canonical Graph snapshot; and
4. requested locale for formatting only, never business or authority state.

For identical ordered inputs and assembler version, output is deterministic.
The snapshot carries one shared identity and exact source-version provenance.
Its state is one of:

- `COMPLETE` — all required authorities and expected evidence are present;
- `PARTIAL` — safe output exists with explicit gaps/limitations;
- `STALE` — output is valid for older named source versions;
- `AUTHORITY_MISSING` — a required authoritative input is unavailable;
- `DENIED` — authorization rejects the request before evidence loading;
- `NOT_FOUND` — the authorized identity does not exist;
- `ERROR` — bounded internal failure with no raw diagnostic disclosure.

Synthetic data never substitutes for live data silently. Partial or stale data
must remain visibly classified and must not be promoted to complete.

## 10. Versioned internal preview DTO/API boundary

A future new internal preview boundary may expose the one shared snapshot to:

- Product projection;
- Technical projection;
- Graph response; and
- Evidence/Citation response.

It is separate from the existing strict Workflow DTOs and must not add fields
to them. The boundary requires explicit supported-version negotiation, a
versioned error envelope, stable reason/limitation codes, ETag/source-version
or equivalent stale detection, authorization before loading, redaction before
serialization, and one unchanged shared snapshot identity across sibling
responses.

Unsupported versions fail explicitly. Errors distinguish denied, not found,
authority missing, partial, stale, and internal error without leaking whether
an unauthorized execution exists. This is an internal Technical Preview
boundary, not a finalized public API, frozen Contract, compatibility promise,
or certification claim.

## 11. Frontend adapter boundary

The frontend has two explicit modes:

- `live`, consuming the authorized internal preview boundary; and
- `synthetic preview/test`, consuming the existing deterministic fixture.

Live mode never falls back silently to synthetic mode. Loading, error, stale,
partial, denied, authority-missing, and not-found states are rendered
explicitly. Product and Technical views retain the same Platform Execution
Identity, shared snapshot identity, and Graph snapshot identity. The frontend
does not persist authoritative execution or business state. The existing
fixture remains an offline-preview and regression asset, not production
authority.

## 12. First Native implementation slice

### In scope after separate authorization

- existing Kubernetes Workflow and Task resources;
- current Native-only execution path;
- replaceable Execution Evidence Repository port;
- bounded SQLite adapter under Section 6;
- evidence capture from the current execution coordinator;
- deterministic shared snapshot assembler;
- new internal versioned preview DTO/API;
- Product and Technical live adapters;
- Graph and Evidence/Citation responses over the same snapshot;
- ALLOW and DENY, including DENY zero-call proof;
- failure, `UNKNOWN`, partial, and stale behavior;
- restart durability test;
- prohibited-data/no-secret test; and
- namespace/security-domain isolation test.

### Out of scope

- authoring or publish;
- public CRD or status changes;
- OpenClaw, Hermes, MCP, and production Knowledge/RAG;
- full recovery or certification;
- Golden Demo harness or Release;
- exactly-once claims; and
- distributed or multi-node persistence.

No downstream implementation Session is allocated or authorized by this
artifact. The future implementation task ID remains unresolved.

## 13. Rollback

Rollback disables evidence capture and the live frontend adapter while
preserving existing Kubernetes execution and status behavior. The frontend may
return only to explicitly selected synthetic preview mode. Existing evidence
is retained or deleted through its governing policy. No CRD, Task, or Workflow
migration rollback exists because none is introduced. SQLite file cleanup is
performed only by explicit, bounded tooling after target validation; it is
never implicit application or rollback behavior.

## 14. Future gates

Implementation requires all applicable independent gates:

1. implementation exact-path gate;
2. SQLite persistence and security gate;
3. internal DTO/API compatibility gate;
4. Native evidence capture gate;
5. Product/Technical live-adapter gate;
6. exact-head CI; and
7. durable integration.

Any need for a public API/CRD change, distributed persistence, permanent
execution ownership, tenant architecture, production certification, recovery
semantics, or Contract freeze returns to a new Human G2 decision.

## 15. Checkpoint result

```text
SESSION: S5-ARCH-010
LIFECYCLE: REVIEW
CHECKPOINT: A — ARCHITECTURE_DECISION_AND_G2_BOUNDARY
CURRENT_STEP: 1_OF_3
HUMAN_ARCHITECTURE_DECISION: PASS_WITH_CONSTRAINTS
HUMAN_G2_DECISION: APPROVED_FOR_BOUNDED_V0_2_ARCHITECTURE_ONLY
SELECTED_ARCHITECTURE: HYBRID_F
V0_2_PERSISTENCE_DIRECTION: SQLITE_BACKED_APPEND_ONLY_INTERNAL_EVIDENCE_REPOSITORY
PERSISTENCE_CLASSIFICATION: BOUNDED_SINGLE_NODE_V0_2_PERSISTENCE / NOT_PRODUCTION_CERTIFIED / NOT_MULTI_NODE
IMPLEMENTATION_AUTHORIZED: NO
IMPLEMENTATION_TASK_ID: UNRESOLVED
NEXT_GATE: Human S5-ARCH-010 Checkpoint A Review
```
