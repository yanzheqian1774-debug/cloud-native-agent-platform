# S5-V023-ARCH-300 — Trusted Browser Identity and Exact-Resource Authorization v1

## 1. Decision record

| Field | Value |
| --- | --- |
| Session | `S5-V023-ARCH-300` |
| Type | `G2_BOUNDED_ARCHITECTURE_PREREQUISITE` |
| Decision status | `Proposed` |
| Implementation status | `Not Started` |
| Session status | `ARCHITECTURE_PROPOSED / AWAITING_HUMAN_ARCHITECTURE_ACCEPTANCE / SESSION_OPEN` |
| Fixed source | commit `91928f285160f74927a7dbd3a905b5bdaa7bbf6f`; tree `ed7e66cb2dac585232c3b5a1117ff27cb000e543` |
| Live-main check | remote `refs/heads/main` was the fixed source at task start; delta `NONE` |
| Implementation authority | `NO`; this record allocates no implementation, migration, deployment, release, or downstream Session |

This is a Human-review candidate. It MUST NOT be interpreted as
`HUMAN_ACCEPTED`, `IMPLEMENTED`, `MAIN_DURABLE`, production IAM, SSO availability,
or permission to close IMPL-299.

## 2. Scope and inherited authority

This candidate addresses only the two prerequisites that block a normal browser
from using the durable business workbench:

1. convert a verified caller credential into a trustworthy, revocable browser
   session and server-owned principal/scope; and
2. request, decide, activate, inspect, and revoke exact-resource grants after
   Problem, Plan, Execution, Resource Use, and Evidence identities become known.

It preserves these already accepted boundaries:

- Business Problem owns Problem, Criterion, Criteria Set, their revisions, and
  exact Problem/Plan binding;
- Workflow Control owns Plan preparation and approval facts;
- Execution owns Run, Task Run, Attempt, Invocation coordination, and canonical
  Resource Use history;
- Evidence remains a separately authorized immutable fact/reference domain;
- Kubernetes remains the implemented Control Plane source of truth;
- `PREPARE`, `APPROVE`, `START`, execution `READ`, Resource Use `READ`, and
  Evidence-reference disclosure are independent permissions;
- replay is disclosed only after current authorization; `OUTCOME_UNKNOWN` never
  authorizes redispatch.

This candidate does not change a public CRD, Kubernetes API group, frozen
Contract, domain owner, provider protocol, or the single-host supervised
execution/UNKNOWN boundary.

## 3. Verified starting point and gaps

### 3.1 Reusable current capability

`GovernedExecutionAuthority` is a server-owned verifier for individually
provisioned Bearer credentials. Its configuration contains credential SHA-256
digests plus trusted `principalId`, `tenantId`, `securityDomain`, expiry, and
exact grants. It compares digests, rejects missing/unmatched/expired credentials,
and issues server-derived principals and decisions.

The durable v0.2.3 Problem/Plan and governed Execution HTTP entries already use
this verifier. Their exact-resource checks are reusable semantics, not a browser
login product. The configured credential itself exists outside the authority
file and cannot be reconstructed from its digest.

### 3.2 Actual availability

No repository or inspected deployment contract proves an enterprise IdP, OIDC,
SAML, authenticated ingress, browser login, browser session, logout, CSRF
defence, or self-service grant product. The only currently reusable identity
source is the individually provisioned Bearer credential verifier. It is suitable
as a bounded bootstrap identity source only when each person receives a distinct
credential through an external secret-delivery process.

This candidate deliberately does not claim SSO. A later enterprise IdP may
replace the bootstrap authenticator behind the same trusted-principal port after
its own Human-approved integration.

### 3.3 Non-reusable browser boundaries

Several v0.2.2/v0.2.3 resource APIs currently accept defaulted or caller-writable
`X-Tenant-ID`, `X-Security-Domain`, `X-Principal-ID`, or
`X-Product-Read-Authorized`. Those headers are test/development adapters and
cannot authenticate a normal user. The current frontend performs unauthenticated
fetches and, for Digital Employee, constructs identity headers from build-time
values. There is no safe way to recover a Bearer token from the authority file,
and no dynamic exact-resource grant workflow exists.

## 4. Recommended decision

Adopt a **same-origin Workbench BFF with PostgreSQL-backed opaque sessions and a
new PostgreSQL-backed Grant Administration Authority**.

The browser talks only to a fixed, typed `/api/workbench/v1` surface. The BFF
authenticates the session cookie, constructs an in-process `TrustedRequestContext`,
checks the current grant projection, and invokes existing domain application
ports. It is not a general reverse proxy and accepts neither a destination URL nor
arbitrary method/path/header forwarding.

This is recommended over authenticated ingress because no usable authenticated
ingress or enterprise identity source is currently proven. It is recommended
over forwarding Bearer tokens from the SPA because a long-lived credential would
then enter browser persistence, application code, logs, or every API request. It
is recommended over embedding new dynamic grants in the current credential file
because file replacement cannot provide a safe user-facing request/decision
workflow or transactional, append-only revocation for newly created identities.

The proposal introduces two real G2 responsibilities:

- **Browser Session Authority**: new authoritative session state, stored in the
  already approved PostgreSQL deployment dependency; and
- **Grant Administration Authority**: new authoritative grant request, decision,
  effective-grant, and revocation state, also stored in PostgreSQL.

They are new application authorities and schemas, even though they introduce no
new database product or infrastructure dependency. Human acceptance of this
record is required before either is implemented.

It also introduces two candidate protocols that do not exist in the current
implementation: immutable static-authority generations activated through a
PostgreSQL generation record, and a dual-route-set/dual-listener child bootstrap
inside the existing supervisor. They are architecture candidate scope, not
ordinary configuration or already-supported topology.

## 5. Identity, session, and browser security

### 5.1 Bootstrap login

The first bounded implementation uses an individually provisioned bootstrap
credential as follows:

1. a server-rendered same-origin login form first receives an opaque, single-use
   login nonce, bound to exact Origin/Host and expiring after 5 minutes, then posts
   that nonce and the credential over TLS directly to the BFF;
2. the BFF excludes the field and request body from access/application logs and
   passes it once to the existing credential verifier;
