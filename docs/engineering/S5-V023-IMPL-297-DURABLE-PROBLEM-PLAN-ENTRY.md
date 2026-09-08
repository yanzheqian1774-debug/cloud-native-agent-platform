# S5-V023-IMPL-297 — Durable Business Problem and governed Plan entry

This increment connects normal HTTP to the existing Product Problem/Criteria
owner, Workflow Control Plan/approval owner and governed Execution consumer.
It uses explicit resource identities and deterministic preparation, not matching.
The original PARTIAL_DRAFT recovery and 21/62 test results remain recorded in the
[historical checkpoint](S5-V023-IMPL-297-RECOVERY-CHECKPOINT.md). Implementation
continued only after the subsequent
[Human owner/authorization decision](../../architecture/s5/v0.2/S5-V023-IMPL-297-OWNER-AUTHORIZATION-ADDENDUM-V1.md).
This document does not grant Ready, merge, deployment or Session closure.

## HTTP contract for subsequent business frontend work

All paths below have prefix `/api/internal/v0.2.3`. Requests authenticate through
`Authorization: Bearer …`, using `GOVERNED_EXECUTION_AUTHORITY_FILE`. Missing or
invalid credentials fail closed; identity/scope headers cannot authorize this
entry. Trusted configuration is read for every Product/Plan request so revoked
grants also deny replay. The unchanged Execution entry loads its policy through
its existing supervised bootstrap.

| Method/path | Request | Result |
| --- | --- | --- |
| POST `/business-problems` | title, description, ownerId, idempotencyKey | `revision` with exact identity/digest |
| GET `/business-problems` | none | scoped `problems` (latest revision per Problem) |
| GET `/business-problems/{id}` | none | `problem` aggregate, immutable `revisions`, `lifecycle` |
| POST `/business-problems/{id}/revisions` | predecessorRevisionId, expectedVersion, title, description, ownerId, idempotencyKey | original or new immutable `revision` |
| POST `/business-problems/{id}/lifecycle` | toState, expectedVersion, idempotencyKey | businessProblemId, aggregateVersion |
| POST `/success-criteria` | criterionType, measurement, requiredEvidenceKinds, evaluatorType/version, applicability, idempotencyKey | immutable `revision` |
| POST `/success-criteria` (revision) | preceding fields plus successCriterionId, predecessorRevisionId, expectedVersion | successor `revision` |
| GET `/success-criteria/revisions/{revisionId}` | none | exact `revision` |
| POST `/business-problems/{id}/criteria-sets` | problemRevisionId, orderedCriterionRevisionIds, expectedVersion, idempotencyKey, optional predecessorSetRevisionId | exact ordered set `revision` |
| GET `/business-problems/{id}/criteria-sets` | none | all immutable set `revisions` |
| GET `/business-problems/{id}/criteria` | none | deduplicated criterion revisions explicitly used by that Problem's sets |
| POST `/business-problems/{id}/plans` | exact preparation request below | Plan, state, envelope, approvals, replayed |
| GET `/plans/{id}?version=1` | explicit version | exact Plan readback |
| POST `/plans/{id}/approvals` | preparation assertions plus exact decision request below | Plan and immutable approval decision |

Product value objects inside `revision`, `problem`, `revisions`, `lifecycle` and
`approvals` preserve their typed domain snake_case fields, including
`business_problem_id`, `revision_id`, `revision`, `digest`, `aggregate_version`,
`current_state`, `current_revision_id`, `set_revision_id` and
`ordered_criterion_revision_ids`. Command DTO fields and top-level Plan fields
are camelCase. Unknown fields (including client authority/approval assertions)
are rejected. `ownerId` is Product ownership metadata, never credential identity.

Preparation requires all of:

```json
{
  "problemRevisionId": "exact-problem-revision",
  "problemRevisionDigest": "<64 hex>",
  "criteriaSetRevisionId": "exact-set-revision",
  "criteriaSetDigest": "<64 hex>",
  "expectedProblemVersion": 3,
  "workflowDefinitionId": "exact-workflow",
  "workflowDefinitionRevisionId": "exact-workflow-revision",
  "workflowDefinitionDigest": "<SHA-256>",
  "employeeDefinitionId": "exact-employee",
  "employeeDefinitionRevisionId": "exact-employee-revision",
  "employeeDefinitionDigest": "<64 hex>",
  "digitalEmployeeInstanceId": "exact-instance",
  "assignmentId": "exact-assignment",
  "idempotencyKey": "prepare-request-1"
}
```

Workflow SHA-256 accepts prefixed or compact encoding and normalizes it before
claim/envelope construction. The response identifies `planId`, `planVersion`,
`planDigest`, `aggregateVersion`, `status`, `content`, `approvals`, `replayed`.
Preparation produces `PENDING_APPROVAL` with zero decisions. Its envelope reserves
an approval identity for exact downstream compatibility; reservation is not an
approval fact or execution permission.

