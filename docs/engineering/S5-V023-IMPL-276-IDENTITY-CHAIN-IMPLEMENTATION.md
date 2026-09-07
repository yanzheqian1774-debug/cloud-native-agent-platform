# IMPL-276 identity-chain prerequisite

Session remains `S5-V023-IMPL-276`. Resource Use is deferred. The accepted
[composition decision](../../architecture/s5/v0.2/S5-V023-IMPL-276-DIGITAL-EMPLOYEE-COMPOSITION-IDENTITY-ADDENDUM-V1.md)
is branch-recorded, not main-durable until separately authorized integration.

## Backend flow

1. `EmployeeDefinitionService` creates an independent immutable scoped revision
   with exactly one primary Agent; separate validation, approval, publication and
   matching decisions are append-only facts. Each operation requires its own
   permission. Member reads require independent permission; publication is not
   execution authorization. Exact references retain their owner's digest spelling,
   including `sha256:` for Workflow/Runtime Profile resources.
2. `PublishedEmployeeDefinitionAuthority` resolves the exact employee revision.
   Instance persistence validates the publication and resource revisions again in
   its transaction, recording a separate immutable binding. Assignment retains its
   existing owner, effective interval and history; instance locking serializes
   competing assignments.
3. Submit `execution_plan_bytes(canonical_workflow, assignment_id, instance_id)`
   as a **new** Plan's canonical content through the existing Workflow Control
   Plan repository and approval path. Its SHA-256 becomes `PlanRecord.plan_digest`.
   `ApprovedPlanIdentity` carries both the original candidate digest (`digest`)
   and this independent persisted Plan digest (`plan_digest`), plus exact Plan
   ID/version and approval ID. Existing Plan bytes are never inferred or converted.
4. Construct `ExecutionApplicationService(repository, authorization)` using a
   trusted internal authorization port, then call `start`/`retry`. No permission
   context is accepted from a public DTO. Missing permission fails before lookup.
   The transaction validates Instance, Assignment, publication, approved Plan,
   canonical content and exact relationships before writing Run/Task Run/Attempt
   and its employee binding. Replays also revalidate; invalid current eligibility
   is not bypassed by finding an old Attempt.
5. Retry creates one successor of a failed Attempt, retaining original employee
   revision/composition and approved Plan. Existing governed Workflow Control retry
   also copies canonical identity and binding within its existing UoW. It retains
   its own authorization, CAS, intervention and idempotency facts.
6. Product Placement requires new execution lineage. Persistence compares the
   primary Agent Definition ID, revision and digest with the Agent Instance record,
   the requested revision, and Runtime Instance relationship in one transaction.
   A mismatch leaves no placement request or decision.

The executable normal-flow example is `employee_identity_support.py` with real
Agent, Workflow and Runtime Profile publication and real Workflow Control approval;
`test_employee_identity_chain_postgres.py` exercises both execution retry paths.
No new public endpoint, frontend or provider execution is introduced.

## Migration and historical compatibility

`0014_digital_employee_identity.sql` adds only a separate schema, revisions,
lifecycle facts and immutable Instance/Execution bindings. It adds no mandatory
lineage columns to historical rows, and performs no backfill, relabel or rewrite.
The adapter verifies its checksum. Migrations 0001–0013 remain unchanged.

Historical Agent-derived Instances retain authorized readback with explicit
`LEGACY_UNVERIFIED` classification in the internal model. Raw historical records
remain available from their original repository. They cannot acquire new exact
execution lineage by being read, started or retried. Generic technical placement
history remains supported; it does not authorize Product employee placement.

## Validation

The `Employee Identity Chain` CI workflow provisions PostgreSQL 15 and runs the
new tests plus affected execution, employee and Workflow Control regressions.
Both database environment variables are required. The workflow's test order starts
with migration-0008 compatibility tests on a disposable database, then exercises
additive migrations. Do not run schema compatibility fault injection against a
shared or production database. Every scenario uses unique scope/identity data.

The final repository gates remain pre-commit, `make check`, and exact PR-head CI.
The focused database suite separately proves that its tests are not skipped by the
default local environment. No provider execution, Resource Use, frontend acceptance,
release, merge or deployment completion is claimed by these backend tests.
