# S5-V023-REL-316 handoff

## Result

The bounded 299/305/310 product combination is implemented on
`codex/s5-v023-rel-316-trusted-preparation-combination`. IMPL-310 remains the
consumer base. IMPL-299 Problem/Criteria behavior was introduced by symbol;
IMPL-305 supplied provenance and assembly comparison only because its required
request/decision/Employee capabilities were already present or strengthened in
the 310 consumer.

The combination has one trusted Workbench authority composition, one BFF route
set, one `/authorization-admin` page, and owner-dispatched exact target
validation for Problem/Criteria, Employee, and Agent. The administrator page
derives its domain presentation from the formal request response and states
that URL/query/purpose is not authority. Grant administrator approval and
Employee business `APPROVE` remain separate UI actions and authorization facts.

The PostgreSQL creator receipt migration is `0020`. Migration `0022`, Native
authorization/dispatch/fencing/terminal semantics, and uncommitted IMPL-315
state were not read or changed.

## Implementation checkpoints

- `bdf9f43` — G1 plan and Registry allocation.
- `d7de31e` — Problem/Criteria persistence, creator continuation, owner-dispatched
  target validation, bootstrap and BFF composition.
- `cfa474e` — frontend Problem/Criteria composition, unified authorization
  administration, REL harness/spec/workflow, and lifecycle failure truthfulness.
- `674a1d1` — isolate the dedicated REL spec from both default and IMPL-299 live
  Playwright collection.
- `3885232` — preserve fixed-310 admin control names and update the affected
  combined shell/legacy-label regression expectations.

The passing executable candidate is
`3885232624fc9d24fabb73682c4148e0d8bb313d`, tree
`f66906c35216c01449dc0a8fd738280119c298d0`. The evidence-only delivery commit
follows that candidate.

## Validation

- Targeted real PostgreSQL, authority, Product, Employee, bootstrap, BFF and
  frontend source tests: `69 passed`, one dependency deprecation warning.
- `make check`: Ruff passed, format passed for 422 files, pytest `1678 passed / 168 skipped`, one dependency deprecation warning.
- Frontend lint: passed.
- Live production frontend build: passed; Vite reported its existing large
  chunk advisory.
- Default Playwright collection: `77 tests in 10 files`; REL real spec excluded.
- Dedicated REL collection: `1 test in 1 file`.
- Native HTTPS/PostgreSQL/Chromium click journey: `1 passed`, no retries, no
  skipped/unexpected tests. See the [evidence index](../evidence/s5/v0.2/s5-v023-rel-316/README.md).
- Normal commit hooks passed. CI run/job identifiers are unavailable until the
  Draft PR is pushed and created.

The initial broad PostgreSQL command produced two failures before correction:
one database was not blank for the execution migration test, and the combined
service method temporarily returned a public reference where the fixed 310
internal contract requires an opaque continuation. The rerun used an exclusive
blank database and restored the old internal service contract while keeping
digest references on the public BFF. The final targeted run passed all 69 tests.

## Known limits and Human gates

This REL does not add automatic Problem-to-Employee binding, Plan, model or
resource invocation, Execution/Evidence/Outcome, public revoke, public CRD/API
changes, mobile-specific acceptance, or Native integration. The browser fixture
uses controlled credentials and prerequisite Agent/resource data as documented
in the evidence index; every accepted business transition is performed through
visible controls.

Ready, merge, deployment, release, durable-integration acceptance, original PR
or Session closure, and final Human acceptance remain unperformed and
Human-owned. If target `main` later contains IMPL-315, compare the fixed shared
symbols before integration and do not import or modify Native behavior without
new authorization.

## Rollback

Revert the REL commits in reverse order or abandon the branch. Preserve the
fixed source refs and their original Draft PRs. Handle the dedicated database
separately from code; retain evidence first, and do not erase facts or treat
cleanup as recovery.
