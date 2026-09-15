# S5-V023-IMPL-315 - Native Execution Handoff

## Authority and fixed candidate

- Type: `G1 / BOUNDED IMPLEMENTATION`.
- Human allocation: `AUTHORIZED` on 2026-09-15.
- Implementation owner: this Codex task; no sub-agent and no shared writable worktree.
- Fixed source: `f189212232fc194859a695f0307e83b0c7b73c0f`.
- Fixed tree: `a8a9251d5d2e47605d18bb63e362164ec4c920d2`.
- Branch: `codex/s5-v023-impl-315-native-execution-handoff`.
- Worktree token/path: `5b6f` / `/Users/tristan/.codex/worktrees/5b6f/cloud-native-agent-platform`.
- Migration: `0022_native_execution_dispatch.sql`.
- Planned PostgreSQL asset: container `s5-v023-impl-315-postgres`, database
  `s5_v023_impl_315_native`, host port `127.0.0.1:55415` (confirmed free before
  asset creation).
- Planned Kubernetes asset: a task-owned kind cluster and namespace
  `s5-v023-impl-315-native`; the pre-existing `kind-agentos-dev` context is
  read-only for this task and is not treated as an authorized writable cluster.
- Raw evidence: `/Users/tristan/.codex/evidence/s5-v023-impl-315-native/`.
- Repository evidence: `docs/evidence/s5/v0.2/s5-v023-impl-315/`.

The attachment checksum was verified as
`ebd8912cc0f9cbe4e036be69ecf9778d6283c2588d2337b35cb19e55a8ffde36`.
After fetching visible remote refs, the task ID, branch and migration filename
were absent from repository text/history, local and remote branch tips, GitHub
PRs/issues, and visible worktrees. This is a bounded collision review, not a
claim about inaccessible repositories or other hosts.

## Gate decision

G1 applies because the change introduces an internal PostgreSQL adapter, an
Operator worker and meaningful backend/operator/runtime composition. No G2
condition is required by this plan: the public Agent/Task/Workflow CRDs and API
group remain unchanged; `/v1/invoke` remains compatible; PostgreSQL remains the
already-accepted Execution Authority; Kubernetes remains actual-state authority;
the Runtime remains native-effect authority; and no production persistence
technology is added.

Stop and escalate if implementation requires a public CRD/API or frozen Contract
change, a lifecycle semantic change, a new production database/infrastructure
dependency, or a Control Plane/cross-plane ownership change.

## Directed contract review

### Placement

The canonical `PlacementRequest` and `PlacementDecision` contract and
`PostgresExecutionAuthorityRepository.decide()` already persist exact Attempt,
Agent Instance, Runtime Instance and digest bindings. Dispatch will consume only
a `PLACED` decision, re-read it in the command transaction, verify its canonical
digest and require the persisted Runtime Instance generation to equal the command
generation. Placement remains immutable and is not reminted by the worker.

### Authorization

Intent submission records only `QUEUED`. Immediately before `EFFECT_STARTED`,
the dispatch owner transaction will lock the active claim and exact command,
validate subject/scope, exact dispatch grant, current credential, recovery epoch,
policy generation, revocation state, Attempt/Assignment/Plan binding, Placement,
Runtime generation and fencing token, then commit `EFFECT_STARTED`. The
PostgreSQL authority reader's caller-owned transaction seam and matching grant-row
locks are the only symbols selectively carried from fixed 310. A revocation that
commits first therefore denies the effect; once `EFFECT_STARTED` commits, this
attempt may continue. No database transaction spans Kubernetes or HTTP calls.

### Operator and Runtime

The new Operator worker claims durable commands with `FOR UPDATE SKIP LOCKED` and
an incrementing claim generation plus opaque fencing token. It creates one
deterministically named, labelled existing `agentos.io/v1alpha1` Task, records its
UID as correlation, and uses the existing Native HTTP seam to invoke the existing
Runtime `/v1/invoke` handler. The current public Task schema is unchanged. Managed
dispatch Tasks are excluded from the legacy create handler so only the new worker
owns their status and transport.

