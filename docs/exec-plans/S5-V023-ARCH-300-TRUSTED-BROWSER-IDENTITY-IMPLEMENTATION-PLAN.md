# S5-V023-ARCH-300 — Bounded implementation plan candidate

## Status and authority

| Field | Value |
| --- | --- |
| Architecture | [S5-V023-ARCH-300](../../architecture/s5/v0.2/S5-V023-ARCH-300-TRUSTED-BROWSER-IDENTITY-EXACT-RESOURCE-AUTHORIZATION-V1.md) |
| Plan status | `PROPOSED / NOT_ALLOCATED` |
| Architecture decision | `AWAITING_HUMAN_ARCHITECTURE_ACCEPTANCE` |
| Implementation | `NOT_STARTED / NOT_AUTHORIZED` |
| Deployment / migration | `NOT_AUTHORIZED` |
| Downstream Sessions | `NONE_ALLOCATED` |

This is an implementation boundary and dependency proposal only. No item may start
until the architecture is Human-accepted and implementation scope is separately
allocated.

## 1. Delivery shape

Prefer three dependent implementation tasks, not one task per component:

```text
I1 — identity/session + grant authority foundation
  → I2 — typed BFF and endpoint migration/cutoff
    → I3 — real-browser security and business-flow acceptance
```

I1 and I2 both affect shared backend bootstrap, migration order, authentication,
and API routing, so they must be serialized or owned by one writer. I3 begins only
after I2's deployment boundary is testable. These are dependency/readiness exits,
not three additional Human start approvals. Once the architecture is accepted and
one bounded implementation scope is Human-authorized, work may proceed I1 → I2 →
I3 without pausing for a new start decision at each arrow, subject to the existing
architecture-conflict stop gate, PR acceptance and persistent-integration gate.
This plan does not assign identifiers or Sessions.

## 2. I1 — Session and grant authority foundation

### Backend

- add typed `TrustedRequestContext`, `Authenticator`, `BrowserSessionRepository`,
  `GrantAdministrationRepository`, and `CurrentAuthorizationReader` ports;
- adapt the current `GovernedExecutionAuthority` credential verification behind
  `Authenticator` without weakening existing non-browser Bearer behavior;
- add Browser Session application service: create, authenticate, rotate, expire,
  credential-wide revoke, exact-session revoke, and logout;
- add Grant Administration application service: request, continuation resolution,
  subject-facing offer/inbox, statically meta-authorized assignment, decide/reject,
  activate atomic bundle, inspect, expire, revoke/surrender, atomic continuation
  consumption, CAS, and idempotent replay;
- add immutable static-authority generation loading plus PostgreSQL activation:
  configuration publish is not activation; credential revocation activates the
  new generation and revokes its derived sessions in one database transaction;
  session and dynamic-grant revocations remain separate PostgreSQL-only commits;
- expose activation only through a host-local privileged operator control channel,
  never through either browser or normal service HTTP routes, and audit generation,
  digest and outcome without credential/config contents;
- implement the activation read/write barrier and record the exact request
  authorization linearization point; fail closed across crash windows rather than
  claiming one transaction spans filesystem and database;
- register fixed owner/action/resource builders; reject unknown namespaces and all
  wildcard/prefix forms;
- make current authorization read the PostgreSQL effective projection on every
  protected request and replay;
- preserve minimum-disclosure error mapping.

Expected implementation areas, subject to source inspection in the allocated task:

- `console/backend/src/agent_console/` new session/authentication/authorization
  modules and composition;
- `console/backend/src/agent_console/governed_execution_authorization.py` adapter
  boundary, with existing exact-resource functions preserved;
- `console/backend/src/agent_console/business_problem_application.py` only where a
  typed current-authorization port replaces the concrete file authority;
- `console/backend/src/agent_console/app.py` composition only.

### Persistence

Use the already approved PostgreSQL dependency. Add an additive migration after
the current highest migration only in a separately authorized implementation:

- `browser_identity.sessions`, session rotation/revocation facts and exact
  credential/session indexes;
- `authorization_admin.authority_generation_activations`, grant requests,
  immutable request members, continuation offers/consumption hashes, decisions,
  individual grants, revocations, idempotency claims, and current-effective
  projection;
- scoped keys/FKs, positive aggregate versions, canonical payload digests, bounded
  reason fields, and expiry indexes;
- no credential, cookie, CSRF token, private content, raw provider/model payload,
  or arbitrary policy document.

The migration must be atomic and rollback-safe. It must not change migrations
0001–0017, current domain tables, public CRDs, or the Kubernetes API group.

### Tests

- credential-to-session mapping for two principals/scopes;
- candidate lifecycle defaults without claiming production acceptance: login nonce
  5 minutes; bootstrap credential at least 256-bit and at most 30 days; session idle
  30 minutes and absolute 8 hours; CSRF and continuation 10 minutes;
