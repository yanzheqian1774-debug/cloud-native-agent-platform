# S5-V023-IMPL-308 — P1 Verified Model Minimum Contract Candidate v1

## 1. Decision record

| Field | Value |
| --- | --- |
| Session | `S5-V023-IMPL-308` |
| Type | Same-session bounded contract decision preparation |
| Recovery source commit / tree | `503e2b9c26eed962a720253ce2ac43b9328cd03b` / `4f91210a74bfe13cb4e143d879c43c37c56ea927` |
| Pull request | `#163`; must remain Draft |
| Fixed Human decision object | `451c971b120521333ae46a51830fe17239899a5d` / `3a3339b19c5f90078b305b417eefd0994592d5ad` |
| Decision status | `HUMAN_MODEL_MINIMUM_CONTRACT_ACCEPTED_WITH_CONSTRAINTS` for H308-01, H308-02, and H308-03A |
| Implementation status | `PARTIAL_DRAFT`; internal consumer preparation only |
| Contract status | Minimum verified-selection contract accepted; `NOT_FROZEN`; H308-03B/03C/04A/04B remain `PROPOSED` |
| Implementation authority from this record | `YES`, bounded to H308-01, H308-02, and H308-03A; no authority for the four retained proposals |

### 1.1 Human decision overlay

The Human decision accepts this document exactly as recorded at source
`451c971b120521333ae46a51830fe17239899a5d`, tree
`3a3339b19c5f90078b305b417eefd0994592d5ad`, with these severable results:

- **accepted:** H308-01 Model Governance ownership and minimum restart-stable
  persistence; H308-02 scope-bound pre-ID creation, owner-generated identity,
  continuation, and independent exact grants; H308-03A exact resolution plus
  current exact authorization as the minimum verified-selection contract;
- **retained as proposed:** H308-03B connection freshness, H308-03C real-provider
  acceptance, H308-04A `MODEL` Resource Use, and H308-04B Model Evidence schema.

The retained proposals are neither rejected, cancelled, reassigned, nor a gate
for the accepted selection foundation. This acceptance creates the internal
Model Governance owner/persistence and Model-specific exact-target
responsibilities described by H308-01/02. It does not accept an implementation,
freeze a public Contract, authorize a public API/CRD, or authorize connection
probes, real Model calls, Resource Use, Evidence, Ready, merge, or deployment.

The candidate prose below is preserved as the proposal reviewed at the fixed
object. Its `Recommend Human accept` wording records the historical review
position and must be read through this decision overlay; the old commit is not
retroactively described as accepted.

This candidate makes the smallest concrete decisions needed to implement the
existing P1 verified Model obligation. It does not change M1/M2/M3, P1/P2/P3,
create a public API or CRD, complete Model Control V2, or treat a test fake as a
production owner. The session-carried Human constraint places complete Model
Control V2 in v0.2.3 P2; this candidate does not move P1 obligations into P2.
Repository product documents that describe broader Model Governance under
v0.2.4 are not edited or silently reinterpreted here.

## 2. Inherited authority and verified current gap

The candidate inherits rather than reopens these constraints:

- ARCH-300 is Human-accepted and durably integrated. Its accepted source is
  `4b8672cda51325322d4ec7dc0ac3d78df471d08b`, its durable merge is
  `270d193b936a61c65d4fa20d9a62709a5c2b56ad`, and PR `#161`, ARCH-300, and
  REL-301 are closed. Historical `Proposed` text inside the source artifact is
  pre-acceptance history; it neither reopens nor weakens that Human decision;
- accepted ADR-0005 separates Agent intent, ModelPolicy, ModelGateway, and
  provider adapters; the runtime-local `ModelProvider` is explicitly not the
  platform Model authority;
- the thin embedded Model Binding is a reference, not a Model owner, permission,
  provider connection, invocation, or quality assertion;
- scope is `(namespace, security_domain)` and comes from trusted server context;
- authorization precedes protected lookup, list/count, join, credential
  resolution, Evidence dereference, and external effect;
- exact identity, revision, and digest replace implicit latest, first-item
  selection, display-name matching, and environment inference;
- credentials remain external and only typed Secret Reference metadata may be
  persisted;
- published references, decisions, execution facts, and Evidence are immutable
  history; correction or retry appends a successor rather than rewriting them;
- Model, Provider, Runtime, Agent, Digital Employee, authorization, Evidence,
  and business Outcome remain distinct owners and meanings.

