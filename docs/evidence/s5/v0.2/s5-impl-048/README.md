# S5-IMPL-048 Checkpoint A1 Evidence

## Entry

| Field | Result |
| --- | --- |
| Session | `S5-IMPL-048` |
| Baseline | exact `6e721b15be6bd9df98579f9e8de8d1fab7968120` |
| Branch | `codex/s5-impl-048-knowledge-operations-workbench` |
| Entry worktree | clean, detached at the authorized baseline |
| Collision check | no local branch or GitHub PR for the authorized branch |
| Gate | `G1 / CHECKPOINT 0 -> A1 FAST PATH` |

## Implemented boundary

The A1 domain package provides scoped Knowledge Source, Document and Chunk
identity; immutable Knowledge revisions and exact digests; validation, Human
review and publication; authoritative PostgreSQL persistence; ingestion jobs,
high-water marks and index snapshots; a Qdrant v1.15 REST adapter for derived
vectors; rebuild, restart recovery, archive and authorized resumable purge; and
standalone Workbench Product and Technical components.

PostgreSQL remains lifecycle, identity, digest, scope and snapshot authority.
Qdrant cannot mint or repair SQL authority. Cross-store operations make no
atomicity or exactly-once claim and persist `RECOVERY_REQUIRED` after an
uncertain or partial external effect.

Existing Knowledge authorization, retrieval, nondisclosure, Evidence and
Citation contracts remain unchanged and are included in focused validation.

## Validation evidence

| Gate | Result |
| --- | --- |
| Focused Ruff | PASS |
| Focused Knowledge contract tests | PASS: 41 tests |
| Real PostgreSQL | PASS: PostgreSQL 16 migration, scoped read and optimistic concurrency |
| Real Qdrant | PASS: `qdrant/qdrant:v1.15.4` create/upsert/query, foreign-scope zero-result, scoped delete |
| Frontend lint | PASS |
| Frontend production build | PASS |
| `make check` | PASS: Ruff, format check, `1061 passed`, 4 expected external-service skips, 1 existing deprecation warning |
| `git diff --check` | PASS |

The real-service test configuration uses disposable local containers and test
environment variables only. No credentials or service URLs are persisted in
the repository.

## Security and disclosure

- Trusted scope is resolved before every repository lookup.
- PostgreSQL primary and unique keys include namespace and security domain.
- Qdrant queries and deletes require namespace, security domain, Knowledge
  identity and exact snapshot identity filters.
- A foreign scope obtains no identity, digest, result count, snapshot or
  lifecycle disclosure.
- Source input is bounded and rejects invalid control characters; secret values
  are not accepted as typed fields or copied into index payloads.
- Purge requires an authorization identity and a non-sensitive reason
  classification. Its tombstone excludes source, document and chunk content.

## A1 limitation and continuation

Shared app routing, product-shell navigation and shared styles remain untouched
because S5-IMPL-047 owns those paths. Consequently A1 does not claim a
browser-connected product journey. The same Session must continue after shared
assembly is released to mount the backend router and Workbench route, apply any
shared styling, and run real-browser acceptance against real PostgreSQL and
Qdrant services.

Status: `AWAITING_SHARED_ASSEMBLY_CONTINUATION`.

## Product design reference addendum

The A1 Knowledge components consume the established Agent Workbench and durable
prototype patterns rather than introducing another shell or design system. They
reuse the existing Workbench layout, enterprise cards, lifecycle badges, forms,
filters, action hierarchy, tables, disclosure notices and technical projection
classes. The purge impact flow uses an accessible native dialog and requires
operator-supplied authorization identity and non-sensitive reason classification;
no simulated authority or success is introduced.

The refined component review confirms explicit presentation of:

- Source and Knowledge Pack identity, provenance and exact revision digest;
- Draft, validation, Human review, publication and archive lifecycle hierarchy;
- authorized document/chunk counts only after a scoped backend response;
- ingestion job, high-water mark, index snapshot, rebuild and recovery state;
- Citation availability as an authorization-governed retrieval boundary, without
  inventing Citation records;
- nondisclosing absent/denied messaging;
- archive and exceptional purge impact, including `RECOVERY_REQUIRED`;
- Product and Technical sibling projections over the same backend object.

No shared shell, global navigation, `App.tsx`, `app.css`, frontend persistence,
mock metric, model/cost value or simulated backend action was added. Final visual
and real-browser acceptance remains assigned to the shared assembly continuation.

## Checkpoint A2 — shared assembly and final product acceptance

The Human continuation gate authorized the normal merge of durable main
`18a62fdaea706da4d9b368990273b8a3620579a0`. PR #100 was verified merged at
that exact commit, PR #101 was verified at the A1 source head, and the merge
completed without conflict. The preserved migration order is:

```text
0001_agent_definition_lifecycle.sql
-> 0002_skill_mcp_lifecycle.sql
-> 0003_knowledge_operations.sql
```

Shared assembly mounts only the Knowledge router and deployment dependencies in
FastAPI, the Knowledge route and navigation entry in the established product
shell, and locally scoped Knowledge styles using the established enterprise
tokens. Make and CI add bounded real Knowledge validation with PostgreSQL and
the pinned `qdrant/qdrant:v1.15.4` service. Dependency manifests remain
unchanged.

The production-built real-browser journey proves:

1. Source/Pack draft creation with sanitized real document chunks;
2. scoped identity and exact digest validation, Human review and immutable
   publication;
3. a real Qdrant derived index and backend-authorized retrieval with exact
   Citation, document/chunk digest and provenance;
4. foreign-scope and absent identity equivalence with no identity/count leak;
5. successor content, a new immutable revision/digest and a successor snapshot;
6. actual backend process shutdown/startup with PostgreSQL identity, revision,
   digest and snapshot-reference recovery;
7. Product/Technical sibling identity consistency and the Qdrant-derived-only
   disclosure;
8. archive and successful authorized purge to a non-sensitive tombstone;
9. forced real Qdrant collection loss followed by HTTP 202 and visible
   `RECOVERY_REQUIRED` rather than an atomicity or success claim.

During real acceptance two implementation defects were found and corrected:
Qdrant point IDs are now deterministic UUIDs derived from authoritative chunk
digests, and PostgreSQL compliance purge now locks the exact aggregate version,
removes payload-bearing lifecycle rows, deletes the aggregate and inserts the
minimal tombstone in one SQL transaction.

### A2 validation

| Gate | Result |
| --- | --- |
| Production frontend lint/build | PASS |
| Focused real PostgreSQL and Qdrant | PASS |
| Knowledge browser acceptance | PASS: 1/1 |
| Agent/Knowledge/Skill-MCP browser regression | PASS: 3/3, serialized production build |
| Backend restart recovery | PASS: real process stop/start |
| `make check` with all real services | PASS: `1076 passed`, no skips, one existing deprecation warning |
| Problem Planning regression | PASS within full suite |
| Migration ordering/checksum audit | PASS |
| Dependency/path boundary audit | PASS |

No Runtime, Gateway, operator, CRD, public Contract, Model Provider, Tenant/IAM,
deployment or release change is made. Search Playground, lexical/hybrid
retrieval, recall evaluation, summary, duplicate review and import/export remain
outside this package.