3. the BFF immediately discards the plaintext and stores neither the credential
   nor a reversible derivative;
4. successful verification creates a new opaque session bound to the verifier's
   `credentialId`, principal, tenant, and security domain; and
5. the response sets an opaque cookie and redirects to the Workbench.

The normal Workbench never asks a user to construct an `Authorization` header.
The server-rendered form submits without exposing the credential to the SPA. The
credential is not stored in JavaScript state, Web Storage, IndexedDB,
service-worker cache, URL, source map, bundle, or cookie.

An administrator must provision distinct credentials with at least 256 bits of
entropy outside this product. A credential expires no later than 30 days after
issuance and may be configured shorter. This
is an explicit P1 operational limitation, not a self-service login or SSO claim.
A shared high-privilege credential is prohibited.

### 5.2 Session representation and lifecycle

The browser receives a cryptographically random opaque value with at least 256
bits of entropy. PostgreSQL stores only `SHA-256(session_value)` and:

- `session_id`, schema version, and aggregate version;
- `credential_id`, `principal_id`, `tenant_id`, `security_domain`;
- source authentication policy/version;
- issued, last-used, idle-expiry, absolute-expiry, and revoked timestamps;
- rotation predecessor/successor IDs and bounded revoke reason;
- CSRF token generation/version and audit timestamps.

The cookie is named `__Host-workbench_session` and is `Secure`, `HttpOnly`,
`SameSite=Strict`, `Path=/`, and has no `Domain`. Initial bounded defaults are a
30-minute idle lifetime and an 8-hour absolute lifetime; shorter bootstrap
credential expiry caps both. Successful login, privilege-sensitive transitions,
and bounded periodic renewal rotate the opaque value. Rotation atomically revokes
the predecessor; a short, server-recorded overlap may exist only for an already
in-flight request and never extends either expiry.

Logout atomically revokes the current session before clearing the cookie. An
expired/revoked bootstrap credential invalidates every derived session on the next
request. Administrative session revocation is supported by exact session or exact
credential ID. Authentication and session state fail closed when their authority
is unavailable.

### 5.3 CSRF and origin boundary

Every unsafe request (`POST`, `PUT`, `PATCH`, `DELETE`) requires all of:

- the session cookie;
- an exact allowlisted `Origin` (and `Sec-Fetch-Site: same-origin` where supplied);
- a short-lived, session-bound CSRF token in `X-CSRF-Token`.

`GET /api/workbench/v1/session` returns a fresh signed CSRF token after validating
the session. It is held in page memory only. The token contains no principal,
scope, credential, grant, or protected-resource fact; its signing key is supplied
as an external Secret Reference and never persisted in the database or bundle.
CSRF tokens expire within 10 minutes and after session rotation/revocation. CORS
does not admit credentialed foreign origins. State-changing GET endpoints are
prohibited.

The 5-minute login nonce, at-least-256-bit bootstrap credential with a maximum
30-day lifetime, 30-minute session idle lifetime, 8-hour absolute session
lifetime, and 10-minute CSRF and continuation lifetimes are candidate recommended
defaults. They are not Human-accepted production parameters.

Browser responses use `Cache-Control: no-store`; security headers require TLS,
deny framing, constrain content sources, and prevent referrer leakage. Session and
CSRF values are redacted from logs, traces, Evidence, error bodies, and URLs.

### 5.4 Trusted principal mapping

Only the Browser Session Authority or an explicitly trusted non-browser service
authenticator may construct:

```text
TrustedRequestContext(
  principal_id,
  tenant_id,
  security_domain,
  session_id_or_service_credential_id,
  authentication_source,
  authentication_policy_version
)
```

Resource request bodies and browser headers cannot populate or override these
fields. The BFF passes this typed context directly to application ports; it does
not mint a long-lived replacement Bearer and does not copy browser identity
headers to an internal HTTP hop.

## 6. Grant Administration Authority

### 6.1 Responsibility and bootstrap

The Grant Administration Authority owns only authorization administration. It
does not own Problem, Plan, Execution, Resource Use, Evidence, or their lifecycle.

- Any authenticated principal may submit a request only for an action declared
  requestable by server policy and for a known exact target or owner-minted
  continuation.
- A grant administrator may configure requestability and decide requests only
  while holding a server-configured meta-grant such as
  `GRANT_ADMIN/DECIDE/grant-scope:<tenant>:<security-domain>`.
- A grant administrator holding the corresponding `REVOKE` meta-grant may revoke
  an effective grant. The grantee may surrender its own grant.
- The resource owner supplies canonical target validation and continuation
  resolution; it never writes grant tables.
- A model, frontend, provider, resource creator, descriptive owner field, or
  client assertion never issues a grant.

The current server-owned credential configuration may bootstrap only the first
named grant administrators and scoped collection/create entitlements. It remains
external configuration, uses distinct administrator credentials, and does not
become the dynamic grant store. There is no organization-wide wildcard fallback.

Authorization sources are closed and typed:

- the immutable static-authority generation owns credential identity/status,
  explicitly marked `SERVICE_ONLY` exact grants, explicitly marked
  `BROWSER_BOOTSTRAP` collection/create grants, non-grant requestability rules,
  and the initial `GRANT_ADMIN`/continuation-assignment meta-grants;
- PostgreSQL owns approved dynamic exact grants, their decisions, expiry and
  revocation; and
- a request is allowed only by an applicable, current source. `SERVICE_ONLY`
  grants are ignored for browser-session contexts and never flow through
  credential-to-session mapping. A tuple present in both sources is still one
  permission, while an explicit credential/config revocation, session revocation,
  dynamic grant revocation, expiry, or scope mismatch wins over allow.

Dynamic grant administration can never issue or request a `GRANT_ADMIN` or
continuation-assignment meta-grant. Requestability only permits submission;
continuation possession only identifies a server-approved request candidate; and
neither produces an effective grant. Thus a meta-grant, requestability rule, grant
request, or continuation cannot recursively authorize its own creation or widen
its issuer.

