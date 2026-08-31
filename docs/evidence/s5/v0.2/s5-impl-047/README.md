# S5-IMPL-047 Checkpoint A Evidence

## Entry and authority

- Authorized baseline and entry HEAD: `6e721b15be6bd9df98579f9e8de8d1fab7968120`.
- Branch: `codex/s5-impl-047-skill-mcp-resource-workbench`.
- Entry worktree was clean, detached at the exact baseline, with no competing
  S5-IMPL-047 branch or worktree.
- Authority: S5-ARCH-018, v0.2.x Product Capability and Runtime Charter v1,
  and the durably integrated S5-IMPL-046 lifecycle/Workbench pattern.
- No CRD, public Contract, Runtime, Gateway, Knowledge, dependency, credential,
  or external MCP lifecycle path changed.

## Implemented product slice

Skill Definition/Revision and MCP Server Capability Definition/Revision now have
backend-governed Draft, edit, validation with controlled failure, exact-digest
Human review, immutable publication, successor, enable/disable, deprecation,
archive, relationship/consumer inspection, protected deletion impact, and
non-sensitive tombstone behavior.

The Skill and MCP Workbenches operate on the same canonical backend identities
as their Technical sibling projection. An exact published Skill Revision can be
bound to one exact published MCP Revision and declared capability. Publication
only grants discovery and binding eligibility. A separate
`ALLOW_BOUNDED_CAPABILITY_TEST` authorization is required before the bounded
capability test. Its Evidence records no credential material and marks projected
Evidence redacted. The bounded test is a deterministic in-process capability
probe; it does not claim external MCP execution or external server deletion.

## Persistence and recovery

Migration `0002_skill_mcp_lifecycle.sql` owns the `skill_mcp_resource` PostgreSQL
schema. Scoped composite keys, kind checks, lifecycle fact ordinals, foreign keys,
tombstones, checksum-bound adapter identity, bounded pool acquisition, statement
and lock timeouts, and compare-and-set aggregate versions fail closed. There is no
deployment fallback to memory or SQLite. In-memory storage is test-only.

Real PostgreSQL acceptance used the existing local PostgreSQL 15 container. The
migration and repository test passed and a new service recovered the exact
resource identity, published revision identity, and digest.

## Real browser acceptance

Chromium drove the real Vite frontend through the real FastAPI backend and real
PostgreSQL store. It published an MCP Revision, published a Skill Revision, bound
the exact `quality.lookup` revisions, explicitly authorized one bounded capability
test, observed `SUCCEEDED`, verified `Evidence redacted: true`, and inspected the
Technical sibling projection. Result: `1 passed`.

## Security and limitations

- Trusted namespace/security-domain scope is resolved before repository access.
- Cross-scope lookup/binding is not available.
- Endpoint definitions contain no credentials; no Secret value is persisted,
  returned, logged, or included in digest material.
- Publication does not grant invocation authority.
- MCP archive/deprecation/deletion affects Platform records only and makes no
  external deletion claim.
- Private v0.2.2 Workbench APIs are not frozen public Contracts.
- No HA, multi-region, centralized IAM/RBAC, external MCP transport, certification,
  production readiness, deployment, release, or merge claim is made.
