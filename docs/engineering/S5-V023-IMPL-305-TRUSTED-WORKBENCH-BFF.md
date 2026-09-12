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
| `GET /api/workbench/v1/agents` | `AGENT LIST agent:collection` | one bounded summary per Definition selected by its formal `publishedRevisionId` |
| `GET /api/workbench/v1/agents/{definition_id}/revisions/{revision_id}` | exact `AGENT READ agent:{definition_id}:{revision_id}` | only the authorized immutable Agent revision and bounded role fields |
| `GET /api/workbench/v1/employees` | `EMPLOYEE LIST employee:collection` | bounded Employee revision summaries with owner-derived `publicationState` |
| `GET /api/workbench/v1/employees/{definition_id}/revisions/{revision_id}` | exact `EMPLOYEE READ employee:{definition_id}:{revision_id}` | only the authorized immutable Employee Definition revision and digest |
| `GET /api/workbench/v1/instances/{instance_id}` | exact `INSTANCE READ instance:{instance_id}` | bounded Instance projection |
| `GET /api/workbench/v1/instances/{instance_id}/assignments/{assignment_id}` | exact `ASSIGNMENT READ assignment:{assignment_id}` | bounded Assignment projection after parent check |
| `GET /api/workbench/v1/instances/{instance_id}/assignments/{assignment_id}/placements/{placement_id}?attemptId=...&agentInstanceId=...` | exact `PLACEMENT READ placement:{placement_id}` | bounded Placement projection after complete owner parent and active-attempt checks |
| `GET /api/workbench/v1/workflows` | `WORKFLOW LIST workflow:collection` | minimal Workflow Definition summaries, when the optional Workflow registry is enabled |
| `GET /api/workbench/v1/workflows/{definition_id}/revisions/{revision_id}` | exact `WORKFLOW READ workflow:{definition_id}:{revision_id}` | only the authorized revision and bounded projections, when the optional Workflow registry is enabled |
| `GET /api/workbench/v1/authorization/continuations?state=AVAILABLE` | current authenticated subject and scope | available, unconsumed continuation references without protected resource identities |
| `POST /api/workbench/v1/authorization/grant-requests` | current authenticated subject; one continuation reference, or the existing direct exact-target mode | one persisted `PENDING` request projection after server-side requestability and target validation |
| `GET /api/workbench/v1/authorization/grant-requests/{request_id}` | applicant, or exact scoped `GRANT_ADMIN / INSPECT` | minimum request state with the persisted aggregate version |
| `POST /api/workbench/v1/authorization/grant-requests/{request_id}/decisions` | independent exact scoped `GRANT_ADMIN / DECIDE` | request-version CAS to one terminal decision and, for approval, one atomic exact-grant bundle |

All request bodies and registered query models are strict Pydantic contracts. Incoming
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

### Complete current exact-grant decision reader

The shared authority now exposes `CurrentExactGrantDecisionReader` with the
consumer-facing `authorize_current(context, grant, now=...)` shape required by
the verified Model foundation. A successful result is a complete dynamic grant
decision containing the persisted `decision_id`, exact trusted context and
`owner/action/exact_resource`, active policy generation, persisted decision
policy version, persisted decision/grant creation time as `issued_at`, and the
persisted grant expiry. Static entitlement or an existing boolean grant result
is deliberately insufficient and returns no complete dynamic decision.

`GenerationAuthorizationReader.bind_current_exact_decisions(connection,
generation=...)` is the caller-owned transaction contact. It reuses the BFF's
already-open connection without changing isolation or committing, verifies the
current credential/session, generation and recovery epoch, locks the matching
session and dynamic grant rows, and reads the exact decision from
`authorization_admin.grants`/`effective_grants`. The lower/upper validity bounds
remain `not_before <= now < expires_at`; a matching current revocation, expiry,
credential invalidation, generation mismatch or recovery invalidation returns
no decision. A protected owner transaction that reads first retains its share
locks through owner commit, while a grant/session revoke that commits first
makes the new read fail closed.

Controlled recovery continues to mark every unconsumed continuation offer
revoked and old-epoch continuation consumption remains invalid after activation.
An independently callable continuation-offer revoke/surrender command and HTTP
surface are still `OPEN`: the accepted contracts do not currently define its
actor authorization, reason/idempotency command, or audit response. This batch
does not invent those semantics.

## Startup and route separation

`app.py` retains the private service application and never registers Workbench
routes. `workbench_app` remains `None` unless all production settings succeed:
`WORKBENCH_AUTHORITY_RUNTIME_FILE`, `WORKBENCH_ALLOWED_HOST`, and
`WORKBENCH_ALLOWED_ORIGIN`; the authority database fingerprint must equal
`EXECUTION_DATABASE_URL`. Agent Definition and Digital Employee reads are composed
explicitly from their already-required durable assemblies and use the same
authorization database. Workflow Definition reads are an optional registry
extension: when `WORKFLOW_RUNTIME_DATABASE_URL` is absent, the mandatory accepted
registry remains enabled; when it is present, the
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

- Capability discovery, continuation assignment, grant revocation, and
  continuation revoke/surrender remain unregistered. The current batch also
  registers the independently authorized exact-request Decision operation; it
  adds no administrator queue, list, search, count, or enumeration. A submit can
  succeed only when the injected I1 service has
  a formal target validator: continuation mode resolves a persisted offer and
  revalidates its owner claim; direct mode preserves the existing requestability
  plus known-exact-target validation. The default composition does not invent a
  validator or an owner continuation mint rule.
- Workflow Definition LIST and exact-revision READ use the caller-owned connection
  and are registered when their optional same-database dependency is configured.
  Agent/Employee Definition exact and list reads plus Instance, Assignment, and
  Placement exact reads are registered on the same boundary. Workflow CREATE and
  all lifecycle mutations and Employee Definition lifecycle mutations remain
  unregistered. Existing header-based routes stay private.
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
| Continuation inbox, grant request submit, request inspect | `FORMALLY_REGISTERED / OWNER_VALIDATOR_REQUIRED_FOR_SUBMIT` | Session-authenticated strict routes expose only current-subject offers and minimum request state. Submit still fails closed unless the injected service can revalidate the owner target. |
| Grant decision | `FORMALLY_REGISTERED` | Independent exact `GRANT_ADMIN / DECIDE`, replay-before-CAS, request aggregate version, self-approval prohibition, closed basis mapping, bounded window and minimum result are implemented. |
| Grant revocation, continuation assignment/revoke/surrender | `COMPONENT_ONLY / NOT_REGISTERED` | Immutable revocation readback and independent continuation lifecycle semantics remain outside this accepted batch. |
| Workflow Definition read | `OPTIONAL / FORMALLY_REGISTERED` | LIST and exact-revision READ use the current authorization transaction when the optional same-database Workflow service is configured; no aggregate history or adjacent revisions are disclosed. |
| Workflow Definition lifecycle | `PRIVATE_OWNER_ROUTE_ONLY / NOT_REGISTERED` | CREATE, edit, validate, review, publish, and other lifecycle mutations are not in the public registry. |
| Agent Definition read and discovery | `FORMALLY_REGISTERED` | Exact READ and collection LIST are independent; LIST follows only the formal `publishedRevisionId`, and both use bounded DTOs on the authorization transaction. |
| Employee Definition read and discovery | `FORMALLY_REGISTERED` | Exact READ and collection LIST are independent; revision-scoped `publicationState` is derived from verified owner facts and missing/corrupt facts fail closed. |
| Employee Definition lifecycle mutation | `PRIVATE_OWNER_ROUTE_ONLY / NOT_REGISTERED` | CREATE, validation, approval, publication, and matching decisions remain private owner operations. |
| Instance, Assignment and Placement | `FORMALLY_REGISTERED` | Each exact read has its own grant. Placement requires only its exact grant but verifies the complete 310 parent chain, request binding, primary Agent identity, Runtime, and active Attempt on the caller transaction. |
| Governed Execution START and Skill dispatch | `PRIVATE_FORMAL_ROUTE_ONLY / NOT_REGISTERED` | Dispatch must consume the existing durable preparation/dispatch authorization barrier; the ordinary database owner adapter is not that barrier. |
| Execution and invocation readback | `PRIVATE_FORMAL_ROUTE_ONLY / NOT_REGISTERED` | No BFF trusted-context owner port currently couples current authorization to the formal readback. |
| Resource Use and Evidence reference | `PARTIAL_OWNER_PROJECTION / NOT_REGISTERED` | Some facts are reachable through governed Execution readback, but no accepted standalone BFF owner port exists. Evidence content/dereference remains outside the accepted contract. |

