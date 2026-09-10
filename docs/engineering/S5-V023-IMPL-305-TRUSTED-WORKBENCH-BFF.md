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
`4ef9ee40b4fb099d93823e3aa98c801e90c2087c`. It records gaps only. Nothing here
authorizes a production route, registry change, lifecycle change, merge, or
deployment.

### ARCH-300 status calibration

ARCH-300 architecture is `HUMAN_ARCHITECTURE_ACCEPTED_WITH_CONSTRAINTS`. The
accepted candidate is source
`4b8672cda51325322d4ec7dc0ac3d78df471d08b`, tree
`fde4ba3d1b5cdf7a019ca12f5801e6ef5bfe2533`; the Human decision was recorded on
PR #161 after that candidate commit. Durable merge
`270d193b936a61c65d4fa20d9a62709a5c2b56ad` has the same tree, contains the
accepted source as its second parent, and is an ancestor of current `origin/main`.

The literal `Proposed / Not Started` fields retained inside the accepted artifact
describe its pre-acceptance candidate snapshot; they do not reopen or negate the
later Human decision. Architecture acceptance and implementation completion are
separate: this branch implements I1 and a bounded, still incomplete I2 subset;
I3, deployed isolation, complete browser capability coverage, production
readiness, and IMPL-299 acceptance are not complete. Therefore the implementation
status used here remains `PARTIAL_DRAFT / SESSION_OPEN`, not `Not Started` and not
`Implemented`.

The accepted ARCH-300 candidate contains no `AGENT` or `PLACEMENT` authorization
owner row and does not freeze the pagination or `publicationState` fields below.
Every such addition is independently **PROPOSED / NOT_REGISTERED /
NOT_IMPLEMENTED** and requires a new Human decision; accepting ARCH-300 does not
accept these additions automatically.

### Placement exact READ

- **Accepted basis:** ARCH-300 requires exact owner/action/resource authorization
  before protected lookup, existence/list/count disclosure, owner joins, replay,
  or effects, and preserves independent READ permissions plus minimum disclosure.
  Accepted platform boundaries keep Definition, Instance, Assignment, Placement,
  Agent Instance, Runtime Instance, and Attempt as distinct identities. Existing
  `INSTANCE READ instance:{instance_id}` and `ASSIGNMENT READ
  assignment:{assignment_id}` mappings are unchanged; the implemented BFF holds
  current session/grant locks through a caller-owned PostgreSQL transaction.
- **Candidate new decision — PROPOSED:** add `PLACEMENT / READ /
  placement:{placement_id}` and no other Placement action. The candidate browser
  route is
  `/api/workbench/v1/instances/{instance_id}/assignments/{assignment_id}/placements/{placement_id}`
  with required `attemptId` and `agentInstanceId` query coordinates. This
  Placement operation requires only the proposed exact Placement READ grant.
  Parent possession or that grant must not imply any other grant; in particular,
  no Execution, Resource Use, Evidence, Runtime, or Agent detail READ is derived.
- **Authorization versus relationship checks:** the complete 310 page flow still
  needs existing `INSTANCE / READ / instance:{instance_id}` when it separately
  reads the Instance and existing `ASSIGNMENT / READ /
  assignment:{assignment_id}` when it separately reads the Assignment. Those are
  independent browser operations, not additional grants on Placement READ. After
  Placement authorization, its owner must validate the supplied Instance,
  Assignment, Placement Request, Attempt, and Agent Instance relationships as
  invariants of the one Placement projection. Those non-disclosing joins do not
  independently return any parent object and therefore do not acquire implicit
  Instance, Assignment, Execution, or Agent READ grants.
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
  parent-bound Placement projection after its current Placement grant. Not
  accepting it leaves the 310 Placement panel on the private header-based API and
  therefore not browser-trusted; it does not affect the already registered
  Instance or Assignment reads. The prior unaccepted three-grant recommendation
  is superseded because accepted ARCH-300 supplies no basis for converting
  non-disclosing owner joins into extra grants. Requiring multiple grants later
  would be a separate Human decision: denial of either parent grant would hide an
  otherwise readable Placement and 310 would have to acquire and retain all three.