Current source has no formal owner for Model identity/revision/digest, no
accepted Model-specific grant vocabulary, and no exact Model-bound provider
connection or invocation Evidence contract. `model_binding_resolution.py`
therefore remains contract preparation, not proof that these gaps are closed.

## 3. Recommended minimum owner and authoritative records

### 3.1 Recommendation M01 — Model Governance is the logical owner

**Recommend Human accept:** one logical `Model Governance` domain service owns
Platform Model identity, immutable Model Revision, exact provider configuration
references, lifecycle eligibility facts, and any Model connection-observation
projection described by the optional freshness proposal in Section 5. It does
not own Execution Resource Use or Evidence.

The minimum owner surface is:

```text
ModelGovernanceService
  -> ModelDefinitionRepository
  -> ModelRevisionRepository
  -> ModelProviderConfigurationRepository
  -> ModelConnectionObservationRepository  # only if H308-03B is accepted
```

`Model Governance` is a logical domain boundary, not the runtime provider
package and not a generic adapter. Provider adapters translate an already
authorized exact binding and own native interaction; they cannot create Model
identity, revise its digest, grant use, publish it, or declare business success.

This is a **new architecture responsibility**. It is necessary because no
current owner can provide restart-stable exact readback, immutable revisions,
revocation, or auditable provider/profile relationships. Treating the runtime's
environment-selected provider/model as authority would preserve the recorded
ADR-0005 drift and could not satisfy scope, history, or exact digest guarantees.

Substantive alternative: a separate Provider Configuration domain could own
Provider/Endpoint/Profile records. It is not recommended for P1 because it adds
cross-domain publication and recovery coordination before any current owner
exists. The candidate keeps separate typed aggregates under one Model
Governance boundary so they may be split later without changing Model Binding.

### 3.2 Authoritative record set

All records are scoped and use Platform identities, never database row IDs or
provider-native names as Platform identity. Any descriptive owner identity is
provenance only and grants no action on any target.

| Record | Minimum authoritative content | Owner and mutability |
| --- | --- | --- |
| `ModelDefinition` | `scope`, `model_id`, owner identity, created provenance | Model Governance; stable root |
| `ModelRevision` | `model_revision_id`, predecessor, canonical digest, exact Provider/Endpoint/Profile revision references, provider-native model identifier, declared compatibility/capabilities, non-secret invocation limits | Model Governance; immutable after publication |
| `ModelProviderRevision` | provider identity/revision/digest, adapter contract identity/revision, supported operation classes | Model Governance registry metadata; immutable revision |
| `ModelEndpointRevision` | endpoint identity/revision/digest, normalized non-secret address/reference, region and transport constraints | Model Governance configuration metadata; immutable revision |
| `ModelConnectionProfileRevision` | profile identity/revision/digest, Endpoint Revision, typed Secret Reference metadata/version, bounded timeouts; optional freshness-policy reference only if H308-03B is accepted | Model Governance configuration metadata; immutable revision; no secret value |
| `ModelLifecycleFact` | validation, review, publication, enable/disable, deprecation, revocation and successor facts with actor/decision/time | Model Governance; append-only |
| `ModelConnectionObservation` | optional H308-03B exact observation identity/key, revisions, credential-reference version, adapter revision, result, platform sequence/time, and Evidence reference | Model Governance observation projection if H308-03B is accepted; append-only; not Evidence ownership |

The Model Revision canonical digest covers a versioned canonical payload:

```text
contract version + scope + model identity + revision identity + predecessor
+ exact Provider Revision + exact Endpoint Revision + exact Connection Profile Revision
+ provider-native model identifier
+ invocation-affecting compatibility/capability declarations and non-secret limits
```

Display names, descriptions, timestamps, current lifecycle projection, mutable
health, Evidence, database IDs, and secret values are excluded. Any change to an
invocation-affecting field or referenced revision creates a successor
`ModelRevision` and a new digest. A provider health observation alone does not.
The owner computes the canonical digest; consumers only compare it.

### 3.3 Configuration and persistence recommendation

**Recommend Human accept:** use narrow typed repository ports with PostgreSQL as
the primary deployment adapter, within the existing bounded product-continuity
direction. Focused in-memory adapters are test-only; absence or incompatibility
of the deployment store fails closed and never falls back to memory or runtime
environment configuration.

This requires a future additive Model-owned schema and is therefore a new
persistent architecture responsibility. This candidate assigns no migration
number or physical table layout. A separately authorized implementation must
first deploy compatible readers, then allocate its schema path under the owning
implementation task, without modifying a historical migration.

