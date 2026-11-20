# Bounded fixed cycle executable composition (G1)

Base: 8c0c8d9 plus frozen 82-file fixed-work net candidate 614dc3e2.
This is a separate successor, not part of the active deployment package.

## Scope and authority

Provide a fixed Python CLI and concrete owner factory, not configurable imports,
plugins, an HTTP startup hook or another execution engine. Reuse SERVICE_ONLY
StaticGenerationAuthenticator, existing AuthorityFoundation, PlanningSuggestionService,
ServicePlanningRegistry (0070), exact source binding (0073), independent issuer
ResourceAutomation, ReadonlyContinuation and PreparedNativeCoordinator. Existing
Native manager/manifest/claim/effect locks remain separate and authoritative. The
cycle process does not launch or signal Native, migrate a schema, mint credentials,
register prices, approve models, fabricate Plans, or clear an exact admission.
No public CRD or lifecycle change is needed. No G2 conflict identified for this
bounded composition; general service answer delegation and automatic renewal remain
outside it.

## Configuration / startup

Explicit private configuration, default disabled, pins source manifest and every
runtime/policy file. One configured DB from the authority runtime; all repository
connections use that same DB. External service credential remains private; never
log it. Bound service policy v2 required: exact work/target/source binding, real
service subject/credential, event windows, model/profile, original ledger and limits.
Separate resource issuer credential and exact static service work scope are required;
Human owned-admission/authority is not borrowed. Readonly policy must contain the
same exact service/problem/source. Missing dependencies fail closed.

Use existing-only repository/foundation checks. A new dedicated planning composition
uses the same original provider/credential resolver/ledger classes and exact published
profile pricing, but never migrate/configure. Do not mutate the API's service or
budget instance. Check-only constructs, authenticates and observes current gates,
then closes pools; no begin/step/run, provider request, grant command or dispatch.
It reports observation rather than future execution readiness. CLI run is separately
explicit and enabled; SIGTERM stops polling after the current owner call completes.
No automatic crash retry. Original persisted event keys and UNKNOWN gates survive
restart. Configuration/source hashes are rechecked before each step.

## Dependencies / deployment boundary

Root must supply already migrated 0067/0069/0070/0073 plus original schemas, current
SERVICE_ONLY subject credential, independent issuer and current grants, exact source
binding/Plan target/catalog snapshot, published model/profile pricing and unchanged
root ledger/caps/deadline. Service and issuer lease renewal must use existing authority
owners, not this process. Daily natural cycles require at least 24h; 8h leases do
not silently extend. Existing Native manager may consume committed commands only
under its own exact provenance and locks. API need not restart to start/stop this
separate process. Existing unresolved/UNKNOWN work is never backfilled or replayed.

## Validation

Pure controlled tests: default off does not touch dependencies; strict/private/pinned
config and source; wrong Human identity fails SERVICE_ONLY; check-only never enters
step/run/provider/grant; fixed factory builds original owners and rejects absent
pricing/service scope; UNKNOWN remains an observation on restart. Original bounded
loop and owner tests retain their engineering-only evidence. If feasible add isolated
random-DB composition checks without provider calls. No actual DB, HTTP, model,
service, or grant operation in this task. Full natural-cycle acceptance belongs to
root's later real deployment, not factory mocks or controlled planning output.

## Implemented entry and explicit first-slice restrictions

`python -m agent_operator.fixed_work_cycle_entry --configuration /private/cycle.json
--check-only` is the default mode (omitting both mode switches is also check-only).
An `enabled:false` configuration returns DISABLED before dependency reads. Root must
explicitly set enabled true to inspect configured owners and additionally pass
`--run` to poll. It never starts an HTTP server, API, Native host or Kubernetes task
itself. `--run` reuses FixedWorkCycleService's machine/DB/scope/work singleton lock.
SIGTERM/SIGINT sets the stop event; an in-flight original owner call may finish before
the process reports STOPPED. Do not SIGKILL and then treat unknown owner effects as
absent. A later explicit restart reuses stored event keys, never repairs UNKNOWN.

Configuration schema: `fixed-work-cycle-process.v1`, strict enabled boolean,
sourceRoot (exact running checkout), sourceFiles (complete SHA256 inventory of all
.py under core/src, runtime/src, operator/src, console/backend/src and all .sql under
console/backend/migrations), authorityRuntime/planningRuntime/servicePolicy/
resourcePolicy/readonlyPolicy/serviceCredential (each {path,sha256}, absolute private
regular files owned by the process UID), pollSeconds 5..300, and optional
policyPlanApprovalEnabled false. No caller/module/plugin field is accepted. Generate
sourceFiles offline with fixed_work_cycle_configuration.source_files(sourceRoot),
then save the private config atomically. Pin the exact release after integration;
this task creates no actual private service configuration.

The authority runtime's database fingerprint and migration file must match the same
source release and every repository uses its DSN. All external authority generation,
recovery control, signing keys, model credentials/pepper and issuer credential remain
under their original owners' file/config validation. No secret value appears in the
report. Policies and service credential are hash-rechecked before each step; renewal
requires an explicit stopped successor configuration, not in-process file swapping.

The first concrete factory intentionally requires a single published Knowledge
source: servicePolicy.resourceSnapshot == the exact0073 inputSource.source, after
current service READ + immutable binding verification. A distinct catalogue snapshot
is NOT synthesized or accepted as an input snapshot. The normal planning factory's
empty resource callback is replaced by this read-only exact source port; existing
API planning code is unchanged. Static service workScopes and readonly works must
match the service principal/problem/content digest; this factory never attaches the
Human OwnedBusinessAdmission reader. The resource issuer must be another current
SERVICE_ONLY subject with its original GRANT_ADMIN DECIDE and requestability.

Check-only resolves the real published model binding with original current authority,
validates the exact Problem/Criteria through PlanningApplication, checks current
service/source/schedule/independent issuer and static readonly scope, and verifies
existing ledger/pricing. It does not probe Kubernetes or reserve costs; future
resource preparation/START/effect and budget sufficiency are explicitly not certified
by CHECKED_ONLY. Per-plan grants, if enabled by policyPlanApprovalEnabled, are only
requested during real host.step through the existing ServiceCyclePlanApproval and
GrantAdmin, never during construction or check-only.

No existing source/model/executor/public-contract file is modified by this successor.
No new migration. Native remains separately deployed using its own policy pins,
manifest, exact receipt discovery and claim/effect authority. Root must supply that
manager's service-compatible scopes and current credentials; the CLI cannot make
an unconfigured execution backend ready.
