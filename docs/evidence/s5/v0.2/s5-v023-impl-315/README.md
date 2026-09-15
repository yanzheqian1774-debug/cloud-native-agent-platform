# S5-V023-IMPL-315 Native Execution Handoff Evidence

## Candidate and migration identity

- Fixed base source: `f189212232fc194859a695f0307e83b0c7b73c0f`.
- Fixed base tree: `a8a9251d5d2e47605d18bb63e362164ec4c920d2`.
- Branch: `codex/s5-v023-impl-315-native-execution-handoff`.
- Migration: `0022_native_execution_dispatch.sql`.
- Migration SHA-256:
  `e98bf162b1fdd9dc9e0883894b9afb6612447e45c43110dcc821f2cc0cde238f`.
- PostgreSQL ledger adapter: `native-execution-dispatch-postgresql-v22`.

The final source/tree and CI run are bound in the Draft PR and final task handoff;
they cannot be embedded in the commit that creates itself.

## Required semantics exercised

The real PostgreSQL suite covers exact queue/readback, same-key payload conflict,
persisted Plan/Attempt/Assignment/Placement/Runtime binding mismatch, one-winner
concurrent claim, lease reclaim with monotonic generation, old-worker fencing,
revocation/effect serialization, current authorization denial with zero external
effect, `UNKNOWN` no-reclaim, stable-worker observe-only restart, terminal digest
conflict, and full rollback/replay at command terminal, Attempt terminal, Evidence,
and technical Outcome checkpoints.

The Operator suite covers denial before Kubernetes/HTTP, successful transport,
ambiguous transport to `UNKNOWN`, `EFFECT_STARTED` observe-first replay, crash after
effect permission with no automatic dispatch, and Task correlation across Attempt,
Placement, Runtime instance/generation, claim generation, and fencing-token digest.

## Real L3 evidence

The task-owned assets were used explicitly:

- PostgreSQL container `s5-v023-impl-315-postgres`, database
  `s5_v023_impl_315_native`, host port `127.0.0.1:55415`;
- kind context `kind-s5-v023-impl-315`, three Ready nodes;
- namespace `s5-v023-impl-315-native`;
- Runtime Deployment and Service `researcher-agent`;
- one durable PostgreSQL command and one Kubernetes Task
  `s5-v023-impl-315-74965b151d52c8805a231a30558afe2c`;
- Kubernetes Task UID `f20e8431-efec-498b-b0a3-4968739e07bb`.

The initial worker image failed before claim because a transitive source package was
absent. Two following Jobs failed before claim because the owner-restricted authority
control correctly rejected Kubernetes Secret symlinks. The next Job claimed once,
committed `EFFECT_STARTED`, created and correlated the Task, invoked the Runtime once
over real HTTP, observed `Succeeded`, and then crashed before the terminal transaction
because of an incorrect Attempt ordinal projection. The corrected Job used the same
stable worker identity, recovered the persisted claim, observed the existing Task,
and atomically committed the authoritative terminal bundle. It did not redispatch.

Final exact readback:

- command `SUCCEEDED`, claim generation `1`;
- Attempt `SUCCEEDED`;
- ordered facts `QUEUED`, `CLAIMED`, `EFFECT_STARTED`, `CORRELATED`, `SUCCEEDED`;
- one Evidence record bound to the same Attempt and Kubernetes UID;
- one technical Outcome with `business_problem_resolved=false`;
- Runtime access log count for `POST /v1/invoke` with HTTP 200: exactly `1`;
- successful recovery-worker result count: exactly `1`.

Raw logs, Task JSON, PostgreSQL JSONL readback, image digests, failed-Job history,
asset inventory, and their `SHA256SUMS` are preserved outside the worktree at
`/Users/tristan/.codex/evidence/s5-v023-impl-315-native/l3/`. The pre-L3 database
backup is preserved under the sibling `recovery/` directory.

## Evidence levels

- L3 Native transport/runtime: **PROVEN** for real PostgreSQL, an in-cluster
  Operator worker, a real Kubernetes Task/workload, HTTP `/v1/invoke`, Runtime
  handler identity echo, authoritative observation, and atomic PostgreSQL return.
- L4 real model invocation: **NOT_PROVEN**. The Runtime used the explicit mock
  provider only to exercise transport and handler behavior; it is not represented as
  a real model call.
- L5 governed model selection/use: **OUT_OF_SCOPE / NOT_PROVEN**.

The repository's deployment manifests and Operator Dockerfile were outside this
task's write scope and were not changed. Enabling the composed worker therefore
requires an Operator image that already packages the `core`, `console`, `gateway`,
`operator`, and `runtime` Python modules plus explicit external authority files and
environment configuration. The L3 run used a task-owned, non-production image with
exactly those current-worktree modules. Production packaging/deployment remains out
of scope rather than being implied by this evidence.

## Assets and rollback

No shared `kind-agentos-dev` object was modified. The dedicated database, kind
cluster, namespace, Runtime workload, successful Task, failed Jobs, and successful
Job remain preserved for inspection. Code rollback is limited to this branch/PR.
Migration rollback is non-destructive: stop the worker and retain additive schema and
facts, or restore/discard only the verified task-owned database. Preserve the Task,
UID, correlation, and any `UNKNOWN/RECOVERY_REQUIRED` record before removing test
assets. Code rollback is not data rollback.