The worker observes Kubernetes Task status before any post-start action. Once
`EFFECT_STARTED` exists it never dispatches again. A missing, ambiguous or
untrustworthy observation becomes `UNKNOWN/RECOVERY_REQUIRED`; it never becomes
success or known failure. Only a terminal Kubernetes observation with matching
UID, command, Attempt, Placement, Runtime and fencing correlations can enter the
terminal PostgreSQL transaction.

The composed worker uses one stable externally configured worker identity. On
restart it first resumes only that identity's `EFFECT_STARTED` rows for observation;
it does not mint a new effect claim. Task annotations bind the persisted claim
generation and fencing-token digest as well as Attempt, Placement, Runtime instance
and generation.

## Implementation plan

1. Add migration 0022 with immutable dispatch command payload/digest, state,
   lease, monotonically increasing claim generation, fencing token, Kubernetes
   correlation and append-only facts. Use a 30-second claim lease and no lease on
   `EFFECT_STARTED`; polling/backoff is one second in the composed worker.
2. Add storage-independent command/claim/terminal values and repository ports,
   then implement PostgreSQL enqueue, claim/reclaim, effect permission,
   correlation, unknown and terminal operations with exact replay/conflict rules.
3. Add the server-side application that accepts an exact persisted Attempt and
   Placement and records only a canonical `QUEUED` command. Keep command input
   bounded and secret-free.
4. Selectively add the caller-owned current-authorization reader seam from fixed
   310 and test revocation/effect serialization. Do not import Workbench/BFF/UI.
5. Add the Operator worker/adapter and lifecycle composition. Preserve the public
   Task CRD; make transport and Kubernetes clients injectable for deterministic
   failure-point tests.
6. Extend the existing completion writer so command terminal, Attempt technical
   state, ordered Evidence and technical Outcome commit atomically. Business
   Problem state is untouched.
7. Test positive exact readback, zero-effect rejection, revocation linearization,
   concurrent claim/fencing, the three required crash points, UNKNOWN
   no-redispatch, terminal rollback/replay/conflict, and existing compatibility.
8. Run targeted tests, real PostgreSQL integration, `make check`, normal hooks,
   and an isolated L3 kind scenario with a real Operator worker, Kubernetes Task
   and workload, HTTP `/v1/invoke`, and Runtime handler. Record transport,
   handler, model and governance evidence separately.
9. Inspect diff/status, record migration checksum and asset/rollback notes, commit,
   non-force push, create one Draft PR, and follow automated CI to a terminal state.

## Compatibility, risks and rollback

The schema change is additive and internal. Existing desired-command,
Placement, Task, Runtime and Evidence readers remain compatible. The principal
risk is ambiguity after external effect start; the design deliberately sacrifices
automatic retry and reports `UNKNOWN/RECOVERY_REQUIRED`. Claim expiry is allowed
only before `EFFECT_STARTED`, and every mutation after a claim checks generation
and fencing token.

Code rollback is the 315 branch/PR. Migration rollback is not destructive: stop
the 315 worker and leave additive tables/data intact, or discard only the verified
315 test database. Preserve UNKNOWN workloads and correlations for observation.
Delete only assets created by this task after confirming they have no evidence
value. Human gates for Ready, merge, production deployment, release, acceptance
and Session closure remain unheld.

## Validation evidence

The task-owned PostgreSQL ledger records version 22 with checksum
`e98bf162b1fdd9dc9e0883894b9afb6612447e45c43110dcc821f2cc0cde238f`.
Real L3 execution and recovery evidence is summarized in
`docs/evidence/s5/v0.2/s5-v023-impl-315/README.md`. L4 real model invocation remains
`NOT_PROVEN`; L5 governed model use remains out of scope.
