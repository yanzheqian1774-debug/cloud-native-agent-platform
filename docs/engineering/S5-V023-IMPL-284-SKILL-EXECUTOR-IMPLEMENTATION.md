# S5-V023-IMPL-284 Skill Executor Implementation

## Authority and baseline

- Task: `S5-V023-IMPL-284`; gate: `G1`; scope: internal backend `READ_ONLY`
  Skill Attempt invocation only.
- Accepted base: commit `bcdbcd9dc4bd21500863f9e3ebc2c2b806569a8e`, tree
  `c53e789f7518d3e0690e881a351449fa211a4845`.
- Branch: `codex/s5-v023-impl-284-readonly-skill-executor` in the isolated `af43`
  worktree.
- Governing decisions: `S5-V023-ARCH-263`, `S5-V023-ARCH-266`, and, only if an
  MCP adapter is used, `S5-V023-ARCH-259`. This implementation uses no MCP adapter.
- Active `S5-V023-IMPL-281` owns `.github/workflows/employee-identity.yml` and
  `core/tests/test_compatibility.py`; those paths remain untouched until its ownership
  ends or a controlled integration supplies the CI extension.

## One-time exact reuse map

| Object | Owner | Source authority | Exact identity | Normal call/read entry | Current availability | IMPL-284 wiring |
| --- | --- | --- | --- | --- | --- | --- |
| Approved Plan and approval | Workflow Control / Execution | ARCH-208; migrations 0009/0011 | scope + `plan_id` + positive `plan_version` + `plan_digest`; approval row with `APPROVE` and same digest | `PostgresWorkflowControlRepository` / `execution_authority.plans` and `plan_approval_decisions` | Durable PostgreSQL current state and append-only decision | Validate exact approved row before claim; never resolve latest |
| Workflow Run / Task Run / Attempt | Execution | ARCH-019/ARCH-208; migration 0008 | scope + `workflow_run_id` + `task_run_id` + `attempt_id`; exact FK chain and Attempt digest | `PostgresExecutionAuthorityRepository`; `execution_authority.workflow_runs`, `task_runs`, `attempts` | Durable PostgreSQL | Validate the full same-scope lineage inside invocation authority transaction |
| Employee Definition / Instance / Assignment | Digital Employee plus Execution | durable identity chain; migrations 0014/0008 | exact definition/revision/digest, instance ID, assignment ID and execution binding for Attempt | `DigitalEmployeeApplicationService`, `PostgresDigitalEmployeeDefinitionRepository`, `PostgresExecutionAuthorityRepository` | Durable PostgreSQL | Verify assignment-to-instance and Attempt execution binding, including plan digest, approval and authorization decision |
| Skill revision / operation / I/O schemas | Skill lifecycle | ARCH-263 plus existing Skill lifecycle; migrations 0002/0004 | scope + Skill definition ID + exact published revision ID/digest + named operation; schemas embedded in that revision content | `SkillMcpService` / `PostgresSkillMcpRepository` and `skill_mcp_resource.resources` | Durable lifecycle record; existing bounded invocation is test-only echo and is not reused as execution proof | Read the exact published immutable revision after authorization; validate operation and exact input/output schema digests |
| Skill Binding | Skill/Agent composition | ARCH-263 and existing binding facts | exact `binding_id` + binding digest + Skill revision/digest + Attempt/Plan/Employee snapshot | governed binding rows/records | Agent and Skill/MCP binding foundations exist; no Attempt Skill execution binding exists | Persist an immutable invocation binding snapshot; reject stale/mismatched bindings |
| Executor revision | Execution adapter boundary | ARCH-263 | allowlisted `executor_id` + immutable `executor_revision` + configuration digest | injected executor registry | No governed Skill executor exists | Add replaceable registry and bounded HTTP `READ_ONLY` adapter; no request-supplied URL or script |
| Authorization decision and side-effect policy | Execution/Governance | ARCH-263 | exact decision ID plus versioned policy ID/revision/digest and `READ_ONLY` classification | authorization port invoked before repository lookup | Resource Use has authorization-first application behavior; no Skill policy record | Add authorization/policy ports and persist exact decisions before dispatch; unknown/write classes fail closed |
| Invocation Evidence | Execution | ARCH-263 and Evidence boundary | scope + immutable Evidence ID/digest linked to invocation and exact snapshot | invocation repository atomic terminal commit | Existing Evidence implementations are domain-specific | Add bounded/redacted Skill Evidence rows in the invocation authority transaction; no raw request/response or secrets |
| Resource Use UoW | Execution | ARCH-266; migration 0015 | deterministic `resource_use_id` for Attempt + `SKILL` + slot + ordinal 1; facts, measurements, evidence, claim, snapshot/high-water | `ResourceUseApplicationService` / `PostgresResourceUseRepository` | Durable PostgreSQL authority implemented by IMPL-282 | Reuse its tables and reducer semantics; atomically write terminal Skill fact, measurements, Evidence link, claim and Resource Use snapshot in the same database transaction |

