# S5-IMPL-056 Checkpoint A0 Evidence

## Result

| Field | Value |
| --- | --- |
| Status | `PASS / CHECKPOINT_A0_READY_FOR_HUMAN_CONTRACT_REVIEW` |
| Session | `S5-IMPL-056` |
| Checkpoint | `0 -> A0` |
| Human decision | `AUTHORIZED / CONTRACT_ONLY` |
| Architecture authority | `S5-ARCH-019 / DURABLY_INTEGRATED / BINDING / CLOSED` |
| Next gate | Human Contract Review |

## Entry revalidation

- Fetched `origin/main` and verified local HEAD and `origin/main` were exactly
  `2c6a5930eefb99467f9821ef9aa0ebc55159dcb4` before branch creation.
- Verified GitHub Actions run `33471232560` was completed successfully for that
  exact `main` SHA.
- Found no repository text, local/remote branch, tag, worktree, PR or Issue collision
  for `S5-IMPL-056`, and no pre-existing execution Contract writer at either
  authorized core path.
- Inspected open S5-IMPL-054 PR #109 and S5-IMPL-055 PR #110 file ownership; neither
  touches any of the five S5-IMPL-056 authorized paths.
- Verified the migration chain remains exactly `0001` through `0007`; migration
  `0008` does not exist.
- Created branch `codex/s5-impl-056-execution-authority-typed-contract` only after
  these checks passed.

## File-by-file G1 A0 plan

1. `core/src/agent_core/execution_contract.py`: immutable nominal execution
   identities, scoped relationship values, Placement and Runtime desired/observed
   state values, command result vocabulary, canonical serialization and digests.
2. `core/src/agent_core/execution_repositories.py`: scope-required typed Protocol
   candidates only; no storage implementation.
3. `core/tests/test_execution_contract.py`: invariants, fail-closed parsing,
   replay/conflict, freshness, digest and byte-stable Track B fixture coverage.
4. `core/tests/test_execution_repository_contract.py`: Protocol shape and mandatory
   scope-parameter conformance fixtures.
5. `docs/evidence/s5/v0.2/s5-impl-056/README.md`: entry, implementation, validation,
   exact-head and limitation evidence.

## Published internal Contract

### Identity Contract

- Distinct frozen nominal values cover Digital Employee Instance, Agent Instance,
  Assignment, Workflow Run, Task Run, Attempt, Runtime Instance, Placement,
  Evidence, Outcome, Intervention, Command and Observation identities.
- Opaque IDs are normalized non-empty UTF-8 values with a 200-byte maximum.
- `ScopeIdentity` normalizes namespace and security domain independently and enforces
  a 128-byte maximum on each.
- `Generation` is an explicit positive integer with monotonic transition validation.
- Scoped relationship aggregates enforce Assignment -> Workflow Run -> Task Run ->
  Attempt ownership. Helpers make retry, rerun and correction successor semantics
  explicit; replacement desired state contains no Attempt identity.

### Placement Contract

- Placement requests contain the exact A0 input fields and deterministically sort
  requirement collections.
- Exact request-ID/canonical-byte replay is accepted; changed bytes conflict.
- `PLACED` requires a Runtime Instance and `REJECTED` prohibits one.
- Decisions are frozen and bound to a lowercase SHA-256 digest; parsing verifies the
  digest before consumption.

### Runtime State and Command Contract

- Desired state contains Runtime Instance, generation, allowlisted desired state,
  command identity, requester, timestamps and reason classification.
- Append-only observation values keep provider/Kubernetes handles inside typed
  correlations and independently express normalized state, health and readiness.
- Missing observation resolves to `UNKNOWN`; an expired observation resolves to
  `STALE`. Neither `RUNNING` nor `READY` represents Attempt or business success.
- Command results are exactly `REQUESTED`, `APPLIED`, `OBSERVED`, `REJECTED`,
  `UNKNOWN`, `STALE` and `RECOVERY_REQUIRED`. Applied, observed or ambiguous effects
  prohibit blind reissue.

### Repository Port candidates

Protocols cover identity aggregate save/get, Placement decide/get/get-by-request,
desired command append/read, Runtime observation append/read, and bounded
Evidence/Outcome/Intervention relationship reads. Every operation requires a trusted
`ScopeIdentity`. No adapter, database, import, or other storage behavior exists.

### Canonicalization and Track B compatibility

- Serialization is deterministic UTF-8 canonical JSON in a `v0.2.3-a0` envelope;
  it never uses Python object representation.
