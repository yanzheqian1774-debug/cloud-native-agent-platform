# S5-V023-IMPL-282 Resource Use Implementation

Status: correction implementation and local acceptance validation complete;
Draft PR #152 update and CI remain pending.

The validation results below describe the previously committed candidate
`7bb45fdeed5ae82d440356c8824e44b89ce29b7b`. They are retained as historical
evidence only and do not validate the current correction diff.

## Scope and reuse

This increment adds an internal PostgreSQL-owned, Attempt-scoped Resource Use
authority. It reuses canonical Execution Attempt, Plan, Workflow Run, Task Run,
Digital Employee definition/instance, authorization decision, Knowledge
retrieval Evidence, and Qdrant snapshot identities. It adds no HTTP API, CRD,
API group, executor, provider, or persistent infrastructure.

Each `(scope, Attempt, resource kind, managed slot)` has exactly one occurrence.
Facts, measurements, Evidence references, claims, and snapshots are append-only.
The named high-water is the sole CAS-mutated pointer. Missing measurement is
represented by a null value and explicit availability, never zero.

## Checkpoints

- Workspace transfer: the six-file unstaged correction diff was transferred
  read-only from `/Users/tristan/.codex/worktrees/4102/cloud-native-agent-platform`
  to the writable target worktree at
  `/Users/tristan/.codex/worktrees/fae8/cloud-native-agent-platform`. The target
  uses the local-only branch `codex/s5-v023-impl-282-takeover`; delivery remains
  on remote branch `codex/s5-v023-impl-282-resource-use-foundation` and Draft PR
  #152. Target HEAD/tree remain `7bb45fdeed5ae82d440356c8824e44b89ce29b7b` /
  `d327ec99d85c604f50abf0e078f420e0264b6fc8`. All six files matched the source
  byte-for-byte after transfer and `git diff --check` passed.
- Correction completed: the formal `retrieve_with_resource_use` Knowledge path
  now uses a pre-dispatch PostgreSQL UoW for Knowledge binding, Resource Use
  identity, dispatch fact and idempotency, followed by the real Qdrant call and
  a terminal PostgreSQL UoW for Knowledge Evidence plus Resource Use fact,
  measurement, Evidence reference, claim, high-water, snapshot and idempotency.
  A replay with dispatch preparation but no terminal Evidence raises
  `KNOWLEDGE_RESULT_PENDING_CONFIRMATION` and never calls Qdrant again. Exact
  Knowledge, Attempt, Task, Workflow, Plan/approval, Digital Employee and
  optional Agent/Runtime placement lineage is checked before dispatch.
- Migration 0015: committed checksum
  `90cf451635bc538cc145a37d47a907b478a0c611951e517aea398412b90c30be`;
  current correction checksum
  `69fed4a0a618652a54106c601e12d40dd28f2538a514e5ce55c7f5a0dd9f3f1d`.
  It was applied only to the new blank task database `resource_use_282`, where
  the ledger records version 15, that current checksum, and adapter
  `resource-use-postgresql-v1`. No pre-existing ledger was modified.
- Current validation: focused unit/compatibility selection passed 15 tests;
  real PostgreSQL/Qdrant acceptance passed 4 tests; the affected combined
  Knowledge/Resource Use selection passed 20 tests; the exact updated
  employee-identity CI selection passed 73 tests with no skips; `make check`
  passed with 1504 tests passed, 70 environment-dependent tests skipped, and
  one existing Starlette deprecation warning. The real tests cover negative
  exact-lineage rejection, concurrency, terminal rollback, immutable history,
  restart recovery, and exactly one Qdrant search across replay.
- Active task resources: containers
  `s5-v023-impl-282-takeover-postgres` (database `resource_use_282`, local port
  55482) and `s5-v023-impl-282-takeover-qdrant` (local port 63283). No command or
  test remains running. The next unfinished step is final diff review, normal
  commit, explicit non-force push to the original remote branch, and Draft PR
  #152 CI verification.

- Takeover: branch `codex/s5-v023-impl-282-resource-use-foundation`; source
  `8160adbc04ff1508ba5c9d093407edf5948be611`; tree
  `13d5b4be26e044cfdc94fc37d1e7511bc10862ad`; four preserved drafts; no tracked
  diff; prior carrier `systemError`; no Git lock.
- Before first migration: `0015_resource_use_measurement.sql` SHA-256
  `90cf451635bc538cc145a37d47a907b478a0c611951e517aea398412b90c30be`.
- Real services: exclusive containers `s5-v023-impl-282-postgres` and
  `s5-v023-impl-282-qdrant`; existing Knowledge PostgreSQL/Qdrant integration
  test passed (1 test).
- Domain node: reducer/measurement tests passed (4 tests).
- Resource Use PostgreSQL node: 5 tests passed against the exclusive
  PostgreSQL 15 service, including deterministic replay, CAS, scope isolation,
  atomic Knowledge observation commit, and restart readback.
- Combined Knowledge/Resource Use node: 25 tests passed against the exclusive
  PostgreSQL 15 and Qdrant services.
- Repository gate: `make check` passed with 1500 tests passed, 67
  environment-dependent tests skipped, and one existing Starlette deprecation
  warning. The Resource Use database test is one of the default-run skips and
  was separately executed without a skip as recorded above.

## Implemented read model

The internal application service returns immutable `ResourceUseSnapshot` with
snapshot/digest identity, resource-use identity, named high-water, reducer
version, effective state, exact fact and measurement IDs, Evidence references,
limitations, conflicts, and creation time. `READ`, `LIST`, and `COUNT`
authorization occurs before repository lookup. Denial and absence share
`RESOURCE_USE_NOT_FOUND`; writes additionally reject authorization-decision
mismatch, CAS mismatch, and scoped idempotency payload mismatch.

No product HTTP/frontend contract is introduced.

## Fact integration boundary

Knowledge retrieval is integrated from the governed Attempt retrieval result:
the existing owner Evidence is not rewritten. The adapter commits its typed
Resource Use fact, citation measurement, immutable Evidence reference, claim,
snapshot, and high-water atomically in PostgreSQL. Replay of this commit does
not dispatch Qdrant again. An unavailable external result maps to
`OUTCOME_UNKNOWN` and is not automatically retried. Skill and MCP invocation
remain unintegrated because no governed invocation authority is present in this
task.