The current main frontend still uses private/preview APIs and does not consume this
new public registry. Therefore the matrix is `PARTIAL_DRAFT`: absence from the
public route set is fail-closed behavior, but it is not delivery of the missing I2
capabilities.

## Historical Agent Definition authorization gap

At the earlier checkpoint the closed authority registry had no Agent Definition owner entry:
`OWNER_ACTIONS` and `OWNER_RESOURCE_PREFIXES` in
`console/backend/src/agent_console/authority_configuration.py` contain no `AGENT`
mapping. The later Human decision in this document accepted the bounded addition,
and checkpoints `eb0512a` and `9b912f3` now register exact READ and LIST without
borrowing `EMPLOYEE` or adding lifecycle authority.

The recorded gap was a bounded exact-revision read to render the primary Agent member of
an Employee Definition without receiving Agent revision history, reviews, facts,
or adjacent revision pointers. The implemented additive contract is:

- owner/action/resource: `AGENT / READ / agent:{definition_id}:{revision_id}`;
- owner port: caller-owned connection exact-revision read with digest validation;
- response: requested Agent revision identity, digest, role content needed by 310,
  and no aggregate history or lifecycle decision collection.

The implementation affects
`console/backend/src/agent_console/authority_configuration.py`,
`agent_definition_repository.py`, `agent_definition_postgres.py`,
`agent_definition_service.py`, a new `workbench_agent.py`, explicit
`workbench_bootstrap.py`/`app.py` composition, and corresponding focused unit and
PostgreSQL authorization tests. This was an independent additive contract gap; it
does not reopen accepted ARCH-300 and does not block Employee or other already
registered owner contracts.

## Validation record

- checkpoint `17cccb3`: commit hooks passed Ruff lint, Ruff format, and pytest;
- Workflow repository, service, and owner-adapter batches from checkpoint
  `57e95d3` remain 19 passed and were not rerun by the composition increment;
- composition, public/private route inventory, startup dependency, and fail-closed
  tests: 28 passed; targeted Ruff lint and format checks passed;
- Employee exact READ focused unit/composition batch: 33 passed; targeted Ruff
  lint and format checks passed. The response excludes scope, facts, predecessor
  and adjacent Employee revisions;
- accepted-decision checkpoint `8b0ac52` records all six Human dispositions and
  constraints without reopening ARCH-300;
- batch A checkpoint `eb0512a`: Agent exact READ plus Employee exact
  `publicationState`; focused unit/composition 26 passed, related lifecycle 15
  passed and 2 skipped, and dedicated PostgreSQL authorization cases 4 passed;
- batch B checkpoint `9b912f3`: Agent/Employee LIST and signed keyset pagination;
  focused unit/composition 40 passed and dedicated PostgreSQL authorization cases
  4 passed. Agent selection uses the formal `publishedRevisionId`, so no residual
  revision-selection semantic gap was found;
- batch C checkpoint `3c3e51c`: Placement exact READ and the fixed 310
  `placement_request_matches` port; focused unit/composition 45 passed and
  dedicated PostgreSQL Placement authorization cases 2 passed. The historical
  310 end-to-end test did not reach Placement because its unchanged Agent
  migration exceeded the fixed 5-second statement timeout in both the existing
  and fresh isolated database; no timeout or retry was added;
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

This addendum records the bounded Human decision for the fixed IMPL-310 candidate
`4ef9ee40b4fb099d93823e3aa98c801e90c2087c`. The six dispositions below are
`HUMAN_CONFIRMED` for implementation in this Session. They do not authorize a
lifecycle change, frontend change, Ready transition, merge, deployment, release,
or acceptance of IMPL-299, IMPL-310, or IMPL-305 as a whole.

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
The later Human decision recorded by this addendum independently accepts those
bounded additions with the constraints below; it does not reopen or rewrite
ARCH-300.

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

| Human decision | Disposition | Exact contract | Mandatory constraint |
| --- | --- | --- | --- |
| Placement exact read | `ACCEPTED_WITH_CONSTRAINTS` | `PLACEMENT / READ / placement:{placement_id}`; typed route, verified four-ID binding, bounded DTO, uniform 404 | Use only the Placement grant for this operation; retain complete owner parent-chain, scope, Decision-to-Request-to-Attempt/Agent-Instance, and Runtime active-attempt checks. Separate related-object detail reads retain independent authorization. `compatibilityFacts` uses an explicit field allowlist and `digest` follows the formal owner definition. |
| Optional multi-grant Placement policy | `NOT_ADOPTED_FOR_FIRST_BATCH` | Do not additionally require `INSTANCE / READ / instance:{instance_id}` or `ASSIGNMENT / READ / assignment:{assignment_id}` on Placement READ | This does not grant either parent detail read and does not weaken the mandatory owner relationship checks. |
| Agent exact read | `ACCEPTED_WITH_CONSTRAINTS` | `AGENT / READ / agent:{definition_id}:{revision_id}` and the bounded single-revision response above | Return only the authorized immutable revision and the explicitly listed fields. |
| Agent discovery list | `ACCEPTED_WITH_CONSTRAINTS` | `AGENT / LIST / agent:collection`; page contract `50/200`, `definitionId` keyset, no total | Select each Definition's revision by an explicit formal owner rule; never choose the first row or implicitly follow `latest`. If the current owner rule is insufficient, record that one semantic gap and continue the other implementable work. LIST does not imply object READ. |
| Employee discovery list | `ACCEPTED_WITH_CONSTRAINTS` | existing `EMPLOYEE / LIST / employee:collection`; bounded summary and `50/200` composite-key page contract | Bind the opaque cursor to trusted scope and query conditions, enforce input validation, return only `items/nextCursor`, and disclose no total. LIST does not imply object READ. |
| Employee publication field | `ACCEPTED_WITH_CONSTRAINTS` | revision-scoped `publicationState: PUBLISHED \| NOT_PUBLISHED` derived from formal owner facts | Missing or corrupt source is an error, not `NOT_PUBLISHED`; the field implies neither matchability, runtime state, nor authorization validity. |

