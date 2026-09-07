# S5-V023-IMPL-288 Governed Skill Dispatch Implementation

## Authority, gate, and scope

Session `S5-V023-IMPL-288` is a Human-authorized G1 integration on accepted base
`764dfec0e2f03eb4cc33409ca1ca56100dd88bd6` (tree
`3bd823b5cf596993cbd4ed9ede3ab0e2d285a094`). It reuses the durable Execution,
Workflow Control, Digital Employee identity, Skill Invocation, Evidence, and
Resource Use authorities. It adds no migration, scheduler, matching algorithm,
queue, retry behavior, public API, CRD, API group, frontend, or Business Outcome.

## Formal entry and complete normal path

```text
POST /api/internal/v0.2.3/executions
  -> trusted internal principal and scope dependency
  -> server-minted scoped authorization decision
  -> exact APPROVED Plan and approval read
  -> exact Assignment and Digital Employee Instance validation
  -> ExecutionApplicationService.start
  -> Workflow Run / Task Run / Attempt and execution binding transaction
  -> exact published Employee Skill member and operation resolution
  -> compose_governed_skill_invocation dependencies
  -> durable Invocation and Resource Use dispatch preparation
  -> allowlisted HttpReadOnlySkillExecutor
  -> terminal Invocation Evidence and Resource Use snapshot transaction
  -> authorized exact GET read
```

Publication is not matching, matching is not execution authorization, and neither
is treated as an execution decision. The entry accepts only an already approved,
exactly identified Plan. It does not select a Plan, Assignment, Employee, Skill, or
operation by implicit latest. The caller supplies exact identity/digest assertions
and input, but cannot supply an authorization decision, policy, executor identity,
executor endpoint, or side-effect class. Extra fields are rejected by the strict
wire schema. The executor endpoint and revision are configured only by the service
bootstrap and must match the immutable published Skill operation.

## Owners, transactions, and existing gaps

| Stage | Existing owner and entry | Transaction or effect boundary | Remaining gap |
| --- | --- | --- | --- |
| Trusted request | internal FastAPI dependency | no protected lookup before principal/scope | relies on the existing trusted internal-header boundary; no enterprise IAM |
| Plan/approval | Workflow Control `PostgresWorkflowControlRepository` | scoped exact read of immutable Plan and approval | no automatic matching or Plan authoring endpoint added |
| Run/Task/Attempt | Execution `ExecutionApplicationService.start` | existing PostgreSQL lineage/idempotency transaction | no background scheduler or automatic task fan-out |
| Employee/Assignment | Digital Employee and execution lineage | revalidated in the Execution transaction | publication/matchability never grants execution |
| Skill dispatch | `GovernedAttemptSkillInvocationService.invoke` | request/claim/`DISPATCH_RECORDED` commit before HTTP | one managed `READ_ONLY` Skill slot only |
| Provider | `HttpReadOnlySkillExecutor` from the bootstrap allowlist | external HTTP effect after durable dispatch | localhost bounded executor only; no MCP or writes |
| Terminal facts | Skill Invocation plus Resource Use repositories | Invocation facts, redacted Evidence, Resource Use facts/measurements/snapshot commit atomically | exactly-once external effects are not claimed |
| Readback | exact governed Execution GET | Execution, Invocation, and separately authorized Resource Use reads | Evidence content is deliberately not dereferenced |

No test helper is used by the production entry. The acceptance test uses existing
domain services to create and publish its isolated Agent, Workflow, Runtime Profile,
Skill, Employee, Instance, Assignment, and approved Plan. That preparation is test
resource provisioning, not a new user-facing matching or Plan-authoring route.

## HTTP contract

`POST /api/internal/v0.2.3/executions` accepts exact `planId`, `planVersion`,
`planDigest`, `approvalId`, `assignmentId`, `digitalEmployeeInstanceId`, `taskId`,
`skillId`, `skillRevisionId`, `skillDigest`, `operation`, `idempotencyKey`, and a
bounded JSON `input`. First creation returns `201`; same-payload replay returns
`200` with the same Run, Task Run, Attempt, Invocation, Evidence, and Resource Use
identities and makes no second provider call.

