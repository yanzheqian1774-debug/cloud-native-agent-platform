# S5-V023-IMPL-282 Resource Use Implementation

Status: implementation and local validation complete; Draft PR pending.

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
