# IMPL-293 — Workflow Skill authoring and governed consumption

## Authority, baseline and isolation

Session `S5-V023-IMPL-293`; original bounded implementation plus Human-approved
bounded Skill operations scope supplement and the later Human-approved UI
compatibility regression supplement. G1 implementation uses the accepted
[288 authority addendum](../../architecture/s5/v0.2/S5-V023-IMPL-288-GOVERNED-EXECUTION-AUTHORITY-ADDENDUM-V1.md).
No new migration, issuer, scheduling authority, provider protocol or product
frontend behavior is introduced.

Fixed base: `adcd648a0fc8ca60066f52665ce0e83d7332b7dd`.
Base tree: `73c136b927aaa87d7234c46b110f3d75d5872213`.
Branch: `codex/s5-v023-impl-293-workflow-skill-authoring`.
The independent `abdc` worktree has one writer. Startup inspection found no
other 293 branch, commit, PR or accessible task.

At resumed inspection, remote main was `6035917d7a6f31ee12cf121ff9958d2326f9879d`:
290 / PR #157 integration, six reachable additional commits, changing frontend
and one delivery matrix only. No overlap with this task's backend/CI paths.
This increment retains its fixed base without merge, rebase or refresh.

## Implementation and compatibility

Production Workflow composition now resolves Runtime Profiles and Skills through
their existing scoped domain repositories. A Skill reference must identify the
current published, enabled, non-archived, non-deprecated Skill revision and exact
asserted digest. Validation also resolves each task's explicit operation binding.
There is no first-operation or capability/name fallback. Publication rechecks
references after exact revision review. Client assertions grant no authority.

The Skill HTTP schema preserves `operations` and validates the existing governed
wire record, reusing `ExecutorRevision`, `SideEffectPolicy` and `SkillIOLimits`.
Only the existing READ_ONLY path is supported. Operation/policy/limits fields
are exact; names must be unique, schemas must be objects, and identity/limit
values must satisfy the existing domain constructors. The same validation is
used at the Skill lifecycle boundary and by the Workflow resolver. No second
execution contract or new persistent authority is introduced.

Create/edit envelopes and ordinary resource content reject unknown fields;
operation validation never uses global `extra=allow`. Existing manifest export
metadata remains compatible with the existing import envelope. Operations are
rejected for MCP resources; MCP invocation semantics are unchanged.

Operations field behavior:

| Input | New/legacy Skill content | Edit of draft with operations |
| --- | --- | --- |
| Omitted | Remains absent; no generated operations | Rejected (422) |
| Explicit null | Rejected (422) | Rejected (422) |
| Empty list | Rejected (422) | Rejected (422) |
| Non-empty valid list | Exact contents preserved | New draft revision, normal review/publication |

The existing GET projection already returns stored content, revision and digest;
it needs no replacement. Historical missing-operation Skills remain readable and
retain their digests, but cannot satisfy an executable operation binding. No
historical Workflow, Skill or Plan is backfilled or recomputed. Workflow GET/edit
binding preservation, explicit-null/omission protection, successor history, CAS,
Runtime Profile resolution and immutable publication remain in force.

The compatibility supplement exercises the real browser management path over
the production Skill HTTP API. It creates an operation-backed Draft through the
API, opens that exact Draft in the normal Skill page, changes only description,
observes the unmodified PUT request, and compares its operations with the prior
authoritative GET. A second authoritative GET must retain the same resource ID
and operations while returning the edited description. This adds no operations
authoring UI and does not replace the existing historical no-operations edit
coverage.

## Exact execution connection and product limitation

The acceptance prepares **Skill and Workflow through normal production HTTP APIs**
against the task's real PostgreSQL instance, without dependency overrides, a test
resolver or business-row SQL on that path. The shared old execution helper now
accepts an explicit HTTP authoring callback; when supplied, it never constructs
the legacy Workflow test resolver. Existing tests retain their original setup.

Plan preparation uses the existing `PostgresWorkflowControlRepository.create_plan`
and `append_approval` domain ports with `PlanRecord`, exact canonical bytes from
`execution_plan_bytes`, Workflow revision/digest and the existing Human approval
record. Other assignment/employee prerequisites use existing domain services.
These are explicit test prerequisites, not a normal durable Plan product API.
The ordinary Problem API's `problems/service.py` remains process-local/inert and
is not connected to that durable preparation port: **NOT_CONNECTED**.