The accepted first implementation boundary is limited to:

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

All six accepted decision rows above are implemented in checkpoints `eb0512a`,
`9b912f3`, and `3c3e51c`. The formal Agent owner rule was sufficient: LIST uses
the aggregate's verified `publishedRevisionId` and never infers `latest` or chooses
the first revision. Remaining 305 matrix items are the separately gated grant
administration/continuation HTTP surface, governed Execution and Skill dispatch,
Execution/invocation readback, standalone Resource Use/Evidence reference reads,
frontend consumption, I3/deployment isolation, and complete 299 acceptance.

That batch does not authorize lifecycle operations, migrations unless separately
required and approved, frontend rewiring, I3/deployment proof, merge, or release.

These bounded additions are `HUMAN_CONFIRMED` and their implementation checkpoints
have passed the evidence stated above. Delivery remains
`PARTIAL_DRAFT / SESSION_OPEN`; Draft PR #164 must not be made Ready, merged, or
deployed by this addendum.

## S5-V023-IMPL-305 recovery batch for 308

The exact-decision dependency batch changed only the shared authority contracts,
application adapter, PostgreSQL adapter, focused authority PostgreSQL tests, and
this implementation record. It did not change the 308 Model registry entries or
the 308 branch, and it had no path overlap with the current 299 branch diff.

Validation executed for this batch:

- focused non-database authority tests: `14 passed`;
- exclusive real PostgreSQL 15 exact-decision and recovery-continuation tests:
  `2 passed, 12 deselected`;
- complete exclusive real PostgreSQL 15 authority contract file: `14 passed`;
- repository `make check`: Ruff lint and format checks passed, followed by
  `1649 passed, 154 skipped` (environment-gated suites remain explicitly
  skipped by the repository baseline).

The batch remains part of the existing Draft PR #164 and does not authorize
Ready, merge, deployment, or closure of the full 305 Session.

## S5-V023-IMPL-305 recovery batch for IMPL-299 authorization ports

Recovery source is commit `5948a499de16a59d785774b67823bd8bb4521983`,
tree `967dcd0682a5c1ad0e6dc0144d82e43cb2b1f7c2`. The read-only IMPL-299
handoff is fixed at commit `b7123ae0c1c70992f4fb5a65bec5ff24283ecaf9`, tree
`dacd0da76ef3cc7821ab6636bfd94c42a5c29c50`. IMPL-299's PostgreSQL
service evidence is inherited as service-level evidence only; it contains no
trusted-browser acceptance.

This batch adds three session-authenticated routes:

| Route | Strict input | Minimum output | Authorization and validation |
| --- | --- | --- | --- |
| `GET /api/workbench/v1/authorization/continuations?state=AVAILABLE` | the query must be exactly one `state=AVAILABLE` | `continuations[]` with `continuationId`, `purpose`, `expiresAt`, `requestableActions` | current session subject/scope; only unexpired, issued, current-generation, current-recovery, unrevoked and unconsumed offers |
| `POST /api/workbench/v1/authorization/grant-requests` | `exact-grant-request.v1`, bounded purpose, and exactly one source: one `continuationId` or one-or-more `requestedGrants`; `Idempotency-Key`; session CSRF | `requestId`, `PENDING`, persisted `aggregateVersion`, `submittedAt`, `purpose`, action labels | continuation reference is resolved from PostgreSQL under the current subject/scope and its fixed members are revalidated by the owner validator; direct mode retains requestability plus known-exact-target validation |
| `GET /api/workbench/v1/authorization/grant-requests/{request_id}` | typed path only | the same request status shape, with current persisted version and no exact resource | applicant, or current exact `GRANT_ADMIN / INSPECT / grant-scope:{tenant}:{security_domain}`; unknown, hidden, foreign-scope and unauthorized requests share `404 AUTHORIZATION_REQUEST_NOT_FOUND` |

The inbox never returns an encoded continuation payload. It returns
`continuation-ref.<sha256>` derived from the already persisted signed envelope.
The digest is a stable opaque offer reference; PostgreSQL resolves it only for
the current bound subject/scope, issued/expiry interval and recovery epoch. The
application then checks policy generation, purpose and the complete offer members
and invokes the owner validator in the request transaction before unique
consumption. The browser therefore neither receives nor constructs a hidden exact
target in continuation mode. Direct mode is separate and can use only a target
that the server's existing validator proves known and requestable.

`BUSINESS_PROBLEM / READ / business-problem:collection` is added only to the
closed `BROWSER_BOOTSTRAP` configuration allowlist because the existing Problem
create owner operation requires collection CREATE and collection READ. The loader
does not inject it into every credential: a deployment must explicitly place the
tuple in that credential's immutable generation. The allowlist rejects
`business-problem:{id}` as a bootstrap grant, and collection READ never implies
exact READ for a newly created Problem.

The login form's successful GET response alone uses
`Referrer-Policy: same-origin`, so its same-origin form POST can carry Origin as
required. Every other successful or error response retains `no-referrer`.

### IMPL-299 wiring instruction

After a future accepted Problem owner adapter commits the canonical Problem
identity/revision and persists the creator offer, IMPL-299 should:

1. retain the exact opaque continuation reference correlated by the accepted
   Problem-create response, or replay that create with the same domain
   idempotency key to recover the same correlation; do not select among inbox
   offers by purpose/action labels alone;
2. submit exactly that one reference with a stable request idempotency key and no
   `requestedGrants` member;
3. persist only the returned `requestId` as navigation/recovery state and poll the
   applicant request-status route;
4. render `PENDING` or `REJECTED` as non-authorized states; after `APPROVED`, call
   the already registered exact Problem READ route using the canonical Problem ID
   from the formal create response; and
5. let that exact READ reauthenticate the session and re-evaluate the current
   grant/decision in its caller-owned transaction. The request status, an
   `APPROVED` label, a cached boolean, and collection READ are never substitutes
   for that current exact authorization.

This wiring requires no public decision DTO in the ordinary 299 page. An
independent administrator decision entry remains necessary somewhere outside the
applicant page before status can become approved.

### Validation for this recovery batch

- source/mock: focused Ruff lint/format and BFF/bootstrap/config tests cover exact
  route/schema composition, unauthenticated and foreign Origin/Host/header/CSRF
  rejection, the narrow login header exception, continuation/direct-source
  exclusivity, conflict mapping, foreign request hiding and minimum status
  projection;
- real PostgreSQL 15: the complete authority foundation file covers subject/scope,
  expiry, future-issued and generation rejection, unique consumption, same-key
  replay, changed-payload conflict, recovery invalidation, applicant/admin inspect,
  and request aggregate version `1 -> 2`; a focused HTTP case uses the real
  Browser Session Authority, PostgreSQL repository and public BFF routes;
- real browser: a local browser used the real login form/session and PostgreSQL
  fixture offer to call inbox, submit and inspect. The visible projection showed
  an opaque reference, `202 PENDING`, and aggregate version 1 without the hidden
  Problem target. It used a loopback HTTP-only harness because the browser
  correctly rejected the temporary self-signed HTTPS certificate; therefore it
  is not TLS, ingress/network isolation, production composition, I3, or complete
  trusted-browser acceptance evidence.

