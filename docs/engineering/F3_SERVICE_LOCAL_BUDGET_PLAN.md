# Service local budget G1 implementation plan

Approved bounded task: keep one original cumulative ledger/profile/pricing/cutoff and
its 200-call/$20 extension; add an opt-in exact Service scope capped at 20 calls/$1
across Planning and Native together. No production activation, model calls, commit
or full release check in this worktree. Existing Human histories are immutable.

Gate: G1 (internal cross-module budget admission on the existing PostgreSQL adapter).
S5-ARCH-018 permits domain-owned additive tables and same-transaction facts in the
same logical database; no new infrastructure, public CRD/API/frozen Contract or
runtime lifecycle semantics. Stop if that boundary cannot be retained.

1. Add a private, pinned scope configuration binding the exact service principal,
   credential, work revision/digest, BOUND digest, service-policy digest, events,
   expiry and approval evidence. Identity excludes caps so changing a cap cannot
   reset an existing scope. No scenario IDs in core code.
2. Add migration 0080: immutable scope registration and reservation attribution
   in the original draft_provider_budget schema, scoped FK to original reservations.
   Migration is explicit; no request-time DDL.
3. Verify Planning provenance through original ServicePlanningRegistry and persisted
   preparation; Native through original BoundServiceExecutionBridge, actual
   Attempt/Skill invocation and claimed MODEL journal key. Never accept a caller
   subject/label as authorization. Verify before the ledger lock in the same
   transaction to retain existing service -> ledger lock ordering.
4. Original reserve keeps its global check. Under that same ledger row lock check
   local sums (settled actual / unsettled worst-case), append attribution with the
   original reservation, and validate exact replay without counting twice. Dispatch
   rechecks provenance/config/attribution. Unknown outcomes remain held.
5. Wire only explicit new Service selection into cycle and single/two-leaf Native
   configuration; absent selection preserves old owners. New deployment must pin
   the new configuration to claim local-budget enforcement. No Human review fact
   is fabricated from automated policy validation.
6. Validate focused real-PostgreSQL cases in isolated disposable DBs: global+local
   intersection, mixed Planning/Native usage, worst-case hold and settlement,
   duplicate/foreign attribution, scope/config conflict, missing proof, concurrent
   final-slot races, and affected old extension/Service/Native paths. Run Ruff on
   changed files. Root integrates patch and runs normal frozen release gate once.

Compatibility: additive private internal configuration/table changes only; old
records are neither backfilled nor attributed to Service. A selected scope fails
closed if schema/provenance is missing. Prior unscoped reservations cannot be
silently adopted, relabelled, or replayed. Migration and install remain pending.
