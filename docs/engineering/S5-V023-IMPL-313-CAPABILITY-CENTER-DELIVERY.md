# S5-V023-IMPL-313 Capability Center first-batch delivery

## Status and boundary

This delivery remains `PARTIAL_DRAFT / SESSION_OPEN`. It adds the first Skill
and MCP directory/detail experience. It does not complete or cancel the wider
M1/M2/M3 or P1/P2/P3 obligations, and it grants no Human acceptance, merge,
deployment, or release authority.

The implementation is frontend-only. It changes no backend route, schema,
resource identity, scope, authorization source, write command, retry, timeout,
skip, or success threshold.

## Bounded read-surface audit

Compared with base `f189212232fc194859a695f0307e83b0c7b73c0f`, the batch adds no
network request. `CapabilityCenterDirectory` consumes the pre-existing complete
`listResources(kind)` response, while `CapabilityResourceDetails` consumes the
pre-existing exact `getResource(kind, resourceId)` projection. Search, status
filtering, view switching, and pagination are local projections over that
already-returned data.

The base list endpoint already returns complete aggregate records, including
revisions and revision content, to the browser. This batch does not enlarge that
response. It newly renders the selected revision description and identity facts,
the explicitly present Skill operation name/executor identity, and MCP Tools from
an actual discovery snapshot. A capability is never inferred to be an operation
or Tool. No credential value is introduced; MCP credential material remains an
external reference and invocation evidence remains redacted.

The internal Skill/MCP API still derives namespace/security-domain/principal
from request headers with development defaults. Repository queries are bounded
by namespace and security domain, but local filtering and hidden fields are not
authorization. This is pre-existing shared ingress/authorization debt, not a new
313 behavior.

### Coordination list for the 305 shared connection owner

- Ensure the trusted BFF, rather than an untrusted browser, supplies verified
  tenant, security-domain, and principal context to the internal Skill/MCP API.
- Deny direct untrusted access to the internal list/detail and write routes.
- Decide whether the list contract should continue returning complete aggregate
  histories or use a bounded directory DTO; 313 does not introduce such a DTO.
- Preserve the existing scope-before-read/write behavior and controlled denial
  responses when shared routing is connected.

## Existing contract and experience inventory

| Area | Current implementation | Remaining first follow-up path |
| --- | --- | --- |
| Copy, clone, import, export, successor | Formal clone, bounded manifest import/export, and immutable successor APIs are connected to both Skill and MCP Workbenches. Each action now requires an operation-specific confirmation that shows its effect and the exact source facts available from the resource or manifest. Clone accepts an exact existing revision; successor remains CAS-bound and available only for a published resource without a Draft. Mutations retain their formal response, then require directory and exact-detail readback before selecting the result. | Add only further negative-state coverage against these existing actions; they are not a governed template catalog. |
| Skill operation input and validation/test | The backend has a formal governed operation wire record and validates schemas, executor revision/configuration digest, side-effect policy, and I/O limits. Normal UI editing preserves the complete operation object. The Workbench displays real operations and saved management tests. | Add an operation authoring/editor surface only against the existing operation contract, including field-level validation and exact operation test input. Do not synthesize operations from `capabilities`. |
| MCP Tool detail, input, and management test | Health, immutable discovery snapshot, discovered Tool schema, explicit selection, bounded management input, invocation result, and redacted evidence are connected. These facts do not grant Attempt-level invocation authority. | Improve Tool-focused detail/schema presentation and negative-state coverage while retaining snapshot and selection identity. |
| Formal template directory and provenance | No formal template directory, template identity, provenance, publisher, or source-revision contract exists. Clone/import/export cannot be presented as that authority. | Contract candidate: immutable `templateId`, source kind/resource/revision/digest, publisher/owner scope, provenance type, manifest version/digest, lifecycle, visibility, and authorized retrieval rules. Architecture/Product review is required before implementation if this becomes a new managed resource or cross-scope authority. |
| Ranking and statistics | Existing dashboard numbers are raw counts from the already scoped list response. There is no ranking authority, time window, deduplication key, usage aggregation, or authorization-filtered statistics contract. | Contract candidate: explicit metric name, event authority, subject identity, fixed time window/timezone, deduplication key, aggregation method, scope/authorization filter, minimum sample disclosure, and `NOT_MEASURABLE` semantics. Do not derive ranking from frontend counts. |

### Reuse operation support

| Operation | Skill | MCP | Effect and authoritative completion |
| --- | --- | --- | --- |
| Clone | Existing generic clone endpoint | Existing generic clone endpoint | Creates a separate Draft from the confirmed exact revision. The source is unchanged. Completion requires the 201 response, directory readback containing the new resource, and exact target detail readback. The detail renders only the backend-recorded `CLONED_FROM_TEMPLATE` relationship fields. |
| Export | Existing bounded manifest endpoint | Existing bounded manifest endpoint | Downloads the exact manifest returned by the backend and changes no resource. The confirmation exposes `manifestVersion`, `sourceRevisionId`, `sourceDigest`, and `credentialMaterial` exactly as returned. |
| Import | Existing bounded manifest import endpoint | Existing bounded manifest import endpoint | Creates a separate Draft after confirming the exported manifest and target name. Completion requires the 201 response plus directory and exact target detail readback. The current endpoint does not persist source relationship fields, so the UI explicitly reports `NOT_RECORDED_BY_BACKEND` instead of inferring provenance. |
| Successor | Existing generic successor endpoint | Existing generic successor endpoint | Available only for a published resource without a current Draft. It preserves the published revision, applies the current aggregate version CAS, and completes only after the response plus directory and exact same-resource detail readback expose the new Draft. |