Credentials are resolved only after authorization by a provider-neutral Secret
Reference resolver. Durable records and Evidence may contain the secret
reference identity/version and redacted presence/rotation state, never the
secret, Authorization header, environment value, raw prompt, or raw response.

### 3.4 Lifecycle, writers, readers, and unavailable states

Model authoring reuses the existing governed resource lifecycle pattern:

```text
create Draft -> edit Draft -> validate -> Human review exact digest
-> publish immutable Revision -> optional successor
-> disable/enable -> deprecate or revoke -> retain history
```

- only a trusted principal holding the scope-bound create entitlement may create
  a Model; only a principal holding the applicable exact management grant may
  mutate Draft state or append a lifecycle action after owner-ID commit;
- publication requires the existing exact-digest Human review pattern; this
  candidate does not create a second approval system;
- authorized readers receive exact scoped records or disclosure-safe not-found;
- only `PUBLISHED + ENABLED` and otherwise eligible revisions may be newly
  bound or invoked;
- `DISABLED` is reversible and prevents new use; `DEPRECATED` prevents new bind
  and use; `REVOKED` permanently prevents new bind and use;
- none of these states delete a published Revision, an accepted binding, or
  historical execution/Evidence;
- an unavailable provider is an observation, not Model lifecycle. It makes a
  current verified-connection projection fail or become stale but does not
  rewrite publication history.

Pre-ID creation follows accepted ARCH-300. A trusted, scope-bound
`CREATE_MODEL/model:collection` entitlement authorizes only the create command.
Model Governance generates and durably commits the canonical `model_id`; the
client cannot choose it. After commit, the owner returns a creator-bound,
short-lived continuation for the exact committed Model target. Continuation
consumption may create requests for exact read or management grants, but the
continuation, creator status, collection entitlement, and successful create do
not grant them. Each exact grant still requires its own independent Grant
Administration decision.

## 4. Recommended authorization contract

### 4.1 Recommendation M02 — exact grant vocabulary

**Recommend Human accept:** reuse the ARCH-300 exact grant shape
`ExactGrant(owner, action, exact_resource)` with this closed Model mapping:

| Operation | `owner` | `action` | Trusted-server `exact_resource` template |
| --- | --- | --- | --- |
| Create one Model before an ID exists | `MODEL_GOVERNANCE` | `CREATE_MODEL` | `model:collection` |
| List the bounded scoped catalog | `MODEL_GOVERNANCE` | `READ_MODEL` | `model:catalog` |
| Inspect one exact identity/revision and its allowed projection | `MODEL_GOVERNANCE` | `READ_MODEL` | `model:revision:{model_id}:{revision_id}:{digest}` |
| Persist an exact Model Binding into one exact consumer revision | `MODEL_GOVERNANCE` | `BIND_MODEL` | `model:binding:{consumer_kind}:{consumer_id}:{consumer_revision_id}:{model_id}:{revision_id}:{digest}` |
| Invoke through one exact Attempt binding snapshot | `MODEL_GOVERNANCE` | `INVOKE_MODEL` | `model:invocation:{attempt_id}:{binding_snapshot_id}:{model_id}:{revision_id}:{digest}` |
| Revise/publish/disable/enable/deprecate/revoke or, if separately accepted, connection-test | `MODEL_GOVERNANCE` | `MANAGE_MODEL_REVISION` | `model:management:{operation}:{model_id}:{target_revision_or_new}` |

Every segment is constructed from typed validated values by the trusted server;
the authority compares the complete string exactly and supports no wildcard.
Scope remains a separate mandatory field on the principal, grant, record, and
repository key. An exact resource string never overrides or supplies scope.

`action` names the permitted operation; `exact_resource` names only its complete
target. Neither field supplies the other, and a match on one never relaxes a
mismatch on the other. `model:collection` and `model:catalog` are closed
scope-bound sentinels, not wildcards. `CREATE_MODEL` permits only one owner-ID
create command. `READ_MODEL/model:catalog` permits only deterministic bounded
listing inside the trusted scope. Neither authorizes foreign scope, exact Model
read, management, Evidence, bind, invoke, or any post-create operation.

`SELECT_MODEL` is deliberately not added in P1. The P1 resolver resolves one
caller-supplied exact binding and performs no ranking. Persisting a chosen value
is covered by `BIND_MODEL`. Policy-based governed selection, override, routing,
and fallback stay in Model Control V2 P2 and may later justify a distinct action.

