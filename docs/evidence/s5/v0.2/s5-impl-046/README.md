# S5-IMPL-046 Checkpoint A Evidence

## Authority and scope

- Session: `S5-IMPL-046` — v0.2.2 Agent Definition Product Vertical Slice.
- Authorized baseline: `440cd31dff6959bcaf11a9c66becc973c70d77f6`.
- Exact-main CI at entry: run `33362640164`, `SUCCESS`.
- Branch: `codex/s5-impl-046-agent-definition-product-slice`.
- Architecture: Human Gate records S5-ARCH-018 as closed and durably integrated.
- Scope: private Console product-continuity surface only. No public API/CRD,
  Runtime, operator, gateway, execution or deployment authority was added.

## Implemented product loop

The existing product shell now exposes an Agent Workbench backed by the real
backend and PostgreSQL. It creates a stable Agent Definition and mutable Draft,
validates controlled content, binds Human review to the exact SHA-256 digest,
publishes an immutable Revision, creates successors rather than editing
published content, and exposes enable/disable, deprecation, archival, deletion
impact, protected history, relationships and minimum lifecycle facts.

Product and Technical views are sibling projections of the same canonical
record. Technical inspection exposes exact Definition, Revision, digest, scope
and aggregate version. Publication explicitly grants no execution authority.

The existing business-problem journey now begins with an explicit
`supplier-quality-analysis` Agent gap. A governed rematch reads only enabled,
unarchived, non-deprecated published revisions from the durable repository. It
records the exact matched Definition, Revision and digest and preserves
`executionAuthority: NOT_GRANTED`. Draft, disabled, deprecated and archived
resources are not eligible.

## Persistence and recovery

PostgreSQL is the primary adapter for this new domain. The adapter has a bounded
pool and acquisition timeout, stable fail-closed errors, authorization-first
scope keys, uniqueness and foreign-key constraints, compare-and-set aggregate
versions, transactional record/fact updates, and a checksum-bound ordered
migration. It never falls back to SQLite, memory or an empty database when the
configured store is unavailable or incompatible.

Local real-PostgreSQL validation used an isolated PostgreSQL 15 container on
loopback with temporary storage and trust authentication strictly for the local
test boundary. No credential was added to Git, browser assets, responses or
logs. A fresh repository/service instance recovered the same stable Definition
identity, Published Revision identity and digest.

## Browser acceptance

Browser acceptance used the real React frontend, FastAPI backend and PostgreSQL
adapter. The automated Chromium journey created a Draft, validated it, reviewed
the exact digest and published the immutable Revision successfully.

An additional in-app browser run exercised the complete connected product loop
against real local Ollama planning/embedding providers and an isolated Qdrant
instance:

1. Disabled the published Agent Definition and submitted the supplier-quality
   business problem.
2. Completed the Human clarification checkpoint and real controlled planning.
3. Verified the original problem contained `state: GAP` for
   `supplier-quality-analysis`.
4. Re-enabled the exact published Revision in the Workbench.
5. Returned to the original problem and requested governed rematch.
6. Verified `state: MATCHED`, exact `matchedRevisionId`, exact `matchedDigest`,
   and `executionAuthority: NOT_GRANTED`.

## Truthful limitations

- Private internal API; no public Contract or CRD is introduced or frozen.
- Bounded single-node PostgreSQL only; no HA, replica, multi-region or
  production-readiness claim.
- Existing v0.2.1 Problem records remain process-local. This task persists the
  Agent Definition domain, not the Product Journey domain.
- Scope discriminators are tenant-ready safety boundaries, not complete Tenant,
  IAM or RBAC implementation.
- Relationship consumers are reported only when explicitly recorded; no
  external-system inference is performed.
- Publication authorizes governed discovery/matching only and never execution.

## Validation result

- `make check` with the real PostgreSQL integration variables: `1054 passed`,
  one existing Starlette/httpx deprecation warning.
- Ruff lint and formatting: passed.
- Frontend ESLint and production build: passed.
- Playwright real frontend/backend/PostgreSQL journey: `1 passed`.
- Manual in-app browser connected gap/rematch journey: passed.
- `git diff --check`: passed.
- Secret scan: no live credential found; the Secret manifest contains only
  explicit `REPLACE_OUTSIDE_GIT` placeholders.