Two-person separation is not imposed by this candidate because accepted IMPL-297
does not require it. Nevertheless, authority is independent: being the creator,
Problem owner, PREPARE caller, approver, or START caller never derives another
permission. The same human may hold two permissions only through two explicit
grant decisions.

### 6.2 Canonical facts

Each approved grant has immutable identity and audit fields:

```text
Grant(
  grant_id,
  subject_principal_id,
  tenant_id,
  security_domain,
  owner,
  action,
  exact_resource,
  decision_id,
  request_id,
  basis_type,
  basis_reference,
  issuer_principal_id,
  issuer_meta_decision_id,
  policy_version,
  audit_source,
  not_before,
  expires_at,
  created_at
)
```

The exact resource is a normalized non-wildcard string using existing naming
rules. `*`, prefixes, regex, omitted resource, organization-wide substitution,
and client-defined owner/action namespaces are rejected. Grant requests and
decisions store bounded reason categories and digests, never credentials,
session/CSRF values, raw private content, model prompts, or provider payloads.

Request, decision, grant activation, and revocation are append-only facts with a
CAS-protected current projection. An approval may issue one bounded bundle, but
every bundle member receives its own `grant_id` and exact
owner/action/resource tuple. Partial bundle activation is prohibited.

### 6.3 Dynamic identities and subject-facing continuations

An exact resource becomes grantable only after its domain owner has durably
committed the canonical identity. A continuation is an opaque, authenticated
envelope minted by the resource owner and containing a random nonce plus
server-verifiable subject, tenant, security domain, purpose, owner/action set,
canonical-resource reference, owner revision/policy generation, issued time and
expiry. Its lifetime is at most 10 minutes. It is not a bearer credential or a
grant: presenting it under any other authenticated subject/scope fails, and the
browser cannot change its contents.

Each participant obtains a different continuation addressed to that participant:

- after a canonical create/prepare commit, the owner returns the creator's
  creator-facing continuation in that creator's authenticated response;
- an administrator holding the static, scoped continuation-assignment meta-grant
  may create an approval or execution *offer* for an exact committed owner fact
  and a named target principal; the owner validates the fact and mints a distinct
  approver- or executor-facing continuation; and
- the target retrieves only its own offers through its authenticated continuation
  inbox. Another participant never forwards or shares its envelope. The ID alone
  is useless without the bound session principal and scope.

Minting is idempotent over owner, exact resource revision, subject, purpose and the
originating domain/assignment command idempotency identity. The Grant
Administration Authority persists the resulting offer before returning its opaque
envelope. If a domain commit succeeds but offer persistence or the response fails,
replaying the original domain command does not repeat the domain effect; it resumes
the same keyed mint and returns the original offer. A different mint payload under
that key conflicts. This is a recoverable cross-authority protocol, not a claim
that unrelated owner transactions and authorization administration always share
one database transaction.

Assignment is an audited request opportunity, not approval. The assignee must
submit a grant request, and an independently authorized grant decision must still
create every exact grant. The assignment issuer cannot target itself unless a
separate static policy explicitly allows that case; no dynamic decision can create
that policy or its meta-grant.

The Grant Administration Authority resolves the continuation through the owning
port, revalidates current canonical identity/status/scope/requestability, and in
one PostgreSQL transaction inserts a unique continuation-consumption hash plus the
grant request and its exact resource members. Concurrent consumption has one
winner. Same subject, continuation and idempotency digest returns the original
request; a different subject, purpose or payload fails. An expired, revoked,
already-consumed-with-different-key, stale-owner-revision or non-requestable
continuation creates no request.

This permits requesting Resource Use or Evidence-reference access without first
leaking a restricted Evidence ID. A continuation cannot specify arbitrary URLs,
methods, headers, SQL, owners, actions, resources or meta-grants. If response loss
leaves consumption uncertain, the bound subject reads by the same idempotency key;
the envelope is never transferred or replaced by automatic READ/APPROVE authority.

### 6.4 Static generation coordination and request linearization

The existing authority file and PostgreSQL cannot participate in one transaction.
This candidate therefore does not claim cross-medium atomicity. Instead, static
configuration becomes a set of immutable, digest-addressed generation files, and
PostgreSQL stores the single active generation/digest. The active database row,
not filesystem rename time or process reload time, is the activation authority.

The external configuration owner performs a configuration update in this order:

1. write and durably publish a new immutable generation file without replacing or
   deleting the currently active file;
2. ask the single supervised child to load it, validate schema, monotonic
   generation, canonical digest, references, absence of wildcards, and all source
   classifications;
3. under the process activation write barrier, commit the new active
   generation/digest in PostgreSQL; for credential removal/revocation, the same
   PostgreSQL transaction also revokes every session derived from that credential;
   and
4. only after commit, publish the already validated in-memory snapshot and release
   the barrier. The PostgreSQL commit is the configuration or credential-revocation
   linearization point.

Activation is an operator/deployment control operation available only on a
host-local privileged control channel; it is absent from both browser and normal
service HTTP route sets. Its caller identity, generation, digest, result and bounded
failure reason are audited without file contents or credentials.

Failure before step 3 leaves the old generation active. Failure after its commit
causes the child to fail closed rather than serve with the old snapshot; restart
loads the exact active immutable generation by digest before readiness. Missing or
mismatched active files keep both protected route sets unready. Old generations
remain retained while referenced and are garbage-collected only by a separately
validated retention operation. This activation row, immutable-file protocol and
recovery behavior are new persistent/protocol architecture candidate state.

Session revocation is PostgreSQL-only: exact-session logout/admin revoke or
credential-wide revoke commits the session revocation rows/projection, and that
commit is its linearization point. Dynamic grant revocation is also PostgreSQL-only:
the revocation fact and removal from the effective projection commit together, and
that commit is its linearization point. Neither operation rewrites the static file.

Each protected request passes the process activation read barrier, pins the active
static generation, then reads current session and applicable dynamic-grant state
from PostgreSQL. The successful final current-authorization read is that request's
authorization linearization point. A revocation committed before it is observed;
a revocation committed after it does not retroactively cancel an already
authorized in-flight call. Authorization material is scoped to that one typed
domain call and is never cached for a later request. A process crash between a
configuration commit and in-memory publication cannot serve because the child
exits/fails readiness and reconstructs the committed generation on restart.