The fixture offer proves only the three public ports. It does not prove
`Problem create -> owner mint -> request -> decision -> exact read`, and it does
not change IMPL-299 from `NOT_EVIDENCED` at the trusted-browser product level.

## Human-accepted creator READ continuation and administrator Decision batch

Status: `ACCEPTED_FOR_IMPLEMENTATION_WITH_ONE_TIME-ANCHOR_DECISION_PENDING`.

The Human continuation record after checkpoint `e3efd945` accepts only one
creator continuation purpose and member:

- purpose `CONTINUE_PROBLEM_READ`;
- exactly `BUSINESS_PROBLEM / READ /
  business-problem:{businessProblemId}`;
- canonical reference derived from the committed owner result;
- mint identity bound to the original create command and immutable revision-1
  result, never to a later Problem revision;
- one typed `creatorContinuation` correlation returned by create, with no inbox
  purpose/action guessing;
- continuation request source exclusivity: one continuation reference and no
  `requestedGrants` in the same command;
- separate owner-commit and Grant Administration mint transactions; mint failure
  never compensates or deletes the Problem;
- same-create-command recovery without duplicate create, expiry reset, or
  automatic replacement offer;
- current owner-fact validation again at consumption; and
- no Plan `PREPARE`, mutation permission, collection permission, wildcard, or
  other authority.

That acceptance does **not** accept the earlier `created_at` time anchor. Source
inspection proves that Problem `created_at` is generated by the application
before the caller-owned owner transaction, while the existing owner idempotency
result stores only `revision_id`. Neither fact proves the database commit time or
an immutable complete creation receipt.

### Creator-origin receipt time anchor — PROPOSED / HUMAN DECISION REQUIRED

The proposed recovery foundation is an immutable creator-origin receipt inserted
in the same owner transaction as Problem creation and visible only after that
transaction commits. Its minimum persisted facts are tenant/namespace, security
domain, creator principal, original create command identity, Business Problem ID,
revision ID and number, aggregate version, revision digest, canonical resource
reference, committed-owner-revision encoding, and one database-clock timestamp.
The minimum uniqueness is the trusted scope plus creator principal plus original
create command identity; a second row or different immutable result under that
identity is a conflict. Mint and mint recovery must load this receipt by the
original create identity and use only its immutable values. Later Problem
revisions cannot change it. Existing Problems without a receipt fail closed and
must not receive a backfilled or inferred historical receipt.

PostgreSQL time captured inside the transaction is **not the actual commit
timestamp**. If an actual commit timestamp cannot be obtained as a durable,
portable owner fact, the concrete proposal is to use the receipt's transaction-
persisted database time as a conservative start point for the ten-minute mint
window. Commit delay can then make the usable post-commit window shorter or end
it before mint, but can never extend the window because of that delay. This one
choice remains `PROPOSED / HUMAN DECISION REQUIRED` and blocks only mint behavior
that depends on the ten-minute anchor. It is not recorded as accepted here.

The independent administrator Decision contract is accepted exactly as follows:

- `expectedVersion` is `authorization_admin.grant_requests.aggregate_version`;
  after `FOR UPDATE`, both the numeric version and `PENDING` state must match;
- every call reauthenticates and independently requires exact
  `GRANT_ADMIN / DECIDE / grant-scope:{tenant}:{security_domain}`;
- same key/same canonical wire payload replays the original result before CAS;
  same key/different payload is `IDEMPOTENCY_PAYLOAD_MISMATCH`; a different key
  losing concurrent or terminal CAS is `AUTHORIZATION_STATE_STALE`;
- issuer equal to immutable request subject is
  `GRANT_SELF_APPROVAL_PROHIBITED` with zero writes;
- public basis type is closed to `TICKET | POLICY`, explicitly mapped one-to-one;
  only its canonical type/reference digest is persisted, with the documented
  inability to reconstruct, search, or externally verify the source evidence;
- the response is the minimum decision DTO and exposes no request members,
  internal meta-decision, policy/audit fields, basis digest, or grant list;
- `INSPECT` does not imply `DECIDE`, and this batch adds no cross-subject list,
  search, queue, count, enumeration, revoke, or surrender operation;
- APPROVE requires `expiresAt`; omitted `notBefore` becomes the first winning
  transaction's `server_now`, explicit `notBefore` cannot precede that time, and
  `effective_not_before < expiresAt <= effective_not_before + 8 hours`;
- REJECT forbids both time fields; replay returns the first stored times without
  recalculation; and
- terminal `APPROVED` does not replace current exact-grant authorization on READ.

### G1 implementation plan

1. Extend the internal decision command/repository result with request aggregate
   CAS and effective time facts, keeping the existing PostgreSQL authority as
   owner and adding no persistence dependency.
2. Move request disclosure and issuer/subject enforcement into the locked
   repository transaction after replay lookup; validate closed basis and the
   accepted approval/rejection time union in the application.
3. Register one strict session/CSRF/Host/Origin-protected exact-request Decision
   route and map only the accepted bounded errors/result fields.
4. Validate service/repository CAS, replay ordering, concurrent terminal conflict,
   self-approval zero-write, time bounds, exact DECIDE independence, public
   boundary rejection, real PostgreSQL, public HTTP, and real browser evidence.
5. Leave creator mint unimplemented until the receipt time-anchor choice is
   accepted; independently document its fail-closed migration and recovery facts.

### Decision implementation checkpoint

Checkpoint `a0f0d64` completes the independent Decision portion without a
migration. `GrantDecisionCommand` and `GrantAdministrationRepository` require the
request aggregate version and trusted issuer scope. The PostgreSQL adapter first
checks current recovery, verifies immutable subject/scope, locks the scoped
idempotency claim, returns an equal replay before CAS, then locks the request
`FOR UPDATE` and compares both `aggregate_version` and `PENDING`. A winning
approval captures `clock_timestamp()` inside that transaction after the lock,
normalizes omitted `notBefore`, validates the eight-hour maximum, persists the
decision and complete grant bundle atomically, and increments the request to
version 2. Replay reconstructs the original persisted decision time and grant
window. Rejection persists no grant or validity window.

The public route uses the existing browser authentication, exact Host/Origin,
session CSRF, untrusted-header rejection and no-store boundary. Its first success
is `201`, equal replay is `200`, and the typed result contains only schema,
request/decision IDs, terminal state, request aggregate version, decision time,
and approval window when applicable. It exposes no request member, basis value or
digest, grant ID, meta-decision, policy version, or audit source.

Validation at this checkpoint:

- focused source/BFF/bootstrap/app: Ruff passed and `34 passed`;
- repository `make check`: Ruff lint, Ruff format check over 409 files, and
  `1662 passed, 156 skipped`;
- complete backend without external-service variables: `674 passed, 151
  skipped`; the skips remain the repository's explicit external PostgreSQL,
  Qdrant and dedicated fixture gates;
- real PostgreSQL 15, one isolated database per case: `16 passed`, including
  numeric CAS, same-key replay and mismatch, different-key terminal concurrency,
  self-approval zero-write, closed basis/time validation, DECIDE versus INSPECT,
  public session/CSRF routes, and applicant status readback;
- public loopback HTTPS HTTP client against Uvicorn and real PostgreSQL: session
  create `303`, first Decision `201 APPROVED`, request version 2, and only the
  accepted minimum response fields; and