The canonical invocation read model is backend-owned and authorization-gated. Its
product and technical projections are derived from one persisted snapshot; neither
projection may infer business success from technical Skill success.

## G1 implementation plan

1. Add migration 0016 with immutable typed invocation, fact, claim, Evidence, and
   current-projection tables. Preserve migrations 0001-0015.
2. Add typed domain records for exact execution snapshot, versioned I/O limits,
   side-effect policy, append-only facts, terminal states, redacted Evidence, and
   canonical product/technical read projections.
3. Add repository and PostgreSQL adapter. The begin transaction authoritatively
   validates Plan approval, Run/Task/Attempt, Assignment/Employee binding, exact
   published Skill revision/operation/schema, binding/executor/policy decisions,
   slot cardinality, and idempotency. It commits `DISPATCH_RECORDED` before returning
   authority to call the provider.
4. Add the governed Attempt application service and an allowlisted HTTP executor.
   Authorization and policy evaluation precede any protected lookup or dispatch.
   Enforce byte/depth/property/time limits by named fields, validate JSON schemas,
   and redact bounded summaries. A timeout/disconnect becomes `OUTCOME_UNKNOWN` and
   is never automatically redispatched.
5. Commit terminal Invocation facts, bounded Skill Evidence, Resource Use fact and
   measurements, claim/high-water and both canonical snapshots atomically in one
   PostgreSQL transaction. Missing measurements remain null with their explicit
   availability state.
6. Add focused domain, security, protocol, concurrency, rollback/recovery, restart,
   immutability and regression tests. A deterministic local HTTP read-only service
   provides real boundary evidence and counts actual requests.
7. Run focused tests, PostgreSQL/protocol acceptance, then `make check`; inspect
   status/diff. CI workflow extension remains an integration checkpoint while 281
   owns that path.

## Compatibility and risks

- Additive internal backend modules and migration only; no CRD, API group, public
  HTTP/frontend, lifecycle, or frozen-contract change.
- Exactly-once external effects are not claimed. Durable dispatch identity prevents
  replay; ambiguous post-dispatch results remain `OUTCOME_UNKNOWN`.
- P1 supports one deterministic managed Skill slot per Attempt and `READ_ONLY` only.
- The protocol service is test support; production behavior is the formal injected
  HTTP adapter and allowlisted executor registry.

## Checkpoint

- Completed: authority read, baseline/branch/session uniqueness, active-path check,
  reuse map, G1 plan, migration 0016, typed domain/application/repository/composition,
  PostgreSQL adapter, live HTTP executor, canonical read model, atomic Skill
  Evidence/Resource Use terminal UoW, focused tests and local quality gate.
- Pending: commit/push, Draft PR, and PR CI. The isolated CI workflow addition is
  intentionally deferred because active IMPL-281 still owns that exact file.
- Migration 0016 SHA-256:
  `2c1a6c663ce607705c7d6c3cca9ff21feec6a1bb513831cebc740b0732bdb657`.
- Local evidence: focused live PostgreSQL/protocol and affected regression gate
  `58 passed / 0 skipped`; `make check` passed with `1507 passed / 86 environment
  skipped`, Ruff clean, and all 353 Python files formatted.
- Task-owned external resource used during validation:
  `s5-v023-impl-284-postgres`, accepted pinned image
  `postgres@sha256:bfee8fabec7c662311eff39111a890f68a46a78a3b35e91353e185e7d5918517`,
  isolated database `skill_invocation_284` and ephemeral localhost port. The
  container and database were removed after final local validation; no IMPL-284
  protocol process or container remains active.

## Implemented application and recovery call chain

```text
future governed Attempt scheduler (OPEN)
  -> compose_governed_skill_invocation(...)
  -> GovernedAttemptSkillInvocationService.invoke(request, input)
  -> scoped authorization -> versioned READ_ONLY policy
  -> allowlisted executor revision resolution
  -> PostgresSkillInvocationRepository.prepare_dispatch(...)
       -> exact PostgreSQL lineage, Skill revision/operation/schema/binding checks
       -> scoped idempotency claim + exact execution snapshot
       -> Invocation REQUESTED + DISPATCH_RECORDED
       -> Resource Use REQUESTED + DISPATCH_RECORDED + claim/high-water/snapshot
       -> COMMIT
  -> HttpReadOnlySkillExecutor real protocol call
  -> PostgresSkillInvocationRepository.commit_terminal(...)
       -> terminal Invocation facts + redacted Skill Evidence
       -> Resource Use facts + measured duration/request/invocation counts
       -> Evidence link + terminal claim + high-water + snapshot
       -> canonical Invocation projection -> COMMIT
```