No extra `READ_MODEL` grant is required inside an already authorized
`BIND_MODEL` or `INVOKE_MODEL` operation. Those decisions authorize the minimum
protected exact read needed to complete that operation. `READ_MODEL` exists for
independent inspection. Connection testing is an exact
`MANAGE_MODEL_REVISION` operation rather than a fifth grant class. Evidence
content dereference retains the existing separate Evidence authorization.

After `CREATE_MODEL` commits, Model Governance may mint the accepted ARCH-300
creator-facing continuation bound to the exact owner-generated ID, subject,
scope, purpose, owner revision/policy generation, and expiry. It is only a
request opportunity. Independent decisions issue each exact `READ_MODEL` or
`MANAGE_MODEL_REVISION` grant; approval of one action/target tuple never issues
another tuple. No client-defined Model ID or pre-ID exact-resource placeholder
is accepted.

### 4.2 Authorization ordering and validity

For every operation:

1. authenticate and construct the trusted principal/scope;
2. construct the exact action/resource from typed request identities;
3. authorize before Model lookup, list/count, relationship join, credential
   resolution, connection probe, Evidence read, or provider dispatch;
4. verify the decision binds the current principal, scope, action, exact
   resource, policy generation/version, issue/expiry time, and decision ID;
5. perform only the authorized operation and persist the decision ID with any
   binding or Resource Use fact.

Denial, foreign scope, missing identity, and unauthorized existence return the
same disclosure-safe not-found class and produce zero resolver, credential, or
provider calls. Detailed mismatch/status errors are available only after the
exact protected read is authorized.

A binding-time `BIND_MODEL` decision authorizes only creation of that exact
binding. It does not authorize invocation. Each actual invocation requires a
current `INVOKE_MODEL` decision valid immediately before dispatch. Revocation,
expiry, policy-generation replacement, subject/scope mismatch, or exact-resource
mismatch invalidates a decision. If revocation occurs after a provider dispatch,
it prevents later calls and retries but does not erase or relabel the already
recorded dispatch/outcome.

## 5. P1 verified selection and independent additions

### 5.1 Recommendation M03A — minimum P1 verified selection contract

**Recommend Human accept:** P1 verified selection means only that the caller
supplies one exact Model binding, the platform resolves the same scoped identity,
revision, digest, and exact Provider/Endpoint/Profile revisions from the Model
owner, verifies lifecycle eligibility, and obtains a current exact
`BIND_MODEL` or `INVOKE_MODEL` decision for that subject and target. There is no
ranking, implicit latest, display-name lookup, provider fallback, or environment
substitution.

Resolution and authorization are independent facts. A resolved binding does not
prove permission; a permission does not prove the Model exists; neither proves
connection freshness, provider dispatch, technical success, quality, cost, or a
business Outcome. This two-fact selection contract is the minimum P1 foundation
implemented by the current internal consumer preparation. H308-03B and H308-03C
below are additive proposals and are not prerequisites for accepting or
implementing this foundation.

### 5.2 Recommendation M03B — optional connection-freshness proposal

Connection freshness is a **new candidate capability**, not a demonstrated or
mandatory condition of the original P1 verified-selection contract. If Human
accepts it, use this closed definition:

```text
ModelConnectionObservation(
  observation_id, observation_sequence, scope,
  model_id, model_revision_id, model_digest,
  provider_id, provider_revision_id, provider_digest,
  endpoint_id, endpoint_revision_id, endpoint_digest,
  profile_id, profile_revision_id, profile_digest,
  credential_reference_id, credential_reference_version,
  adapter_id, adapter_revision, probe_kind,
  result = SUCCEEDED | FAILED | UNKNOWN,
  platform_recorded_at, provider_observed_at?,
  provider_correlation_id?, evidence_reference?, limitation_codes
)
```

Model Governance generates `observation_id` and a gap-tolerant monotonically
increasing `observation_sequence` for the exact observation key consisting of
scope plus all Model/Provider/Endpoint/Profile, credential-reference, adapter,
and probe-kind identities above. Durable append obtains
`platform_recorded_at` from an injected trusted UTC platform clock; provider
timestamps are informational and never establish freshness. A clock regression,
missing platform time, incompatible record, or ambiguous recovery reduces to
`UNKNOWN`, never current success.

