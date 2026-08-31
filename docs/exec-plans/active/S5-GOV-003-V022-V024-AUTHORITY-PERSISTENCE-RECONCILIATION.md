# S5-GOV-003 — v0.2.2–v0.2.4 Authority and Persistence Reconciliation

## Authority and boundary

| Field | Value |
| --- | --- |
| Session | `S5-GOV-003` |
| Type | `GOV` |
| Checkpoint | `0/A — Entry Revalidation and Bounded Governance Reconciliation` |
| Human allocation | `CONFIRMED` |
| Authorization | `GO WITH CONDITIONS` |
| Baseline | `474b19e7bf32a342d93b4b891f6c7a799b9261b6` |
| Branch | `codex/s5-gov-003-v022-v024-authority-persistence-reconciliation` |
| Architecture gate | `G0` for this governance-only change; subsequent persistence work requires `G2` |

This plan durably records Human-confirmed product definitions and the selected
persistence direction. It authorizes no product code, persistence code,
database, public API, CRD, deployment, release, architecture implementation, or
downstream Session.

## Entry revalidation

- Fetched `origin`; `origin/main`, starting `HEAD`, and the authorized baseline
  were exactly `474b19e7bf32a342d93b4b891f6c7a799b9261b6`.
- Exact-main CI run `33353367214` was `SUCCESS` for that SHA.
- The dedicated worktree was clean and the authorized branch did not collide.
- Repository text, branches, worktrees, GitHub PRs/issues and visible active
  tasks contained no competing S5-GOV-003 writer or expected-path owner.
- Historical S5-ARCH-014–017 task traces were observed, but durable main lacks
  sufficient authority records. They remain reserved/unreconciled and are not
  reconstructed, accepted, started, or reused here.

## Recorded product sequence and dependencies

```text
v0.2.1 → v0.2.2 → v0.2.3 → v0.2.4 → v0.3.0
```

There is no v0.2.5 in the current Human-confirmed sequence.

1. v0.2.2 establishes the Factory, Enterprise Resource Workbench and durable
   product-continuity identities and histories needed downstream.
2. v0.2.3 binds durable definitions to Run, Attempt, Placement, Runtime/Agent
   Instance, invocation, Event, Evidence, Outcome and Feedback closure.
3. v0.2.4 consumes durable definitions and execution Evidence for governed
   Model Catalog, Evaluation, Selection, exact binding and fallback.

S5-IMPL-044 is a supporting v0.2.2 Accounting primitive. S5-IMPL-043 is a
v0.2.4 foundation/thin slice. Neither proves its full minor-version outcome.

## Binding Workbench continuity

The reconciliation preserves the Business Workbench; Enterprise Resource
Workbench; Runtime Operations Workbench; Model Governance Workbench; and
Technical Inspection described in [PRODUCT.md](../../../PRODUCT.md#binding-workbench-continuity).
Product View and Technical View remain sibling projections over common
canonical objects and identities. Neither frontend becomes lifecycle, planning,
execution, authorization, or Evidence authority.

The common resource experience progresses from Dashboard and Catalog/List
through Detail, applicable Draft/Authoring, Validation/Test, Human Review,
Publication, immutable Revision History, Relationships/Consumers,
Invocation/Retrieval History, and Deprecation. This is a resource-appropriate
governed lifecycle pattern, not a requirement for a generic table or a
view-only dashboard.

The first v0.2.2 Agent Definition slice implements this pattern first without
reducing or superseding the planned Skill, MCP, Knowledge, Digital Employee,
Runtime Operations, or Model Governance workbenches.

## Persistence decision and next architecture gate

The selected direction is domain-owned typed repository ports; bounded
single-node SQLite adapters for v0.2; immutable revisions and append-only or
link-based histories; transaction, replay, digest-conflict, schema-version and
migration validation; replaceable PostgreSQL; Qdrant retained for vector
storage; durable SQL identities/references for Knowledge and index snapshots;
external secret values with only typed references and non-sensitive status
persisted; Runtime observed state reacquired and reconciled after restart; and
Accounting derived from durable facts unless a high-water snapshot is
separately approved.

This is direction for a subsequent consolidated persistence G2, not an accepted
implementation design. `S5-ARCH-018` is candidate-only, unallocated and not
active.

## Authorized paths

- `PRODUCT.md`
- `ROADMAP.md`
- `PROJECT_STATE.md`
- `docs/governance/REGISTRY.md`
- this exec plan
- `docs/evidence/s5/v0.2/s5-gov-003/README.md`
- `docs/evidence/s5/README.md` only for stable Evidence linkage

## Validation and exit

Validate Markdown links and governance structure; exact sequence, lifecycle and
terminology; unsupported claims and expected paths; `git diff --check`;
repository checks including `make check`; pre-commit followed by non-mutating
validation; secret/private-data patterns; focused diff/status; and exact-head CI
after PR creation.

Exit is a bounded governance commit and PR awaiting Human review and Durable
Integration. No merge, release, deployment, S5-ARCH-018 allocation, or v0.2.2
implementation allocation is performed by this Session.