- cookie hashing, rotation, overlap boundary, idle/absolute/credential expiry,
  logout and administrative revoke;
- CSRF signing/expiry/session binding and log redaction;
- grant request/decision/rejection/revoke/surrender, exact matching, no wildcard,
  static-only meta-grant enforcement, service-only/browser source separation, CAS,
  replay conflict and fault-injected atomicity;
- immutable-file/active-generation failure injection before and after each
  activation step, including credential-wide session revocation and restart from
  the exact committed digest;
- creator/approver/executor subject-bound continuation retrieval, transfer denial,
  one-winner atomic consumption and same-idempotency recovery;
- fault-injected domain-commit/offer-mint response loss proves same-key recovery
  returns the original offer without repeating the domain effect;
- current authorization and revoked replay before lookup/write/provider call;
- restart reconstruction from PostgreSQL.

## 3. I2 — Typed BFF, endpoint migration, and bypass cutoff

### Browser/backend API

- implement only fixed `/api/workbench/v1` session, capability, grant, and domain
  operations required for the IMPL-299 journey;
- route directly to typed domain application ports with
  `TrustedRequestContext`; never accept an upstream URL or arbitrary forwarding
  fields;
- wrap the already governed Problem, Criterion, Criteria Set, Plan, Execution,
  Skill Invocation read, Resource Use read, and Evidence-reference filter paths;
- migrate Workflow, Employee Definition, Instance, and Assignment dependencies
  from caller headers to the same trusted context and explicit exact grants;
- implement owner-minted, expiring authorization continuations and exact server
  resolution for Plan, Execution read, Resource Use, and Evidence-reference targets;
  creators receive only creator-bound responses; named approvers/executors receive
  distinct owner-minted offers only through their authenticated inbox after a
  statically meta-authorized assignment; nobody shares a token;
- reject external identity/authorization headers on browser routes;
- keep non-browser service Bearer entry only on the private internal listener.

The first delivery must not add a generic proxy, SSO placeholder, full IAM policy
language, organization inheritance, Evidence content API, or standalone Resource
Use product API unless separately accepted.

### Frontend/browser connection

- add a server-rendered login form and session bootstrap shell;
- use same-origin credentialed fetch through a single API client that obtains and
  holds the CSRF token in memory;
- remove build-time/caller-writable identity and authorization headers;
- display current principal/scope and `ALLOWED`, `REQUESTABLE`, `PENDING`, and
  `NOT_AVAILABLE` actions;
- render `PENDING` as “等待授权”, never as approved/complete;
- on 401 clear in-memory projections and return to login; on revoked action refresh
  capability state; on timeout preserve unknown and reuse only the same idempotency
  key;
- never place credentials/session/CSRF values in URL, Web Storage, IndexedDB,
  service-worker cache, telemetry, or source maps.

### Supervised child and deployment configuration

- one TLS same-origin public route exposes only static assets and typed Workbench
  routes;
- extend the existing `agent_console.governed_execution_supervisor`, which today
  starts one one-worker Uvicorn child and one listener, to start exactly one child
  bootstrap that pre-binds two sockets and serves two distinct ASGI applications
  in one asyncio process: public Workbench routes and private internal routes;
- share one composition root, PostgreSQL pools, supervision lifetime pipe,
  database-keyed host lock and process-wide Invocation ownership; do not create a
  second backend/execution child;
- readiness requires both listeners, both closed route inventories, active
  authority generation and PostgreSQL authorities; add a bounded authenticated
  child-to-supervisor readiness handshake because current status becomes `RUNNING`
  immediately after spawn, and retain `STARTING` until both listeners are proven;
- either-listener bind/start, handshake or unexpected exit closes both and exits
  the child; SIGTERM or supervisor lifetime-pipe EOF drains/closes both within one
  bounded shutdown before confirmed child exit, while the inherited lock remains
  held until that exit;
- bind internal APIs to the private listener/service and enforce ingress plus
  NetworkPolicy/firewall denial from browser-reachable networks;
- in Kubernetes, expose only the public port through public Service/Ingress; use a
  distinct ClusterIP Service for the private port with default-deny ingress and
  allow only named service accounts/pod selectors that need the service contract;
- explicitly deny `/api/internal/*` and the backend internal port at public ingress;
- configure exact Origin/Host allowlists, request-size limits, timeouts, secure
  response headers, and credential/session/CSRF redaction;
- supply session/CSRF signing material and bootstrap authority file only through
  existing Secret Reference mechanisms;
- keep the governed execution child under its existing single-host supervisor;
  do not introduce a second execution process or cross-host claim.

Startup validation proves only bound addresses/ports, route inventories, one child
and local readiness. Deployment acceptance must separately prove the applied
network boundary from an independent browser-network client. Configuration text,
loopback binding and BFF header stripping are not evidence that isolation is in
force.