- **Minimum DTO and necessary references — PROPOSED:** disclose `placementId`,
  `requestId`, `decision`, `runtimeInstanceId`, `policyVersion`,
  `compatibilityFacts`, `limitationCodes`, `decidedAt`, `digest`, and a verified
  `binding` containing exactly `instanceId`, `assignmentId`, `attemptId`, and
  `agentInstanceId`. The binding confirms the relationship that the owner checked;
  it is not a detail projection or grant for any referenced object. Do not return
  adjacent decisions, request history, observations, Execution or Outcome claims,
  Resource Use, or Evidence.
- **Hiding and transaction boundary:** authenticate and authorize before the owner
  adapter runs. Missing/revoked grant or session must execute zero owner queries.
  Missing object, foreign scope, any parent/identity mismatch, non-assembled
  Runtime, and inactive Attempt must then share `404 PLACEMENT_NOT_FOUND` with the
  authorization-hidden case and the same bounded body shape. Authorization and
  every Placement/Instance/Assignment/Request/Attempt/Agent Instance/
  active-attempt read must use the same caller-owned transaction connection; no
  nested connection, commit, or independently refreshed snapshot is allowed.
- **Implementation and revocation verification boundary:** a future owner port
  must prove the exact DTO, binding, scope isolation, uniform hiding, one
  connection, and zero owner queries after a winning grant/session revocation. A
  protected read that wins commits before the racing revoke; a revoke that wins
  makes the first/new request and any replay fail before any Placement or parent
  fact is queried or disclosed. Tests must also fail closed if any fixed IMPL-310
  parent or active-attempt check is removed.

### Agent Definition exact-revision READ

- **Accepted basis:** Agent Definition is distinct from Employee Definition and
  from Agent Instance. Existing Agent lifecycle persistence has immutable
  revision IDs and digests, while an Employee Definition member binds one exact
  Agent definition/revision/digest. The accepted general boundary is exact
  authorization before disclosure; ARCH-300 does not currently assign an Agent
  owner/action/resource row.
- **Candidate new decision — PROPOSED:** retain the recommendation
  `AGENT / READ / agent:{definition_id}:{revision_id}` for
  `GET /api/workbench/v1/agents/{definition_id}/revisions/{revision_id}`. The BFF
  must construct the exact target from typed path values and must not accept a
  current/published alias. This permission is independent from proposed Agent
  LIST, Employee READ, Instance READ, and any Agent lifecycle permission.
- **Current implementation:** the private Agent API reads a complete aggregate and
  projects all revisions, reviews, facts, relationships, lifecycle controls, and
  adjacent identities. Its repository `get` opens its own connection and the
  closed authority registry has no `AGENT` entry. The existing Employee BFF read
  returns only the Employee member reference; it is not Agent authorization.
- **Gap:** there is no caller-connection exact Agent revision repository method,
  trusted-context owner adapter, strict response DTO, registered route, or grant
  vocabulary. Reusing the aggregate projection would over-disclose and using
  `EMPLOYEE` would collapse domain ownership.
- **Acceptance effect and minimum response — PROPOSED:** acceptance would allow
  only `{definitionId, revisionId, digest, name, role}` where `role` contains
  exactly `{title, duties, businessPurpose, capabilities}`. The digest is verified
  against the requested immutable revision. Bindings, data,
  Knowledge/Skill/Runtime requirement text, predecessor or adjacent revisions,
  reviews, facts, relationships, aggregate version, draft/current/published
  pointers, and lifecycle decisions remain undisclosed. Non-acceptance leaves
  Agent detail unavailable through the trusted BFF and does not weaken the
  already implemented Employee revision route.
- **Implementation verification boundary:** a future exact-revision method must
  select and digest-check one revision on the caller-owned authorization
  connection, return uniform `404 AGENT_NOT_FOUND` for unauthorized, missing,
  hidden, foreign-scope, or revision/digest-invalid targets, and prove grant and
  session revocation before lookup/replay disclosure. It must not register Agent
  lifecycle operations or change the existing private API.

### Employee Definition publication source and field gap

- **Accepted basis:** ARCH-300 keeps immutable definitions/revisions under their
  Definition owner and does not allow browser headers or another resource owner to
  manufacture lifecycle authority. Publication and matching are independent; an
  immutable revision and digest alone do not prove current publication.
