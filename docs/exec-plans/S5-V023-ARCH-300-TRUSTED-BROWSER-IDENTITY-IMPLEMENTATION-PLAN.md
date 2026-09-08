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
after the required deployment boundary is testable. This plan does not assign
identifiers or Sessions.

## 2. I1 — Session and grant authority foundation

### Backend

- add typed `TrustedRequestContext`, `Authenticator`, `BrowserSessionRepository`,
  `GrantAdministrationRepository`, and `CurrentAuthorizationReader` ports;
- adapt the current `GovernedExecutionAuthority` credential verification behind
  `Authenticator` without weakening existing non-browser Bearer behavior;
- add Browser Session application service: create, authenticate, rotate, expire,
  credential-wide revoke, exact-session revoke, and logout;
- add Grant Administration application service: request, continuation resolution,
  decide/reject, activate atomic bundle, inspect, expire, revoke/surrender, CAS,
  and idempotent replay;
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
- `authorization_admin.grant_requests`, immutable request members, decisions,
  owner-minted continuations, individual grants, revocations, idempotency claims,
  and current-effective projection;
- scoped keys/FKs, positive aggregate versions, canonical payload digests, bounded
  reason fields, and expiry indexes;
- no credential, cookie, CSRF token, private content, raw provider/model payload,
  or arbitrary policy document.

The migration must be atomic and rollback-safe. It must not change migrations
0001–0017, current domain tables, public CRDs, or the Kubernetes API group.

### Tests

- credential-to-session mapping for two principals/scopes;
- cookie hashing, rotation, overlap boundary, idle/absolute/credential expiry,
  logout and administrative revoke;
- CSRF signing/expiry/session binding and log redaction;
- grant request/decision/rejection/revoke/surrender, exact matching, no wildcard,
  meta-grant enforcement, CAS, replay conflict and fault-injected atomicity;
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

### Deployment configuration

- one TLS same-origin public route exposes only static assets and typed Workbench
  routes;
- bind internal APIs to a separate private listener/service or enforce an
  equivalent ingress and NetworkPolicy deny from browser-reachable networks;
- explicitly deny `/api/internal/*` and the backend internal port at public ingress;
- configure exact Origin/Host allowlists, request-size limits, timeouts, secure
  response headers, and credential/session/CSRF redaction;
- supply session/CSRF signing material and bootstrap authority file only through
  existing Secret Reference mechanisms;
- keep the governed execution child under its existing single-host supervisor;
  do not introduce a second execution process or cross-host claim.

### Tests

- route-contract tests for each fixed BFF operation and owner/action/resource
  builder;
- forged `Authorization`, proxy, tenant/domain/principal, and product-authorized
  headers rejected;
- direct public/internal port and `/api/internal/*` bypass tests from the browser
  network;
- old header-bearing endpoints cannot access the same protected fact through any
  exposed route;
- frontend build contains no credential or deployment principal/scope default.

## 4. I3 — Real-browser and security acceptance

Run against real BFF/backend/PostgreSQL and the normal supervised Execution entry.
Use distinct non-production credentials and no real external provider beyond the
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

Document exact commands, environment topology, test identities, redacted evidence,
commit/tree, and limitations. Do not run unrelated live-service tests.

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
  claim follows automatically from completing a task.

## 6. Human gates

Before I1 allocation, Human must accept or revise:

- BFF rather than authenticated ingress for the bounded first delivery;
- Browser Session Authority and Grant Administration Authority ownership;
- PostgreSQL schemas and owner-minted continuation model;
- per-user bootstrap credential limitation and initial administrator model;
- private internal listener/network cutoff as a release-blocking constraint.

Before deployment, Human must separately approve:

- named identities/administrators, credential delivery and rotation runbook;
- exact cookie/session/CSRF lifetimes, allowed hosts/origins, Secret References,
  ingress and NetworkPolicy manifests;
- migration execution, rollback plan, evidence environment, and acceptance result.

Enterprise IdP/SSO, two-person administration, cross-host HA, Evidence content,
and complete Resource Use product APIs remain separately gated future work.