- Canonical collections are sorted and timestamps are UTC-normalized.
- Digests are lowercase SHA-256.
- Allowlisted mapping constructors reject unknown/missing fields and invalid enums.
- The Track B Placement fixture is asserted byte-for-byte with digest
  `0449066a6cba3eca8d2f79890f248f2c9c7688cbd76d1cb8222a6748f4a35d8c`.

## Validation

- Focused Ruff lint: passed.
- Focused contract suite: `29 passed`.
- `make check`: passed with Ruff lint, Ruff format check and repository pytest.
- Repository pytest: `1135 passed, 13 skipped, 1 warning`.
- Skips require optional real PostgreSQL or Qdrant services and are unrelated to this
  Contract-only Checkpoint. The warning is the existing Starlette/httpx deprecation.
- The first sandboxed baseline run reached `1134 passed, 13 skipped` and failed only
  because the sandbox prohibited the MCP test's localhost socket bind. The exact same
  gate passed when rerun with local-socket permission.

## Commit, draft PR and exact-head CI

The immutable commit SHA, draft PR URL and its exact-head CI run are reported in the
Checkpoint A0 result after this evidence-bearing commit is created and validated by
GitHub. This avoids embedding a self-referential commit or a stale pre-evidence CI
run in the commit itself.

## Limitations

This Checkpoint publishes an internal, not-frozen candidate Contract only. It grants
no database migration, persistent adapter, SQLite import/cutover, reconciliation
loop, Kubernetes/provider effect, Native translator, OpenClaw implementation,
frontend, assembly, deployment, execution, IAM/RBAC/Tenant architecture, HA,
automatic recovery, exactly-once effect, certification, production readiness or
release authority. Product ID uniqueness and authorization-context provenance are
repository/application enforcement responsibilities outside this Contract-only
Checkpoint.

## Checkpoint A1 — execution persistence

Checkpoint A1 starts from durable baseline
`b077c6ec1172dbd6ec33cf08691212a98c8c6d22` and implements only the authorized
PostgreSQL execution-authority storage, immutable Evidence adapter, verified
SQLite Evidence import, and single-writer cutover/rollback barrier. Migration
`0008_execution_runtime_authority.sql` follows the complete existing `0001` through
`0007` chain and records its exact SHA-256 checksum and adapter identity.

The PostgreSQL validation uses a real PostgreSQL 15 instance. It covers clean-chain
migration, repeat application, checksum verification, rejection of missing,
corrupt, and newer migration metadata, pooled connections, atomic concurrent
Evidence replay, digest conflicts, scope isolation, restart durability, and bounded
failure mapping. The import validation verifies a quiesced immutable SQLite backup,
deterministic sequence-order import, resumable checkpoints, exact record identity,
payload digest, storage sequence and recorded-time preservation, and full count/high
water parity. Cutover and rollback tests prohibit dual writers, silent SQLite
fallback, and rollback that would discard post-cutover PostgreSQL facts.

The compatibility consumer assertion remains an exact fail-closed allowlist. Its
only A1 change is the four Human-authorized Console consumers; the pre-existing
authorized set is unchanged. No Runtime Manager, provider effect, OpenClaw,
frontend, CRD, deployment, S5-IMPL-057, or S5-IMPL-058 scope is included.

Checkpoint A1 validation and exact-head CI identifiers are reported in the Human
Checkpoint result after the evidence-bearing commit and Draft PR exist, avoiding
self-referential or stale evidence.

### Checkpoint A correction and bounded operational limitations

The correction adds durable typed identity save/readback, Outcome and Intervention
reads, execution relationship queries, command-result facts, complete aggregate
column validation, versioned checkpoint compare-and-set, bounded import-set identity,
interrupted-import resumption, scope isolation, relationship foreign keys, and
restart coverage across every Track A repository surface.

Four operational responsibilities remain deliberately outside this repository-only
checkpoint and fail closed at their existing barriers:

- SQLite writer quiescence must be independently proven by the downstream Track H
  operational cutover gate; the importer rejects invocation unless its caller
  supplies explicit quiescence evidence.
- Post-cutover SQLite read-only enforcement belongs to the Track H/deployment gate;
  the cutover coordinator never selects SQLite and PostgreSQL simultaneously and
  provides no silent fallback.
- Complete SQLite authority restoration belongs to the Track H/deployment rollback
  gate; rollback is rejected unless all writers are stopped, the backup is verified,
  and no PostgreSQL fact would be discarded.
- The legacy SQLite schema stores decomposed fields rather than original canonical
  bytes. Track A reconstructs canonical form deterministically and verifies the
  durable payload digest; no claim of independent original-byte comparison is made.

These limitations prohibit any production cutover-readiness claim at Checkpoint A.
No deployment, production/staging mutation, Kubernetes wiring, OpenClaw work, or
A+B production assembly is included.
