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

## Contract addendum for fixed IMPL-310 candidate

This addendum is a bounded recommendation for the fixed IMPL-310 candidate
`4ef9ee40b4fb099d93823e3aa98c801e90c2087c`. It records gaps only. ARCH-300 is
still `Proposed / Not Started`; every authorization owner, action, resource, and
response field identified below as **PROPOSED** remains unregistered and
unimplemented. Nothing here authorizes a production route, registry change,
lifecycle change, merge, or deployment.

### Placement exact READ

- **Accepted basis:** the current source keeps Definition, Instance, Assignment,
  Placement, Agent Instance, Runtime Instance, and Attempt as distinct identities.
  The already implemented BFF boundary authorizes before protected lookup, uses a
  caller-owned PostgreSQL connection, holds current session/grant locks through
  the owner call, and collapses unauthorized and missing exact resources to a
  minimum-disclosure `404`. Existing `INSTANCE READ instance:{instance_id}` and
  `ASSIGNMENT READ assignment:{assignment_id}` mappings are unchanged.
- **Candidate new decision — PROPOSED:** add `PLACEMENT / READ /
  placement:{placement_id}` and no other Placement action. A candidate browser
  route may use
  `/api/workbench/v1/instances/{instance_id}/assignments/{assignment_id}/placements/{placement_id}`
  with required `attemptId` and `agentInstanceId` query coordinates. The request
  must carry all three independent exact grants: the existing Instance READ,
  existing Assignment READ, and proposed Placement READ. Parent possession or a
  Placement grant must not imply any other grant; in particular, no Execution,
  Resource Use, Evidence, Runtime, or Agent detail READ is derived.
- **Current implementation:** the private Digital Employee owner first verifies
  Assignment belongs to Instance; Attempt belongs to that Assignment and Digital
  Employee Instance; the Agent Instance exists and matches the Instance's exact
  primary Agent definition/revision/digest; the Placement decision exists and has
  a Runtime Instance; its request matches the supplied Attempt and Agent Instance;
  and the Attempt is still active for that Runtime Instance and Agent Instance.
  IMPL-310 depends on that exact chain and active-attempt check; neither may be
  weakened or replaced by client assertions.
- **Gap:** `PLACEMENT` is absent from `OWNER_ACTIONS` and
  `OWNER_RESOURCE_PREFIXES`; the private Placement application/repository path
  opens owner-managed connections for several reads and does not accept the BFF
  caller connection. There is no registered trusted-context Placement owner port.
- **Acceptance effect:** accepting the proposal would permit only one exact,
  parent-bound Placement projection after three current grants. Not accepting it
  leaves the 310 Placement panel on the private header-based API and therefore not
  browser-trusted; it does not affect the already registered Instance or
  Assignment reads.
- **Minimum DTO and hiding:** disclose only `placementId`, `requestId`,
  `decision`, `runtimeInstanceId`, `policyVersion`, `compatibilityFacts`,
  `limitationCodes`, `decidedAt`, and `digest`. Do not return supplied parent
  coordinates, adjacent decisions, request history, observations, Execution or
  Outcome claims, Resource Use, or Evidence. Missing grant, missing object,
  foreign scope, any parent/identity mismatch, non-assembled Runtime, and inactive
  Attempt must share `404 PLACEMENT_NOT_FOUND` with the same bounded body shape.
- **Implementation and revocation verification boundary:** a future owner port
  must perform authorization and every parent-chain/active-attempt read on the
  caller-owned connection without commit or nested connection. Focused PostgreSQL
  tests must prove the exact DTO and uniform hiding, and prove both grant and
  session revocation: a protected read that wins commits before the racing revoke;
  a revoke that wins makes the first/new request and any replay fail before any
  Placement or parent fact is disclosed. Tests must also fail closed if any of the
  fixed IMPL-310 parent or active-attempt checks is removed.

### Agent Definition exact-revision READ

- **Accepted basis:** Agent Definition is distinct from Employee Definition and
  from Agent Instance. Existing Agent lifecycle persistence has immutable
  revision IDs and digests, while an Employee Definition member binds one exact
  Agent definition/revision/digest. The accepted general boundary is exact
  authorization before disclosure; ARCH-300 does not currently assign an Agent
  owner/action/resource row.
- **Candidate new decision — PROPOSED:** retain the recommendation
  `AGENT / READ / agent:{definition_id}:{revision_id}`. The BFF must construct the
  exact target from typed path values and must not accept a current/published
  alias. This permission is independent from proposed Agent LIST, Employee READ,
  Instance READ, and any Agent lifecycle permission.
- **Current implementation:** the private Agent API reads a complete aggregate and
  projects all revisions, reviews, facts, relationships, lifecycle controls, and
  adjacent identities. Its repository `get` opens its own connection and the
  closed authority registry has no `AGENT` entry. The existing Employee BFF read
  returns only the Employee member reference; it is not Agent authorization.
- **Gap:** there is no caller-connection exact Agent revision repository method,
  trusted-context owner adapter, strict response DTO, registered route, or grant
  vocabulary. Reusing the aggregate projection would over-disclose and using
  `EMPLOYEE` would collapse domain ownership.
- **Acceptance effect and minimum DTO:** acceptance would allow only the requested
  `definitionId`, `revisionId`, verified `digest`, `name`, and bounded role content
  needed by 310: `title`, `duties`, `businessPurpose`, and `capabilities`.
  Bindings, data, Knowledge/Skill/Runtime requirement text, predecessor or adjacent
  revisions, reviews, facts, relationships, aggregate version, draft/current/
  published pointers, and lifecycle decisions remain undisclosed. Non-acceptance
  leaves Agent detail unavailable through the trusted BFF and does not weaken the
  already implemented Employee revision route.