### 6.5 Grant consistency, revocation, and replay

Within the approved PostgreSQL database, each grant decision and all of its
effective grant rows commit in one transaction. Revocation fact and removal from
the current-effective projection also commit in one transaction. The authorization
reader queries the current projection on every protected request; session or BFF
caches cannot extend grant validity.

Authorization precedes protected lookup, existence/list/count disclosure,
idempotency/claim replay disclosure, owner joins, provider calls, and writes.
Consequently a revocation affects new requests and replays immediately after its
commit. It does not rewrite historical decision references or append-only domain
facts.

Same scoped idempotency key and same canonical request/decision/revocation digest
returns the original identity and state. The same key with different semantics
returns conflict. Failure before commit leaves no effective grant. When the client
does not know whether a response committed, it reads the request/decision by its
idempotency key and treats the result as unknown until the authority confirms it;
it never repeats a protected domain effect merely to infer authorization.

## 7. Authority and trust-boundary matrix

| Owner / boundary | Trusted input | Output | Validation responsibility | Write responsibility | Bypass constraint |
| --- | --- | --- | --- | --- | --- |
| Static Authority Configuration | immutable generation file plus PostgreSQL active-generation row | credential facts, source-typed static grants/requestability/meta-grants | digest, monotonic generation, source type, expiry/revocation, no wildcard | external admin stages file; supervised child activates generation; PostgreSQL owns active pointer | file publish/reload is not activation; `SERVICE_ONLY` never enters a browser session |
| Bootstrap Credential Verifier | credential submitted once over TLS; active static generation | verified credential/principal/scope/expiry/generation | digest, expiry, revocation, distinct identity, source policy | no request-time write | no shared browser credential; no credential recovery from digest |
| Browser Session Authority **(new)** | verified principal/scope and secure randomness | opaque cookie, trusted request context, CSRF token | current credential/session, expiry, rotation, origin/CSRF | `browser_identity` PostgreSQL schema | browser cannot set principal/scope; internal session values never accepted as headers |
| Workbench BFF **(new)** | typed routes, validated session, bounded body | domain response or minimum-disclosure error | request schema, size, CSRF, current exact grant before dispatch | no domain or grant facts directly | fixed route registry only; no arbitrary proxy target or header forwarding |
| Grant Administration Authority **(new)** | trusted context, exact target/subject-bound continuation, static meta-grant, idempotency/CAS | request, decision, individual exact grants, continuation consumption, revocation projection | subject/scope, owner namespace, action, exact resource, requestability, issuer authority, validity | `authorization_admin` PostgreSQL schema | dynamic grants cannot create meta-grants; neither creator nor model/client can sign; no wildcard/prefix matching |
| Business Problem | trusted context and authorized typed command | Problem/Criterion/Criteria Set identities/revisions | existing exact grants and domain invariants | existing Product PostgreSQL schemas | old header adapters not browser reachable |
| Workflow Control | trusted context, exact prepared Plan/decision | Plan, append-only approval | independent PREPARE/READ/APPROVE and bindings | existing Workflow Control PostgreSQL schema | PREPARE never implies APPROVE; approval never implies START |
| Definition owners | trusted context and authorized Workflow/Employee commands | immutable definitions/revisions | exact owner/action/resource and lifecycle | existing definition schemas | caller headers no longer construct scope/actor |
| Execution | trusted context, approved exact Plan, START decision | Run/Task Run/Attempt/Invocation identities | START, binding, claim, supervision, current authorization | existing Execution/Invocation schemas | denial before provider; UNKNOWN never redispatched |
| Resource Use | trusted context, exact Attempt/use grant | authorized snapshot/projection | separate Resource Use READ and Evidence filtering | existing Execution-owned Resource Use schema | Execution READ does not imply Resource Use READ |
| Evidence | trusted context, exact reference/content grant | authorized reference or content projection | separate reference/dereference/export decision | existing Evidence authority | READ elsewhere never implies Evidence disclosure |
| Edge/ingress | TLS request to an allowlisted Workbench route | BFF request only | host, TLS, path, size; strip/reject identity headers | deployment configuration only | `/api/internal/*` is not exposed to browser networks |

### 7.1 Runtime topology and enforceable isolation

The verified current implementation is narrower than this recommendation:
`agent_console.governed_execution_supervisor` starts one one-worker Uvicorn child
for `agent_console.app:app` with one host/port. It already owns the database-keyed
host lock, lifetime pipe, confirmed-child-exit status and process-wide Invocation
ownership. It does **not** currently provide two listeners or two route sets.

The bounded implementation must extend that supervisor rather than run a second
backend or execution process. The one supervisor starts exactly one child process;
that child pre-binds a public Workbench socket and a private internal socket and,
in one asyncio process with one worker, serves two distinct ASGI applications:

- the public application registers only static/login/session and the closed typed
  `/api/workbench/v1` route set; and
- the private application registers existing internal/service Bearer routes,
  including governed Execution.

Both applications share the same composition root, PostgreSQL pools, supervised
recovery guard and process-wide Invocation ownership. The child reports ready only
after both sockets are bound, both route registries pass the closed-route check,
the active authority generation is loaded, and required PostgreSQL authorities are
ready. Because the current supervisor records `RUNNING` immediately after spawn,
the extension must add a bounded child-to-supervisor readiness handshake and keep
status `STARTING` until the supervisor verifies both listener identities. If either
bind, application startup, handshake or readiness step fails, the child
closes both sockets and exits. If either server task exits unexpectedly, the child
stops the sibling server and exits; the existing supervisor then records the exact
child exit and retains/releases ownership under the already accepted rules. On
SIGTERM, both listeners stop accepting, drain within the shared bounded shutdown,
then the child exits. Supervisor lifetime-pipe EOF triggers the same coordinated
shutdown; the inherited host lock remains held until child exit. There is no
public-only partial-success mode and no second owner of Execution.

