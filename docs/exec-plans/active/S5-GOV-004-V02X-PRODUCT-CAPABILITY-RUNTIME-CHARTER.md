# S5-GOV-004 — v0.2.x Product Capability and Runtime Charter v1

## Authority and boundary

| Field | Value |
| --- | --- |
| Session | `S5-GOV-004` |
| Type | `GOV` |
| Control session | `v0.2-CONTROL-003` |
| Checkpoint | `0/A — Entry Revalidation and Durable Charter Recording` |
| Human allocation | `CONFIRMED` |
| Baseline | `5b990fe561d2044de61dc3ce3899e024327aab33` |
| Exact-main CI | run `33369618464`, `SUCCESS` |
| Branch | `codex/s5-gov-004-v02x-product-runtime-charter` |
| Architecture gate | `G0` governance recording; no implementation or architecture change |

This charter is the Human-confirmed product capability and Runtime boundary for
v0.2.x. It preserves S5-ARCH-018 and all S5-IMPL-046 limitations. It does not
redesign the Portfolio, change implementation, reopen architecture, allocate a
downstream Session, claim v0.2.2 completion, or resume S5-IMPL-042.

## Product charter

v0.2.x is both a Core Enterprise AI Capability Platform and a user-facing
product that can be truthfully used, demonstrated and operated. It must manage
core Agent, Digital Employee, Skill, MCP, Knowledge, Model, Workflow, Runtime,
and Evidence/Outcome resources.

Where applicable to a domain, management includes Draft, validation,
exact-digest Human review, immutable publication, successor, relationship,
enable/disable, deprecation, archive and protected deletion semantics. New
product-continuity domains use PostgreSQL as their primary deployment
persistence. Qdrant is a derived Knowledge vector index, never Knowledge
identity or lifecycle authority.

The product must provide domain-specific Workbenches in a coherent shell, real
resource discovery/binding/composition, a real Digital Employee composition,
version-required Runtime execution, authorized Knowledge Operations, and
Evidence, Citation and Outcome. Product and Technical Views remain sibling
projections over canonical backend-owned objects. Acceptance uses real-browser
journeys against real services and states limitations explicitly.

## Version boundary

### v0.2.2 — Core Resource Management and Composition

- Agent, Skill, MCP and Knowledge foundation;
- Digital Employee Definition and resource composition;
- Runtime Provider/Profile and binding;
- PostgreSQL persistence for new product-continuity domains;
- Resource Catalog and domain Workbenches; and
- a real resource-composition browser journey.

### v0.2.3 — Digital Employee Execution and Runtime Closure

- Assignment, Digital Employee Instance and Runtime Instance;
- Run and Attempt;
- reuse and productization of the v0.1 Kubernetes-native Runtime;
- one bounded real OpenClaw execution vertical slice;
- Knowledge ingestion and authorized retrieval;
- Skill/MCP invocation;
- Evidence, Outcome and Intervention;
- reconciliation and recovery; and
- Runtime Operations Workbench.

### v0.2.4 — Model and Capability Composition

- Model Catalog plus Provider and model management;
- evaluation and Runtime compatibility;
- Agent, Digital Employee and Knowledge model binding;
- usage and latency; and
- token and cost when measurable, otherwise explicit `NOT_MEASURABLE`.

### v0.3.x — Enterprise Governance and Operations

The complete Runtime Manager, Tenant and Organization, centralized Policy and
Authorization, Marketplace, FinOps, HA/autoscaling/failover, certification,
generalized Recovery, governed optimization and ecosystem operations remain
v0.3.x boundaries.

## Minimum v0.2.x governance

Identity, Revision, digest, Human Review, publication, authorization, isolation,
Secret Reference, Evidence, audit, impact analysis, deletion protection and
fail-closed behavior remain mandatory in v0.2.x. This minimum does not claim
complete v0.3.x centralized governance.

## Product acceptance

Backend-only, API-only, architecture-only, mock-only, generic-table-only,
fixture-only or browserless delivery does not satisfy a v0.2.x capability. An
accepted capability requires a real user entry, frontend operation, backend
authority, required durable persistence, real composition or consumption,
version-required execution, Evidence/Outcome, real-browser acceptance and
explicit limitations.

## Runtime continuity

The v0.1 Native Runtime technical validation is preserved and reused. v0.2.3
productizes and reconnects that Runtime; it does not reimplement Native Runtime
from zero. OpenClaw is mandatory only as a bounded v0.2.3 vertical slice. The
complete Enterprise Runtime Manager remains v0.3.x.

## Delivery sequence and writer boundary

1. Agent Definition vertical slice — durably integrated, with S5-IMPL-046
   limitations preserved.
2. Skill and MCP Resource Lifecycle and Workbench.
3. Knowledge Operations and Workbench.
4. Shared Product Shell and Resource Workbench assembly.
5. Digital Employee Definition and resource composition.
6. Complete v0.2.2 browser acceptance and release gate.
7. v0.2.3 Runtime execution closure.
8. v0.2.4 Model and capability composition.

After this charter is durable, Skill/MCP and Knowledge may run as two isolated
implementation tracks. Shared frontend shell, route, dependency, migration and
CI paths require one owner. At most two heavy implementation writers may run
concurrently. This governance Session does not allocate those writers or tasks.

## Entry revalidation and consistency

- `HEAD`, fetched `origin/main` and the authorized baseline matched exactly.
- Exact-main CI run `33369618464` completed successfully for that SHA.
- No repository, branch, worktree or open-PR use of S5-GOV-004 existed.
- GitHub reported no open PRs; no competing writer owned the governance paths.
- Durable v0.2.2–v0.2.4 definitions, merged S5-ARCH-018 authority and merged
  S5-IMPL-046 Evidence were inspected.
- PostgreSQL-primary persistence, bounded transitional/local-test SQLite,
  Qdrant-derived indexing, protected deletion, Workbench authority and Runtime
  continuity are consistent with S5-ARCH-018.
- No direct contradiction was found.

## Changed-path authority and exit

The exact paths are `PRODUCT.md`, `ROADMAP.md`, `PROJECT_STATE.md`,
`docs/governance/REGISTRY.md`, this charter, and
`docs/evidence/s5/v0.2/s5-gov-004/README.md`.

Exit is one bounded governance commit and PR for Human review and Durable
Integration. No product implementation, architecture decision, broad Portfolio
rebaseline, downstream IMPL/REL allocation, release or completion claim is
authorized.
