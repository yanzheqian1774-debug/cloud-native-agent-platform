# S5-V023-IMPL-297 recovery checkpoint

Status: `PARTIAL_DRAFT / OWNER_DECISION_REQUIRED / SESSION_OPEN`.
This document is an implementation checkpoint, not an accepted architecture decision.

## Execution recovery and fixed identity

Recovered on 2026-09-08 in the existing branch worktree:
`/Users/tristan/.codex/worktrees/878e/cloud-native-agent-platform`.
Branch: `codex/s5-v023-impl-297-durable-problem-plan-entry`.
HEAD/base: `ae002a2e9a4b765fe311e1e74328a9b6111a4929`.
HEAD tree: `d007b63a4ab4a6bd38849d3c03df5ff6927d07a7`.

The old execution (`01a0812b-20b4-7042-8294-111b6b719e61`) reports a failed
turn and `systemError` after a transport disconnect. Process inspection found
no remaining test, shell mutation, commit or push command for this worktree.
Idle tool-runtime processes retained cwd handles; no second active writer was
observed. No commands were restarted or shared application assets operated.

Read-only ancestry inspection corrects the old local-main statement:
`main=3cd910f150a13e366c45cd6f83878f395a74efe8` is the merge base and an
ancestor of the fixed baseline. `main...HEAD` counts are `0 / 392`: this is
a stale local reference, not advancement or divergence. Live `ls-remote`
returned the fixed baseline for remote main, including the follow-up check.
No fetch, refresh, checkout, reset, restore, stash or rebase was performed.

## Recovered paths and completeness

Initial Git inventory contained no staged changes, three modified paths and
two untracked paths, all under `console/backend/src/agent_console/`:

- `business_problem_domain.py`: aggregate read value; 13 added lines.
- `business_problem_repository.py`: aggregate and membership read ports; 10 added lines.
- `business_problem_postgres.py`: scoped read adapters; 83 added lines.
- `business_problem_schemas.py`: 3,700-byte DTO draft, not registered HTTP.
- `business_plan_postgres.py`: 14,719-byte UoW draft, not production-connected.

All five parsed successfully with Python AST. This proves syntactic file
completeness only, not implementation or acceptance. The UoW draft was preserved
byte-for-byte: SHA-256
`49b5169f27e5f9379e7aae5260b2fa43d91ca1069b103563de95b885757d0c43`.
It has 23 Ruff findings. Its presence must not be read as a completed Plan entry.

This recovery adds only this checkpoint and
`console/backend/tests/test_business_problem_entry_foundation.py`.
The test uses Product owner methods to create all business records; SQL is
limited to isolated database provisioning and migrations. It does not claim
normal HTTP, approved Plan, execution, Evidence or provider acceptance.

## Local owner and transaction audit

Authority references:

- [ARCH-258](../../architecture/s5/v0.2/S5-V023-ARCH-258-BUSINESS-PROBLEM-SUCCESS-CRITERIA-AUTHORITY-V1.md),
  sections 2, 3, 6, 7, 9: Product owns Problem/Criteria, exact approved Plan
  bindings, scoped idempotency/CAS, denial before disclosure and rollback.
- [ARCH-208](../../architecture/s5/v0.2/S5-V023-ARCH-208-WORKFLOW-CONTROL-PLAN-APPROVAL-INTERVENTION-PERSISTENCE-V1.md),
  sections 6, 8, 11: Workflow Control command claims, atomic UoW and owner ports.
- [IMPL-288 addendum](../../architecture/s5/v0.2/S5-V023-IMPL-288-GOVERNED-EXECUTION-AUTHORITY-ADDENDUM-V1.md):
  bearer credentials and separately authorized Execution/Invocation/Resource
  Use/Evidence actions; consumption of an already approved Plan.

Current `PlanRepository.create_plan` and `append_approval` are implemented by
`PostgresWorkflowControlRepository`; `append_approval` atomically writes the
decision and Plan status. Each method opens its own connection/transaction.
`PostgresBusinessProblemRepository.bind_plan` opens another transaction, checks
expected Problem aggregate version and the already-approved exact Plan, then
writes Product binding and its `BIND_PLAN_TO_PROBLEM` claim. Neither public port
accepts a shared connection. Existing Workflow Control UoW operations do not
contain a Product binding operation. Accepted general atomicity requirements
do not by themselves authorize a new cross-owner writer.

