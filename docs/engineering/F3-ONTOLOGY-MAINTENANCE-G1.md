# Ontology bounded maintenance G1

Parent reviewed this implementation boundary. Reuse existing owner, grant owner,
prepared_resource_commands immutable JSON receipts and transaction, no new table,
no generic permission model and no published model configuration changes.

Only explicit server-maintenance scopes (tenant/domain/subject/exact ontology IDs,
optional bounded create prefix, actions, expiry) permit automatic exact grants.
Business READ does not imply maintenance. Default configuration absent/disabled.
CREATE/REVISE bind actual command, actor, scope, base revision/digest, head version,
content and policy generation. Owner checks managed commands even through legacy
routes, prior to replay; replay cannot bypass current grant/revocation/expiry.
Preserve existing independent review and lifecycle validation. Never grant USE or
execution/tool authority. Existing unmarked owner requests remain compatible.

No kind column/constraint exists on prepared_resource_commands (migration 0034).
Use distinct key and result schema, never consume other owners' receipts. Admission
and owner command are one transaction; failure rolls all back. Historical GET uses
current precise READ and original actor/scope/key ownership, independent of expired
write policy. Report writeEligible separately; a write always revalidates policy.

Test with disposable PG and actual grant service: permitted lifecycle, unrelated
business reader denied, foreign subject/domain denied, changed key payload rejected,
stale base/CAS, exact owner raw-route bypass, expiry/revocation/generation changes,
receipt reading after write expiry, independent reviewer, no use or model effects.
Normal hooks queued with parent. Actual deployment/configuration owned by parent.

## Implemented candidate and integration boundary

Add optional BUSINESS_ONTOLOGY_MANAGEMENT_POLICY. Absent means no new routes;
disabled policy denies writes while already-installed historical GET remains readable.
The config is MaintenancePolicy with explicit subjects/ontologyIds/actions and expiry,
service issuer and credentialPath; current generation must independently permit exact
BUSINESS_ONTOLOGY actions and READ requests with purpose ONTOLOGY_MAINTENANCE.
No configuration, credentials or actual grants are activated by this source package.

POST /api/workbench/v1/ontology-maintenance/commands accepts action, commandKey,
ontologyId, expectedVersion and reason. CREATE includes complete content. REVISE
includes complete content plus exact baseRevision/baseDigest; lifecycle commands
include revision/digest instead. Server computes new revision identity. It returns
ontology-maintenance-receipt.v1 with outcome, writeEligible and policyDecisionId.
GET /commands/{key} reads the original actor's immutable outcome with current exact
READ, even after maintenance policy expiry. It does not submit grants or owner writes.

All owner commands keep the existing OntologyCommand format. A scoped grant validator
accepts only the trusted command's exact target, never mutates the global validator.
Existing arbitrary legacy revision identifiers remain valid; raw CREATE/REVISE checks
look for actual immutable managed admission instead of reserving a name prefix.
Grant decision and admission and owner lifecycle commit share one transaction.
Existing independent review and dependency READ remain mandatory. Same-key payload
changes, stale head and base, foreign actor, expiry/revocation/generation fail closed.

Validation: 45 real isolated PG tests passed in 48.70s (new 10, original lifecycle
and execution regression). Includes actual HTTP session/CSRF+owner combination;
concurrent successors leave exactly one success and no orphan admission. One existing
Starlette/httpx deprecation warning only. Python lint passed. Full hook pending queue.

UI integration is not delivered by this backend-only candidate: the current page still
uses legacy routes. Next package must select this capability, retain stable commandKey,
recover UNKNOWN by GET only, and distinguish historical receipt from write eligibility.
Actual ordinary maintainer/edit/validate/review/publish/binding and business execution
acceptance belongs to root after configuration and installation. Definition query and
real NL patch generation remain later pieces of the retained first-version scope.

## UI connection follow-up

Server GET /ontology-maintenance/capabilities/{identity} returns current bounded
maintenance eligible actions; no grants or owner writes occur. A readonly subject
receives no actions. creationAvailable permits entering a candidate identity, while
CREATE itself still requires current eligibility for that exact entered identity.
The page never infers write rights from READ or a displayed administrator name.
Absent/failed capability read means no writable controls, not fallback to old writes.

The page submits only to the maintenance facade with exact base revision/digest and
head version. Stable commandKey is persisted under current tenant/domain/principal
and ontology identity BEFORE POST. Pending commands block other maintenance writes;
network failure, malformed receipt, 408 or 429 stay UNKNOWN. Refresh/manual recovery
performs GET only and never retries POST. Explicit application 4xx rejections clear
the pending command, allowing correction and a new submission. A current-session
identity check immediately before POST prevents cross-account dispatch. Pending
storage contains command identity only, not source content or credentials. If no
receipt can be read, state stays unverified; this package does not silently resolve
an absent receipt as failure or recreate a command.

Readonly users retain four frozen detail tabs and independent readable history, but
no maintenance-description or submit/edit controls. URL preserves exact ontology and
revision on refresh and keeps other return-context parameters. The later R4 candidate
three-tab structure/new graph/enterprise-ontology import contract is not applied.

Validation: 16 controlled browser tests passed in 26.1s, production TypeScript/build
passed. Actual PG HTTP capability/CSRF/history test passed after API extension.
Same-size readonly/editor screenshots in ontology-maintenance-ui-final-r1. Parent owns
actual ordinary-account activation and acceptance; no live calls performed here.

## G1 follow-up: bounded newly created definitions

Parent confirmed a missing lifecycle boundary: createPrefix currently permits only
CREATE, so a new ID absent from ontologyIds cannot continue. Extend only internal
maintenance policy scope, not frozen OntologyCommand or the database schema.

For a prefix-scoped definition, derive creator solely from this scope's immutable
ontology-maintenance CREATE admission joined to its successful ontology-owner CREATE
fact and exact owner-command digest. A prefix alone, a failed admission, a legacy
object without that admission, or another actor's object grants no follow-on scope.
The current creator may use only actions listed by the current active policy; current
issuer, generation, expiry, dependency/read grants and owner lifecycle checks remain.
Historical creation is provenance, not a surviving permission lease.

Add optional createdBySubjects (default empty) to a policy scope. It only participates
in REVIEW, requires explicit same scope/createPrefix, a proven creator in that list,
and reviewer != creator. It never gives REVISE/PUBLISH or generic ownership to the
reviewer. Exact ontologyIds remains backward compatible. Scope eligibility drives
both server admission and readonly capabilities so new definitions remain operable.

Test actual isolated PG: generated new ID outside ontologyIds -> CREATE -> VALIDATE
-> TEST -> independently scoped REVIEW -> original creator PUBLISH; same-prefix legacy
object, other creator's object, self-review, wrong allowed creator and expired current
policy all denied. Keep original lifecycle/authorization regressions. No real policy
or account activation here. Full hook queues behind root integration.

Follow-up implemented: creator proof joins immutable managed CREATE admission to
successful owner CREATE fact and exact command digest, same actor/scope/definition.
Capabilities and write admission share the same policy.work created_by predicate.
Optional createdBySubjects participates only in independent REVIEW, default empty.
Successful create/receipt recovery refreshes frontend readonly capabilities so the
new object's VALIDATE action appears without per-ID operator reconfiguration.

47 real isolated PG regression tests passed in 39.00s, including new-object full
lifecycle, no exact READ for reviewer denial, same-prefix foreign/legacy rejection,
uncommitted admission-shaped record rejection, expired current creator policy.
17 controlled browser tests passed in 24.0s, including actual capability refresh
from CREATE to VALIDATE; production build passed. No new graph/prototype redesign.
