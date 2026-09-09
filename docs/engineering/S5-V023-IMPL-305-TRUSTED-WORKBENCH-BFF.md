# S5-V023-IMPL-305 Trusted Workbench BFF

Status: `PARTIAL_DRAFT / SESSION_OPEN`; bounded I2 implementation, not I3 acceptance.

Base: `9c28fa5b28c0cab6a39dc05f5367e93c8bcc8913`

This increment implements the independent ARCH-300 I2 boundary: strict Workbench
schemas, a closed typed route registry, browser session/CSRF/Origin/Host checks,
and a current exact-grant adapter that keeps the I1 generation barrier and the
owner call inside one caller-owned PostgreSQL transaction.

Routes are registered only when composition supplies an explicit transactional
owner handler. A handler receives the trusted context, authorization decisions,
and the same PostgreSQL connection used for the current-grant check. Existing
header-based or separately-transactional owner ports are not silently wrapped.

IMPL-295 / REL-306 closed at fixed commit
`f189212232fc194859a695f0307e83b0c7b73c0f`; that baseline was merged without
rebasing. Its serial migration writer, compatibility checks, failure propagation,
health deadline, and harness behavior remain intact.

## Registered routes

The public application always has only `/healthz`, five session operations, and
the explicitly supplied operation registry. Production composition registers the
following owner-backed routes only when the external authority runtime file,
exact Host/Origin, active generation/recovery record, the same execution database,
and durable Business Problem assembly are all available:

| Browser route | Owner action/resource | Actual owner effect |
| --- | --- | --- |
| `POST /api/workbench/v1/problems` | `BUSINESS_PROBLEM CREATE` and `READ` on `business-problem:collection` | owner `create_problem` |
| `GET /api/workbench/v1/problems` | `BUSINESS_PROBLEM LIST` on the collection | owner `list_problems` |
| `GET /api/workbench/v1/problems/{id}` | `BUSINESS_PROBLEM READ business-problem:{id}` | owner aggregate/history read |
| `POST /api/workbench/v1/problems/{id}/revisions` | exact `REVISE` plus `READ` | owner CAS revision write |
| `POST /api/workbench/v1/problems/{id}/lifecycle` | exact `TRANSITION` plus `READ` | owner lifecycle write |
| `POST /api/workbench/v1/success-criteria` | collection `CREATE`, or exact `REVISE`; required `READ` facts | owner criterion revision write |
| `GET /api/workbench/v1/success-criteria/revisions/{id}` | exact revision `READ` | owner revision read |
| `POST /api/workbench/v1/problems/{id}/criteria-sets` | exact set `CREATE`/`REVISE` and `READ`, Problem `READ`, each submitted criterion revision `READ` | owner criteria-set CAS write |
| `GET /api/workbench/v1/problems/{id}/criteria-sets` | exact set `READ` | owner set revision read |
| `GET /api/workbench/v1/problems/{id}/criteria` | set and Problem `READ`, then each owner-discovered revision `READ` | owner filtered criterion read |
| `POST /api/workbench/v1/problems/{id}/plans` | exact `PLAN PREPARE` and prepared `READ`, Problem/set/reference reads | Workflow Control preparation and Problem binding in one UoW |
| `GET /api/workbench/v1/plans/{id}?version=N` | `PLAN READ plan:{id}:{N}` | owner plan/approval projection |
| `POST /api/workbench/v1/plans/{id}/approvals` | independent exact `PLAN APPROVE` plus `READ`; owner-discovered Problem/set/reference reads | owner approval append with decision basis |
| `GET /api/workbench/v1/employees/{definition_id}/revisions/{revision_id}` | exact `EMPLOYEE READ employee:{definition_id}:{revision_id}` | only the authorized immutable Employee Definition revision and digest |
| `GET /api/workbench/v1/workflows` | `WORKFLOW LIST workflow:collection` | minimal Workflow Definition summaries, when the optional Workflow registry is enabled |
| `GET /api/workbench/v1/workflows/{definition_id}/revisions/{revision_id}` | exact `WORKFLOW READ workflow:{definition_id}:{revision_id}` | only the authorized revision and bounded projections, when the optional Workflow registry is enabled |

All request bodies and the Plan query are strict Pydantic contracts. Incoming
authorization, proxy-authorization, principal, tenant, domain, product-read, and
trusted-context headers are rejected. Host is exact on every request; Origin,
`Sec-Fetch-Site` when present, and session-bound CSRF are required for unsafe
requests. The cookie is `__Host-workbench_session`, Secure, HttpOnly,
SameSite=Strict, and Path `/`; responses are no-store with bounded errors.

## Linearization boundary

