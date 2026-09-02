# S5-IMPL-078 — Deterministic Release Runner

## Scope and authority

This package adds release-rehearsal orchestration only. It changes no product,
backend domain, migration, CRD, Kubernetes, runtime, public/staging, deployment,
DNS, TLS, firewall, or release-candidate behavior. It did not run attempt-06 or
perform a cutover.

The fresh allocation check found no branch, tag, issue, open PR, or repository
path using suffix `078`. The implementation started from durable `origin/main`
`045c01466ad95ff6be4200cb8d189a5d0ea54101`. PR #114 was already merged and its
backend/core persistence paths do not overlap the five paths in this package.

## Implemented result

- Strict versioned contract with the authorized product source/tree,
  acceptance-tool minimum, LIVE_DEMO/lockfile identity, exact local image
  digests, isolated ports, workspace/runtime identity, role policy, exact
  interpreter, approved source roots, and fail-closed retention policy.
- Allowlisted stage records and sanitized fixed error classifications.
- No-mutation preflight.
- Digest-pinned PostgreSQL 15 container-client micro-rehearsal with exact-role
  TCP identity, DDL, CRUD, rollback, mode-0600 ephemeral credentials, and
  ownership-verified cleanup.
- Deterministic Docker fault categories and focused negative controls for
  contract shape, interpreter, image pinning, port duplication, unsafe SQL
  identifiers, disclosure, and unowned cleanup.
- Complete readiness/private-precheck orchestration with migrations 0001–0007,
  pinned Qdrant, composite product/acceptance provenance, locked LIVE_DEMO
  build, immutable candidate, explicit venv/browser identities, REL-076 Harness,
  recursive disclosure scanning, optional sentinel continuity, and exact
  cleanup.

## Current validation evidence

- Focused Ruff and formatting checks: passed.
- Focused runner tests: `28 passed`; combined runner/REL-076 Harness focused
  suite: `55 passed`.
- Repository-contract `preflight`: passed with all mutating stages marked
  `NOT_APPLICABLE`.
- Real isolated `micro-postgres`: passed through provenance, Docker preflight,
  PostgreSQL start/provision/readiness, and owned cleanup. No owned containers or
  credential files remained.
- Real complete `readiness-rehearsal`: passed every structured stage through
  browser acceptance, nondisclosure, manifest equality, continuity, and owned
  cleanup.
- Real complete `private-acceptance-precheck`: passed the same fail-closed
  sequence without creating or authorizing a release candidate.
- Frontend lint/build: passed.
- `make check`: `1218 passed`, `22 skipped`, one existing Starlette/httpx
  deprecation warning.

Final full validation, exact-head CI and Draft PR identity are recorded only at
Human Checkpoint A. This package grants no deployment, release-candidate,
cutover, merge, or promotion authority.
