# S5-IMPL-014 — Native Execution Evidence and Shared Read Model Evidence

## Session

| Field | Value |
| --- | --- |
| Session | `S5-IMPL-014` |
| Architecture authority | `S5-ARCH-010 / HYBRID_F` |
| Durable baseline | `13bc16f746a58912bc093ff249ff390250ce20cf` |
| Implementation branch | `codex/s5-impl-014-native-evidence-shared-read-model` |
| Implementation head | The immutable commit containing this evidence; exact SHA is recorded in the Draft PR and Checkpoint A return |
| Authorized paths | 29 after Human-approved Checkpoint A and Checkpoint B expansions |
| Classification | Native-only Technical Preview; bounded local single-node persistence; not production certified |

## Authority boundaries

- Kubernetes Workflow and Task resources remain execution and current-state
  authority.
- The Execution Evidence Repository is append-only evidence authority only.
- The existing Canonical Graph remains relation and visibility authority.
- The deterministic assembler is read-only and owns shared snapshot identity.
- Product and Technical projections are siblings over the same snapshot.
- Frontend adapters consume authority; they do not persist or reconstruct it.

Evidence persistence failure after a Native or Provider effect never rewrites a
successful execution to failure and never triggers an automatic Provider replay.
The coordinator returns the truthful execution outcome together with separately
classified evidence availability. Live preview cannot classify unavailable or
incomplete evidence as a complete verified success.

## Evidence domain and safety

`ExecutionEvidenceRecord` is immutable and schema-versioned. It contains bounded,
normalized identities, ordinals, classifications, stable reason codes, Provider
call counts and allowlisted references. It rejects unknown or secret-shaped
content before canonicalization.

Credentials, tokens, raw prompts, raw model input/output, raw Provider bodies,
raw tool arguments, stack traces, host paths, environment dumps, arbitrary
metadata and unrestricted diagnostics are neither persisted nor digested.

The producer digest excludes repository-assigned sequence, recorded time, SQLite
metadata, database location and process identity. Same record ID and digest is a
deterministic replay. Same record ID and a different digest fails closed without
adding a row.

Checkpoint B correction binds every production record to Kubernetes-owned
Workflow UID and Task UID supplied by the Task handler. Missing or contradictory
subject identity prevents evidence append without changing the execution result.
Task display names and `workflow.unbound` are never production associations.

Evidence and Citation references carry their own type, scope, decision, reason,
visibility, source and provenance. Only independently allowed references in the
authorized namespace/security domain reach the snapshot; denied references are
omitted without identity, metadata, digest or count disclosure.

## SQLite boundary

The standard-library `sqlite3` adapter requires an explicit database location.
It transactionally bootstraps only an empty database to schema version 1, rejects
unknown/newer/partial schemas, uses atomic `BEGIN IMMEDIATE` append transactions,
a bounded busy timeout, WAL and full synchronization for the bounded local
single-node use case, and scoped namespace/security-domain reads.

Database, WAL and SHM files are runtime artifacts outside Git. Open, corruption,
locking, bootstrap and transaction failures map to stable bounded codes without
exposing paths, SQL or raw diagnostics. WAL grants no multi-node, shared-filesystem,
HA or production durability claim.

Because this implementation is unmerged, the corrected initial SQLite v1 schema
uses a final adapter marker and composite Workflow UID/Task UID subject index.
Databases created from the rejected pre-correction candidate fail closed; no
artificial production migration or upgrade support is claimed.

## Trusted authorization and shared snapshot

The internal route is:

`GET /api/internal/preview/v1/executions/{namespace}/{workflow_name}/{task_name}`

Its principal, authorized namespace and security domain come from a trusted
server-side dependency. Client paths only locate a resource after authority is
resolved. Ordinary headers cannot create authority. Denied requests load no
evidence and disclose no existence, counts, high-water mark, evidence identity,
shared snapshot identity, Graph identity or internal diagnostic.

The assembler freezes the evidence high-water mark before reading and hashes the
assembler version, authorized scope, Workflow UID/resourceVersion, ordered Task
UID/resourceVersion inputs, Platform Execution Identity, fixed high-water mark,
ordered evidence record IDs/digests and unchanged Graph snapshot identity.
Product and Technical responses preserve the same execution, shared snapshot,
Graph, authorization, Runtime, outcome, evidence, citations and raw relations.
The versioned `execution-snapshot-v2` completeness policy requires a unique final
execution-outcome event, contiguous unique ordinals and consistent authorization/
Provider-call evidence. A contiguous non-terminal prefix remains partial.

## Frontend modes

- `synthetic-preview` is deterministic, non-authoritative, visibly labelled and
  performs no network or Runtime invocation.
- `live` consumes only the internal preview API. Loading, partial, stale, denied,
  authority-missing, not-found and error conditions remain explicit. Live mode
  never silently falls back to the fixture, and UNKNOWN/incomplete/unavailable
  evidence is never promoted to success.

Live frontend code consumes Canonical Graph relations verbatim. It does not expand
relation-type tuples, mint relation identities, infer direction/cardinality or
reconstruct filtered relations.

## Validation evidence

- Domain/SQLite/coordinator/snapshot/API/security and existing sibling view tests
  pass.
- Full pytest: 726 passed with one existing Starlette/httpx deprecation warning.
- Ruff lint and format checks pass.
- Frontend clean-install lint, TypeScript compilation and production build pass
  from temporary storage without repository dependency or lockfile mutation.
- Compatibility ownership uses exact file entries only; no wildcard or broad
  exemption exists, and an unrelated Console consumer remains rejected.
- Exact-head CI is recorded in the Draft PR and Checkpoint A return after push.

## Rollback and limitations

Rollback disables injected evidence capture and live preview without changing
Kubernetes execution/status behavior. Synthetic preview remains available only
through explicit selection. Evidence deletion is never implicit.

There is no public API or CRD change, Canonical Graph semantic change, dependency
or lockfile change, Workflow lifecycle change, exactly-once claim, multi-node
persistence, production certification, Golden Demo readiness, Provider
certification, release acceptance, OpenClaw/Hermes/MCP/Knowledge implementation,
or generalized Recovery behavior.