- **Implementation verification boundary:** a future exact-revision method must
  select and digest-check one revision on the caller-owned authorization
  connection, return uniform `404 AGENT_NOT_FOUND` for unauthorized, missing,
  hidden, foreign-scope, or revision/digest-invalid targets, and prove grant and
  session revocation before lookup/replay disclosure. It must not register Agent
  lifecycle operations or change the existing private API.

### Employee Definition publication source and field gap

- **Accepted basis:** the current Employee owner persists lifecycle decisions as
  ordered facts. Its authoritative read derives publication from the latest
  applicable `PUBLISH`, `UNPUBLISH`, `REVOKE_PUBLICATION`, or `DEPRECATE` action;
  publication remains independent from `GRANT_MATCH`. An immutable revision and
  digest alone do not prove current publication.
- **Candidate new decision — PROPOSED:** add a bounded `publicationState` field to
  Employee BFF list summaries and, if 310 must label an exact detail without a
  separate list lookup, to exact Employee READ. Its values should be only
  `PUBLISHED` or `NOT_PUBLISHED`, derived by the Employee owner at read time from
  its ordered facts. The browser must not reconstruct the state from returned
  facts, and `publicationState` must not imply matchability, instantiation, or
  execution authority.
- **Current implementation:** the private Employee projection returns `published`,
  `matchable`, and the full ordered fact list; IMPL-310 currently computes its UI
  stage from those private fields. The registered exact Employee BFF DTO omits
  publication, matching, aggregate version, facts, predecessor, and adjacent
  revisions.
- **Gap:** the trusted surface therefore has no authoritative field with which 310
  can distinguish a currently published Employee revision. Exposing the private
  fact list would exceed the minimum need; inferring publication from revision
  identity or Agent state would be false.
- **Acceptance effect:** acceptance permits a current two-state publication label
  only. Non-acceptance requires 310 to display publication as unavailable on the
  trusted surface; it must not retain its private-API inference as a BFF claim.
- **Implementation verification boundary:** compute the field inside the Employee
  owner using the caller-owned connection and the same authorization snapshot as
  the protected revision/list read. Tests must cover publish, unpublish,
  publication revocation, and deprecation ordering; matching changes must not
  change publication. Grant/session revocation must win before either revision or
  publication state is disclosed.

### LIST permissions required by IMPL-310

- **Accepted basis:** ARCH-300's candidate registry and the current closed
  authority configuration already define `EMPLOYEE / LIST /
  employee:collection`, distinct from exact object READ. The current BFF registers
  no Employee LIST route. There is no accepted or registered Agent vocabulary.
- **Candidate new decisions — PROPOSED:** register an Employee list operation only
  after a caller-connection owner port exists, using the existing
  `EMPLOYEE LIST employee:collection`; separately add `AGENT / LIST /
  agent:collection`. Agent LIST is part of the same new owner decision as Agent
  READ, not an alias for it. Neither collection grant authorizes an exact detail;
  neither exact READ grant authorizes enumeration.
- **Minimum summaries:** Employee LIST should return only
  `employeeDefinitionId`, `employeeDefinitionRevisionId`, verified
  `employeeDefinitionDigest`, `role`, and the proposed two-state
  `publicationState`. Agent LIST should return only `definitionId`, `name`, the
  current published `revisionId` and verified `digest`, bounded `title`, plus
  `enabled` and `archived` eligibility flags required by 310's selector. Omit
  responsibilities/member composition, Agent content beyond title, all draft and
  historical revisions, counts, reviews, facts, relationships, bindings, and
  adjacent pointers. A list item is discovery metadata, not proof that object
  READ is allowed.
- **Current implementation:** IMPL-310 calls private Employee and Agent collection
  APIs. Those implementations open owner-managed connections and return full
  revision or aggregate content; 310 then filters Agent candidates by published
  revision, enabled, and not archived. Instance and Assignment remain known-ID
  reads, and Placement remains a coordinate-complete exact read; 310 requires no
  Instance, Assignment, or Placement LIST permission.
- **Gap:** there are no BFF collection owner ports with bounded summaries on the
  caller-owned authorization transaction. Agent LIST additionally lacks registry
  vocabulary. Directly wrapping either private list would over-disclose and break
  the authorization/revocation linearization boundary.
- **Acceptance effect:** accepting both proposals supplies only the two discovery
  lists needed by 310; exact Employee, Agent, Instance, Assignment, and Placement
  detail still requires its own object READ grant. Rejecting Employee LIST removes
  the trusted Employee directory; rejecting Agent LIST removes trusted primary
  Agent discovery, even if a separately known exact Agent revision could later be
  read.
- **Implementation verification boundary:** future list ports must authorize
  before existence, count, or row disclosure; use the caller-owned connection;
  enforce deterministic bounded pagination/limits before registration; and prove
  that grant/session revocation prevents the list query and replay disclosure.
  Tests must show LIST without object READ returns summaries but exact detail is
  denied, while object READ without LIST returns only the known object and cannot
  enumerate or disclose collection counts.

These four gaps are intentionally additive. Until Human acceptance freezes the
new `AGENT` and `PLACEMENT` vocabulary and the bounded publication/list fields,
they remain `PROPOSED / NOT_REGISTERED / NOT_IMPLEMENTED`. Delivery remains
`PARTIAL_DRAFT / SESSION_OPEN`; Draft PR #164 must not be made Ready, merged, or
deployed by this addendum.