- real browser against a temporary loopback HTTP-only Uvicorn harness and real
  PostgreSQL: authenticated session `200` as `human:browser-admin`, first Decision
  `201 APPROVED`, request version 2, and persisted `decidedAt == notBefore` when
  the browser omitted `notBefore`. The browser rejected the temporary self-signed
  HTTPS certificate and no safety bypass was attempted. Therefore this last item
  is browser behavior evidence, not TLS, ingress, network isolation, production
  composition, I3, or complete 299 product acceptance.

### Exact IMPL-299 handoff boundary after this checkpoint

IMPL-299 owns only applicant experience wiring after a creator receipt time anchor
is accepted and the owner mint portion is implemented in 305. It must retain the
typed `creatorContinuation` returned by the corresponding Problem create/replay,
submit exactly that reference with no `requestedGrants`, persist only its returned
request ID for recovery/navigation, and poll the existing minimum applicant
status. It must not choose an offer from inbox labels, add Plan `PREPARE`, embed an
administrator Decision form in the applicant flow, or treat `APPROVED` as current
authorization. The independent administrator may use the exact request-ID
Decision route implemented here through a separately authorized entry. After
approval, 299 must call the existing exact Problem READ route, which reauthenticates
and reevaluates the current owner/grant facts. Until the one receipt time-anchor
decision is accepted and creator mint exists, 299 must keep create-to-read
continuation fail closed and must not synthesize or backfill a reference.

The detailed pre-acceptance proposal text below is retained as provenance. Where
it labels the now-accepted Decision or READ-only creator shape `PROPOSED`, the
Human-accepted batch above supersedes that old status. Its `created_at` issuance
anchor is explicitly **not accepted** and is superseded only by the separate
receipt proposal above, which remains pending.

### Concentrated open-decision overview

| Topic | Existing contract | Concrete gap | Recommended Human decision | Alternative | Impact | Blocks complete IMPL-299 loop |
| --- | --- | --- | --- | --- | --- | --- |
| Problem creator continuation | Owner-minted, subject/scope-bound, at-most-ten-minute offer persisted after canonical owner commit; request members cannot be widened by the browser | Exact creator members, canonical Problem reference, owner revision encoding, and replayable post-commit mint hook are not frozen | First batch: freeze one Problem-owned exact `READ` offer over the immutable committed create result and recover it by the original command identity | Separately accept the ARCH-300 example's expanded `READ` plus Plan `PREPARE` bundle, or keep new Problems fail-closed pending administrator assignment | Business Problem application/owner adapter, grant target validator, create response and tests | **Yes** for create-to-exact-read |
| Administrator decision CAS and basis | Independent exact `GRANT_ADMIN / DECIDE`; service and repository prohibit self-approval and atomically move `PENDING` to a terminal state | Browser command has no accepted `expectedVersion`; `basisReference` has no authoritative mapping to the persisted closed `basis_type` | Add `expectedVersion` to the decision command and compare the locked aggregate version; freeze a closed external basis enum and one mapping to internal `basis_type`, retaining a digested reference | Keep decision on a private/internal administrator tool and expose only applicant status | BFF schema/route, application command, PostgreSQL CAS, errors and admin tests | **Yes** for an independently approved browser journey |
| Grant revoke | Revocation fact and effective-grant removal are atomic; current reads fail after commit | Public CAS, immutable revocation identity/version/result and subject/admin readback are absent; current repository returns only boolean | Freeze expected grant version plus immutable `revocationId`, version and readback projection before adding the route | Keep revoke internal and rely on expiry for this preview | Authority contract/application/repository/BFF and revocation race tests | **No** for the minimal create-to-read step; **yes** for full grant lifecycle acceptance |
| Continuation offer revoke/surrender | Expiry, consumption, generation and recovery invalidation already fail closed | Actor authorization, reason/idempotency command, immutable result and distinction between administrator revoke and subject surrender are undefined | Define one append-only offer-revocation contract with separate authorized actor cases and replay semantics | Retain expiry/recovery/consumption only and expose no route | Continuation contract, persistence, inbox filtering, BFF and audit tests | **No** for the minimal create-to-read step; **yes** for full continuation lifecycle acceptance |

### Expected-version source calibration

The earlier statements "accepted input already has `expectedVersion`" and "there
is no accepted `expectedVersion`" each collapse distinct evidence. The precise
source classification is:

| Question | Exact source | Finding |
| --- | --- | --- |
| What status does the architecture document itself display? | `architecture/s5/v0.2/S5-V023-ARCH-300-TRUSTED-BROWSER-IDENTITY-EXACT-RESOURCE-AUTHORIZATION-V1.md`, decision record lines 3-18 | The retained candidate snapshot says `Decision status: Proposed`, `Implementation status: Not Started`, and explicitly says it is not Human-accepted. This literal snapshot is historical metadata, not the later acceptance record. |
| Does the decision example contain the field? | the same architecture artifact, section 8.5, lines 732-755 | Yes. The illustrative `exact-grant-decision.v1` body contains `"expectedVersion": 1`; sections 6.2 and 7 also require a CAS-protected current projection/CAS generally. The example does not say which persisted aggregate the integer denotes or define replay-versus-CAS ordering. |
| Is there an explicit Human acceptance record for this exact field contract? | this implementation record, `ARCH-300 status calibration`, plus accepted source `4b8672cda51325322d4ec7dc0ac3d78df471d08b` and PR #161 merge `270d193b936a61c65d4fa20d9a62709a5c2b56ad` | The later record establishes `HUMAN_ARCHITECTURE_ACCEPTED_WITH_CONSTRAINTS` for the fixed architecture candidate. No inspected record separately freezes the decision example's `expectedVersion` aggregate, lock/CAS semantics, or replay ordering. Field-level Human acceptance is therefore **`UNKNOWN`**, not disproved and not inferred from example presence; the missing field-level record also does not invalidate or reopen the overall Human acceptance. |
| Does the current command/repository carry it? | `grant_administration_application.py`, `GrantDecisionCommand` lines 56-65 and `decide_request` lines 595-680; `authority_contracts.py`, `GrantAdministrationRepository.decide_request` lines 316-325; `authority_postgres.py`, `decide_request` lines 1233-1333 | No numeric expected version crosses the application or repository port. The application passes only `expected_status=PENDING`; the repository claims idempotency, locks the request, compares only its state, then increments `grant_requests.aggregate_version`. This is terminal-state serialization, not the example's explicit numeric CAS. |
| Is there a public browser port? | `workbench_bff_schemas.py` lines 45-81 and `workbench_bff.py` lines 357-439 | No. The public surface has continuation inbox, request submit, and request inspect contracts only. There is no decision request/response schema and no `/decisions` route. |

Accordingly, the accepted architecture supplies the general CAS, independent
administrator and self-approval constraints. The example supplies evidence that
an `expectedVersion` field was contemplated. The complete field semantics below
remain **`PROPOSED / HUMAN_ACCEPTANCE_REQUIRED`**. The current implementation gap
must not be rewritten as an absence of architecture intent.

### Contract proposal 1 — Problem creator continuation

#### Existing accepted contract and current gap

The **existing accepted architecture contract** requires the resource owner to
mint a subject/scope-bound opaque offer only after durable canonical owner commit,
with at most a ten-minute lifetime, fixed members, keyed replay, atomic
consumption, and no browser-controlled identity or member widening (ARCH-300
sections 6.2-6.3). It explicitly describes a recoverable cross-authority protocol,
not one transaction spanning owner and Grant Administration.

