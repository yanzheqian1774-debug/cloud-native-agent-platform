# S5-ARCH-019 — v0.2.3 Execution and Runtime Authority Plan

## Status

`CLOSED / COMPLETED / SESSION_CLOSED / DURABLY_INTEGRATED / BINDING /
G2_ARCHITECTURE_ONLY`

PR #106 merged at durable main `4200bd33c489bd544c04c3209f58b5b84c80bd14`;
exact-main CI run `33467767800` succeeded. S5-REL-060 is also `CLOSED /
COMPLETED / SESSION_CLOSED`. Reopening either Session is prohibited.

## Objective

Produce a review-ready G2 decision for canonical execution identity, PostgreSQL and
Kubernetes authority, desired/observed reconciliation, Execution Evidence cutover,
Native reuse, bounded OpenClaw lifecycle and two future backend track boundaries.

## Authority and exclusions

- Authorized baseline: `c06c5d8da89e1df960e64f48036c9dea2f8166a5`.
- S5-ARCH-018 is accepted and durably integrated; this plan specializes it and does
  not reopen it.
- S5-IMPL-053 may proceed in parallel and owns protected assembly/frontend paths.
- No code, migration `0008`, CRD/API, dependency, deployment, implementation Session
  allocation, Contract freeze, completion or production claim is authorized.
- Migration `0008` is `FUTURE_RESERVED_FOR_V0.2.3_EXECUTION_AUTHORITY /
  NOT_IMPLEMENTED / NOT_ALLOCATED`; implementation authority is `NONE` until a
  separate Human allocation.
- The v0.2.2 chain remains `0001`–`0007`; Wave 3B requires no migration. Any Wave 3B
  migration requirement is `STOP / G2` and requires new Human authority.

## Checkpoint 0

- Fetch and verify exact baseline and exact-main CI.
- Search Registry/text, local/remote branches, worktrees, GitHub PRs/issues and Human
  allocations for collision.
- Verify clean isolated worktree and S5-IMPL-053 path separation.
- Read mandatory guidance, accepted decisions and current Runtime/Evidence source.
- Record an exact authorized file plan before editing.

## Checkpoint A deliverables

1. Proposed authority and identity decision.
2. Desired/observed model and Kubernetes safety prohibitions.
3. Single-writer PostgreSQL Evidence import/cutover/rollback decision.
4. Conceptual sole ownership of migration `0008` by future Track A.
5. Native reuse and bounded post-Native OpenClaw decisions.
6. Immutable Intervention, Outcome, retry, rerun and correction semantics.
7. Non-overlapping future Tracks A/B and serialized shared integration paths.
8. Evidence, governance and architecture indexes.

## Validation

- architecture link integrity;
- terminology, identity and authority audit;
- migration ownership and S5-IMPL-053 collision audit;
- limitation, unsupported-claim and secret scan;
- `git diff --check`;
- `make check`;
- `uv run pre-commit run --all-files`, followed by diff inspection and non-mutating
  validation;
- Draft PR and exact-head CI.

## Future implementation gate

Architecture review and Durable Integration are complete. S5-ARCH-019 and S5-REL-060
remain closed. Any future Track A/B implementation requires a separate Human
allocation and G1 plan; none is granted here.
