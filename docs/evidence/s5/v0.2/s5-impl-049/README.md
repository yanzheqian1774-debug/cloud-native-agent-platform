# S5-IMPL-049 — Skill and MCP Professional Experience Evidence

## Authority and Checkpoint 0

- Human Gate: `S5-IMPL-049 CHECKPOINT 0 AND CHECKPOINT A AUTHORIZED — GO WITH CONDITIONS`.
- Authorized baseline and entry HEAD: `b21888277de3f285bfb349a1e43901f69abf70bb`.
- Exact baseline CI: `33395352329 / SUCCESS` (Human-supplied control fact).
- Branch: `codex/s5-impl-049-skill-mcp-professional-experience`.
- Entry worktree: clean, detached at the exact authorized baseline, then switched to the authorized branch.
- Local branch/worktree inspection found no S5-IMPL-049 or S5-IMPL-050 ownership collision. GitHub API inspection was unavailable at entry; no conditional shared path was modified.
- Architecture Gate: G1. The implementation preserves S5-ARCH-018 typed repository and PostgreSQL authority and the existing `SkillMcpService` lifecycle.

## Product Result

The Skill Workbench now provides a searchable and lifecycle-filtered catalog, truthful dashboard metrics, a contract Builder projection, input/output schemas, parameters, validation, timeout/error/side-effect/idempotency/permission declarations, dependencies, examples, saved test cases, durable test results, result-to-revision comparison, immutable revision lineage, template cloning, and bounded manifest import/export.

The MCP Workbench registers a Streamable HTTP endpoint plus an external `secret-ref:` identity. It provides backend-originated health testing, immutable Tool/Resource/Prompt discovery snapshots, governed Tool selection, separate invocation authorization, real bounded Tool invocation, credential-redacted Evidence, drift inspection, relationships, revision history, bounded manifest import/export, and Product/Technical sibling projections over the same identity.

## Transport Boundary

- Protocol revision: MCP `2025-06-18`.
- Transport: Streamable HTTP only; initialization plus `notifications/initialized` and JSON responses.
- No stdio, deprecated HTTP+SSE compatibility, redirects, automatic retry, or external deletion claim.
- Default destination policy resolves the destination and permits localhost only for this bounded acceptance slice.
- Backend-originated calls enforce a 30-second maximum command timeout, 512,000-byte response limit, JSON-RPC envelope checks, exact negotiated protocol revision, and response redaction.
- Cancellation is recorded as `CANCELLED_BEFORE_DISPATCH`; timeout and connection/protocol failures use stable reason codes. Ambiguous side-effecting calls are never retried.
- Discovery grants neither publication nor invocation authority. Governed selection records `invocationAuthority: NOT_GRANTED`; invocation requires `ALLOW_BOUNDED_MCP_INVOCATION` separately.

## Persistence and Migration

`0004_skill_mcp_professional_experience.sql` adds scoped append-only `professional_facts` for saved tests/results, health, discovery/schema snapshots, governed selections, drift, and invocation facts. The PostgreSQL adapter applies and checks both lifecycle schema version 1 and professional schema version 2 with independent SHA-256 checksums and adapter identities.

Real PostgreSQL 15 validation used an ephemeral localhost container and proved migration application, optimistic aggregate persistence, saved-test restart recovery, and the `TEST_CASE_SAVED` professional fact. No credential value or sensitive raw MCP payload is persisted; inputs and outputs are recursively redacted by sensitive field name before entering the aggregate or fact store.

## Deterministic MCP Acceptance Server

The acceptance fixture is localhost-only test infrastructure, not a production MCP server. It exposes a fixed Tool, Resource and Prompt and controlled catalog drift. Backend tests prove initialization, discovery, governed selection, success, cancellation-before-dispatch, redaction and drift. The Chromium fixture independently proves a real backend-to-server Tool call.

## Real Browser Acceptance

The focused Playwright journey ran in real Chromium against:

- PostgreSQL 15;
- the real FastAPI backend;
- a Vite production build;
- a deterministic localhost MCP Streamable HTTP server.

It created and immutably published MCP and Skill revisions through exact-digest Human review, tested MCP health, discovered one Tool/Resource/Prompt, governed the Tool selection, separately authorized a real invocation, inspected redacted Evidence, searched and filtered the Skill catalog, saved and ran a revision-bound test, bound exact Skill/MCP revisions, ran the preserved bounded capability probe, and verified Product/Technical identity continuity.

Result: `1 passed`.

## Validation Record

- Focused Skill/MCP backend suite: `9 passed` (one existing Starlette/httpx deprecation warning).
- Real PostgreSQL plus real MCP focused suite: `3 passed`.
- Frontend lint: passed.
- Frontend production build: passed.
- Focused real Chromium Playwright: `1 passed`.
- Full post-hook `make check`: `1072 passed, 5 skipped`, with the Skill/MCP PostgreSQL and real MCP tests executed; one existing Starlette/httpx deprecation warning.
- Pre-commit: Ruff lint, Ruff format and pytest passed.
- `git diff --check`: passed.
- Secret and ownership audit: passed; only authorized primary Skill/MCP and Evidence paths changed, with no conditional shared or prohibited path modified.
- Exact-head CI: pending push/PR at the time this local Evidence record was written.

## Product and Technical Consistency

Product View owns no lifecycle, publication, discovery, selection or invocation authority. Technical View projects the same canonical resource ID, scope, aggregate version, immutable revision digests, saved tests/results, discovery/drift, governed selections, Evidence count and limitations.

## Limitations

- This is a private v0.2.2 Workbench API, not a frozen public Contract or production certification.
- The destination policy is intentionally localhost-only in this bounded real slice; arbitrary external endpoint access is prohibited.
- External Secret Reference resolution/authentication is not generalized and credential material is never accepted or stored.
- Cancellation is guaranteed before dispatch; in-flight remote cancellation negotiation is not claimed.
- JSON response mode of Streamable HTTP is supported; SSE streaming is not added.
- No generalized IAM/RBAC, external MCP deletion, production marketplace, HA, release, deployment or certification claim is made.

## Durable Integration Routing Recommendation

Route the non-draft PR through Durable Integration after exact-head CI succeeds. Review should focus on the migration checksum pair, destination/redaction boundary, fact append semantics, production-browser Evidence, and preservation of separate discovery/publication/invocation authority. Do not merge, deploy, allocate REL, close the Session or start downstream work from this implementation Session.