The BFF opens one READ COMMITTED transaction from the authority repository. The
first current authorization read validates active generation/recovery, locks the
browser session row `FOR SHARE`, and locks every matching dynamic grant row `FOR
SHARE`. READ COMMITTED is required because an equal owner request may wait on the
owner's idempotency advisory lock after authorization and must then observe the
winner's completed claim. Exact session revoke locks the session row `FOR UPDATE`;
grant revoke locks the grant row `FOR UPDATE`. Those locks and the activation read
barrier remain held through replay or owner commit. Therefore an authorized owner
effect/replay commits before a racing revocation, while a revocation that wins
first makes the request fail closed; switching snapshots does not allow an effect
to escape current authorization.

The owner adapter constructs the legacy principal only from
`TrustedRequestContext`, supplies a current-grant authority bound to that same
connection, and calls the existing Business Problem/Workflow Control owner. The
owner UoW accepts the caller connection and does not commit or open another
connection. Owner-discovered criterion/reference grants are checked on the same
snapshot before their protected read. Replay follows the same current checks.

## Startup and route separation

`app.py` retains the private service application and never registers Workbench
routes. `workbench_app` remains `None` unless all production settings succeed:
`WORKBENCH_AUTHORITY_RUNTIME_FILE`, `WORKBENCH_ALLOWED_HOST`, and
`WORKBENCH_ALLOWED_ORIGIN`; the authority database fingerprint must equal
`EXECUTION_DATABASE_URL`. Employee Definition exact READ is composed explicitly
from the already-required Digital Employee assembly and uses that same execution
database. Workflow Definition reads are an optional registry extension: when
`WORKFLOW_RUNTIME_DATABASE_URL` is absent, the 13 Business Problem, Criteria, and
Plan operations plus Employee exact READ remain enabled; when it is present, the
Workflow service must be available and its database fingerprint must equal the
authority and execution database or startup fails closed. Database credentials
are never included in the failure reason.

The supervisor retains its legacy one-listener form and adds an explicit dual
mode (`--public-port` plus `--private-port`). Dual mode starts one child and one
event loop, pre-binds both sockets, runs two Uvicorn servers with one worker,
checks closed route inventories, reports `STARTING`, and changes to `RUNNING` only
after a bounded 20-second child readiness handshake. Either server exit, listener
failure, SIGTERM, or supervisor lifetime loss closes both. An expected signal
shutdown returns zero; either server's unprompted return, partial startup failure,
readiness failure, or supervisor loss returns nonzero. This is local process
evidence only; it is not RBAC, admission, NetworkPolicy, ingress, or packet-denial
evidence.

## Routes deliberately not registered

- Capability discovery and grant request/decision/revocation/continuation HTTP
  routes require a formal cross-owner exact-target validator. I1 exposes the
  application service but the fixed baseline has no production validator port;
  registering a mock would allow requests without owner fact proof.
- Workflow Definition LIST and exact-revision READ use the caller-owned connection
  and are registered when their optional same-database dependency is configured.
  Employee Definition exact-revision READ is registered on the same boundary.
  Workflow CREATE and all lifecycle mutations, Employee Definition lifecycle
  mutations, Instance, and Assignment APIs remain unregistered. Existing
  header-based routes stay private.
- Governed Execution START and Skill invocation require their durable
  preparation/dispatch authorization barrier. They are not wrapped as ordinary
  database handlers. Execution read, Resource Use, and Evidence-reference routes
  also remain unregistered until that formal owner port exists.
- Evidence content/dereference and standalone Resource Use remain outside the
  accepted contract.

These omissions mean the full 299 browser journey and complete I2 are not claimed.
The default-disabled public BFF does not unlock IMPL-299.

## I2 route-matrix status

| 299 capability family | Current production status | Why it is or is not public |
| --- | --- | --- |
| Login, current session, rotation, logout, CSRF, Origin and Host | `FORMALLY_REGISTERED` | Five public operations use the I1 Browser Session Authority; unsafe operations require same-origin plus session-bound CSRF. |
| Business Problem, Criteria and Plan | `FORMALLY_REGISTERED` | The 13 routes above call the durable Product/Workflow Control owner through the same authorization transaction. |
| Grant requests, decisions, revocation and continuations | `COMPONENT_ONLY / NOT_REGISTERED` | I1 application components exist, but production composition has no formal cross-owner exact-target validator/continuation resolver. |
| Workflow Definition read | `OPTIONAL / FORMALLY_REGISTERED` | LIST and exact-revision READ use the current authorization transaction when the optional same-database Workflow service is configured; no aggregate history or adjacent revisions are disclosed. |
| Workflow Definition lifecycle | `PRIVATE_OWNER_ROUTE_ONLY / NOT_REGISTERED` | CREATE, edit, validate, review, publish, and other lifecycle mutations are not in the public registry. |
| Employee Definition exact revision read | `FORMALLY_REGISTERED` | Exact `EMPLOYEE READ employee:{definition_id}:{revision_id}` uses the current authorization transaction and discloses only the requested revision identity, digest, role, responsibilities, and exact composition members. |
| Employee Definition lifecycle mutation | `PRIVATE_OWNER_ROUTE_ONLY / NOT_REGISTERED` | CREATE, validation, approval, publication, and matching decisions remain private owner operations. |
| Instance, Assignment and Placement | `PRIVATE_OWNER_ROUTE_ONLY / NOT_REGISTERED` | Exact owner facts exist, but their application methods do not accept the BFF caller transaction/trusted-context authority. |
| Governed Execution START and Skill dispatch | `PRIVATE_FORMAL_ROUTE_ONLY / NOT_REGISTERED` | Dispatch must consume the existing durable preparation/dispatch authorization barrier; the ordinary database owner adapter is not that barrier. |
| Execution and invocation readback | `PRIVATE_FORMAL_ROUTE_ONLY / NOT_REGISTERED` | No BFF trusted-context owner port currently couples current authorization to the formal readback. |
| Resource Use and Evidence reference | `PARTIAL_OWNER_PROJECTION / NOT_REGISTERED` | Some facts are reachable through governed Execution readback, but no accepted standalone BFF owner port exists. Evidence content/dereference remains outside the accepted contract. |

