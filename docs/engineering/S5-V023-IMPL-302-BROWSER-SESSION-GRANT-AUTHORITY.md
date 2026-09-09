# S5-V023-IMPL-302 Browser Session and Grant Authority

Status: I1 foundation implemented; public Workbench BFF remains disabled.

Base: `270d193b936a61c65d4fa20d9a62709a5c2b56ad`

Architecture authority:
`architecture/s5/v0.2/S5-V023-ARCH-300-TRUSTED-BROWSER-IDENTITY-EXACT-RESOURCE-AUTHORIZATION-V1.md`.

## Delivered ownership and ports

Browser Session Authority is the only writer of `browser_identity`. It exposes
typed authentication, login-nonce, session create/current/rotate/logout and
credential/exact-session revocation ports. Only it or an explicitly trusted
service authenticator constructs `TrustedRequestContext`. Raw bootstrap
credentials, login nonces, session secrets, CSRF tokens and continuation
envelopes are not stored.

Grant Administration Authority is the only writer of `authorization_admin`. It
exposes exact grant request, subject-bound continuation offer/inbox/atomic
consumption, decision/rejection, current authorization and revocation/surrender
ports. Dynamic meta-grants, wildcard or unknown operations, issuer self-approval,
scope crossover, partial grant bundles and idempotency payload drift fail closed.

Immutable configuration files are digest-addressed. PostgreSQL's active row is
the activation authority; file publication or process reload is not activation.
The process read/write barrier pins one generation per protected call, and
credential removal plus derived-session revocation commits with generation
activation. Session and dynamic-grant revocations remain PostgreSQL-only
linearization points.

The owner-only host control record is independent of database backup and the
existing supervisor temporary state. Missing, malformed, stale, non-owner-only or
database/generation/recovery-mismatched records close protected readiness.
Controlled restore increments the recovery epoch, revokes restored sessions and
continuations, removes restored grants from the effective projection, and
requires explicit operator completion. It does not claim to detect an arbitrary
uncontrolled database rollback.

## Migration

`0018_browser_session_grant_authority.sql` is owned by this Session and leaves
`0001` through `0017` unchanged. It adds the `browser_identity` and
`authorization_admin` schemas, independent checksum ledgers, append-only session,
decision, grant, revocation, continuation, recovery and audit facts, plus the
CAS/current projections required by I1. `PostgresAuthorityRepository` is the
single adapter/writer for these schemas.

Migration validation covers a fresh authority database, upgrade after the full
`0017` baseline, checksum replay, and transaction rollback on rejected
self-approval. Tests use a dedicated PostgreSQL database per case.

The candidate `0018` SHA-256 is
`b493349a53efb6bbf6bda33df6830a172eed2a5c6e5a596cb3703a6ca297ca13`.
Migration execution uses a bounded 30-second statement timeout and a separate
3-second lock timeout. The migration SQL itself does not alter business-request
or browser-health lifetimes.

## Required configuration

There are no privileged production defaults. Startup requires all of:

- the PostgreSQL URL and exact `0018` migration path;
- an absolute immutable-generation path and expected SHA-256 digest;
- absolute external Secret paths for CSRF and continuation signing keys;
- an operator-managed absolute host recovery-control path;
- the normalized database fingerprint and explicit deployment operator ID; and
- explicitly supplied login-nonce, idle, absolute-session and CSRF lifetimes.

The static generation has a closed schema and source classifications. Browser
credentials cannot consume `SERVICE_ONLY` grants. Dynamic grants cannot create
`GRANT_ADMIN` or continuation-assignment meta-grants. A generation activation
must increase the generation, cannot decrease recovery/control epochs, and must
carry forward all revocation tombstones.

Production Host/Origin, administrator identities, Secret values and deployment
paths remain operator inputs; test values are not production approvals.

## I2 and I3 obligations

I2 must consume these ports through the same process composition root and wrap
each protected request in `AuthorityGenerationController.protected_request()` so
the generation remains pinned across session/current-grant checks and the typed
domain call. It must:

- map session cookies and service credentials to `TrustedRequestContext` without
  accepting identity fields from browser headers or bodies;
- validate allowlisted Origin and session-bound CSRF before every state change;
- call current exact authorization before lookup, list/count, replay disclosure,
  owner joins, provider calls or writes;
- use owner-validated continuation minting and Grant Administration consumption,
  without forwarding envelopes between principals or auto-granting READ/APPROVE;
- preserve minimum-disclosure errors and no-store/redacted responses; and
- implement the accepted dual-listener/static-route bootstrap without creating a
  second Execution owner or altering current service-only Bearer behavior.

I3 must provide the accepted RBAC/admission/NetworkPolicy/browser-network proof.
Until I2 and I3 pass, the public BFF stays disabled, browser authentication is not
available, and IMPL-299 is not unblocked.

## Validation entry points

Unit validation:

```text
uv run pytest -q \
  console/backend/tests/test_authority_configuration.py \
  console/backend/tests/test_browser_session_application.py \
  console/backend/tests/test_authority_recovery.py
```

Dedicated PostgreSQL validation (zero skips required):

```text
AUTHORITY_I1_TEST_DATABASE_URL=<exclusive-postgresql-url> \
uv run pytest -q \
  console/backend/tests/test_authority_foundation_postgres.py -r s
```

CI provides `AUTHORITY_I1_TEST_DATABASE_URL` in the quality job and fails the
dedicated step if pytest reports any skipped test.

Local candidate validation on 2026-09-09 used a Session-labelled PostgreSQL 15
container and disposable root databases:

- complete I1 PostgreSQL selection: 8 passed, zero skipped;
- remaining three 302 test paths: 10 passed;
- `make check` with I1 enabled: Ruff and format passed; 1574 tests passed and
  110 unrelated environment-dependent tests skipped.
