# S5-V023-IMPL-244 Checkpoint A Evidence

## Scope and authority

This bounded backend increment reuses the accepted PostgreSQL product-continuity,
Qdrant-derived-index, Digital Employee Instance, and canonical Attempt boundaries.
It adds no public CRD/API, database product, deployment dependency, frontend path,
Skill/MCP invocation, general Attempt orchestration, or release state.

PostgreSQL is authoritative for managed Knowledge lifecycle, exact Attempt/Knowledge
bindings, and immutable retrieval Evidence. Qdrant contains only scoped derived
vectors. Authorization is checked before Attempt, Knowledge, or Qdrant lookup.

## Implemented proof path

The deterministic P1 bootstrap uses `KnowledgeLifecycleService` domain operations to
create, validate, Human-review, publish, and ingest one Chinese-first supplier-quality
Knowledge resource. Its Knowledge, source, collection, document, revision, ingestion,
and snapshot identities are fixed for Human inspection; callers provide an isolated
scope and own cleanup.

Attempt retrieval validates the exact tenant/security domain, existing Attempt,
Digital Employee Instance and optional Agent Instance, binding, published revision and
digest, active or explicitly permitted stale snapshot, and authorization decision.
Only then does it query Qdrant with scope, Knowledge, and snapshot filters. Returned
payloads are revalidated against authoritative PostgreSQL content before deterministic
citations and Evidence are appended.

The internal DTO includes Knowledge name, source, collection, immutable revision,
index snapshot, freshness, binding, authorization state, retrieval state, bounded
citations, exact Evidence, and unavailable/stale reason.

## Failure and truthfulness boundary

- deny produces no Attempt/Knowledge lookup, Qdrant query, binding, or Evidence effect;
- no result produces explicit `NO_RESULT` with no citation;
- stale index is explicit and blocked unless the request allows stale use;
- unavailable Qdrant produces `UNAVAILABLE` Evidence and no citation;
- foreign scope, Digital Employee/Agent mismatch, revision/digest conflict, and
  snapshot conflict fail closed before Qdrant lookup;
- replay is deterministic and conflicting immutable identities are rejected;
- restart readback reconstructs the identical Evidence from PostgreSQL.

## Validation boundary

Focused tests cover lifecycle, source/collection/document identity, deterministic
bootstrap, real derived-index use, citations, Attempt and Evidence binding, restart,
denial, isolation, no-result, stale/unavailable Qdrant, conflicts, and cleanup.
Final command results, commit/tree, Draft PR, and exact-head CI are reported by the
Checkpoint A control session after those non-self-referential facts exist.

This is ready for Human Checkpoint A review only. It does not claim capability D Human
acceptance, P1 completion, Golden Demo, Preview, release, merge, or promotion.