- **Candidate new decision — PROPOSED:** add a bounded `publicationState` field to
  Employee BFF list summaries and, if 310 must label an exact detail without a
  separate list lookup, to exact Employee READ. It is the current publication
  status of the specified immutable revision within its owning aggregate, not the
  aggregate lifecycle state and not a claim that some other revision is
  published. Its exact candidate enum is `PUBLISHED | NOT_PUBLISHED`:
  `PUBLISHED` means the latest applicable owner fact for this revision is
  `PUBLISH`; `NOT_PUBLISHED` deliberately combines no publication fact with latest
  `UNPUBLISH`, `REVOKE_PUBLICATION`, or `DEPRECATE`. The browser must not
  reconstruct the state from returned facts.
- **Current implementation:** the Employee owner persists ordered lifecycle facts
  and derives publication from the latest applicable `PUBLISH`, `UNPUBLISH`,
  `REVOKE_PUBLICATION`, or `DEPRECATE` action. Its private projection returns
  `published`, `matchable`, and the full ordered fact list; IMPL-310 currently
  computes its UI stage from those private fields. The registered exact Employee
  BFF DTO omits publication, matching, aggregate version, facts, predecessor, and
  adjacent revisions.
- **Gap:** the trusted surface therefore has no authoritative field with which 310
  can distinguish a currently published Employee revision. Exposing the private
  fact list would exceed the minimum need; inferring publication from revision
  identity or Agent state would be false.
- **Acceptance effect:** acceptance permits a current two-state publication label
  for the specified revision only. It returns neither a published-revision pointer
  nor any adjacent revision identity, and it implies neither matchability,
  instantiation eligibility, Assignment, Placement, nor runtime state.
  Non-acceptance requires 310 to display publication as unavailable on the trusted
  surface; it must not retain its private-API inference as a BFF claim.
- **Implementation verification boundary:** compute the field inside the Employee
  owner using the caller-owned connection and the same authorization snapshot as
  the protected revision/list read. Tests must cover publish, unpublish,
  publication revocation, and deprecation ordering; matching changes must not
  change publication. Grant/session revocation must win before either revision or
  publication state is disclosed.

### LIST permissions required by IMPL-310

- **Accepted basis:** the Human-accepted ARCH-300 registry and the current closed
  authority configuration already define `EMPLOYEE / LIST /
  employee:collection`, distinct from exact object READ. The current BFF registers
  no Employee LIST route. There is no accepted or registered Agent vocabulary.
- **Candidate new decisions — PROPOSED:** register an Employee list operation only
  after a caller-connection owner port exists, using the existing
  `EMPLOYEE / LIST / employee:collection` for
  `GET /api/workbench/v1/employees`; separately add `AGENT / LIST /
  agent:collection` for `GET /api/workbench/v1/agents`. Agent LIST is part of the
  same new owner decision as Agent READ, not an alias for it. Neither collection
  grant authorizes an exact detail; neither exact READ grant authorizes
  enumeration.
- **Minimum summaries — PROPOSED:** each Employee item is exactly
  `{employeeDefinitionId, employeeDefinitionRevisionId,
  employeeDefinitionDigest, role, publicationState}`; it has no published pointer
  or adjacent revision reference. Each Agent item is exactly `{definitionId,
  name, revisionId, digest, title, enabled, archived}` for the aggregate's current
  published revision; the response does not expose the `publishedRevisionId`
  pointer separately or any sibling revision. Omit responsibilities/member
  composition, Agent content beyond title, all draft and historical revisions,
  counts, reviews, facts, relationships, bindings, and adjacent pointers. A list
  item is discovery metadata, not proof that object READ is allowed.