Application startup can verify only local facts: distinct bound addresses/ports,
the exact public/private route inventories, rejected identity headers, single
worker/child identity and authority-generation readiness. Those checks do not
prove network isolation. A Kubernetes deployment must expose only the public port
through the public Service/Ingress, place the private port behind a distinct
ClusterIP Service, default-deny private-port ingress, and allow only named service
accounts/pod selectors that require the non-browser contract. Equivalent non-Kubernetes
firewall rules must name the allowed callers. A deployment may claim bypass closure
only after those controls are applied and an independent client in the
browser-reachable network proves the private address/port and
`/api/internal/*` unreachable while the public typed routes remain reachable.
Configuration declarations, route documentation, loopback binding in a local test,
or BFF header stripping alone are not isolation evidence. If the deployment cannot
produce that proof, affected resources remain `OPEN / NOT_BROWSER_AVAILABLE`.

## 8. Candidate HTTP contracts

All responses use `Cache-Control: no-store`. Error bodies contain only
`{"reasonCode":"...","requestId":"..."}` and never echo credentials, cookies,
CSRF tokens, protected target IDs, grants outside the caller's view, or existence.

### 8.1 Session

```http
GET /api/workbench/v1/login

200 <server-rendered form containing one opaque, 5-minute, single-use login nonce>
```

```http
POST /api/workbench/v1/session
Content-Type: application/x-www-form-urlencoded

loginNonce=<opaque, single-use>
bootstrapCredential=<sensitive, never logged>
```

Success: `303 See Other`, `Location: /workbench`, and the secure session cookie.
Failure: `401 AUTHENTICATION_REQUIRED`; authority unavailable:
`503 AUTHENTICATION_UNAVAILABLE`. The response is deliberately identical for
unknown, expired, revoked, or malformed credentials.

```http
GET /api/workbench/v1/session

200 {
  "schemaVersion": "workbench-session.v1",
  "principal": {
    "principalId": "human:alice",
    "tenantId": "tenant-a",
    "securityDomain": "supplier-quality"
  },
  "session": {
    "expiresAt": "...",
    "idleExpiresAt": "..."
  },
  "csrfToken": "<short-lived session-bound token>"
}
```

`POST /api/workbench/v1/session/rotate` rotates after CSRF validation and returns
`204`. `DELETE /api/workbench/v1/session` revokes before clearing the cookie and
is idempotent. Missing/expired/revoked sessions return
`401 AUTHENTICATION_REQUIRED`.

### 8.2 Capability discovery

```http
POST /api/workbench/v1/authorization/capabilities
{
  "schemaVersion": "authorization-capability-query.v1",
  "queries": [
    {"owner":"PLAN","action":"APPROVE","resource":"plan:p-123:1"},
    {"continuationId":"authz-continuation-opaque"}
  ]
}

200 {
  "capabilities": [
    {"state":"ALLOWED","grantId":"grant-...","expiresAt":"..."},
    {"state":"REQUESTABLE","requestTemplateId":"request-template-..."}
  ]
}
```

Possible states are `ALLOWED`, `REQUESTABLE`, `PENDING`, and `NOT_AVAILABLE`.
`NOT_AVAILABLE` intentionally combines nonexistent, hidden, non-requestable, and
cross-scope targets. Grant IDs appear only to their subject or authorized grant
administrator.

### 8.3 Subject-facing continuation inbox

```http
GET /api/workbench/v1/authorization/continuations?state=AVAILABLE

200 {
  "continuations": [{
    "continuationId": "opaque-subject-bound-envelope",
    "purpose": "APPROVE_PLAN",
    "expiresAt": "...",
    "requestableActions": ["APPROVE"]
  }]
}
```

Only envelopes bound to the authenticated principal/tenant/security-domain are
returned; protected resource IDs are omitted until independently readable. An
administrator with a static scoped continuation-assignment meta-grant may call a
typed assignment endpoint with a named target principal, exact purpose, and owner
fact reference. The owner validates and mints the target's envelope. The endpoint
cannot assign meta-grants, approve a request, or return the envelope to the issuer.

### 8.4 Grant request

```http
POST /api/workbench/v1/authorization/grant-requests
Idempotency-Key: <caller-generated opaque key>
{
  "schemaVersion": "exact-grant-request.v1",
  "purpose": "CONTINUE_PROBLEM_PLAN",
  "requestedGrants": [
    {"owner":"BUSINESS_PROBLEM","action":"READ",
     "resource":"business-problem:problem-123"},
    {"owner":"PLAN","action":"PREPARE",
     "resource":"plan:prepare:problem-123"}
  ],
  "continuationIds": []
}
```

The subject is always copied from the authenticated request context; the ordinary
request cannot name or override it. Success is `202` with
`requestId`, `state: PENDING`, `aggregateVersion`, `submittedAt`, and bounded
requested action labels. It does not assert that authorization is approved.

### 8.5 Decision and revocation

```http
POST /api/workbench/v1/authorization/grant-requests/{requestId}/decisions
Idempotency-Key: <opaque key>
{
  "schemaVersion": "exact-grant-decision.v1",
  "expectedVersion": 1,
  "decision": "APPROVE",
  "reasonCategory": "ASSIGNED_BUSINESS_DUTY",
  "basisReference": "ticket-or-policy-reference",
  "notBefore": "...",
  "expiresAt": "..."
}
```

Approval returns `201` (or `200` replay) with `decisionId`, `state: APPROVED`,
and one `{grantId, owner, action, exactResource, notBefore, expiresAt}` per member.
Rejection returns the same shape with no grants. The issuer identity, meta-decision,
policy version, and audit source are recorded but sensitive policy content is not
returned to the applicant.

```http
POST /api/workbench/v1/authorization/grants/{grantId}/revocations
Idempotency-Key: <opaque key>
{
  "schemaVersion": "exact-grant-revocation.v1",
  "expectedVersion": 1,
  "reasonCategory": "DUTY_ENDED"
}
```

Success returns the immutable `revocationId`, `grantId`, `revokedAt`, and
`state: REVOKED`. Repeated same-key/same-payload calls return the same result;
different payload returns `409 IDEMPOTENCY_PAYLOAD_MISMATCH`. Stale CAS returns
`409 AUTHORIZATION_STATE_STALE`.

### 8.6 Grant request status and minimum disclosure