The **current implementation gap** is bounded but material. Problem create returns
the committed `BusinessProblemRevision`; revision 1 is encoded today as
`revision_id = f"{business_problem_id}:1"`, numeric `revision = 1`, and aggregate
version 1 (`business_problem_application.py`, lines 116-139). The public operation
envelope has only an unstructured `continuationIds` tuple, and the generic owner
transaction commits only when `WorkbenchOwnerAuthorization.execute` returns.
`GrantAdministrationService.mint_owner_continuation` and durable offer storage
exist, but no Problem-specific post-commit coordinator constructs the claim,
freezes its members, or correlates its stable reference with the create result.

#### Recommended exact contract — PROPOSED

| Element | Recommended exact value or rule — `PROPOSED` |
| --- | --- |
| Purpose and multiplicity | First batch: mint exactly one creator offer with purpose `CONTINUE_PROBLEM_READ` for each successfully committed Problem-create command identity. Do not mint one offer per member. `CONTINUE_PROBLEM_PLAN` is reserved for the separately accepted expanded option below. |
| Canonical Problem reference | `canonical_resource_reference = "business-problem:" + businessProblemId`, exactly the existing exact Problem resource name. It is built from the committed owner result, never from a follow-up browser field. |
| Owner revision encoding | Build canonical UTF-8 JSON with sorted keys and no insignificant whitespace from `{schemaVersion:"problem-owner-revision.v1", tenantId, securityDomain, businessProblemId, revisionId, revision, aggregateVersion, digest}` using only the committed revision/aggregate facts. Store `owner_revision = "problem-owner-revision.v1.sha256." + lowercase_hex(sha256(json_bytes))`. The Problem validator must reload that exact revision in the claim's trusted scope and reproduce the value; `revisionId`, numeric revision, aggregate version, and digest are all bound and none is parsed from the hash. |
| Recommended first-batch member | Exactly one member: `BUSINESS_PROBLEM / READ / business-problem:{businessProblemId}`. It contains no Problem `REVISE`/`TRANSITION`, Plan permission, Criterion/Criteria Set permission, meta-grant, wildcard, or collection grant. This is the minimum bundle that closes create-to-exact-read. |
| Subject and scope | `subject_principal_id`, tenant and security domain come only from the `TrustedRequestContext` that authorized the create. `ownerId`, request JSON, headers and browser-returned values cannot supply or override them. |
| Mint call point and transaction boundary | First finish `WorkbenchOwnerAuthorization.execute(CREATE_PROBLEM, ...)` and exit its connection scope so the Business Problem transaction has committed. Then a BFF-level Problem-create coordinator builds the descriptor from that returned committed revision and calls `mint_owner_continuation` on Grant Administration. Offer persistence is a second PostgreSQL authority transaction. No code or document may call this one cross-authority transaction. |
| Origin-command mint key | `mint_key = "problem-create-continuation.v1.sha256." + lowercase_hex(sha256(canonical_json))`, where `canonical_json` is built only from the original immutable committed create result and command identity: `{owner:"BUSINESS_PROBLEM", tenantId, securityDomain, subjectPrincipalId, purpose:"CONTINUE_PROBLEM_READ", canonicalResourceReference, committedOwnerRevision, originatingCommandIdempotencyKey}`. The committed owner revision is the revision-1 encoding above; the coordinator must never substitute the Problem's later current revision, aggregate version or lifecycle state. Consequently, after later Problem revisions, the same create key still recovers the same original offer/reference. The raw browser idempotency key is never returned. Same key plus the same canonical mint payload returns the stored offer/reference; same key with any different semantic payload returns `409 IDEMPOTENCY_PAYLOAD_MISMATCH`. |
| Issuance and expiry | `issuedAt` is the committed revision's `created_at`; `expiresAt = issuedAt + 10 minutes`. Those values are deterministic across create replay. A first post-commit mint attempted at or after expiry creates no offer and reports the expired recovery state below. |
| Create response correlation | Add exactly one typed `creatorContinuation` member beside the committed Problem result. Its exact fields are `schemaVersion: "problem-creator-continuation.v1"`, `relation: "PROBLEM_CREATOR"`, `purpose: "CONTINUE_PROBLEM_READ"`, `state: AVAILABLE \| CONSUMED \| EXPIRED`, `expiresAt: UTC timestamp`, optional `continuationId: "continuation-ref.<64 lowercase hex>"`, and optional `requestId`. `continuationId` is required for `AVAILABLE` and `CONSUMED`, and for `EXPIRED` when an offer had been persisted; it is absent only when the deterministic mint window elapsed before any offer commit. `requestId` is required only for `CONSUMED` and absent otherwise. The same response contains `businessProblemId`, `revisionId`, `aggregateVersion` and digest, so the association is explicit without adding a resource identity to the ordinary inbox. |
| Multiple equal-label offers | `purpose` and action labels are display metadata and are never a selector. Each offer has its own stable `continuationId`; the client stores the one from the corresponding create response. If response recovery is needed, it replays that exact create command and recovers the same reference. Two Problems with identical purpose/actions remain distinct because their canonical reference, owner revision, mint key and opaque reference differ. |
| Member immutability | Continuation-mode request submission must carry exactly one `continuationId` and zero `requestedGrants`. Resolution replaces no members: for the first batch it loads only the persisted exact Problem READ member and revalidates the committed owner revision. The same reference can never request a subset, superset, different action, different target, different subject or different scope. |
| Commit/mint failure state | If owner commit succeeds and mint is definitely or possibly uncommitted, return `503 CONTINUATION_MINT_UNAVAILABLE`; do not delete or compensate the Problem. A retry must use the same Problem-create idempotency key: owner replay returns the same revision, then the coordinator resumes the same mint key. If offer persistence committed but the response was lost, replay returns the already stored opaque reference and does not repeat create. |
| Response loss and offer state | A first successful response returns `AVAILABLE`. If that response is lost, same-key create replay reads the committed Problem result and the persisted offer by mint key, then returns the same `continuationId`, original `expiresAt` and current state; it does not regenerate the envelope or timestamps. Expiry never rolls back the Problem and never auto-mints a replacement: replay returns `EXPIRED`; if no offer ever committed, the response has no `continuationId`. After consumption, replay returns `CONSUMED`, the same reference and its `requestId`; grant-request status is authoritative for that request. Same create key/same payload replays, same key/different create payload keeps the existing owner idempotency conflict, and a different create key is a different create command that may create a different Problem. |

The recommended response addition is deliberately creator-specific. It does not
turn the generic inbox into a protected-resource directory, and it does not make
an offer, a `PENDING` request, or an `APPROVED` status into authorization.

**Extension option requiring separate explicit Human acceptance:** use purpose
`CONTINUE_PROBLEM_PLAN` and the ordered all-or-nothing members (1)
`BUSINESS_PROBLEM / READ / business-problem:{businessProblemId}` and (2)
`PLAN / PREPARE / plan:prepare:{businessProblemId}`, matching the ARCH-300 section
8.4 example. This option must have a distinct purpose and mint key from the
recommended READ-only first batch; accepting the READ-only contract does not
accept or silently upgrade an existing reference to the expanded bundle.