## Validation evidence classification

The complete `skill-mcp-workbench.spec.ts` includes both categories and they
must remain separately reported:

- Real backend paths: operation-backed Skill create/detail/edit/readback;
  lifecycle publication; Skill test/binding/management invocation; MCP health,
  discovery, selection and management invocation; search/filter/resource switch;
  390px layout; CAS, in-flight freeze and late-response isolation.
- Mock transport path: the dedicated directory test uses `page.route` to prove
  seven-item local pagination, card/compact switching, and Chinese content
  search deterministically. It is interaction evidence, not backend or
  authorization evidence.

Of the nine tests in the spec, eight use the real backend. The four late-response
tests use `page.route` only to hold or forward real requests and responses; they
do not fabricate successful backend payloads. The directory interaction test is
the only fully mocked transport path.

## Preserved runtime history

Every row below describes only that run's actual candidate and starting state.
An initialized or accumulated database result is not evidence for a fresh start.
All six formal runs exited with status 1 and remain preserved under
`/private/tmp/s5-v023-impl-313-real-browser/`.

| Runtime | Candidate | Database at start | Executed | Result |
| --- | --- | --- | --- | --- |
| `runtime` | initial `release`; frontend digest `dd6aca97...1261`; release-manifest file digest `85451bb3...6194` | Newly allocated 313 database volume; exact pre-run table count was not retained | 0/7 browser tests | Backend startup did not become healthy within the harness boundary; browser did not run. |
| `runtime-2` | same initial `release` and digests | Same database after the preceding partial startup, therefore pre-initialized rather than fresh; exact count not retained | 7/7 | 6 passed / 1 failed / 0 skipped; first retained failure classified as the main real journey timeout. |
| `runtime-3` | `release-2`; frontend digest `a02ac84c...28bc`; release-manifest file digest `dd339c1f...47d7` | Accumulated 313 database; exact count not retained | 0/7 browser tests | Backend startup did not become healthy within the harness boundary; browser did not run. |
| `runtime-4` | same `release-2` and digests | Accumulated 313 database; exact count not retained | 7/7 | 2 passed / 5 failed / 0 skipped; retained first failure is a selector-state mismatch in the main journey. |
| `runtime-5` | same `release-2` and digests | Database explicitly recreated; three probes confirmed 0 public business tables before the run | 7/7 | 5 passed / 2 failed / 0 skipped; the clean result remains valid and is not attributed solely to resource accumulation. |
| `runtime-6` | `release-3`; frontend digest `a02ac84c...28bc`; release-manifest file digest `4ed87455...1160` | Database explicitly recreated; three probes confirmed 0 public business tables before the run | 7/7 | 6 passed / 1 failed / 0 skipped; exit 1. The formal harness retained only `BROWSER_DIAGNOSTIC_GAP / UNKNOWN`. |

The faster PostgreSQL/Qdrant probes before `runtime-5` and `runtime-6` establish
only those probes' readiness and initial-state observations. They do not prove a
root cause for any earlier startup or browser failure.

## Final diagnostic and discovery completion boundary

The final line-reporter diagnostic after `runtime-6` ended normally as a failed
command after about 204 seconds with exit status 1. It ran all seven tests:
4 passed / 3 failed / 0 skipped. Its accumulated database state was not fresh
and its exact initial row counts were not retained. The three saved failures
were the main real journey at the second discovery, plus the Skill late-response
edit and lifecycle cases. Resource accumulation and pagination can affect the
race locators, but that does not erase the independent clean failures from
`runtime-5` or `runtime-6` and is not recorded as a universal root cause.

For the main journey, the precise observation was: the exact second discovery
POST returned HTTP 200, while the Workbench was still awaiting its subsequent
authoritative `GET /api/internal/v0.2.2/resources/mcp` directory readback. The
new snapshot had therefore not yet entered rendered UI state. The test now arms
both waits before the click, matches the exact resource discovery POST, and
accepts only a directory GET whose body contains that POST's new snapshot ID.
It still verifies HTTP status, distinct old/new snapshot identities, absence of
a copied selection for the new snapshot, and the final UI/history state. These
waits inherit the existing 60-second per-test deadline; no sleep, timeout,
retry, skip, or assertion threshold changed.

## Post-fix minimum validation

The first attempted minimum command selected no tests because its anchored grep
was not accepted by that invocation; exit 1 is a command-selection failure, not
a product result. A subsequent `--list` confirmed exactly seven collected tests.
The corrected one-test selection then executed the main real-service journey
against the preserved accumulated database (start: 9 MCP resources with 4
snapshots and 3 selections; 12 Skill resources with 17 revisions). It failed
before reaching discovery: the newly published MCP reached aggregate version 4,
but its health request returned `backend unavailable / SKILL_MCP_UNAVAILABLE`
and wrote no health observation. Result: 0 passed / 1 failed, exit 1. This does
not validate or invalidate the discovery synchronization change, so no complete
formal harness was started afterward.