`GET /api/workbench/v1/authorization/grant-requests/{requestId}` is available to
the applicant and authorized grant administrators. States are `PENDING`,
`APPROVED`, `REJECTED`, `CANCELLED`, and `EXPIRED`. Unknown, hidden, foreign-scope,
or unauthorized IDs all return `404 AUTHORIZATION_REQUEST_NOT_FOUND`.

Common failures are:

| HTTP | Reason | Semantics |
| --- | --- | --- |
| 401 | `AUTHENTICATION_REQUIRED` | session missing, expired, or revoked |
| 403 | `CSRF_VALIDATION_FAILED` | unsafe request lacked valid same-origin proof |
| 404 | `<OWNER>_NOT_FOUND` | minimum-disclosure authorization/target failure |
| 409 | `AUTHORIZATION_STATE_STALE` | CAS failed; no partial grant write |
| 409 | `IDEMPOTENCY_PAYLOAD_MISMATCH` | same key, different semantic digest |
| 422 | `EXACT_GRANT_INVALID` | wildcard, unregistered owner/action, or invalid lifetime |
| 503 | `SESSION_AUTHORITY_UNAVAILABLE` / `GRANT_AUTHORITY_UNAVAILABLE` | fail closed |

## 9. Trusted browser API boundary and compatibility inventory

The BFF route set is generated from an explicit operation registry. Each entry
fixes the browser route, owning application port, action, resource builder,
request/response schema, and disclosure policy. It never accepts a backend URL.

| 299 resource/API | Current source capability | Candidate browser treatment | Compatibility / remaining OPEN |
| --- | --- | --- | --- |
| Problem | durable `/api/internal/v0.2.3/business-problems*`; Bearer + exact grants | typed BFF create/list/read/revise/transition wrappers; reuse domain port and resource names | directly reusable application semantics; internal HTTP path remains non-browser |
| Criterion | durable success-criterion create/revise/read with exact grants | typed BFF wrappers; continuation after create | directly reusable application semantics |
| Criteria Set | durable create/revise/read bound to exact Problem/criterion revisions | typed BFF wrappers | directly reusable application semantics |
| Plan | durable prepare/read/approve with independent grants | typed BFF wrappers; PREPARE continuation yields exact Plan target | directly reusable; approval UI must show `PENDING_AUTHORIZATION` until effective grant exists |
| Workflow | durable v0.2.2 lifecycle API currently trusts caller headers | migrate principal dependency to trusted context and define exact lifecycle grants before exposure | auth adapter and grant map required; browser availability remains OPEN until migrated |
| Employee Definition | durable lifecycle API currently trusts caller headers | migrate to trusted context and exact grants | auth adapter and grant map required |
| Instance | durable create/read API currently trusts caller headers | migrate to trusted context and exact create/read grants | auth adapter and grant map required |
| Assignment | durable create/read/start/retry surfaces currently trust caller headers | migrate to trusted context; keep assignment, start, retry separate | exact action map and wrapper required; no implicit START |
| Execution | governed start and readback already use Bearer/exact grants | typed BFF start/read; construct exact START target server-side; preserve supervision | reusable domain/auth semantics; BFF must not create a second execution owner |
| Skill Invocation | governed Attempt-bound invocation/read exists inside Execution; older management endpoints trust headers | expose only typed governed operation/read needed by 299 | generic management invocation remains non-browser/OPEN unless separately mapped |
| Resource Use | exact read is currently nested in governed Execution read | typed filtered read or continuation-backed exact grant | standalone Resource Use browser endpoint is OPEN; domain owner unchanged |
| Evidence reference | current governed projection filters each exact reference and does not dereference content | continuation-backed `READ_REFERENCE`; reveal only after grant | Evidence content/dereference API remains OPEN and requires its own action/contract |

The candidate operation registry is exact and closed:

| Resource class | Browser entry | Authentication | Required owner/action/resource | Fact owner |
| --- | --- | --- | --- | --- |
| Problem | `/api/workbench/v1/problems` and `/problems/{id}/*` | Browser Session Authority → `TrustedRequestContext` | `BUSINESS_PROBLEM/CREATE` or `LIST` on `business-problem:collection`; `READ`, `REVISE`, `TRANSITION` on `business-problem:<problem_id>` | Business Problem |
| Criterion | `/api/workbench/v1/success-criteria*` | same | `SUCCESS_CRITERION/CREATE` on `success-criterion:collection`; `REVISE` on `success-criterion:<criterion_id>`; `READ` on `success-criterion:revision:<revision_id>` | Business Problem |
| Criteria Set | `/api/workbench/v1/problems/{id}/criteria-sets*` | same | `SUCCESS_CRITERIA_SET/CREATE`, `REVISE`, or `READ` on `success-criteria-set:<problem_id>`, plus exact Problem/criterion reads | Business Problem |
| Plan | `/api/workbench/v1/problems/{id}/plans`, `/plans/{id}`, `/plans/{id}/approvals` | same | `PLAN/PREPARE/plan:prepare:<problem_id>` and `PLAN/READ/plan:prepared:<problem_id>` for preparation; `PLAN/READ` or independent `APPROVE` on `plan:<plan_id>:<version>` | Workflow Control; Business Problem retains binding |
| Workflow | `/api/workbench/v1/workflows*` | same | `WORKFLOW/CREATE` or `LIST` on `workflow:collection`; lifecycle action on `workflow:<definition_id>:aggregate`; reference read on `workflow:<definition_id>:<revision_id>` | Workflow Definition |
| Employee Definition | `/api/workbench/v1/employee-definitions*` | same | `EMPLOYEE/CREATE` or `LIST` on `employee:collection`; lifecycle action on `employee:<definition_id>:aggregate`; reference read on `employee:<definition_id>:<revision_id>` | Digital Employee Definition |
| Instance | `/api/workbench/v1/instances*` | same | `INSTANCE/CREATE/instance:collection`; `INSTANCE/READ/instance:<instance_id>` | Execution identity domain |
| Assignment | `/api/workbench/v1/instances/{id}/assignments*` | same | `ASSIGNMENT/CREATE/assignment:prepare:<instance_id>`; `ASSIGNMENT/READ/assignment:<assignment_id>`; retry/start actions remain separate | Execution identity domain |
| Execution | `/api/workbench/v1/executions*` | same | `EXECUTION/START/governed-execution:start:<canonical_request_digest>`; `EXECUTION/READ/governed-execution:read:<workflow_run_id>:<attempt_id>` | Execution |
| Skill Invocation | nested typed Execution operation/read | same | `SKILL/INVOKE_SKILL/skill-invocation:invoke:<canonical_request_digest>`; `SKILL/READ_SKILL_INVOCATION/skill-invocation:read:<invocation_id>` | Execution Invocation |
| Resource Use | nested typed execution/resource-use read | same | `RESOURCE_USE/READ/resource-use:read:<resource_use_id>` | Execution Resource Use |
| Evidence reference | filtered projection and exact reference request | same | `EVIDENCE/READ_REFERENCE/evidence-reference:read:<evidence_id>` | Evidence |