The existing governed application independently checks the approved Plan's exact
Workflow revision and task, published employee membership, Skill revision and
operation, schema identities, side-effect policy and allowlisted executor.
Invocation persistence rechecks these facts before dispatch. The real test uses
the production supervisor/bootstrap, verifies `SUCCEEDED`, Resource Use and
Evidence references, and verifies replay retains one real HTTP provider call.
Publication is not execution authorization. UNKNOWN is not provider termination;
this change does not alter recovery or permit redispatch of an existing Invocation.
No complete user Problem-to-execution journey, M1/M2/P1 completion, production
readiness or business success is claimed.

## Complete changed paths

- `console/backend/src/agent_console/skill_mcp_schemas.py`
- `console/backend/src/agent_console/skill_mcp_api.py`
- `console/backend/src/agent_console/skill_mcp_service.py`
- `console/backend/src/agent_console/workflow_definition_resolver.py`
- `console/backend/src/agent_console/workflow_definition_api.py`
- `console/backend/src/agent_console/workflow_definition_service.py`
- `console/backend/tests/test_skill_operation_schema.py`
- `console/backend/tests/test_workflow_definition_resolver.py`
- `console/backend/tests/test_workflow_skill_authoring_postgres.py`
- `console/backend/tests/test_governed_execution_api_postgres.py`
- `.github/workflows/employee-identity.yml`
- `console/frontend/tests/e2e/skill-mcp-workbench.spec.ts`
- `docs/engineering/S5-V023-IMPL-293-WORKFLOW-SKILL-AUTHORING.md`

## Validation and CI selection

The focused real HTTP scenario covers Skill create/edit/GET and publication,
Workflow create/validate/review/publication/GET, unrelated edits, null/omission
protection, changed successor binding without modifying history, unpublished and
cross-scope Skills, missing revision, wrong digest, unknown operation, contradictory
reference/binding, historical reads and execution refusal, supervised successful
dispatch and same-request replay.

The real-browser Skill regression additionally verifies that the actual normal
UI PUT carries the exact operation list returned by the authoritative pre-edit
GET, receives HTTP success, and is confirmed by an authoritative post-edit GET.
The pre-existing browser successor edit continues to cover historical Skills
without operations.

The existing Skill CI job is reused with all prior tests and fail-on-any-skip
behavior retained. It adds the real authoring module and resolver/schema/Skill
API/service regressions. The existing Identity job's selection is unchanged.
Both jobs now report source SHA, actual checkout SHA, checkout tree and parents.
The Skill job has its own database through migration 0017; it does not share the
Identity job's differently staged database. No CI infrastructure is duplicated.

Final local validation: the exact CI Skill selection passed **57 tests, zero
skips**, in 309.70 seconds. Final `make check` passed lint/format and **1547 tests,
105 environment skips** in 31.31 seconds. Those skips are not real-service passes.
The selection contains 34 PostgreSQL-required cases and 23 focused cases.
Those 23 overlap the default passing suite; the 34 overlap its environment skips.
The reported totals are not additive.
The target test retains production supervisor output in a task-owned file so its
many real HTTP requests cannot block an unread pipe. The existing startup deadline
and all production supervision/recovery semantics remain unchanged.
Source/CI provenance is recorded in the PR and completion report. Earlier evidence is not substituted: the initial real HTTP
failure reproduced lost operations; the earlier broad PostgreSQL run was
interrupted after two passes. Both were superseded by final candidate validation.

## Assets and follow-up

Only task-owned container `s5-293-postgres`, database `s5_293`, and new ephemeral
HTTP/supervisor ports are used. After restart its loopback PostgreSQL port was
58749 (previously 57089). Existing migration/checksum validation runs through the
production repository bootstrap; no migration or business fixture SQL was added.
No 288/290 worktree, database, container, port, credential or supervisor state is
reused. Supervisor and provider processes are stopped by test cleanup.

Retained local assets: task branch/worktree, `.venv`, exclusively owned PostgreSQL
container/data, and `/tmp/s5-293-*.log` validation logs. The database is stopped at
delivery. The branch and Draft PR await Human pre-merge review; no Ready transition,
merge, deployment, force push or branch refresh is authorized.

Follow-up remains separately scoped: connect the ordinary durable Plan product
entry. Single-host execution support and cross-host limitations remain exactly as
accepted in 288.