The reducer reads through an owner high-water and selects the greatest
`observation_sequence` for the exact key. A latest `FAILED` yields failed; latest
`UNKNOWN` yields unknown; absence yields not verified; a latest `SUCCEEDED` is
current only while `platform_now < platform_recorded_at + ttl`. At or after that
boundary it is stale. Any exact-key change begins with no observation. The TTL is
a candidate profile parameter in `30..300` seconds, with proposed default and
maximum `300`; accepting a different value does not alter binding identity.

A binding records exact immutable configuration references and never embeds a
continually expiring freshness claim. Freshness is recomputed only for the
current operation and cannot rewrite a historical binding. A probe may use an
authenticated provider operation that identifies the exact native model; a
TCP/TLS handshake alone is insufficient. Freshness proves neither continuous
availability nor a successful inference.

### 5.3 Recommendation M03C — optional real-provider acceptance

One bounded real provider invocation with provider-confirmed technical success
is a useful **new acceptance proposal** for the later invocation integration. It
is not evidence already produced by P1 selection, cannot be a prerequisite to
the first call, and is not automatically assigned to P2 or any other version.
It requires separate provider credentials, bounded cost, redaction, and explicit
execution authorization. Denial must produce zero provider calls; ambiguous
recovery remains `OUTCOME_UNKNOWN`. One success is an immutable historical
technical result, not current liveness, quality, SLA, or business success.

### 5.4 Recommendation M04 — separate Resource Use and Evidence decisions

H308-04A and H308-04B are independent additions:

1. **H308-04A — MODEL Resource Use.** Execution remains the sole writer and
   owner of canonical Attempt Resource Use history. Add a `MODEL` Resource Kind
   carrying `resource_use_id`, Attempt and binding snapshot identities, the
   invocation authorization decision, exact Model/Provider/Endpoint/Profile
   revision identities/digests, request/dispatch/provider correlation, and the
   existing technical state progression. Persist-before-dispatch, replay,
   restart, high-water, and `OUTCOME_UNKNOWN` semantics remain Execution-owned.
2. **H308-04B — independent Evidence schema.** Evidence remains the separately
   authorized existing Evidence owner and sole Evidence writer. Add a versioned
   allowlisted Model invocation Evidence payload that references the Execution-
   owned `resource_use_id` and exact correlations; it does not become an
   Execution table or a Model Governance write. Evidence reference disclosure
   and content dereference retain their independent exact grants. No Resource
   Use permission automatically grants Evidence access, and no Evidence grant
   authorizes invocation or Resource Use access.

No writer may write the other owner's canonical facts. Provider adapters return
native observations to the owning application ports; they own neither Resource
Use nor Evidence. A Resource Use transition is not reused as an Evidence event,
and an Evidence append is not reused to advance Execution state. Existing
Resource Use meanings remain
`REQUESTED -> DISPATCH_RECORDED -> ACCEPTED -> RUNNING -> SUCCEEDED/FAILED`,
with `OUTCOME_UNKNOWN`, `REJECTED`, and `NOT_EXECUTED` preserved. Dispatch does
not prove acceptance, and technical success does not prove business success.

## 6. Typed ports and data flow

### 6.1 Recommended port shapes

Architecture-level names are candidates; they are not frozen APIs:

```text
ModelDefinitionRepository
  get_revision(scope, model_id, revision_id) -> ModelRevision | NotFound
  read_lifecycle(scope, model_id, revision_id, high_water) -> ModelEligibility
  add_revision / append_fact / advance_head  # management path only

ModelProviderConfigurationRepository
  resolve_exact(scope, provider_ref, endpoint_ref, profile_ref)
    -> ExactProviderConfiguration | NotFound

ModelUseAuthorizationPort
  authorize(scope, subject, purpose, exact_resource)
    -> CurrentAuthorizationDecision | NotFound

ExactModelResolver
  resolve_exact(scope, ExactModelBinding)
    -> ResolvedModelBinding | NotFound

ModelConnectionObservationRepository
  append(observation) -> Appended | Replayed | Conflict
  current(scope, ExactModelBinding, through_high_water)
    -> ConnectionVerification  # entire port only if H308-03B is accepted

ModelInvocationPort
  invoke(AuthorizedResolvedModelInvocation) -> NativeInvocationObservation
```

`ResolvedModelBinding` is a secret-free owner snapshot. It carries exact Model,
Provider, Endpoint, and Profile revision identities/digests plus lifecycle and
source high-water; it contains neither credentials nor connection/invocation
claims. `AuthorizedResolvedModelInvocation` adds the exact Attempt/binding
snapshot and current authorization decision. Runtime receives this sealed value
and cannot choose another model, provider, endpoint, profile, or fallback.

