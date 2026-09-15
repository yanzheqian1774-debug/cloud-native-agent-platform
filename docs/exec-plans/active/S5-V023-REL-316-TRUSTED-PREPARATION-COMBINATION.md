# S5-V023-REL-316 — 299/305/310 trusted preparation combination

## Allocation and fixed inputs

- Session: `S5-V023-REL-316`.
- Type / gate: `REL / G1 / BOUNDED_INTEGRATION`.
- Human routing entry decision: `ACCEPTED_WITH_CONSTRAINTS`.
- Writer: this REL Codex conversation is the sole integration writer.
- Branch: `codex/s5-v023-rel-316-trusted-preparation-combination`.
- Isolated worktree: `/Users/tristan/.codex/worktrees/0c12/cloud-native-agent-platform`.
- Consumer source/tree: IMPL-310 `62ed0fee0ccf322a4276a7f20c65151395d726e8` / `57813acbe9bd7a07c671145e12385a98f0a66977`.
- Fixed IMPL-305 source/tree: `5a32fbb918a3c30ad50141e8bfbe7613673dc412` / `36ae844488fe94c2b0c2e10760a063e7e5a14616`.
- Fixed IMPL-299 source/tree: `020c1d6eae35c47a418d210b5e982e8d54b03889` / `9ecf47874411e6656371b0eef973d36b4dde070e`.
- Audited target main source/tree: `f189212232fc194859a695f0307e83b0c7b73c0f` / `a8a9251d5d2e47605d18bb63e362164ec4c920d2`.
- Pull request: Draft [#172](https://github.com/yanzheqian1774-debug/cloud-native-agent-platform/pull/172); it remains not Ready.
- Human gates: Ready, merge, deployment, release, durable-integration acceptance, and Session close remain `PENDING / HUMAN_ONLY`.

## Candidate validation status

The executable candidate is
`674a1d13f54bc41b82e967b0c6d7309dc074cbee`, tree
`cca1f448efb8de40fde6a45fd9208f2fa9c879bf`. Symbol-level combination,
targeted PostgreSQL tests, frontend lint/live build, default and dedicated
Playwright collection, the native-HTTPS click journey, `make check`, and normal
commit hooks have passed. The [handoff](../../engineering/S5-V023-REL-316-HANDOFF.md)
and [evidence index](../../evidence/s5/v0.2/s5-v023-rel-316/README.md) record the
results and boundaries. Draft PR creation is complete. Automatic CI tracking is
the remaining Codex-owned delivery step; all Human gates remain pending.

## Directional startup result

At REL start on 2026-09-15, all three fixed commit objects resolved locally and
their trees exactly matched the allocated identities. `git ls-remote` reported
remote `main` at the audited `f189212...` object, which is an ancestor of the
fixed IMPL-310 consumer. Repository text, remote heads, PR titles/branches and
issues inspected for `REL-316` and `299/305/310` showed no material numbering or
ownership collision. Original Draft PRs #164, #165 and #170 retained the fixed
305, 310 and 299 heads. The REL branch was therefore created from fixed 310;
`main` was not substituted for it.

IMPL-315 remains independently authorized on
`codex/s5-v023-impl-315-native-execution-handoff`. This REL will neither read
nor consume its uncommitted work, will not create migration `0022`, and will not
change Native authorization, dispatch, fencing, or terminal semantics.

## Accepted scope and invariants

1. Preserve IMPL-310 formal grant request/independent decision, self-approval
   prohibition, frozen Employee command recovery, repository compatibility,
   and Employee `CREATE`, exact `READ`, `VALIDATE`, business `APPROVE`, and
   `PUBLISH` semantics.
2. `EMPLOYEE/CREATE employee:collection` never implies Employee or Agent
   `READ`.
3. Introduce only IMPL-299 Problem/Criteria product semantics required by this
   closure, including creator continuation/receipt and exact readback.
4. Treat IMPL-305 as provenance and a gap/reference source. A commit absent
   from ancestry is not evidence that the capability is absent.
5. Keep Problem/Criteria and Employee independent. No automatic
   Problem-to-Employee binding, Plan product chain, model/resource invocation,
   Native execution, Execution/Evidence/Outcome expansion, public CRD/API
   group, frozen Contract, authentication architecture, or persistence-authority
   change is in scope.
6. URL, query, purpose, and frontend state select a view only. Authorization is
   derived from trusted session context and current server-owned grants.
7. Grant administration approval and Employee lifecycle business approval are
   separate controls, permissions, and audit facts.

## Implementation sequence and symbol ownership

### 1. Protect the 310 consumer

Retain targeted regression exits for the 310 authority/BFF/Employee
repositories, compatibility doubles, bootstrap startup, frontend Employee
controls, and real-service harness. No 299 or 305 whole-file replacement is
allowed.

### 2. Classify 305 at call sites

Compare 305-only methods and consumers against 310. Record each as already
equivalent, strengthened in 310, composition reference only, or an actual
missing seam. Only a missing seam with a current call site and contract/test
need may be adapted. Do not re-import duplicate grant DTOs or routes.

### 3. Add the 299 Product-domain slice

Bring in additive migration `0020`, typed Product repository/application
continuation behavior, Problem/Criteria Workbench operations, exact target
validation, frontend API/components, and focused tests. Preserve immutable
revisions/digests, ordered Criteria Set membership, idempotent replay, CAS,
scope isolation, and PostgreSQL authority.

### 4. Reconcile shared seams by symbol

- `authority_configuration.py`: exact owner/action/prefix/requestability union;
  no wildcard or recursive meta-grant path.
- `authority_contracts.py`, `authority_postgres.py`, and
  `grant_administration_application.py`: retain 310 compatibility,
  independent decision/CAS/idempotency, and Employee continuation; add only
  creator continuation/receipt interfaces required by 299.
- `workbench_grant_targets.py`: owner-dispatched exact Problem/Criteria and
  Employee/Agent validation; unknown owners fail closed.
- `workbench_bootstrap.py`, domain bootstraps, and `app.py`: one lifecycle and
  one Workbench route set with explicit dependencies and safe close order.
- `workbench_bff_schemas.py` and `workbench_bff.py`: one strict DTO/operation per
  route; trusted session, origin and CSRF checks remain.
- `App.tsx`, navigation, and scoped CSS: retain both entries and expose one
  `/authorization-admin` container. It renders domain-specific summaries from
  the formal request response without treating purpose/query as authority.

### 5. Add the REL acceptance boundary

Create a REL Playwright config whose allowlist contains exactly one combination
click spec and whose output namespace is unique. Extend the isolated browser
harness only through backward-compatible parameters. The journey uses dedicated
PostgreSQL, real BFF, native HTTPS, Chromium, two independent browser principals,
and visible controls at 1440x900. Fixtures may establish credentials, initial
administrator grants and prerequisite referenced resources, but may not perform
an accepted business operation or pre-seed its final result.

The visible journey performs trusted login; Problem, Criterion and Criteria Set
create/grant/recover/read; Employee CREATE request and independent grant
decision; frozen CREATE recovery; denied pre-grant READ; exact Employee/Agent
READ grants; `VALIDATE`, business `APPROVE`, and `PUBLISH`; and fresh-reload
readback. API/PostgreSQL reads are corroboration only. Existing mock and
service-chain specs keep their evidence classification.

## Validation strategy

Run and record:

1. migration and authority/grant/Product/Employee unit and dedicated PostgreSQL
   tests;
2. BFF/bootstrap/validator tests for duplicate routes, malformed DTOs, unknown
   owner, wrong target/scope/revision, self-decision, stale CAS, conflicting
   replay, and repository compatibility;
3. frontend source tests, lint, and production build;
4. default and REL Playwright `--list` audits;
5. the native-HTTPS/PostgreSQL/Chromium click journey at 1440x900;
6. `make check`, normal hooks, focused diff/status review, and Draft-PR CI.

Evidence records candidate source/tree, fixed-input provenance, actual commands
and results, environment/ports, spec/step names, screenshots and artifact
SHA-256, limitations, and rollback. Local runs have no CI run/job identifiers.
Network interruption is distinct from test failure.

## Compatibility, risk, stop, and rollback

Compatibility is additive at internal Workbench seams. Existing 310 public BFF
shapes and repository doubles remain supported. Principal risks are regression
of 310 compatibility, duplicate route/DTO registration, single-domain target
validation, authorization derived from display metadata, mixed Playwright
collection, and cross-task migration/shared-file drift.

Stop for G2 if completion requires changing a frozen Contract, authentication
architecture, persistence authority, public CRD/API group, or Native/Control
Plane ownership. If `main` later includes IMPL-315, compare the fixed shared
symbols and reconcile only REL scope; do not import Native behavior.

Use reviewable checkpoints for plan/provenance, Product persistence, shared
backend seam, frontend/admin composition, and REL acceptance/evidence. Reverting
a later checkpoint must leave fixed 310 semantics intact. Code rollback is a
commit revert or branch abandonment; database restore/recreate is handled
separately and never erases recorded facts. Original input refs, PRs, Sessions,
databases, certificates and artifacts remain untouched.