For proposed lifecycle actions in the not-yet-migrated Workflow, Employee,
Instance, and Assignment rows, the implementation task must freeze the registered
action vocabulary before editing routes. It may not widen an existing action or
infer permission from a descriptive owner field. If current source cannot support
one of these exact mappings without a new owner decision, that row remains
`OPEN / NOT_BROWSER_AVAILABLE` and returns no browser route.

All still-unmigrated endpoints that can read or mutate the same protected facts
remain inaccessible from browser-reachable ingress. A BFF wrapper is not considered
complete until the old route is either (a) bound to a private service listener and
blocked by network policy/ingress allowlist, or (b) converted to the same trusted
context. Merely stripping headers at the BFF is insufficient.

For browser-facing routes, incoming `Authorization`, `Proxy-Authorization`,
`X-Principal-ID`, `X-Tenant-ID`, `X-Security-Domain`,
`X-Product-Read-Authorized`, and any internal trusted-context header are rejected
with `400 UNTRUSTED_IDENTITY_HEADER`; they are never forwarded. Trusted service
credentials may continue only on the private internal listener with existing
Bearer validation and exact grants.

Deployment acceptance must prove that the public ingress exposes only static
assets, `/api/workbench/v1/*`, the login/logout endpoints, and health endpoints
whose content is non-sensitive. It must also prove from a browser-network test
pod/client that `/api/internal/*` and the backend service port are unreachable.

## 10. Complete dynamic authorization example

The following is a sequence of explicit decisions, not an automatic entitlement
chain. `Alice` creates/prepares, `Bob` approves, and `Carol` starts only to make
independence visible; the architecture does not mandate distinct humans.

1. Alice signs in with her own bootstrap credential. Her session maps to
   `human:alice/tenant-a/supplier-quality`.
2. A bootstrap-configured exact collection entitlement permits
   `BUSINESS_PROBLEM/CREATE/business-problem:collection` and the existing
   collection READ required by creation. Alice creates Problem `P1`.
3. The Product owner returns `P1` and a creator-facing continuation bound to
   Alice's principal/scope. Alice
   requests exact `BUSINESS_PROBLEM/READ/business-problem:P1`, required
   Criterion/Criteria Set permissions, and `PLAN/PREPARE/plan:prepare:P1`.
   The Workbench shows `PENDING_AUTHORIZATION`, not success or approval.
4. A grant administrator with a current scoped meta-grant approves the bundle.
   Each tuple receives its own grant/decision identity. Alice creates Criteria,
   a Criteria Set, and prepares Plan `PL1` version 1. Preparation does not approve
   it.
5. A statically meta-authorized administrator creates an `APPROVE_PLAN` offer for
   named principal Bob against exact `PL1:1`. Workflow Control validates the
   committed Plan and mints a Bob-bound continuation; only Bob retrieves it from
   his authenticated inbox. Bob atomically consumes it to request
   `PLAN/READ/plan:PL1:1` and `PLAN/APPROVE/plan:PL1:1`. A grant administrator
   explicitly approves those grants. Alice never receives Bob's continuation,
   and Alice's creator/PREPARE grants do not let her approve.
6. Bob approves exact `PL1:1`; Workflow Control appends the approval fact. Approval
   does not start execution.
7. A statically meta-authorized administrator similarly creates an
   `EXECUTE_APPROVED_PLAN` offer for named principal Carol. Workflow Control mints
   a different Carol-bound continuation only after approval; Carol retrieves and
   atomically consumes it through her own session. A grant administrator separately issues
   `EXECUTION/START/governed-execution:start:<request-semantic-digest>` and the
   required exact Skill invocation grant. Carol starts the existing approved
   Plan through the supervised Execution owner.
8. The start response returns Run/Task Run/Attempt identities plus a Carol-bound
   read-authorization continuation. Other readers receive their own
   administrator-assigned, owner-minted offers; nobody shares Carol's envelope.
   The response does not disclose restricted Evidence IDs.
9. Separate requests and decisions issue:
   `EXECUTION/READ/governed-execution:read:<run>:<attempt>`,
   `SKILL/READ_SKILL_INVOCATION/skill-invocation:read:<invocation>`,
   `RESOURCE_USE/READ/resource-use:read:<resource-use>`, and each
   `EVIDENCE/READ_REFERENCE/evidence-reference:read:<evidence>`.
   Execution READ alone discloses none of the latter facts.
10. Revoking an Evidence grant removes that reference from the next filtered
    projection. Revoking START blocks a new or replayed start before claim
    disclosure/provider call. Historical approval, Attempt, Resource Use, and
    Evidence facts remain immutable. An already dispatched ambiguous invocation
    remains `OUTCOME_UNKNOWN` and is never automatically repeated.

## 11. Ordinary-user workflow

- **Enter:** open the same-origin Workbench, submit an individually provisioned
  credential to the server-rendered login form once, then use only the HttpOnly
  session cookie.
- **Know identity and permissions:** the shell reads the session endpoint and
  capability endpoint. It displays exact principal/scope and action states without
  exposing hidden resource existence.
- **No permission:** `NOT_AVAILABLE` is rendered as unavailable without saying
  whether the target exists. `REQUESTABLE` offers a grant request. `PENDING` shows
  “等待授权”; it never shows “已批准”.