### 6.2 End-to-end flow

```text
Model Governance PostgreSQL authority
  -> authorization-first ExactModelResolver
  -> Agent Definition validation/publication
  -> exact Agent Model Binding snapshot
  -> Digital Employee consumes that exact Agent binding provenance
  -> Attempt + current INVOKE_MODEL authorization
  -> optional current connection observation only if H308-03B is accepted
  -> optional durable MODEL Resource Use / DISPATCH_RECORDED (H308-04A)
  -> Runtime provider adapter / native model
  -> optional Execution-owned Resource Use update (H308-04A)
  -> optional separately authorized Evidence-owner Model Evidence append (H308-04B)
  -> separately authorized BFF projections
```

- Agent consumes the exact Model Revision reference and a binding-validation
  decision. It does not copy provider configuration or own the Model digest.
- P1 Digital Employee consumes the exact Agent binding snapshot plus its source
  Agent Definition revision/digest. It does not gain a new direct Model override
  slot; a future direct employee binding remains P2 unless separately accepted.
- Runtime consumes one current authorized resolved invocation value and returns
  normalized observation facts. Environment configuration cannot replace or
  mutate the selected identities.
- BFF consumes authorized read projections and independent Evidence links. It
  does not mint identity, scope, authorization, health, or invocation success.

## 7. Reuse and required adjustment of the 308 implementation

Keep from `model_binding_resolution.py`:

- `ModelConsumptionScope`, `ModelUseSubject`, and `ExactModelBinding` intent;
- injected authorizer and exact resolver seams;
- authorization-before-resolver ordering;
- binding of authorization to subject, scope, identity, revision, and digest;
- disclosure-safe denial/not-found, exact mismatch checks, and no list/default/
  latest/display-name path;
- secret-free return boundary and zero provider calls.

After Human acceptance, adjust the internal types as follows:

1. align `namespace`/`security_domain` and principal values with the trusted
   authority types through an adapter, without importing BFF or session code;
2. extend `AuthorizedModelUse` with action, exact resource, policy generation/
   version, issued/expiry time, and decision identity; retain equality checks;
3. replace unversioned `provider_reference` and
   `connection_profile_reference` strings with exact typed Provider, Endpoint,
   and Profile revision identities/digests;
4. replace `published`, `enabled`, and ambiguous
   `configuration_available` booleans with an owner-produced typed eligibility
   snapshot and lifecycle/high-water identity;
5. keep optional connection verification and independently owned Evidence outside
   `ResolvedModelBinding`; compose them only in invocation admission/projection;
6. keep the existing function as the use-resolution path or rename it only if
   internal call sites require purpose-specific `BIND_MODEL` versus
   `INVOKE_MODEL`. No compatibility promise exists yet for this internal module.

## 8. Compatibility, revision, and revocation behavior

- Historical Model references missing revision or digest remain
  `UNVERIFIED_OPAQUE_REFERENCE`; they are readable only under their existing
  contract and are never auto-upgraded or selected for new verified execution.
- To migrate an opaque Agent reference, a user explicitly selects an exact
  Model Revision, obtains `BIND_MODEL`, and publishes a successor Agent Revision
  through exact-digest review. The predecessor remains unchanged.
- Existing runtime environment provider/model fields are legacy adapter inputs,
  not evidence that a Platform Model identity exists. They are not backfilled.
- A Provider/Endpoint/Profile change creates exact successor configuration
  revisions and, because Model invocation semantics changed, a successor Model
  Revision. Existing bindings never follow the new head implicitly.
- Disable, deprecate, revoke, or authorization revocation blocks new
  consumption. If H308-03B is accepted, stale connection blocks only an
  operation that explicitly requires a current connection claim. None rewrites
  a published binding, an already dispatched invocation, or historical Evidence.
- Retry creates a successor Attempt and a new Model Resource Use, reauthorizes,
  and re-resolves exact identities. It rechecks connection freshness only when
  H308-03B was accepted for that operation. Late provider observations remain
  attached to the original invocation.
- BFF Product and Technical projections read a compatible backend snapshot and
  show selection, authorization, optional freshness, Resource Use, and Evidence
  independently; missing or unsupported Evidence stays not verified, not false
  success or inferred zero.