`GET /api/internal/v0.2.3/executions/{workflowRunId}/attempts/{attemptId}/skill-invocations/{invocationId}`
returns exact execution and Invocation identities, exact Plan/approval/Employee/
Skill/binding/executor references, technical state and fact high-water, Evidence ID,
and immutable Resource Use snapshot ID/digest/high-water, measurements, limitations,
and conflicts. It returns no Evidence body and creates no Business Outcome. An
authorized Attempt with no Invocation can report `NOT_INVOKED`; `DISPATCH_RECORDED`
is in progress and has no known result; timeout/disconnect is `OUTCOME_UNKNOWN`;
terminal technical states remain separate from business success.

Stable HTTP mapping is:

- `401 AUTHENTICATION_REQUIRED` for a missing trusted principal;
- `403 TRUSTED_SCOPE_REQUIRED` for an incomplete trusted scope;
- nondisclosing `404 GOVERNED_EXECUTION_NOT_FOUND` for denial, cross-scope, or
  protected absence;
- `422` for strict request or bounded input/schema violations;
- `409` for exact Plan, approval, Employee, Skill, binding, executor, policy,
  digest, replay, slot, or CAS conflicts;
- `503 GOVERNED_EXECUTION_STORAGE_UNAVAILABLE` for bootstrap/storage/schema
  unavailability.

## Failure and recovery semantics

Execution and Invocation identities derive from the scoped idempotency key and
exact durable bindings. Concurrent starts converge on one Run/Task Run/Attempt and
one Invocation dispatch. Dispatch preparation commits before the provider request.
If validation fails before dispatch, provider call count is zero. Timeout or
transport ambiguity commits `OUTCOME_UNKNOWN`; replay and process restart return the
same terminal unknown record and never redispatch. A crash or terminal-commit failure
after durable dispatch leaves `DISPATCH_RECORDED`; existing explicit Skill recovery
may mark the original Invocation unknown, but this HTTP entry neither retries nor
automatically creates a successor Attempt. Any retry remains a separately authorized
Workflow Control operation and must create a successor Attempt/Invocation.

## Acceptance and CI

`test_governed_execution_api_postgres.py` uses the FastAPI production composition,
a dedicated PostgreSQL 15 database, and a real local HTTP protocol server. It proves
the normal start/dispatch/read path, trusted-boundary rejection, prevention of
client-minted authority or endpoint selection, cross-scope nondisclosure, exact
digest and input-schema rejection with zero additional calls, Evidence/Resource Use
linkage, same-request replay, concurrent single dispatch, and timeout/restart unknown
without redispatch.

The existing `PostgreSQL Skill Invocation` CI job now selects this test together
with the Skill domain and PostgreSQL/protocol tests. Its existing skip-fail guard is
retained, so this selected capability cannot pass by skipping. All other workflow
checks remain unchanged.

Local validation on the task-owned PostgreSQL and Qdrant services completed with
`21 passed / 0 skipped` for the exact governed Skill CI selection and
`84 passed / 0 skipped` for the existing identity, Knowledge, and Resource Use CI
selection. `make check` completed with `1529 passed / 90 environment-dependent
skipped`; pre-commit, Ruff, and the 358-file format check passed. The only emitted
warning was the repository's existing Starlette `TestClient` deprecation warning.

## Explicit limitations

Still absent and not claimed: automatic Plan/resource matching, a general scheduler
or queue, background dispatch, automatic recovery/retry, successor retry HTTP,
MCP dispatch, write-capable Skills, multiple Skill slots, arbitrary remote executor
URLs, frontend/Runtime Operations UI, Kubernetes Runtime placement, OpenClaw,
M2/P1 resource orchestration breadth, enterprise IAM, HA, exactly-once external
effects, certification, deployment, release readiness, or production readiness.
