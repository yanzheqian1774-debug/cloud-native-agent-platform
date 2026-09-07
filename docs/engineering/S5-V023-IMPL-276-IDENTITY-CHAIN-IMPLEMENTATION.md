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

`employee_identity_support.py` is test support, not a stable operator tool or
production CLI. It assembles real Agent, Workflow and Runtime Profile publication
and real Workflow Control approval for the PostgreSQL acceptance suite;
`test_employee_identity_chain_postgres.py` exercises both execution retry paths.
No frontend, provider execution or public endpoint is introduced.

## Internal HTTP boundary and compatibility

The existing internal v0.2.3 Digital Employee API now uses the independent
Employee Definition authority consistently. Its Definition list and exact-revision
detail endpoints no longer return Agent Definitions. Separate internal operations
create, validate, approve and publish an Employee Definition; publication does not
grant matching. Instance creation consumes the returned
`employeeDefinitionId` and `employeeDefinitionRevisionId`. Agent Definitions
remain independently managed by the Agent API and appear only as exact composition
members.

The wire change is intentional and compatibility-significant. The old ambiguous
`definitionId` and `definitionRevisionId` Instance fields are rejected; clients
must use the explicitly named Employee Definition fields and must first create and
publish that independent object. An Agent Definition ID cannot be submitted as an
Employee Definition ID, and no historical Agent identity is converted. New
Employee-backed Instance responses use `employeeDefinition`; historical records
remain authorized read-only results classified as `legacyDefinitionReference` and
cannot enter the new exact execution chain.

Authorization decisions are constructed from the authenticated internal principal,
not accepted from request DTOs. Missing authentication is distinct from scoped
non-disclosure. An absent or cross-scope Employee Definition returns the same
`EMPLOYEE_NOT_FOUND` response without partial writes. The real HTTP/PostgreSQL
acceptance creates and reads one Employee Definition, advances its exact revision
through validation, approval and publication, creates an Instance and Assignment,
rejects Agent identity masquerading, and proves stale-version, replay, restart and
cross-scope behavior. Start/retry remain internal application-service operations;
HTTP creation does not imply an HTTP execution endpoint.

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

The `Employee Identity Chain` CI workflow provisions an ephemeral PostgreSQL 15
service on an isolated GitHub-hosted job and runs the new tests plus affected
execution, employee and Workflow Control regressions. It runs for selected
pull-request events, main pushes and manual dispatch, has read-only repository
permission, persists no checkout credential, and fails if the selected suite reports
skips.
Both database environment variables are required. The workflow's test order starts
with migration-0008 compatibility tests on a disposable database, then exercises
additive migrations. Do not run schema compatibility fault injection against a
shared or production database. Every scenario uses unique scope/identity data.

For a pull request, GitHub reports the source SHA separately while checkout executes
the platform-generated merge SHA against the selected base. The workflow logs both;
the merge-SHA result must not be described as a detached exact-source checkout.
For a main push they are the same commit. The final repository gates remain
pre-commit, `make check`, and candidate-bound CI.
The focused database suite separately proves that its tests are not skipped by the
default local environment. No provider execution, Resource Use, frontend acceptance,
release, merge or deployment completion is claimed by these backend tests.