Reader-first compatibility is mandatory for H308-04A and H308-04B. Before any
`MODEL` Resource Use or new Evidence payload is written, all affected readers,
reducers,
projections, replay/restart paths, and rollback-compatible binaries must accept
the new version. An older or partially upgraded reader treats an unknown kind or
schema version as `UNSUPPORTED / NOT_VERIFIED`, preserves the opaque fact where
required, and never crashes, drops history, or infers success. Only after that
proof may writers emit the additive kind/schema. No migration number is assigned
by this candidate.

## 9. Acceptance-after-decision implementation path

Human acceptance of this candidate would permit planning, not silently perform,
these bounded steps in order:

1. revise the internal 308 types/tests to the accepted exact references,
   authorization metadata, typed eligibility, and purpose-specific flows;
2. add Model Governance domain values, canonicalization, lifecycle service, and
   typed repository ports with in-memory conformance adapter;
3. deploy reader-first compatibility, then separately allocate any additive
   Model-owned persistence work and prove restart compatibility and no fallback;
4. add the exact grant target builder and authority adapter without changing
   305-owned BFF/session/grant files until their owner accepts the handoff;
5. only if H308-03B is accepted, add its bounded connection observation
   writer/reducer and a fake adapter for deterministic tests; no real call yet;
6. if H308-04A is accepted, add `MODEL` to Execution-owned Resource Use after
   compatible readers; if H308-04B is accepted, separately add the versioned
   payload through the Evidence owner after compatible readers;
7. wire Agent validation first, then Digital Employee provenance and Runtime
   invocation only after 310/shared-path ownership confirms exact files;
8. wire BFF read projections through 305's trusted context and keep Evidence
   dereference separately authorized;
9. run focused unit/conformance/restart/security tests; only if H308-03C is
   accepted, later run one separately authorized bounded real-provider check;
10. keep PR Draft until implementation evidence and Human review are complete.

No step authorizes Ready, merge, deployment, production readiness, provider
certification, or Human acceptance by an agent.

## 10. Validation matrix after acceptance

| Boundary | Required positive proof | Required negative proof |
| --- | --- | --- |
| Canonical Model owner | restart-stable exact Definition/Revision/digest and provider configuration readback | conflicting digest, cross-scope lookup, implicit latest, missing store, and memory fallback fail |
| Lifecycle/history | exact-digest review/publication, successor, disable/enable and immutable history | unpublished/disabled/deprecated/revoked revision cannot be newly bound or used; history is not deleted |
| Authorization | scope-bound `CREATE_MODEL` plus exact `READ_MODEL`, `BIND_MODEL`, `INVOKE_MODEL`, and management resources bind current principal/scope/policy | pre-ID client ID, implicit post-create authority, denial, expiry, revocation, or wrong action/resource/scope produce nondisclosing result and zero downstream calls |
| Resolver | exact Model/Provider/Endpoint/Profile identities/digests and eligibility high-water returned | any reference/digest/status mismatch fails; no display-name/first/default/environment inference |
| Optional connection (H308-03B) | exact authenticated native-model probe reduces by owner sequence and platform clock within the accepted TTL | missing/unknown/stale/latest-failed/key-changed/clock-regressed observation cannot claim current verification or rewrite binding |
| Optional real invocation (H308-03C) | one exact Attempt persists request/dispatch before a bounded call and records provider-confirmed technical success | dispatch is not accepted/success; timeout/restart ambiguity is unknown; denial is zero-call |
| Compatibility | opaque history remains visible as unverified; explicit successor gains exact binding | no historical auto-upgrade, Evidence rewrite, silent fallback, or old binding head-following |
| Security/redaction | only allowlisted IDs/digests/times/status/limitations persist | no secret value, auth header, raw prompt/response, environment dump, foreign count, or timing disclosure |
| Projection | Product/Technical/BFF show selection, authorization, and each accepted extension independently from a compatible snapshot | no frontend authority, synthetic Evidence, success color from selection alone, or business-outcome inference |

## 11. Interface handoff without shared-path modification

### 11.1 Handoff to 305

305 retains ownership of BFF, browser session, principal, grant administration,
and shared authority wiring. The accepted handoff would be:

- input: `TrustedRequestContext` / verified principal with trusted
  `AuthorityScope`, credential/session identity, policy version, and expiry;
- adapter: build only the closed exact Model action/resource mappings defined in
  Section 4 and return an opaque current decision to the Model application
  service;