The recovered draft bypasses both owner write ports: it directly inserts into
`execution_authority.plans`, `execution_authority.plan_approval_decisions` and
`business_problem_authority.plan_bindings`, and updates Plan status. It uses
private Product `_claim`/`_complete` with newly invented command names
`PREPARE_GOVERNED_PLAN` and `DECIDE_GOVERNED_PLAN` in
`business_problem_authority.idempotency_claims`. That table has a completed
result model; it is not the Workflow Control claim state/retention model.
No owner acceptance was found for this substitution.

The draft's single transaction would roll back database writes on an exception,
but that is insufficient to establish its contract. It lacks an explicit
authorization argument, bypasses Product binding's expected-version check at
approval, and its decision replay queries request decision IDs instead of
consistently reading the stored claim identities. The prepare join does not
explicitly tie the selected Problem revision to the selected Problem. No
failure, concurrent replay or rollback tests establish this draft's correctness.
It remains unimported by application/bootstrap; do not repair and activate it
before resolving ownership.

`GovernedExecutionAuthority.require` can technically match arbitrary strings,
but the accepted execution addendum does not define new Problem, Criterion,
Criteria Set, Plan prepare/read/approve/reject action/resource semantics.
Reusable authentication does not grant these actions. No client authority
field, default identity header or test resolver can fill that gap.

## Minimum decision needed, not yet granted

1. Confirm the bounded command owner and owner-provided shared-connection ports
   for Plan preparation and atomic approval/status/Product binding. Specify
   lock/CAS validation at approval, claim owner/table and canonical command
   semantic, original-result replay, conflict and complete rollback semantics.
   Recommended candidate: each domain retains its writer; a named coordinator
   composes owner-approved ports in one PostgreSQL transaction, with no new
   persistent dependency or provider effects. Do not keep direct cross-owner SQL.
2. Confirm separate trusted owner/action/exact-resource authorization contracts
   for Product CRUD/lifecycle and Plan prepare/read/approve/reject, including
   independent review/approval authority and authorization for referenced
   resources before lookup. Reuse the bearer verifier only as authentication.

Affected components are the planned application/API/bootstrap and the UoW
adapter. Existing preview and execution consumers remain unchanged. This
candidate needs no public CRD or historical migration change, but the absence
of a migration is not evidence of owner approval. An alternative is separately
committed owner operations with an explicitly accepted incomplete/recovery
protocol; that protocol is also not currently granted and is not recommended
for this bounded task. No such protocol was introduced.

## Verification and delivery limits

An exclusive `s5-297-recovery-postgres` container (PostgreSQL 15, localhost
port 65358, database `s5_297`) was created for this recovery. Each integration
test creates and removes an `impl297_*` database. No 295 database, provider,
browser or frontend asset was reused. The container was stopped after validation
and retained; the port above records its test-time mapping.

Executed:

- New foundation suite plus existing Business Problem domain: **21 passed,
  0 skipped**. Includes denial before connection, both scope dimensions,
  explicit membership/deduplication, empty sets, stale CAS with unchanged
  aggregate, exact historical revisions/digests and repository restart.
- Focused Ruff lint and format checks for the four Product source files and
  new test passed. The UoW draft is explicitly excluded from this focused result.
- Preview/planning, governed authorization, Execution application and Workflow
  API regressions: **62 passed, 0 skipped**, one upstream TestClient deprecation
  warning. This disjoint regression run is not real HTTP/provider acceptance.
- `make check`: **failed** at lint on the preserved UoW draft (23 findings).
  The full test gate did not run; this is not a passing repository gate.
- `git diff --check`: passed.

Normal durable HTTP, Plan preparation, approval, execution consumption, provider
zero-call/replay and Evidence/Resource Use acceptance remain unproven. No
application, API, bootstrap, execution envelope or CI wiring was added on top
of the unresolved authority. No frozen HTTP contract is offered to frontend.
The old preview remains process-local. Criterion retirement, matching,
scheduler, MCP, model routing and migrations 0001–0017 are unchanged.

The same-branch PR query returned none. No commit, push, PR, CI run, Ready,
merge, deployment or Session closure is claimed at this checkpoint. All
intermediate work remains in the original branch worktree. The next dependent
step is the two bounded owner decisions above, then resume the original 297
application/API/bootstrap and real HTTP plan without a new task or branch.