### Tests

- route-contract tests for each fixed BFF operation and owner/action/resource
  builder;
- forged `Authorization`, proxy, tenant/domain/principal, and product-authorized
  headers rejected;
- direct public/internal port and `/api/internal/*` bypass tests from the browser
  network;
- one supervised child PID/worker; either-listener startup/exit failure closes
  both; existing supervisor-loss and confirmed-child-exit ownership stays intact;
- old header-bearing endpoints cannot access the same protected fact through any
  exposed route;
- frontend build contains no credential or deployment principal/scope default.

## 4. I3 — Real-browser and security acceptance

Run a **minimal real-browser acceptance client** against the formal
session/CSRF/typed-BFF/backend/PostgreSQL chain and the normal supervised Execution
entry. The client may be a small task-owned static page or browser driver exposing
only the controls needed to exercise the formal routes; it must not import, wait
for, or claim delivery of IMPL-299's complete business Workbench pages. Use
distinct non-production credentials and no real external provider beyond the
already accepted bounded test executor required by the allocated acceptance task.

Required scenarios:

1. two browsers sign in as different callers and never share identity/scope/grants;
2. forged headers, foreign Origin, stale CSRF, expired/rotated/revoked session, and
   direct internal access fail closed;
3. denied prepare/approve/start/read causes zero protected writes and zero provider
   calls;
4. create Problem, obtain exact follow-up grants, create Criteria/Set, prepare Plan;
5. prove creator without APPROVE cannot approve; independently authorize and
   approve;
6. independently authorize START and execute the exact approved Plan;
7. show execution result with Evidence restricted, then independently authorize
   Execution, Invocation, Resource Use, and Evidence-reference reads;
8. revoke each grant and prove current request and replay enforcement;
9. force an unknown response around grant commit and safely recover by idempotency
   status;
10. force post-dispatch timeout/crash and prove `OUTCOME_UNKNOWN` with no automatic
    redispatch;
11. inspect browser persistence, build artifacts, URLs, logs, traces, and error
    bodies for credential/session/CSRF leakage.

Document exact commands, environment topology, applied network controls, independent
browser-network probes, test identities, redacted evidence, commit/tree, and
limitations. Passing I3 proves the formal browser identity/BFF chain only; it does
not claim the 299 Workbench is delivered. Do not run unrelated live-service tests.

## 5. Compatibility and rollout constraints

- retain existing non-browser Bearer contracts on the private listener while BFF
  adapters are introduced;
- do not backfill historical identity from caller headers or auto-create grants for
  historical resources;
- no endpoint is browser-enabled until its trusted-context adapter, exact grant
  map, non-disclosure tests, and old-route cutoff all pass together;
- if a legacy endpoint can reach the same protected fact and cannot be made private,
  that resource remains `OPEN / NOT_BROWSER_AVAILABLE`;
- session or grant authority outage disables protected Workbench operations; no
  fallback to headers, shared credentials, cached authorization, or frontend
  decisions;
- revocation does not mutate historical approvals, executions, Resource Use, or
  Evidence;
- no Ready transition, merge, migration, deployment, IMPL-299 closure, or release
  claim follows automatically from completing a task;
- IMPL-299 remains blocked until every prerequisite capability it uses is
  Human-accepted, persistently integrated, named by an exact interface/configuration
  contract, and backed by real-browser evidence on the formal chain. I3 alone does
  not remove that block.

## 6. Human choices and existing gates

Architecture acceptance must accept or revise:

- BFF rather than authenticated ingress for the bounded first delivery;
- Browser Session Authority and Grant Administration Authority ownership;
- PostgreSQL schemas, immutable static-generation activation and per-subject
  owner-minted continuation model;
- per-user bootstrap credential limitation and initial administrator model;
- single-child dual-listener topology and deployment-proven network cutoff as a
  release-blocking constraint;
- candidate lifecycle recommendations: 5-minute login nonce; at-least-256-bit,
  at-most-30-day bootstrap credential; 30-minute idle/8-hour absolute session; and
  10-minute CSRF/continuation. These remain recommendations until accepted.

The existing implementation authorization, architecture-conflict stop, PR
acceptance and persistent-integration gates remain. They do not multiply into a
new Human start approval for each of I1, I2 and I3. Before an actual deployment or
persistent integration, Human must supply or approve the environment-specific
choices that cannot be inferred from the candidate:

- named identities/administrators, credential delivery and rotation runbook;
- accepted cookie/session/CSRF/continuation lifetimes, allowed hosts/origins,
  Secret References, ingress and NetworkPolicy manifests;
- migration execution, rollback plan, evidence environment, and acceptance result.

Enterprise IdP/SSO, two-person administration, cross-host HA, Evidence content,
and complete Resource Use product APIs remain separately gated future work.