Approval resubmits the exact preparation assertions with a separate
`idempotencyKey`, and adds `planVersion`, `planDigest`, `expectedVersion`,
`decision` (`APPROVE` or `REJECT`) and `reasonCategory` (BUSINESS/POLICY
APPROVAL/REJECTION). Both decisions use independently granted PLAN/APPROVE.
No automatic two-person rule is added, and a creator has no implicit APPROVE.
A changed Problem/set/criterion, stale expected version or invalidated referenced
resource is rejected. New semantic work needs a new preparation command; historical
Plan bytes and approval decisions are never rewritten.

Errors use `{"detail":{"reasonCode":"…"}}`: 401 invalid/missing credential;
404 uniform non-disclosing denied/missing object; 409 stale identity, lifecycle,
CAS or idempotency conflict; 422 DTO validation; 503 unavailable authority/storage.
DTO errors retain FastAPI's standard validation detail array. Product writes
return 200 with owner readback; Plan preparation/approval return 201 for new
results and 200 for replay. Replay preserves exact result identities; current
Plan status/approval projection may have advanced after preparation.

## Exact grants

Matching is literal owner/action/resource equality within the credential's
trusted tenant/security domain. No old wildcard, START grant or default identity
header is expanded. List authorization covers the explicit scoped collection;
no cross-scope row, count or join is returned.

| Owner | Actions | Exact resource |
| --- | --- | --- |
| BUSINESS_PROBLEM | CREATE, LIST, READ (create-result readback) | `business-problem:collection` |
| BUSINESS_PROBLEM | READ, REVISE, TRANSITION | `business-problem:{id}` |
| SUCCESS_CRITERION | CREATE, READ (create-result readback) | `success-criterion:collection` |
| SUCCESS_CRITERION | REVISE, READ (revision-result readback) | `success-criterion:{id}` |
| SUCCESS_CRITERION | READ | `success-criterion:revision:{revisionId}` |
| SUCCESS_CRITERIA_SET | CREATE, READ, REVISE | `success-criteria-set:{problemId}` |
| PLAN | PREPARE | `plan:prepare:{problemId}` |
| PLAN | READ (prepare-result/replay readback) | `plan:prepared:{problemId}` |
| PLAN | READ, APPROVE | `plan:{id}:{version}` |
| WORKFLOW | READ | `workflow:{id}:{revisionId}` |
| EMPLOYEE | READ | `employee:{id}:{revisionId}` |
| INSTANCE | READ | `instance:{id}` |
| ASSIGNMENT | READ | `assignment:{id}` |

Mutations also require their readback grant. Plan actions require independent
Problem/set and exact referenced-resource read grants before lookup; criterion
membership may be discovered only under the set read grant and each member is
separately authorized before dereference. Plan reads disclose the approved
identity envelope, not Evidence content or Evidence-reference authority.

## Owners, transactions and replay

`BusinessProblemApplication` uses `PostgresProblemPlanUnitOfWork.transaction`.
The UoW begins/commits/rolls back; all SQL remains in domain adapters. The same
connection is passed to Workflow Control prepare/approval/claim ports, Product
binding/validation ports, and lock-protected Workflow/Employee/Instance/Assignment
reads. The bootstrap uses the same existing execution database for these owners.

Preparation atomically writes a pending Plan, its exact Product association and
completed claims. The existing `plan_bindings` table stores that immutable
association, with authority determined by the joined Plan state. Approval locks
and revalidates the association and Product expected version/current revisions,
appends the owner decision, advances Plan status and completes its claim in one
transaction. Rollback leaves neither success claim nor partial valid result.

Workflow Control owns `PLAN_ENTRY_PREPARE_V1` and `PLAN_ENTRY_APPROVE_V1` in its
existing `execution_authority.idempotency_claims` table (0009/0010), not the
Execution dispatch claim. Product owns `PLAN_ENTRY_BIND_PREPARED_V1` and its
existing create/revision/lifecycle namespaces in
`business_problem_authority.idempotency_claims` (0013). Owner transaction-scoped
advisory locks serialize identical scope/actor/command/key requests. A completed
claim and domain writes commit together; there is no separately committed
IN_PROGRESS record. Result records contain exact identities, not request bodies
or credentials. SHA-256 covers normalized full command semantics and target,
including expected versions and all explicit resource assertions. Claims are
retained without introducing a new cleanup policy.

Current authorization is required on replay. Different payload conflicts even
when a key was already completed. Planning replay never dispatches a provider;
Execution retains its independent request claim, supervised ownership and
UNKNOWN/no-redispatch recovery behavior.

## Execution and compatibility

