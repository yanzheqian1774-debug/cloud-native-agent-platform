# Exact Service budget within the original cumulative ledger

The opt-in `service-local-budget.v1` policy adds a maximum of 20 calls and
1,000,000 microUSD for one exact Service subject, credential, work revision/digest
and BOUND source. Planning and Native MODEL decisions share this one limit. It does
not replace or enlarge the original ledger allowance/extension, profile, pricing,
expiry or current grants. The existing global ledger check still runs first.

This is an internal deployment seam, not a public API or a review/publication fact.
`authorizationEvidenceDigest` references the specific authorization for the scope;
automatic validation never creates or substitutes a `HUMAN_REVIEWED` record.

## Configuration and activation

Prepare a new owner-controlled regular 0600 file (no symlinks) containing:

| Field | Binding |
|---|---|
| `schemaVersion` | `service-local-budget.v1` |
| `namespace, securityDomain, ledgerId` | Existing original ledger scope |
| `subjectId, credentialId` | Exact Service identity from the bound Service policy |
| `work` | Same `resource_id, revision_id, digest` |
| `sourceBindingDigest` | Same original BOUND digest |
| `servicePolicyDigest` | Digest of the enabled final `BoundServicePlanningPolicy` |
| `allowedEventIds` | Exact same bounded event IDs, without additions |
| `expiresAt` | Aware expiry no later than that Service policy |
| `callCap, totalCostCapMicrousd` | `20, 1000000` for the approved scope; smaller values are allowed |
| `authorizationEvidenceDigest` | Exact approved scope/evidence digest |

1. After the normal release gate, explicitly apply migration
   `0080_service_local_budget.sql` on the **same original database**, through
   `service_local_budget.migrate(existing_budget_owner)` or the equivalent reviewed
   migration transaction and version-80 checksum/adapter record. It adds only
   `draft_provider_budget.service_scopes` and `service_reservations`, with immutable
   triggers and scoped foreign keys. Neither reserve nor dispatch runs DDL.
2. Pin the same private file as `CycleConfiguration.serviceBudget` (`FilePin`) and
   as `NATIVE_BOUND_SERVICE_LOCAL_BUDGET_POLICY` in the Service Native leaf. Include
   this key's file digest in that leaf's `policyFiles`. The Human leaf must not
   receive it. Native host preparation/configuration and two-leaf environment
   allowlists support this explicit pin. Keep the original extension selector.
3. The cycle startup check validates the bound policy and version-80 schema.
   Native `Configuration` validates the private pin against the bound policy;
   budget admission verifies schema, current original owners and exact provenance.
   Service owner construction/check-only can configure/migrate other repositories;
   it is **not** a strict read-only operation. No implicit startup is added.
4. Register the immutable scope and attribution only in the first accepted original
   reservation transaction. A selected scope cannot adopt old unlabelled reservations.
   Changed caps/policy/expiry cannot reset the same identity: scope identity excludes
   those fields, while the full immutable record must match on replay.

There is no migration backfill or historical Human change. Removing a selection
cannot replay a labelled reservation, and a registered Service cannot silently
make further unselected calls through the original Service owners. Old deployments
without an opted-in registered scope retain their old behavior; they **must not**
be represented as enforcing a local Service budget.

## Trusted provenance and atomic accounting

Planning uses the original `ServicePlanningRegistry.guard` and persisted exact
planning preparation, actor, credential, policy digest and event. Native carries
an internal `NativeBudgetCall`; the budget owner verifies its original
`BoundServiceExecutionBridge`, current Service credentials, actual Attempt/Skill
invocation, approved event/work/source binding and claimed bounded MODEL journal
key. A supplied principal, label, invocation string or another Skill is insufficient.
The normalization adapter preserves only the internal provenance value; it grants
nothing. The Service bridge is attached to all Service Native runtimes, including
runtimes without durable Human waits.

Original owner checks precede the ledger lock, preserving Service -> ledger lock
ordering. The existing ledger row lock then serializes both original global and
local comparisons, scope registration, reservation and attribution insertion in
one transaction. A failed global/local check leaves no partial fact. Settled
actual cost or unsettled worst-case cost is counted locally as well as globally.
UNKNOWN and absent usage retain the reservation. Settlement can release unused
cost, never a call count. Exact replay reads the original attribution and cannot
increment either total. Dispatch rechecks current provenance and immutable selection
before the original extension dispatch guard; there is no model/provider fallback.

## Validation and release boundary

Focused validation uses a disposable PostgreSQL instance and random databases,
never the actual runtime database. Accounting tests isolate the verified-provenance
port to exercise races/limits; a separate original BOUND -> Planning -> START ->
Native journal/Attempt -> original-chat chain uses actual owner provenance and
real budget reservations with controlled provider/Kubernetes decisions. It is
engineering validation, not live-model or business acceptance.

The root integrator owns the normal frozen release gate, installation, explicit
migration, exact private policy selection and current Service activation. The two
natural event results remain unaccepted until actually observed. Nothing here
unpauses a `TARGET_REVIEW_ONLY` purchase or grants Human immediate execution.

### Migration-marker correction

Selected budget admission itself calls `check_schema` before either Planning or
Native provenance, on every reserve and dispatch path. It verifies the actual
0080 SQL checksum and adapter as well as both tables. This guard is read-only and
does not depend on cycle check-only/startup having run. Existing tables alone
never establish migration readiness. Missing/corrupt markers reject before any
reservation, scope registration or attribution and are never silently repaired.