- **After create:** owner-minted continuations let the user request exact follow-up
  grants after canonical IDs commit, including hidden child Evidence targets.
- **Expiry/revocation:** `401` clears local in-memory state and returns to login;
  `404`/capability downgrade removes the action and offers request status where
  allowed. The UI never optimistically retains authority.
- **Unknown response:** retry only the same grant/domain command with the same
  idempotency key or read its status. A timeout never becomes success, approval,
  or permission and never triggers automatic execution redispatch.

## 12. Acceptance matrix

| Requirement | Required proof |
| --- | --- |
| two caller identities never cross | two distinct bootstrap credentials/sessions; parallel exact reads/writes; no principal/scope leakage or shared cookie |
| forged headers and direct bypass fail | browser sends every identity header; BFF rejects; browser-network client cannot reach internal listener or `/api/internal/*` |
| denied action has zero protected write/provider call | authorization-before-lookup instrumentation, transaction assertions, provider spy count `0` |
| new resource continues after independent authorization | real PostgreSQL Problem create, pending request, administrator decision, exact follow-up action |
| creator without approval cannot approve | creator PREPARE/READ grants plus no APPROVE; approval returns nondisclosing failure and writes zero facts |
| revocation constrains request and replay | effective request succeeds; revoke commits; same command/idempotency replay fails before claim disclosure and provider call |
| session expiry and CSRF rejection | idle/absolute/credential expiry, logout, rotation predecessor, missing/wrong/stale CSRF, foreign Origin |
| credentials absent from bundle, URL, logs, browser persistence | production build scan, browser storage inspection, history/cache inspection, structured log/trace scan |
| normal browser completes Problem→Plan→approve→execute→authorized reads | real browser, real BFF/backend/PostgreSQL, independent grants and identities, filtered then authorized Resource Use/Evidence reference |
| timeout/UNKNOWN never auto-repeats execution | disconnect/crash after durable dispatch; restart/replay stays UNKNOWN with provider call count unchanged |
| grant transaction and revocation are atomic | fault injection before/after commit; no partial bundle; retry returns original decision identity |
| static/PG generation coordination is recoverable | fault injection at file publish, activation commit and in-memory publish; old or committed generation is recovered exactly and no mismatched generation serves |
| revocation classes have exact linearization | config, credential, session and dynamic-grant revoke races prove the documented commit/request ordering and no later request uses revoked state |
| continuations are per-subject and atomic | creator, approver and executor retrieve different envelopes; transfer fails; concurrent consume has one request identity; replay is idempotent |
| one supervised child owns both listeners | one child PID/worker and shared ownership; either-listener startup/exit failure closes both; supervisor-loss behavior remains accepted behavior |
| deployed network isolation is effective | independent browser-network probe reaches public typed routes but cannot connect to private listener or any internal route; manifests alone are insufficient |
| non-disclosure is preserved | foreign/hidden/nonexistent target responses have the same status/body class and no count/timing-sensitive payload |

## 13. Rejected alternatives

- **Authenticated ingress now:** rejected because no actual trusted ingress/IdP
  integration is proven. It remains a future replaceable authenticator.
- **Bearer in SPA/Web Storage:** rejected because it makes a long-lived credential
  browser-held and repeatedly transmitted.
- **One shared privileged Bearer:** rejected because calls cannot map to real
  principals and revocation/audit become shared.
- **Trust caller identity headers:** rejected because the browser can forge them.
- **Static file as the dynamic grant product:** rejected because safe atomic
  request/decision/revocation for new identities and normal-user waiting state are
  absent.
- **Creator automatic APPROVE/START or organization wildcard:** rejected because
  it collapses independent authorities.
- **Generic BFF proxy:** rejected because arbitrary target/method/header forwarding
  recreates the bypass and expands SSRF/confused-deputy risk.
- **Model-selected authorization:** rejected because model output is not an
  authorization issuer or policy decision.

## 14. Human decision summary

### Inherited accepted constraints (not reopened)

- existing Product, Workflow Control, Execution, Resource Use, and Evidence
  owners;
- exact owner/action/resource authorization, auth-before-disclosure/effect, and
  independently authorized PREPARE/APPROVE/START/READ;
- PostgreSQL product-continuity direction;
- single-host supervised execution and `OUTCOME_UNKNOWN`/no redispatch semantics;
- non-disclosure and secret-reference-only boundaries.

### New choices requiring Human acceptance

1. same-origin typed BFF instead of an unproven authenticated ingress;
2. a new PostgreSQL Browser Session Authority and `browser_identity` schema;
3. a new PostgreSQL Grant Administration Authority and `authorization_admin`
   schema;
4. one-time per-user Bearer bootstrap until a separately approved enterprise IdP
   adapter exists;
5. private-listener/network-policy isolation of every legacy internal route that
   can reach the same protected facts;
6. one supervised child serving distinct public/private ASGI route sets and
   listeners under a common fail-closed lifecycle;
7. immutable static-authority generations with PostgreSQL activation and the
   documented configuration/credential/session/grant revocation ordering; and
8. per-subject owner-minted continuation offers, statically meta-authorized
   assignment, and atomic consumption for newly committed or undisclosed exact
   resources.

### Truly unresolved decisions

- the enterprise identity provider and protocol that may later replace bootstrap
  credentials;
- the named initial grant administrators, credential delivery/rotation procedure,
  deployment hostnames and Secret References;
- whether to accept or revise the candidate recommended lifetimes: 5-minute login
  nonce, at-least-256-bit/at-most-30-day bootstrap credential, 30-minute idle and
  8-hour absolute session, and 10-minute CSRF/continuation;
- whether future policy requires mandatory two-person grant administration;
- Evidence content/dereference and standalone Resource Use browser contracts;
- cross-host/HA session and execution coordination, outside this bounded scope.

### Approval boundary

Human acceptance of this candidate would approve architecture only. It would not
allocate an implementation Session, authorize migrations/deployment, make legacy
routes safe, certify IAM, accept production readiness, merge this branch, or close
IMPL-299. Implementation must be separately allocated and must follow the bounded
plan in the companion document.