The current main frontend still uses private/preview APIs and does not consume this
new public registry. Therefore the matrix is `PARTIAL_DRAFT`: absence from the
public route set is fail-closed behavior, but it is not delivery of the missing I2
capabilities.

## PROPOSED Agent Definition authorization gap

The closed authority registry currently has no Agent Definition owner entry:
`OWNER_ACTIONS` and `OWNER_RESOURCE_PREFIXES` in
`console/backend/src/agent_console/authority_configuration.py` contain no `AGENT`
mapping. Consequently 305 does not register an Agent route, borrow `EMPLOYEE` or
another owner, or bypass current authorization.

IMPL-310 needs a bounded exact-revision read to render the primary Agent member of
an Employee Definition without receiving Agent revision history, reviews, facts,
or adjacent revision pointers. The minimum additive contract decision is
**PROPOSED**, not accepted or implemented:

- owner/action/resource: `AGENT / READ / agent:{definition_id}:{revision_id}`;
- owner port: caller-owned connection exact-revision read with digest validation;
- response: requested Agent revision identity, digest, role content needed by 310,
  and no aggregate history or lifecycle decision collection.

The proposed implementation would affect
`console/backend/src/agent_console/authority_configuration.py`,
`agent_definition_repository.py`, `agent_definition_postgres.py`,
`agent_definition_service.py`, a new `workbench_agent.py`, explicit
`workbench_bootstrap.py`/`app.py` composition, and corresponding focused unit and
PostgreSQL authorization tests. This is an independent additive contract gap; it
does not reopen accepted ARCH-300 and does not block Employee or other already
registered owner contracts.

## Validation record

- checkpoint `17cccb3`: commit hooks passed Ruff lint, Ruff format, and pytest;
- Workflow repository, service, and owner-adapter batches from checkpoint
  `57e95d3` remain 19 passed and were not rerun by the composition increment;
- composition, public/private route inventory, startup dependency, and fail-closed
  tests: 28 passed; targeted Ruff lint and format checks passed;
- Employee exact READ focused unit/composition batch: 33 passed; targeted Ruff
  lint and format checks passed. The response excludes scope, facts, publication
  state, predecessor and adjacent Employee revisions;
- dedicated PostgreSQL 15 Employee increment: 2 passed, 8 deselected. Exact
  revision/digest read used the current authorization connection; grant and
  session revocation each denied the next request before the protected owner
  query. The disposable local container was removed after validation;
- dedicated PostgreSQL 15 Workflow increment: 2 passed, 6 deselected. Both grant
  and session revocation cases first called the formal exact-revision owner on the
  authorization connection, disclosed no adjacent revision, then denied without
  executing the protected owner query after revocation;
- focused BFF/session/owner/business/supervisor tests run as the 305 worktree user;
- dedicated PostgreSQL 15 container, isolated databases per case: grant revoke and
  session revoke both blocked behind the owner commit, and subsequent requests
  failed current authorization;
- prior checkpoint CI evidence was confirmed without rerun: runs `34377904525`
  (CI) and `34377904624` (Employee Identity Chain) both completed successfully on
  attempt 1 for source `5e0b77e34a461653764928b489baa0852f4b8592`.
  Pull-request checkout executed merge commit
  `dda7a2a3de91329b1d7b76afcd3563dc30e74373`, not the source commit directly;
- event- and PostgreSQL-lock-driven owner replay cases prove equal concurrent
  payloads return one stored effect, changed payloads conflict, and grant/session
  revocations waiting behind the replay take effect before any later request;
- local dual-listener tests prove route separation and common shutdown only, not
  deployment isolation. Deterministic lifecycle cases cover supervisor loss,
  either-listener unexpected exit, partial startup failure, and expected signal
  shutdown; readiness failure also kills a child that does not honor termination.

Delivery remains `PARTIAL_DRAFT / SESSION_OPEN`. IMPL-299 and IMPL-310 gates stay
in force; this increment does not make the Draft PR ready, merge, or deploy it.
