# S5-V023-IMPL-288 Governed Skill Dispatch Implementation

## Authority, gate, and scope

Session `S5-V023-IMPL-288` is a Human-authorized G1 integration on accepted base
`764dfec0e2f03eb4cc33409ca1ca56100dd88bd6` (tree
`3bd823b5cf596993cbd4ed9ede3ab0e2d285a094`). It reuses the durable Execution,
Workflow Control, Digital Employee identity, Skill Invocation, Evidence, and
Resource Use authorities. It adds the additive checksum-bound migration `0017`
for the governed HTTP request claim. It adds no scheduler, matching algorithm,
queue, retry behavior, public API, CRD, API group, frontend, or Business Outcome.
The Human-accepted decisions specific to this increment are recorded in
[`S5-V023-IMPL-288-GOVERNED-EXECUTION-AUTHORITY-ADDENDUM-V1.md`](../../architecture/s5/v0.2/S5-V023-IMPL-288-GOVERNED-EXECUTION-AUTHORITY-ADDENDUM-V1.md)
as `HUMAN_ACCEPTED / BRANCH_RECORDED / NOT_MAIN_DURABLE`. The older IMPL-276
composition addendum remains a referenced prerequisite and is not a substitute.

## Formal entry and complete normal path

```text
POST /api/internal/v0.2.3/executions
  -> server-side bearer credential resolver
  -> exact owner/action/resource authorization decisions
  -> exact APPROVED Plan and approval read
  -> exact published Workflow task/Skill operation binding
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
and input, but cannot supply a principal, authorization decision, policy, executor
identity, executor endpoint, or side-effect class. Extra fields are rejected by the
strict wire schema. The executor endpoint and revision are configured only by the
service bootstrap and must match the immutable published Skill operation.

`GOVERNED_EXECUTION_AUTHORITY_FILE` points to a server-owned
`governed-execution-auth.v1` JSON document. It contains only SHA-256 credential
digests, expiry, trusted scope and exact grants; bearer values remain external.
Missing, malformed, expired or unmatched configuration fails closed. Execution,
Skill, Resource Use and Evidence decisions remain owner-specific and are not
collapsed into one synthetic authorization identifier.

## Owners, transactions, and existing gaps

| Stage | Existing owner and entry | Transaction or effect boundary | Remaining gap |
| --- | --- | --- | --- |
| Trusted request | governed credential resolver | authentication and exact owner/action/resource decisions before protected lookup | bounded server-owned file adapter; no enterprise IAM |
| Plan/approval | Workflow Control `PostgresWorkflowControlRepository` | scoped exact read of immutable Plan and approval | no automatic matching or Plan authoring endpoint added |
| Run/Task/Attempt | Execution `ExecutionApplicationService.start` | Run, Task Run, Attempt and full HTTP semantic claim in one PostgreSQL transaction | no background scheduler or automatic task fan-out |
| Employee/Assignment | Digital Employee and execution lineage | revalidated in the Execution transaction | publication/matchability never grants execution |
| Skill dispatch | `GovernedAttemptSkillInvocationService.invoke` | request/claim/`DISPATCH_RECORDED` commit before HTTP | one managed `READ_ONLY` Skill slot only |
| Provider | `HttpReadOnlySkillExecutor` from the bootstrap allowlist | external HTTP effect after durable dispatch | localhost bounded executor only; no MCP or writes |
| Terminal facts | Skill Invocation plus Resource Use repositories | Invocation facts, redacted Evidence, Resource Use facts/measurements/snapshot commit atomically | exactly-once external effects are not claimed |
| Recovery | existing Skill `recover` under process-wide Invocation ownership and same-host supervised child lifetime | only after managed predecessor child exit is proven, its durable dispatch becomes one atomic `OUTCOME_UNKNOWN` terminal bundle; no provider call | same-host only; no cross-host coordination, durable lease, background recovery or automatic successor retry |
| Readback | exact governed Execution GET | separately authorized Execution, Invocation, Resource Use and Evidence-reference projections | Evidence content is deliberately not dereferenced |

No test helper is used by the production entry. The acceptance test uses existing
domain services to create and publish its isolated Agent, Workflow, Runtime Profile,
Skill, Employee, Instance, Assignment, and approved Plan. That preparation is test
resource provisioning, not a new user-facing matching or Plan-authoring route. In
particular, Workflow preparation injects a test reference resolver around the
production domain service and PostgreSQL repository. The ordinary Workflow API
cannot yet publish this Skill reference path end to end. Its resolver/authoring
completion remains an M2 required OPEN item. This increment proves only execution
and authorized readback for an already existing legal exact approved Plan.

## HTTP contract

`POST /api/internal/v0.2.3/executions` accepts exact `planId`, `planVersion`,
`planDigest`, `approvalId`, `assignmentId`, `digitalEmployeeInstanceId`, `taskId`,
`skillId`, `skillRevisionId`, `skillDigest`, `operation`, `idempotencyKey`, and a
bounded JSON `input`. First creation returns `201`; same-payload replay returns
`200` with the same Run, Task Run, Attempt, Invocation, Evidence, and Resource Use
identities and makes no second provider call.

The request is executable only when the exact published Workflow revision task
contains a `skillOperationBindings` member for the submitted Skill revision,
digest and operation. Existing published revisions are not changed or backfilled;
the binding becomes effective only through a newly authored revision (normally a
successor), its new digest, Human review/publication, and a new approved Plan.

`GET /api/internal/v0.2.3/executions/{workflowRunId}/attempts/{attemptId}/skill-invocations/{invocationId}`
returns exact execution and Invocation identities, exact Plan/approval/Employee/
Skill/binding/executor references, technical state and fact high-water, Evidence ID,
and, when all Evidence references are authorized, the immutable Resource Use
snapshot ID/digest/high-water. Evidence references require independent exact
authorization. A restricted projection returns no restricted Evidence ID, digest,
or count, marks itself `FILTERED`, and omits the immutable snapshot identity so it
cannot masquerade as the complete snapshot. It returns no Evidence body and creates
no Business Outcome. An
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

Execution and Invocation identities derive from the scoped principal/idempotency
key and exact durable bindings. The Execution-owned request claim digests the
complete HTTP semantic payload, including an input digest, and is created with the
Run/Task Run/Attempt in one transaction. Claim insertion failure rolls back every
identity. An existing identity without its claim is rejected rather than backfilled.
Concurrent starts converge on one Run/Task Run/Attempt and one Invocation dispatch.
Dispatch preparation commits before the provider request. One process-wide,
database-scoped Invocation ownership registry serializes an active synchronous call
across multiple application/composition instances without creating a durable lease
or new scheduling authority. Application close does not remove another active
owner, so a concurrent replay cannot recover an active call.
If validation fails before dispatch, provider call count is zero. Timeout or
transport ambiguity commits `OUTCOME_UNKNOWN`; replay and process restart return the
same terminal unknown record and never redispatch. After supervisor-confirmed child
exit, the formal entry detects an existing non-terminal durable dispatch and calls
the existing Skill recovery operation. Recovery atomically appends the Invocation,
Evidence and Resource Use `OUTCOME_UNKNOWN` terminal bundle without calling the
provider. If that commit fails, the request fails and the durable state remains
`DISPATCH_RECORDED`; the entry does not claim that unknown was saved and still does
not redispatch. Platform child exit does not prove that the external provider
stopped. This HTTP entry does not automatically create a successor Attempt. Any retry
remains a separately authorized Workflow Control operation and must create a
successor Attempt/Invocation.

## Supervised startup and failure boundary

The only supported startup for this governed entry is:

```text
uv run python -m agent_console.governed_execution_supervisor --port <port>
```

The existing server-owned database, authority and executor environment variables
remain required. The supervisor fixes one worker and uses a non-selectable
host-local state root keyed by a credential-free normalized execution-database
fingerprint. It passes an inherited locked descriptor and a one-way lifetime pipe
to the child. The bootstrap validates those descriptors, the lock inode, a random
handshake token and the actual parent PID. Direct Uvicorn startup, HTTP headers and
request fields cannot enable governed execution; other Console routes continue to
start normally.

Database session loss cannot release the host lock. If the supervisor dies, its
child revokes new governed entry access on pipe EOF but keeps the inherited lock; a
replacement supervisor therefore cannot start until that exact child has exited.
The replacement checks the prior lock device/inode and fails closed on replaced or
malformed identity state. PID absence, heartbeat expiry, port vacancy and PostgreSQL
advisory lock acquisition are not used as exit evidence.

This is a same-host constraint. Independent state on another host cannot be
coordinated by this implementation, so cross-host takeover remains unsupported and
must not be enabled without a future accepted coordination or provider-fencing
design.

## Workflow edit compatibility correction

Draft edit now compares retained tasks by `taskId` with the prior draft before any
write. If a prior task has non-empty `skillOperationBindings`, omitting the field or
sending `null` returns `SKILL_OPERATION_BINDING_PRESERVATION_REQUIRED`; revision and
aggregate version remain unchanged. Explicit values continue through the existing
binding validation. Optional reference digests allow a formal GET response to be
submitted back through an unrelated edit. Historical unbound content remains
unchanged and its old digest is never recalculated.

## Acceptance and CI

`0017_governed_execution_claim.sql` is additive and has its own
`governed_execution.schema_migrations` ledger entry, exact SHA-256 checksum and
adapter identity. Bootstrap rejects a checksum/adapter mismatch and any newer
governed-execution schema version. Existing migration ledgers are not rewritten.

`test_governed_execution_api_postgres.py` uses the FastAPI production composition,
a dedicated PostgreSQL 15 database, and a real local HTTP protocol server. It proves
the normal start/dispatch/read path, trusted-boundary rejection, prevention of
client-minted authority or endpoint selection, cross-scope nondisclosure, exact
digest and input-schema rejection with zero additional calls, Evidence/Resource Use
linkage, restricted Evidence-reference projection, full-payload mismatch, atomic
claim rollback, refusal to backfill an unclaimed existing execution, same-request
replay, concurrent single dispatch, active-call ownership, safe continuation after
Execution commit but before Skill preparation, pre-provider crash recovery, recovery
persistence failure, timeout/restart unknown, process loss after provider return but
before terminal commit, non-disclosing wrong-parent reads, ordinary unsupervised
startup denial, same-process dual-application ownership, overlapping supervisor
denial, supervisor-loss fail-closed behavior, database-session loss during an active
provider call, confirmed-child-exit recovery and Workflow binding-preserving edit
round trips without redispatch.

The existing `PostgreSQL Skill Invocation` CI job now selects this test together
with the Skill domain, Skill PostgreSQL/protocol, Workflow API and Workflow service
tests. Its existing skip-fail guard is retained, so this selected capability cannot
pass by skipping. All other workflow checks remain unchanged.

The preceding recovery candidate completed its 30-case exact selection. This
supervised correction expands the existing isolated CI selection to 49 cases: 17
governed HTTP/PostgreSQL/protocol cases, 16 existing Skill PostgreSQL/protocol
cases, 2 Skill domain cases, and 14 Workflow API/service cases. The correction
checkpoint is based on source
`58a24dea96276c3b469dfa0e764dbc78c2adabcf`; its 49-case selection passed against
retained task-owned PostgreSQL with no skip. The
new governed cases use actual supervisor and Uvicorn child processes, actual
process exit, real PostgreSQL session termination and the real local HTTP provider.
After the controlled main merge, the same 49-case selection passed again with no
skip. Repository-wide `make check` passed with Ruff, 362-file formatting and
`1544 passed / 103 environment-dependent skipped`; those skips are not real-service
evidence. Frontend lint and production build also passed after installing the exact
lockfile dependencies. A fresh-database candidate CI run is still required. Earlier
focused evidence remains historical and is not substituted for the new supervised
recovery-window acceptance.

Checkpoint assets are the retained `s5-v023-impl-288-postgres` and
`s5-v023-impl-288-qdrant` containers. Test supervisor/child processes were stopped;
the fixed host-local supervisor status records a confirmed child exit. Checkpoint
`87f07c2cfc1c386aec6e6fab9e0874ad8c135094` was merged with still-exact durable
main `0b62d649bc587f4bde0a3ffaa1acda5fc8666014` by ordinary `--no-ff` merge
`6fec8c0542a97d66691b9a920fa326114d9921e6`. Its parents are the checkpoint and
durable main in that order. The unique next step is non-force push, Draft PR update
and exact-source CI observation.

## Explicit limitations

Still absent and not claimed: end-to-end ordinary Workflow API Skill-reference
authoring/resolution, automatic Plan/resource matching, a general scheduler or queue,
background recovery/dispatch, automatic retry, successor retry HTTP,
MCP dispatch, write-capable Skills, multiple Skill slots, arbitrary remote executor
URLs, frontend/Runtime Operations UI, Kubernetes Runtime placement, OpenClaw,
M2/P1 resource orchestration breadth, enterprise IAM, HA, cross-host recovery
coordination, exactly-once external effects, certification, deployment, release
readiness, or production readiness.