- ordering: BFF calls application service with trusted context; authorization
  happens before Model repository/Evidence access; caller headers never set
  scope or `authorized=true`;
- output: disclosure-safe Model projection with exact IDs/digests, lifecycle,
  independent selection/authorization and separately accepted extension states,
  timestamps/expiry, and authorized
  Evidence references; no credential, raw provider payload, or foreign count;
- no 305 file is modified by this proposal. 305 owner approval is required for
  exact integration paths and tests.

### 11.2 Handoff to 310

310/shared Agent–Digital Employee–Runtime ownership receives only typed facts:

- Agent: `ExactModelBinding` plus binding decision and owner validation snapshot;
- Digital Employee: exact source Agent Definition revision/digest and its Model
  binding snapshot identity; no inferred or direct P1 override;
- Attempt: binding snapshot, current invocation decision, exact resolved refs,
  and only when accepted/required, connection observation identity/expiry;
- Runtime: `AuthorizedResolvedModelInvocation`, with no selection, fallback,
  credential value, or authority expansion capability;
- result: normalized native observation correlated to the same Attempt/Resource
  Use, never a rewritten Agent/Employee binding.

No 310 file is modified by this proposal. Shared consumer paths remain blocked
until 310 ownership confirms exact files and the Human accepts this contract.

## 12. Human decision summary

Human need decide only these substantive items; each recommendation is complete
enough to accept or amend without redesigning the whole system:

| ID | Explicit recommendation | Reason |
| --- | --- | --- |
| `H308-01` | Accept Model Governance as owner of Model identity/revision/digest and typed Provider/Endpoint/Profile metadata, with minimum restart-stable persistence and external Secret References | accepting enables an authoritative selection source; rejecting leaves the selection foundation internal/fake-only and blocks production composition |
| `H308-02` | Accept scope-bound pre-ID `CREATE_MODEL`, owner-generated ID, creator continuation, and independent exact `READ_MODEL`, `MANAGE_MODEL_REVISION`, `BIND_MODEL`, and `INVOKE_MODEL` decisions; do not add P1 `SELECT_MODEL` | accepting enables governed create and exact consumption; rejecting create details does not invalidate exact resolver tests, but production authorization remains blocked |
| `H308-03A` | Accept exact owner resolution plus current exact bind/use authorization as the minimum P1 verified-selection contract | accepting authorizes planning the selection foundation without waiting for freshness or a real provider call; rejecting changes the selection contract itself |
| `H308-03B` | Separately accept, amend, or reject the candidate connection-freshness observation, platform-clock reducer, and TTL parameter | acceptance adds an optional admission/projection capability; rejection has no effect on the H308-03A selection foundation |
| `H308-03C` | Separately accept, amend, or reject one bounded real provider-confirmed invocation as later integration acceptance | acceptance adds a later environment-dependent validation; rejection has no effect on the H308-03A selection foundation |
| `H308-04A` | Separately accept additive `MODEL` Resource Use under Execution ownership | acceptance enables canonical Model use history after reader compatibility; rejection leaves selection intact but without the new use-history kind |
| `H308-04B` | Separately accept a versioned Model Evidence schema under the independent Evidence owner and reader-first compatibility | acceptance enables separately authorized Evidence correlation; rejection leaves selection and H308-04A independent and intact |

Acceptance of `H308-01`, `H308-04A`, or `H308-04B` approves only its stated new
internal responsibility, not a public Contract, CRD, API group, migration,
production deployment, or complete Model Control V2. The decisions are
severable: no bundle of H308-03B, H308-03C, H308-04A, and H308-04B is a single
gate to begin the H308-03A selection foundation. If an item is amended or
rejected, implementation must honor that result without silently assigning the
capability to another version.

## 13. Historical candidate terminal state at the fixed object

```text
PARTIAL_DRAFT
MODEL_CONTRACT_PROPOSED
AWAITING_HUMAN_CONTRACT_DECISION
SESSION_OPEN
```

This document cannot mark itself Accepted. Only a Human decision may change the
contract status and authorize the next bounded implementation plan.

## 14. Current post-decision state

```text
HUMAN_MODEL_MINIMUM_CONTRACT_ACCEPTED_WITH_CONSTRAINTS
SELECTION_FOUNDATION_IMPLEMENTATION_AUTHORIZED
H308_03B_03C_04A_04B_PROPOSED
PARTIAL_DRAFT
SESSION_OPEN
```

Implementation acceptance remains a later Human decision.
