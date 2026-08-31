# S5-IMPL-044 Evidence

## Boundary

This change adds an internal-only, read-only Accounting Read Model. It creates no
API route, frontend surface, database, Kubernetes access, Provider call, model call,
billing authority, quota, chargeback, or operator-visible Accounting capability.

The namespace and security domain are the complete current aggregation boundary.
They are not represented as enterprise Tenant or Organization authority. Every
source and linked record is scope-validated before any count is returned; mixed or
ambiguous input fails closed without disclosing foreign identities or counts.

## Input authorities

The exact source authorities are:

- immutable `SharedExecutionSnapshot` values and their existing Execution Evidence;
- explicitly scoped predecessor/successor `JourneyOutcome` comparison pairs;
- existing immutable `InterventionEventRecord` values;
- existing immutable `OutcomeFeedbackRecord` values.

The component neither reads these authorities from storage nor changes their
identity, lifecycle, content, or provenance.

## Derived metrics

The model deterministically derives execution, attempt, and Provider-call counts;
success, failure, denial, and unknown counts/rates; Workflow, Task, and Platform
Execution Identity coverage; Evidence completeness and limitation counts;
intervention and feedback linkage; and comparable Outcome improvement, regression,
or no-change counts. It propagates exact snapshot, Evidence, and Outcome identities
and the maximum authorized Evidence high-water mark. Output ordering and primitive
serialization are stable, and exact duplicate inputs are idempotent.

Comparable numeric values use the bounded convention that a higher successor value
is an improvement, a lower value is a regression, and equality is no change. Missing
values or mismatched metric names are not treated as comparable.

## Availability and unsupported claims

Availability is explicit:

- `MEASURED` means the supplied facts support the metric;
- `PARTIAL` means a source snapshot is partial, stale, or limitation-bearing;
- `NOT_MEASURABLE` means there is no valid denominator or source fact.

Token usage, monetary cost, and elapsed latency are always `NOT_MEASURABLE` because
the authorized Evidence does not contain those facts. The model makes no price,
cost, billing, latency, tenancy, Provider-certification, or financial claim.

## Validation

Validation on the authorized baseline completed successfully:

- `uv run pytest console/backend/tests/test_execution_accounting.py`: 19 passed;
- `uv run pytest console/backend/tests/test_execution_snapshot.py`: 11 passed;
- the required Evidence/security/shared-view regression group: 44 passed, with one
  existing Starlette/httpx deprecation warning;
- `uv run ruff check .`: passed;
- `uv run ruff format --check .`: 172 files already formatted;
- `git diff --check`: passed;
- `make check`: 1006 passed, with the same existing deprecation warning;
- `uv run pre-commit run --all-files`: all Ruff lint, Ruff format, and pytest hooks
  passed and made no file changes.

## Remaining limitations

- This component is reusable backend logic only and is not exposed through the
  product.
- It aggregates only already-authorized snapshots supplied by a caller; it performs
  no discovery or persistence.
- Namespace equality is required for existing intervention/feedback `tenantId`
  fields, without claiming that namespace is a complete enterprise tenancy model.
- Outcome direction uses the documented higher-is-better bounded convention; no
  generalized metric semantics or business-value authority is introduced.