**Impact and gate:** affected future paths are the Problem-create BFF coordinator
and response schema, the Business Problem continuation validator, Grant
Administration owner-mint integration, and focused commit/mint/replay tests. It
**blocks IMPL-299's create -> request -> exact Problem read path**. It does not
authorize implementation in this batch.

**Exact Human acceptance requested:** accept or reject the recommended READ-only
first-batch contract: its purpose, one exact member, canonical reference, hashed
committed owner-revision encoding, post-commit call point, deterministic mint
key/times, typed response/state correlation, same-reference immutability, and
failure/expiry/consumption replay rules. Decide the two-member READ plus Plan
PREPARE option independently. Until an explicit Human record accepts either, both
remain `PROPOSED` and no Problem creator mint route or hook may be implemented.

### Contract proposal 2 — Grant decision CAS and basis

#### Existing accepted contract and current gap

The **existing accepted architecture contract** requires independent exact
`GRANT_ADMIN / DECIDE / grant-scope:{tenant}:{security_domain}`, issuer/subject
inequality without exception, append-only decision/grant facts, atomic bundle
activation, validity bounds, CAS, and idempotent replay. Its section 8.5 example
contains `expectedVersion`, but, as calibrated above, the exact field semantics
have no separately proven Human freeze and are **`UNKNOWN`**.

The **current implementation gap** is exact: `GrantDecisionCommand` has no
`expected_version`; the repository receives only `expected_status=PENDING`, claims
the idempotency key before locking the request, locks and checks only the state,
then increments `authorization_admin.grant_requests.aggregate_version`. Both
`basis_type` columns are unconstrained `text`; the application accepts any bounded
label. Tests use `TICKET`, but a fixture literal is not a public enum or Human
acceptance. No browser decision schema/route exists.

#### Minimal wire contract — PROPOSED

Approval request:

```http
POST /api/workbench/v1/authorization/grant-requests/grant-request-123/decisions
Idempotency-Key: decision-command-123
Content-Type: application/json

{
  "schemaVersion": "exact-grant-decision.v1",
  "expectedVersion": 1,
  "decision": "APPROVE",
  "reasonCategory": "ASSIGNED_BUSINESS_DUTY",
  "basisType": "TICKET",
  "basisReference": "SEC-1234",
  "expiresAt": "2026-09-12T22:00:00Z"
}
```

Approval response (`201` first commit, `200` same-key/same-payload replay):

```json
{
  "schemaVersion": "exact-grant-decision-result.v1",
  "requestId": "grant-request-123",
  "decisionId": "grant-decision-456",
  "state": "APPROVED",
  "aggregateVersion": 2,
  "decidedAt": "2026-09-12T14:00:00Z",
  "notBefore": "2026-09-12T14:00:00Z",
  "expiresAt": "2026-09-12T22:00:00Z"
}
```

Rejection uses the same route and headers with this complete body; both validity
fields are absent:

```json
{
  "schemaVersion": "exact-grant-decision.v1",
  "expectedVersion": 1,
  "decision": "REJECT",
  "reasonCategory": "BUSINESS_DUTY_NOT_ESTABLISHED",
  "basisType": "TICKET",
  "basisReference": "SEC-1234"
}
```

Its first/replay response has the common six result fields through `decidedAt`,
with `state: "REJECTED"`; it omits `notBefore`, `expiresAt` and any grant list.
The browser does not receive
`issuerMetaDecisionId`, policy version, audit source, basis digest, request
members, or the complete `CurrentExactGrantDecision` internal record through this
mutation response.

#### Recommended exact contract — PROPOSED

| Element | Recommended exact value or rule — `PROPOSED` |
| --- | --- |
| CAS aggregate | `expectedVersion` is the positive current `aggregate_version` of the persisted `authorization_admin.grant_requests` row identified by path `requestId`; it is the same version exposed by the existing minimum request-status response. It is not a grant version, decision version, policy generation, recovery epoch, or owner aggregate version. |
| Locked CAS | In the decision transaction, lock that request row `FOR UPDATE`, then require both `aggregate_version == expectedVersion` and `state == PENDING`. The winning approve/reject appends one decision, atomically appends all grants or none, changes the request to `APPROVED`/`REJECTED`, and increments the request version exactly once. |
| Replay before CAS | Reauthenticate and reauthorize current exact `GRANT_ADMIN/DECIDE` on every call. Inside the same recovery-epoch transaction, resolve/lock the scoped `(issuer, DECIDE_GRANT_REQUEST, Idempotency-Key)` claim and compare the canonical wire-payload digest **before** applying the request CAS. Same key/same payload returns the already committed result even though the request is now terminal/version 2; same key/different payload returns `409 IDEMPOTENCY_PAYLOAD_MISMATCH` and never falls through to CAS. A new key always proceeds to the locked CAS. `expectedVersion`, explicit-or-omitted `notBefore`, and `expiresAt` are included in that digest. Replay reads the stored effective window and never recomputes time. |
| Competing and terminal decisions | Different-key concurrent `APPROVE`/`REJECT` commands may both validate initially, but only one wins the request lock/CAS. The loser returns `409 AUTHORIZATION_STATE_STALE` with no decision/grant write. Any new-key command against `APPROVED` or `REJECTED`, including a semantically equal decision, returns the same stale error; terminal state is not converted or appended again. |
| Basis enum and source | Public `basisType` is the closed enum `TICKET \| POLICY`. `TICKET` is evidenced by existing authority tests; `POLICY` and the two-category boundary are evidenced only by ARCH-300 section 8.5's `ticket-or-policy-reference` placeholder. Neither evidence alone is Human acceptance, so both enum values and closure are part of this proposal. No `OTHER`, free-form type, URL type, or browser-defined type is accepted. |
| Authoritative basis mapping | The BFF maps public `TICKET` -> internal `basis_type = "TICKET"` and public `POLICY` -> internal `basis_type = "POLICY"`; there is no inference from the text of `basisReference`. It validates `basisReference` as trimmed UTF-8, 1-512 characters, with no control characters, then the application persists only `sha256(canonical_json({type:basis_type, reference:basisReference}))` as the existing `basis_reference_digest`. `basisReference` itself is not returned to the applicant or stored in the current authority tables. |
| Basis audit capability and limit | The stored type plus digest can bind the decision and its grants to one exact normalized basis value and can later verify equality if an authorized audit process independently supplies the original type/reference. The authority database cannot recover the original reference from the digest, search reliably by a raw reference, prove that a ticket/policy exists, authenticate its issuer, verify its contents or approval, or establish that it remains current. Such external evidence verification requires a separately accepted integration/audit record and is not claimed here. |
| Independent administrator | Before request disclosure or mutation, require current exact `GRANT_ADMIN / DECIDE / grant-scope:{trusted tenant}:{trusted security domain}` from the authenticated administrator's trusted context. Neither `INSPECT`, `REVOKE`, continuation assignment, creator status, request ownership, nor a dynamic grant implies `DECIDE`; dynamic meta-grants remain prohibited. |
| Administrator entry by exact request ID | The applicant or an existing Human/business workflow conveys the opaque `requestId` to the independent administrator out of band, for example in the `TICKET`/`POLICY` workflow named by `basisReference`. The administrator enters the exact request URL or private-tool command containing that ID. Reading its minimum status first uses the existing exact request-inspect operation and independently requires `GRANT_ADMIN / INSPECT`; submitting the decision requires `GRANT_ADMIN / DECIDE` and does not inherit INSPECT. The decision service may load the exact request internally after DECIDE authorization. This proposal adds no pending-request queue, cross-subject list/search, count, enumeration permission, or delivery of the applicant's inbox to administrators. |
| No self-approval | Compare the authenticated issuer principal with the immutable request subject inside the locked decision transaction. Equality returns `409 GRANT_SELF_APPROVAL_PROHIBITED`; there is no static-policy, meta-grant, role, same-key, or replay exception and zero decision/grant writes occur. |
| Validity window | For `APPROVE`, `expiresAt` is required and `notBefore` is optional; both, when supplied, must be UTC timestamps. Capture one `server_now` in the winning transaction. If `notBefore` is omitted, persist `effective_not_before = server_now` and the grant is immediately eligible after commit. If supplied, require `server_now <= notBefore` and persist it unchanged. In both cases require `effective_not_before < expiresAt <= effective_not_before + 8 hours`. The first commit stores and returns the effective values; same-key replay returns them unchanged and does not recalculate `server_now`, `notBefore` or `expiresAt`. `REJECT` forbids both fields. The eight-hour cap is a bounded first-journey recommendation aligned with the accepted maximum browser-session duration, not an already accepted dynamic-grant lifetime; it is explicitly part of the requested Human decision. Grant currentness remains `not_before <= read_now < expires_at`. |
| Error semantics | Missing/hidden/foreign-scope request or missing current DECIDE authority: `404 AUTHORIZATION_REQUEST_NOT_FOUND`; stale version or already terminal under a new key: `409 AUTHORIZATION_STATE_STALE`; same key/different payload: `409 IDEMPOTENCY_PAYLOAD_MISMATCH`; issuer equals subject: `409 GRANT_SELF_APPROVAL_PROHIBITED`; invalid enum, reference, decision union, version or time window: `422 INVALID_GRANT_DECISION`; unavailable/recovery-closed authority: `503 GRANT_AUTHORITY_UNAVAILABLE`. All failures write no partial decision or grant bundle. |
| `APPROVED` versus a current grant | `APPROVED` is the immutable terminal state of the request and proves only that its decision and full grant bundle committed. It does not prove that any grant is currently effective: `notBefore`, expiry, grant/session/credential revocation, active generation, recovery epoch, subject/scope and exact tuple must still pass. Every exact Problem READ reauthenticates and calls the current exact-grant reader in its owner transaction; the status response, decision response, cached boolean or possession of a `decisionId` is never authorization. |

