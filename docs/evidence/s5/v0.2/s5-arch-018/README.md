# S5-ARCH-018 Checkpoint A Evidence

## Entry revalidation

| Check | Result |
| --- | --- |
| Authorized baseline | `a6ec463a365b5f12e8fb64b0b84772a3beb0ae15` |
| `origin/main` after fetch | exact match |
| Exact-main CI | GitHub Actions `33359075556`, `SUCCESS`, exact authorized SHA |
| Branch | `codex/s5-arch-018-bounded-product-continuity-persistence` |
| Worktree | clean dedicated worktree at entry; no competing S5-ARCH-018 branch/worktree |
| PR / Issue collision | no S5-ARCH-018 PR or Issue found at entry |
| Reserved IDs | S5-ARCH-014–017 remain `RESERVED / UNRECONCILED / NOT_REUSABLE` |
| Decision classification | `AMENDED_PROPOSAL / READY_FOR_HUMAN_ARCHITECTURE_REVIEW` |

The Human control session explicitly allocated S5-ARCH-018 and granted
`GO_WITH_CONDITIONS`. This supersedes only the prior candidate/unallocated
operational row; it does not reconstruct S5-ARCH-014–017 or grant implementation.

## Authorities inspected

- repository engineering gates, Definition of Done and decision-status rules;
- Product, Architecture, Roadmap and current-implementation boundaries;
- S5-GOV-003 continuity and ordering record;
- accepted S5-ARCH-010 Hybrid F Execution Evidence/SQLite boundary;
- accepted S5-ARCH-011 Product Intent and S5-ARCH-013 Definition publication/
  matchability authorities;
- current in-memory planning, Definition, journey, placement, intervention and
  repository boundaries;
- current SQLite Execution Evidence repository and S5-IMPL-014 evidence;
- current Kubernetes Workflow/Task authority and Qdrant-derived Knowledge boundary.

No relevant accepted ADR conflict was found. The proposal preserves Kubernetes
control authority and assigns SQL authority only to bounded product-continuity
facts outside existing public Workflow/Task control state.

## Result

The amended proposal is [S5-ARCH-018](../../../../../architecture/s5/v0.2/S5-ARCH-018-BOUNDED-PRODUCT-CONTINUITY-PERSISTENCE-V1.md).
It covers four durable domains, typed repository ports, PostgreSQL as the primary
deployment adapter, bounded SQLite transition/test use, immutable history,
authorization-first scoping, secret exclusion, Qdrant derivation, restart
reconciliation, derived Accounting, migration/coexistence and the first Durable
Agent Definition implementation entry.

## PostgreSQL amendment

The Human amendment supersedes the earlier proposal that made one bounded SQLite
store the default for all new v0.2 domains. No implementation or Durable Integration
occurred under that text.

- v0.2.2 Product Journey and Enterprise Resource authority deploys on PostgreSQL.
- Existing SQLite Execution Evidence remains unchanged during a visible two-store
  transition; cross-store linkage uses exact identities, digests and scope and has
  no cross-store atomicity claim.
- Before v0.2.3 closed-loop execution completion, a PostgreSQL Evidence adapter must
  pass the existing typed-port conformance suite and a verified import/cutover/
  rollback gate without identity or digest rewriting.
- Qdrant remains a derived Knowledge index; SQL retains Knowledge/document/chunk/
  ingestion/index-snapshot identities, digests, scope and Qdrant references.
- The first Durable Agent Definition deployment uses its domain-owned Repository
  Port with a PostgreSQL adapter. In-memory/SQLite are focused local/test adapters.
- Immutable/link-based history, scope nondisclosure, Secret-reference-only storage,
  Runtime observed-state reconciliation, derived Accounting and Workbench continuity
  remain unchanged.

The first implementation will require an approved PostgreSQL driver/client dependency
if absent, external Secret reference, bounded pool configuration, PostgreSQL service/
database availability, ordered migrations and a backup/restore rehearsal. These are
G1 implementation/deployment prerequisites, not changes made in this ARCH Session.

## Claim boundary

No database, schema, migration, adapter, dependency, backend, frontend, operator,
runtime, gateway, CRD, public API or product behavior was created or modified.
There is no State Plane, Tenant architecture, shared-filesystem, multi-node, HA,
exactly-once, certification, production-readiness, deployment or release claim.

## Validation record

| Validation | Result |
| --- | --- |
| Architecture/index links and exact-path audit | passed; same exact six paths |
| Authority, terminology, domain/lifecycle and persistence-boundary audit | passed |
| Security/nondisclosure, secret/private-data and unsupported-claim audit | passed |
| `git diff --check` | passed |
| `make check` | passed: Ruff lint, Ruff format and `1046 passed`; one existing Starlette/httpx deprecation warning |
| `uv run pre-commit run --all-files` | passed: Ruff lint, Ruff format and pytest |
| Commit / Draft PR / exact-head CI | pending amendment commit and CI |

## Next gate

Human review of the PostgreSQL amendment. Durable Integration, REL allocation and G1
implementation remain prohibited until the amended proposal is accepted.
