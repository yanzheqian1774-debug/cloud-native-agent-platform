# S5-V023-IMPL-222 Checkpoint A Evidence

This task extends only the internal Workflow Control persistence contracts needed
by the paused IMPL-240 application layer. It does not implement that application
layer, frontend behavior, provider calls, Runtime effects, deployment, or release.

## Contract extension

- Migration `0010` is required because `0009` has no distinct review/decision
  facts, successor-Attempt command relation, Placement relation, or durable typed
  operation result record.
- ARCH-208 state names remain authoritative: review is an immutable fact while
  authorization/rejection changes `REQUESTED` to `AUTHORIZED`/`REJECTED`;
  application uses `APPLICATION_PENDING` then `APPLIED` or `FAILED`.
- Retry inserts one next-ordinal Attempt and never mutates its failed predecessor.
- Rerun inserts one successor Run bound to the predecessor's exact approved Plan
  identity, version, and digest and never mutates the terminal predecessor.
- Plan approval and guarded continuation share one serializable transaction.
- Runtime replacement validates the affected Attempt, scoped eligible Placement,
  and existing Runtime desired-command identity before persisting their links.
- The scoped idempotency claim stores the normalized payload digest and exact
  result identities; completed replay reads those identities after restart.

## Validation

Focused domain and real PostgreSQL 15 tests cover migration `0008` through `0010`,
successor Attempt and Run behavior, request/review/decision/application, exact Plan
approval, Placement/Runtime-command linkage, replay/restart, stale and mismatched
claims, immutable terminal predecessors, and rollback on a missing required link.
Full repository and exact-head CI results are recorded in the Draft PR checkpoint.
