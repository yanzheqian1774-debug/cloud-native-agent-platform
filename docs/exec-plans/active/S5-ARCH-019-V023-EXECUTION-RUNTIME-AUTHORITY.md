# S5-ARCH-019 — v0.2.3 Execution and Runtime Authority Plan

## Status

`ACTIVE / AUTHORIZED / CHECKPOINT_A / G2_ARCHITECTURE_ONLY`

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

## Next gate

Human Architecture Review and Durable Integration decision. Implementation remains
unallocated and prohibited until that gate passes.