**Alternative:** keep decision entry exclusively on a private/internal
administrator tool. That tool must still adopt the same request-aggregate CAS,
replay order, closed basis mapping, independent DECIDE and no-self-approval rules;
the public applicant surface remains request status only. This avoids a browser
administrator route but does not supply a complete independently approved browser
journey.

**Impact and gate:** future implementation would affect the Workbench decision
schema/route and error mapping, `GrantDecisionCommand`, the repository port and
locked SQL CAS, plus administrator/idempotency/concurrency tests. A public or
otherwise independently operated decision entry **blocks the complete IMPL-299
authorization loop**, while the applicant page itself still needs only minimum
request status and current exact READ. No mint or decision implementation is
authorized by this proposal.

**Exact Human acceptance requested:** accept or reject, as one contract, the
request-aggregate meaning of `expectedVersion`, replay-before-CAS ordering,
concurrent/terminal behavior, `TICKET | POLICY` enum and one-to-one internal
mapping plus digest-only audit limitations, the exact-request-ID administrator
entry without a cross-subject list, independent exact DECIDE and self-approval
prohibition, optional-`notBefore` immediate-effect semantics and eight-hour cap,
minimum result/error shapes, and the distinction between `APPROVED` and currently
effective authorization. Until an explicit Human record does so, these details
remain `PROPOSED`.

Grant revoke and continuation-offer revoke/surrender remain **`OPEN`**. This
proposal neither defines nor implements those operations.

No row above authorizes implementation by appearing in this table. Draft PR #164
remains Draft; this batch does not make it Ready, merge, deploy, close IMPL-305,
or modify IMPL-299/IMPL-308 branches.

## Human-accepted creator receipt and mint implementation batch

Status: `HUMAN_ACCEPTED_FOR_IMPLEMENTATION / SESSION_OPEN`.

The historical proposal and its original status above are retained as provenance.
The Human has now accepted the creator-origin receipt time anchor and authorized
this bounded implementation batch. The accepted time is the database clock value
persisted with the receipt in the same owner transaction as Problem creation. It
is named the **receipt start time**, not an exact commit timestamp. Rollback makes
both the Problem creation result and receipt nonexistent. The fixed expiry is the
original receipt start time plus ten minutes. Mint occurs only after the owner
transaction commits; owner-commit delay or mint delay may shorten the usable
window but can never extend it. A mint attempt at or after expiry returns
`EXPIRED` and never restarts the window.

The receipt is immutable and binds trusted scope, creator principal, original
create-command identity, the immutable Problem revision-1 identity/version/digest,
canonical Problem reference, committed owner revision, receipt start time and
fixed expiry. Its uniqueness is trusted scope plus creator plus original command
identity. Equal replay loads the original receipt and corresponding offer state;
different payload under the same command identity retains the formal Business
Problem idempotency conflict. Later Problem revisions never alter the receipt,
mint key, expiry, offer identity or recovery correlation. A historical Problem
without a receipt fails closed; this batch does not infer or backfill one.

Owner commit and Grant Administration mint are two PostgreSQL authority
transactions. Mint is keyed by the original command plus receipt and can produce
at most one offer. A definite or uncertain mint failure never deletes the
committed Problem; equal create replay queries or resumes the same mint key rather
than issuing another identity. The first batch mints only purpose
`CONTINUE_PROBLEM_READ` with the one fixed member `BUSINESS_PROBLEM / READ /
business-problem:{businessProblemId}`. It adds no Plan `PREPARE`, Problem mutation,
collection, wildcard, meta-grant or browser-selected subject/scope/target.

Create and equal replay return the typed `creatorContinuation` contract recorded
above. `AVAILABLE`, `CONSUMED` with its original `requestId`, and `EXPIRED` are
recovered from the original receipt and offer/consumption facts. An offer,
`PENDING` request or `APPROVED` status is not authorization: exact Problem READ
continues to reauthenticate and revalidate current grant, generation, recovery,
revocation, subject and scope. The independent public Decision operation remains
the already implemented administrator path; applicant self-approval and
`INSPECT`-as-`DECIDE` remain prohibited.

Migration coordination was checked against the active 308 and 314 task branches
and worktrees before editing. 308 owns `0019_model_governance.sql`; active 314 has
not allocated a later migration and explicitly waits for this receipt batch.
This batch therefore allocates exactly
`console/backend/migrations/0020_business_problem_creator_receipt.sql` and does
not modify migrations `0001` through `0019`.

Delivery remains `PARTIAL_DRAFT / SESSION_OPEN`. This acceptance does not
authorize continuation revoke/surrender, grant revoke, Plan/Execution expansion,
IMPL-299 product-page acceptance, Ready, merge, deployment or closure of all 305.