New Plans use explicit `employee-execution-plan.v2` with immutable preparation
metadata. Execution reconstructs its exact bytes and asks Product's owner port
to verify the persisted exact binding, in addition to its existing exact Plan,
approval, Employee/Assignment, Skill and policy checks. Original v1 encoding and
consumers remain supported; no historical content is backfilled. The execution
supervisor, provider protocol and deployment topology are unchanged.

`/v0.2.1/problems` remains process-local preview. No preview record or candidate
approval becomes durable authority. Problem/Criteria persistence is not Session
or message persistence. Criterion retirement is not represented by the current
schema and is not fabricated. Lifecycle transitions are explicit Product actions;
technical success does not resolve a Problem. No frontend, matching, scheduler,
MCP execution, model routing, automatic retry or Business Outcome was added.
Migrations 0001–0017 are unchanged; no new migration or table was introduced.

## Validation record

The historical recovery's 21/62 results retain their original partial scope.
Final validation results and commit/CI evidence are recorded below after execution.
The 297 exclusive PostgreSQL container is `s5-297-recovery-postgres`; test runs
use isolated `impl297_http_*`, `impl297_*` and legacy regression databases.
All new HTTP scenario business facts, including Agent/Skill/Runtime/Workflow,
Employee/Instance/Assignment and Problem/Plan/approval, are authored via normal
production APIs. Test SQL provisions databases/applies migrations or reads counts;
it does not insert business facts. Failure injection calls actual owner adapters
on real PostgreSQL, without replacing credential or resource resolvers.

A separate CI job preserves existing jobs and uses an isolated PostgreSQL service,
source/checkout identity reporting and a selected-suite zero-skip guard. Local
cold-start readiness waits up to 60 seconds for the real supervisor HTTP health
endpoint; timeout remains a failure. Initial 15-second inherited helper timeouts
were environment failures, not passed acceptance.

## Changed paths

- `.github/workflows/employee-identity.yml`
- `architecture/s5/v0.2/S5-V023-IMPL-297-OWNER-AUTHORIZATION-ADDENDUM-V1.md`
- `console/backend/src/agent_console/app.py`
- `console/backend/src/agent_console/business_plan_postgres.py`
- `console/backend/src/agent_console/business_problem_api.py`
- `console/backend/src/agent_console/business_problem_application.py`
- `console/backend/src/agent_console/business_problem_authorization.py`
- `console/backend/src/agent_console/business_problem_bootstrap.py`
- `console/backend/src/agent_console/business_problem_domain.py`
- `console/backend/src/agent_console/business_problem_postgres.py`
- `console/backend/src/agent_console/business_problem_repository.py`
- `console/backend/src/agent_console/business_problem_schemas.py`
- `console/backend/src/agent_console/digital_employee_definition_postgres.py`
- `console/backend/src/agent_console/digital_employee_postgres.py`
- `console/backend/src/agent_console/execution_application.py`
- `console/backend/src/agent_console/execution_lineage.py`
- `console/backend/src/agent_console/governed_execution.py`
- `console/backend/src/agent_console/workflow_control_postgres.py`
- `console/backend/src/agent_console/workflow_control_repository.py`
- `console/backend/src/agent_console/workflow_definition_postgres.py`
- `console/backend/tests/test_business_problem_api_postgres.py`
- `console/backend/tests/test_business_problem_entry_foundation.py`
- `docs/engineering/S5-V023-IMPL-297-DURABLE-PROBLEM-PLAN-ENTRY.md`
- `docs/engineering/S5-V023-IMPL-297-RECOVERY-CHECKPOINT.md`

## Local validation outcome before publication

- Isolated Product/Plan HTTP, foundation, domain and legacy Product repository
  selection: **28 passed, 0 skipped** (323.25 seconds). This run's collection
  preceded the additional foreign-revision lookup unit test.
- Added foreign-revision denial-before-lookup test: **1 passed** (0.30 seconds).
- Execution/Employee/Workflow Control PostgreSQL compatibility selection:
  **41 passed, 0 skipped** (38.15 seconds), in separate `s5_297_compat` database.
- Final `make check`: **1556 passed, 110 skipped**, one upstream TestClient
  deprecation warning (24.83 seconds); Ruff lint and all 374 format checks passed.
  Environment skips are not real-service acceptance and are not added to the
  PostgreSQL evidence. Overlapping selections are not summed.
- `git diff --check` and fixed-base protected-path checks passed. No frontend,
  migrations 0001–0017, supervision or provider protocol changes.

The final CI selection includes the additional lookup test and retains its zero-skip
guard. Source/tree, Draft PR and CI run/attempt/event/actual checkout evidence are
reported in the delivery response and PR rather than rewriting this record after
its own commit. Session stays open for Human pre-merge review.
