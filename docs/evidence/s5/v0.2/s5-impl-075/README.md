# S5-IMPL-075 — Browser Harness Preflight and Minimum Disclosure

## Result boundary

This package corrects only the repository-owned immutable-browser acceptance
harness defects identified by the S5-DEPLOY-069 attempt-05 forensic result. It
does not change product behavior, backend domain or persistence behavior,
migrations, Runtime, Operator, Kubernetes, CRDs, OpenClaw, deployment runners,
servers or attempt-05 Evidence.

## Implemented controls

- The frontend build step records a sanitized `LIVE_DEMO` identity outside the
  release. The identity is bound to the exact immutable `dist` file manifest;
  missing, incorrect, malformed or stale identity fails before startup.
- CI provisions and uses the exact `browser_validation` PostgreSQL login. Before
  backend startup that role must prove its identity and transactional
  schema/table migration plus insert/select/update/delete readiness.
- Playwright trace, screenshot and video retention is disabled. Raw backend and
  browser output is discarded, and any Playwright output directory is removed
  before the allowlisted acceptance diagnostic is written and scanned.
- The retained diagnostic contains only sanitized acceptance/release correlation
  plus journey ID, phase, assertion category, status code, sanitized exception
  class, correlation digest, restart relation and completion timestamp.
- The existing disclosure patterns remain in force and are extended for request
  bodies, runtime settings, instruction content and internal filesystem paths.
  Recursive plain-file and ZIP scanning remain fail closed.

## Negative and positive controls

Focused tests preserve a pre-correction scanner pattern set and demonstrate that
attempt-05 request-body, runtime-setting, instruction-content and internal-path
controls were previously undetected. The corrected scanner rejects each control
without echoing it. Additional controls prove:

- missing/non-live/stale build identities fail closed;
- the exact PostgreSQL role with migration/read/write readiness passes;
- the wrong role and missing schema-creation grant fail closed;
- raw Playwright trace/error-context retention is absent;
- useful sanitized plain and compressed diagnostics pass recursive scanning.

## Local validation

- Focused Ruff and format checks: passed.
- Focused harness/disclosure tests: `27 passed`.
- Frontend lint: passed.
- Frontend build: passed.
- `make check`: `1183 passed`, `13 skipped`, one existing Starlette/httpx
  deprecation warning.
- `pre-commit run --all-files`: passed.

Fresh exact-head CI and Draft PR identity are recorded at Human Checkpoint A;
release, merge and attempt-06 authority are not granted by this package.
