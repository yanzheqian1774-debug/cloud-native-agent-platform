# S5-V023-REL-316 evidence index

## Candidate and provenance

- Executed product candidate source: `3885232624fc9d24fabb73682c4148e0d8bb313d`.
- Executed product candidate tree: `f66906c35216c01449dc0a8fd738280119c298d0`.
- Fixed consumer IMPL-310: `62ed0fee0ccf322a4276a7f20c65151395d726e8` / tree `57813acbe9bd7a07c671145e12385a98f0a66977`.
- Fixed IMPL-305 input: `5a32fbb918a3c30ad50141e8bfbe7613673dc412` / tree `36ae844488fe94c2b0c2e10760a063e7e5a14616`.
- Fixed IMPL-299 input: `020c1d6eae35c47a418d210b5e982e8d54b03889` / tree `9ecf47874411e6656371b0eef973d36b4dde070e`.
- Audited target and delivery-time remote `main`: `f189212232fc194859a695f0307e83b0c7b73c0f` / tree `a8a9251d5d2e47605d18bb63e362164ec4c920d2`.
- The later evidence-only commit is not part of the executed product tree.

## Real click result

The dedicated allowlist collected exactly one test. It passed with `expected=1`,
`unexpected=0`, `skipped=0`, and a Playwright report duration of 6875.541 ms.
The fixture reached `READY` with `LISTENER_READINESS` as its final completed
stage.

The browser journey used only visible controls for accepted business writes:
trusted applicant login; Problem create; exact Problem access request; an
independent administrator login and decision; Criterion and Criteria Set
creation/authorization/readback; frozen Employee CREATE; separate Employee
READ; Agent READ and lifecycle grants; `VALIDATE`; business `APPROVE`;
`PUBLISH`; and fresh-reload formal readback. It contains no
`page.evaluate(fetch)`, request-context command helper, database write, or
pre-seeded final business result.

PostgreSQL read-only corroboration after the successful run returned:

- one Problem revision, one Criterion revision, and one Criteria Set;
- Employee aggregate version 4;
- Employee facts `CREATE,VALIDATE,APPROVE,PUBLISH` in ordinal order;
- 14 approved applicant requests, including the deliberately separate exact
  grant stages.

## Controlled fixture boundary

The fixture created ephemeral credentials, applicant list/create entry grants,
administrator exact inspect/decide meta-grants, requestability policy, two
published Agent candidates, supporting resource prerequisites, and the
pre-existing 310 regression samples. It did not create the accepted REL Problem,
Criterion, Criteria Set, or `employee-definition:rel-316`, and did not seed any
final state for those objects.

Environment: macOS 26.5.2 arm64, Python 3.12.13, Node.js 22.23.1, Playwright
1.62.1, Chromium 151.0.7922.34, and `postgres:16-alpine` image digest
`sha256:c05eced0bdb41ea9b95a656472a6aa4d50cad0d8a2e33d14eb1c53fd6204f2ae`.
The successful run used dedicated PostgreSQL port 55420, native HTTPS port
18416, control readiness port 18417, and a 1440 by 900 viewport. Test secrets,
private keys, and runtime signing material were removed by the runner and are
not included here.

## Files

- `playwright.json`: raw successful Playwright report.
- `startup.json`: bounded fixture startup receipt.
- `screenshots/rel-316-published-employee-1440x900.png`: fresh-reload published
  Employee readback.
- `screenshots/rel-316-problem-criteria-1440x900.png`: reselected formal Problem
  with exact Criteria Set readback after returning from Employee configuration.
- `SHA256SUMS`: SHA-256 index for the files above. The README is intentionally
  excluded so its own edit cannot invalidate the index.

The archived click report above is a local run, so that report's CI run/job
identifiers are `N/A`. Draft PR-head checks passed with these external records:

- CI `34937417907`: quality `104278262726`, frontend `104278262874`, browser
  `104278262868`;
- Employee Identity Chain `34937417939`: Problem/Plan `104278262794`, identity
  `104278262923`, Skill `104278262937`;
- REL-316 `34937417961`: native-HTTPS Chromium job `104278263190`;
- fixed-310 real Workbench `34937417918`: successful rerun job `104279509699`.

The fixed-310 initial job `104278263002` failed at its final transport-boundary
assertion. An exact local reproduction on a new exclusive PostgreSQL database
passed without code changes, followed by a fully passing CI rerun. It is
classified as an isolated transient test failure, not a network interruption.
These are PR-head checks, not exact-main CI.

Earlier retained local diagnostics are separate from the passing evidence:
missing local
`PYTHONPATH`, a non-live frontend build, the lifecycle failure-color seam found
and fixed, and a final navigation assertion that was corrected to use visible
Problem selection. No network interruption occurred.

## Reproduction and rollback

Build the frontend with `VITE_SUPPLIER_QUALITY_DEMO_MODE=live`, provide a new
exclusive PostgreSQL database through `REL_316_DATABASE_URL`, then run
`scripts/acceptance/s5_v023_rel_316_run.sh`. The script generates private test
material, runs the native-HTTPS server and the exact one-spec allowlist, retains
the non-secret report/screenshots/startup receipt, and removes secret runtime
material.

Code rollback is a normal revert of the REL commits in reverse order or branch
abandonment; it does not alter the fixed 299/305/310 refs. Database rollback is
separate: stop or discard only the dedicated REL database after preserving
evidence. No migration down-operation or deletion of recorded facts is used as
recovery.