- **Pagination — all parameters PROPOSED:** both routes accept optional opaque
  `cursor` and integer `pageSize`; omitted `pageSize` means `50`, values above the
  maximum `200` are rejected with `422`, and no client-supplied sort expression is
  accepted. Identifiers use ascending canonical UTF-8 byte order. Employee rows use
  `(employeeDefinitionId, employeeDefinitionRevisionId)` keyset order; the full
  pair is globally unique and `employeeDefinitionRevisionId` is the tie-breaker
  within one definition. Agent rows use ascending `definitionId` keyset order,
  whose ID is the unique tie-breaker because the list
  has at most one current published revision per definition. A page returns only
  `{items, nextCursor}`; `nextCursor` is absent at the end. The opaque cursor marks
  the exclusive last key, is bound to owner/scope and route, and conveys no grant
  or reusable object authority. No `totalCount`, hidden-row count, offset, previous
  cursor, or empty-versus-hidden distinction is disclosed. Each next-page request
  revalidates current session and LIST authorization and is not promised a
  cross-request database snapshot.
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
  enforce the proposed limits, exclusive keyset boundary, stable ordering and
  unique tie-breakers before registration; disclose no total count; and prove that
  grant/session revocation causes zero owner list queries and no replay
  disclosure. Tests must show LIST without object READ returns summaries but exact
  detail is denied, while object READ without LIST returns only the known object
  and cannot enumerate or disclose collection counts.

### Human decision and first implementation boundary

| Human decision | Exact contract | Existing or new | If accepted | If not accepted |
| --- | --- | --- | --- | --- |
| Placement exact read | `PLACEMENT / READ / placement:{placement_id}`; typed route, verified four-ID binding, bounded DTO, uniform 404 | New owner/action/resource and response contract | Implement one trusted exact Placement projection; separate Instance/Assignment reads retain their own existing grants | Placement remains private/not browser-trusted; existing Instance/Assignment BFF reads are unchanged |
| Optional multi-grant Placement policy | additionally require existing `INSTANCE / READ / instance:{instance_id}` and `ASSIGNMENT / READ / assignment:{assignment_id}` on the Placement operation | New policy requirement; not recommended by current evidence | Revoking any member hides Placement; 310 must obtain and retain all three grants | Recommended single Placement grant remains, while separately reading parents still requires their existing grants |
| Agent exact read | `AGENT / READ / agent:{definition_id}:{revision_id}` and the bounded single-revision response above | New owner/action/resource and route | 310 can verify the exact primary Agent without aggregate/history disclosure | Agent detail remains unavailable through the trusted BFF |
| Agent discovery list | `AGENT / LIST / agent:collection`; candidate page contract `50/200`, `definitionId` keyset, no total | New owner/action/resource, route, summary, and page parameters | 310 can discover bounded current published Agent candidates; object detail remains independently authorized | Primary Agent discovery remains private/unavailable even if a known exact Agent may later be readable |
| Employee discovery list | existing `EMPLOYEE / LIST / employee:collection`; candidate Employee route, summary, and `50/200` composite-key page contract | Grant vocabulary exists; BFF owner port, route, summary, and page parameters are new | 310 gains a trusted revision directory without full object READ or counts | Exact known Employee READ remains available; trusted Employee enumeration does not |
| Employee publication field | revision-scoped `publicationState: PUBLISHED \| NOT_PUBLISHED` derived from latest applicable owner fact | New bounded response field, using existing owner facts | 310 can label the specified revision's current publication state without fact history or adjacent IDs | Publication stays unavailable on the trusted surface and must not be inferred |

After those decisions are accepted, the first implementation batch is limited to:

1. freeze only the accepted additions in `authority_configuration.py` and focused
   registry-validation tests;
2. add caller-connection exact/list repository ports and bounded owner adapters in
   the Agent Definition, Employee Definition, and Digital Employee Placement
   modules, then compose only the accepted typed operations in
   `workbench_bootstrap.py` and `app.py`;
3. add strict response/page contracts and focused unit/composition tests; and
4. add PostgreSQL tests for exact DTOs, digest verification, keyset boundaries,
   stable/tie-break ordering, no totals or adjacent revisions, LIST-versus-READ
   independence, scope hiding, complete Placement parent/active-attempt checks,
   one caller-owned connection, and grant/session revocation with zero owner query
   after revocation wins.

That batch does not authorize lifecycle operations, migrations unless separately
required and approved, frontend rewiring, I3/deployment proof, merge, or release.

These four gaps are intentionally additive. Until Human acceptance freezes the
new `AGENT` and `PLACEMENT` vocabulary and the bounded publication/list fields,
they remain `PROPOSED / NOT_REGISTERED / NOT_IMPLEMENTED`. Delivery remains
`PARTIAL_DRAFT / SESSION_OPEN`; Draft PR #164 must not be made Ready, merged, or
deployed by this addendum.