The composition owns both PostgreSQL pool lifetimes. The invocation repository owns
the pre-dispatch and terminal transactions. Restart recovery calls
`GovernedAttemptSkillInvocationService.recover(request, input)`: a durable dispatch
is never resent; a non-terminal dispatch becomes `OUTCOME_UNKNOWN`. Normal replay
returns the current original Invocation without redispatch. Retry orchestration is
not implemented and must create a successor Attempt and new Invocation upstream.

## Canonical internal read model

`read(scope, invocation_id)` authorizes before lookup and returns
`skill-invocation-read.v1` with:

- `invocationId`, `state`, `resultKnown`, `resourceUseId`, `evidenceId`,
  `errorCode`, and `limitations`;
- the invariant `technicalSuccessNotBusinessSuccess=true`;
- technical high-water, payload/input/output digests and the exact typed fact
  sequence.

Persisted exact execution fields additionally include the Plan/version/digest and
approval; Workflow Run, Task Run and Attempt; Assignment; Digital Employee
Definition/revision/digest and Instance; optional Agent/Runtime Instance; Skill
definition/revision/digest/operation and both schema digests; binding identity and
digest; executor identity/revision/configuration digest; authorization decision;
side-effect policy identity/revision/digest; and named versioned I/O-limit fields.

States are `REQUESTED`, `DISPATCH_RECORDED`, `ACCEPTED`, `RUNNING`, `SUCCEEDED`,
`FAILED`, `CANCELLATION_REQUESTED`, `CANCELLED`, and `OUTCOME_UNKNOWN`. The P1
application emits the request/dispatch path and supported terminal observations;
it exposes no local cancellation operation and never treats a local request as
remote cancellation confirmation.

Stable failures include nondisclosing `SKILL_INVOCATION_NOT_FOUND`, exact lineage,
revision, operation, schema, binding, executor and policy mismatch codes,
`SKILL_IDEMPOTENCY_PAYLOAD_MISMATCH`, I/O size/shape/schema failures,
`SKILL_EXECUTOR_REJECTED`, `SKILL_EXECUTOR_RESPONSE_INVALID`,
`SKILL_EXECUTOR_OUTCOME_UNKNOWN`, slot/CAS storage conflicts, and
`SKILL_RESULT_PENDING_CONFIRMATION` on recovered ambiguity.

## A-G completion

| Area | Status | Evidence / limitation |
| --- | --- | --- |
| A Invocation authority | Implemented | Typed immutable invocation/facts/Evidence plus PostgreSQL projection; claim and dispatch committed before HTTP call; no Skill aggregate history writes |
| B Eligibility/authorization | Implemented | Authorization-first; exact Plan/approval/Run/Attempt/Employee/Skill/schema/binding/executor/policy checks; denial and stale tests prove zero protocol calls |
| C Application wiring | Backend implemented | Formal composition and invoke/recover/read entries exist; upstream scheduler, HTTP and frontend remain `OPEN` |
| D Real READ_ONLY executor | Implemented | Allowlisted local HTTP adapter performs meaningful supplier defect summary; request/response identities and schemas validated; no arbitrary URL/script/MCP path |
| E Evidence/Resource Use | Implemented | Terminal facts, redacted Evidence, measured duration/request/invocation counts, claims/high-water and snapshot commit atomically; technical success is not business success |
| F Replay/concurrency/recovery | Implemented for P1 | Same-payload replay, mismatch, single dispatch, timeout/disconnect unknown, terminal rollback, failed recovery, restart and one-slot tests; no automatic retry or exactly-once claim |
| G Internal read model | Implemented | One authorization-gated canonical backend projection; no product HTTP/frontend added |

## Explicit open items

- No existing upper scheduling entry invokes this service yet. Connecting the future
  governed Attempt scheduler is separate work; test assembly is not described as a
  complete platform scheduler.
- No public HTTP or frontend surface is included or claimed.
- PR CI has not yet run. The new live Skill suite is not yet added to
  `.github/workflows/employee-identity.yml` because IMPL-281 owns that active path;
  controlled integration must add `SKILL_INVOCATION_TEST_DATABASE_URL`, select both
  new test files, and retain the selected-suite no-skip assertion.
- `IDEMPOTENT_WRITE`, `NON_IDEMPOTENT_WRITE`, multi-Skill orchestration, automatic
  unknown retry, compensation, HA and provider certification remain out of scope.
