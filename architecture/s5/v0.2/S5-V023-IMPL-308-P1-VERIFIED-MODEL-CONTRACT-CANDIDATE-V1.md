# S5-V023-IMPL-308 — P1 Verified Model Minimum Contract Candidate v1

## 1. Decision record

| Field | Value |
| --- | --- |
| Session | `S5-V023-IMPL-308` |
| Type | Same-session bounded contract decision preparation |
| Source commit / tree | `bb8ab228bac52d9caecb3e44c95053afa1673767` / `b3406971e4f47f83754ffc789e7cabb6c4b7805a` |
| Pull request | `#163`; must remain Draft |
| Decision status | `PROPOSED / AWAITING_HUMAN_CONTRACT_DECISION` |
| Implementation status | `PARTIAL_DRAFT`; internal consumer preparation only |
| Contract status | Internal v0.2 candidate; `NOT_ACCEPTED / NOT_FROZEN` |
| Implementation authority from this record | `NO`; Human acceptance is required before authority, persistence, Evidence, or shared-consumer changes |

This candidate makes the smallest concrete decisions needed to implement the
existing P1 verified Model obligation. It does not change M1/M2/M3, P1/P2/P3,
create a public API or CRD, complete Model Control V2, or treat a test fake as a
production owner. The session-carried Human constraint places complete Model
Control V2 in v0.2.3 P2; this candidate does not move P1 obligations into P2.
Repository product documents that describe broader Model Governance under
v0.2.4 are not edited or silently reinterpreted here.

## 2. Inherited authority and verified current gap

The candidate inherits rather than reopens these constraints:

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
references, lifecycle eligibility facts, and Model connection observations.

The minimum owner surface is:

```text
ModelGovernanceService
  -> ModelDefinitionRepository
  -> ModelRevisionRepository
  -> ModelProviderConfigurationRepository
  -> ModelConnectionObservationRepository
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
provider-native names as Platform identity.

| Record | Minimum authoritative content | Owner and mutability |
| --- | --- | --- |
| `ModelDefinition` | `scope`, `model_id`, owner identity, created provenance | Model Governance; stable root |
| `ModelRevision` | `model_revision_id`, predecessor, canonical digest, exact Provider/Endpoint/Profile revision references, provider-native model identifier, declared compatibility/capabilities, non-secret invocation limits | Model Governance; immutable after publication |
| `ModelProviderRevision` | provider identity/revision/digest, adapter contract identity/revision, supported operation classes | Model Governance registry metadata; immutable revision |
| `ModelEndpointRevision` | endpoint identity/revision/digest, normalized non-secret address/reference, region and transport constraints | Model Governance configuration metadata; immutable revision |
| `ModelConnectionProfileRevision` | profile identity/revision/digest, Endpoint Revision, typed Secret Reference metadata/version, bounded timeouts and connection-verification TTL | Model Governance configuration metadata; immutable revision; no secret value |
| `ModelLifecycleFact` | validation, review, publication, enable/disable, deprecation, revocation and successor facts with actor/decision/time | Model Governance; append-only |
| `ModelConnectionObservation` | exact Model/Provider/Endpoint/Profile revisions, adapter revision, credential-reference version, probe/result/times and Evidence reference | normalized provider observation recorded by Model Governance; append-only |

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

This requires a future additive Model-owned schema/migration and is therefore a
new persistent architecture responsibility. No migration number or physical
table layout is approved by this candidate. A separately authorized
implementation must allocate paths and migration ownership without modifying
historical migrations `0001`–`0018`.

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

- only a trusted principal holding the exact management grant may create or
  mutate Draft state or append a lifecycle action;
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

## 4. Recommended authorization contract

### 4.1 Recommendation M02 — exact grant vocabulary

**Recommend Human accept:** reuse the existing exact grant shape
`ExactGrant(owner, action, exact_resource)` with this closed Model mapping:

| Operation | `owner` | `action` | Trusted-server `exact_resource` template |
| --- | --- | --- | --- |
| List the bounded scoped catalog | `MODEL_GOVERNANCE` | `READ_MODEL` | `model:catalog` |
| Inspect one exact identity/revision and its allowed projection | `MODEL_GOVERNANCE` | `READ_MODEL` | `model:revision:{model_id}:{revision_id}:{digest}` |
| Persist an exact Model Binding into one exact consumer revision | `MODEL_GOVERNANCE` | `BIND_MODEL` | `model:binding:{consumer_kind}:{consumer_id}:{consumer_revision_id}:{model_id}:{revision_id}:{digest}` |
| Invoke through one exact Attempt binding snapshot | `MODEL_GOVERNANCE` | `INVOKE_MODEL` | `model:invocation:{attempt_id}:{binding_snapshot_id}:{model_id}:{revision_id}:{digest}` |
| Create/revise/publish/disable/enable/deprecate/revoke or connection-test | `MODEL_GOVERNANCE` | `MANAGE_MODEL_REVISION` | `model:management:{operation}:{model_id}:{target_revision_or_new}` |

Every segment is constructed from typed validated values by the trusted server;
the authority compares the complete string exactly and supports no wildcard.
Scope remains a separate mandatory field on the principal, grant, record, and
repository key. An exact resource string never overrides or supplies scope.

The exact `model:catalog` grant authorizes only deterministic bounded listing
inside the already trusted scope; it is not a wildcard and does not authorize
foreign scope, detail Evidence, bind, or use. The service applies lifecycle and
eligibility filters server-side and returns no foreign counts.

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

## 5. P1 verified guarantees and Evidence

### 5.1 Recommendation M03 — four independent guarantees

**Recommend Human accept:** do not expose a single undifferentiated `verified`
boolean. The same P1 chain carries four independent guarantees:

| Guarantee | P1 role | Authority and exact correlation | Validity / invalidation | It does not prove |
| --- | --- | --- | --- | --- |
| Exact identity and configuration resolution | Mandatory before bind and before each new invocation | Model Governance repository; scope, Model ID/Revision/digest, Provider/Endpoint/Profile revisions and lifecycle fact/high-water | Valid for the exact resolved snapshot; re-read for a new consumption. Mismatch, successor substitution, missing/unpublished/disabled/deprecated/revoked reference, store incompatibility, or referenced-config ineligibility fails closed | permission, provider reachability, invocation, quality, cost, or business outcome |
| Current subject authorized to use | Mandatory at binding (`BIND_MODEL`) and actual use (`INVOKE_MODEL`) | existing authority via the proposed exact vocabulary; decision ID, principal, scope, action/resource, policy generation, issued/expiry times | Must be current at the protected read and, for use, immediately before durable dispatch. Expiry, revocation, generation change, or any binding mismatch invalidates it | Model existence, publication, reachability, actual provider effect, success, or future permission |
| Provider connection verified | Mandatory for a P1 `CONNECTION_VERIFIED_CURRENT` claim and for admission to the verified P1 invocation path; not a prerequisite to author a Draft | Model connection observation normalized by the exact provider adapter; exact Model/Provider/Endpoint/Profile and credential-reference versions, adapter revision, probe ID/result, observed/expiry time | Profile declares `connection_verification_ttl_seconds` in `30..300`; recommend default and maximum `300`. A newer failure, TTL expiry, reference/credential/adapter change, or ambiguity yields failed/stale/not-verified | continuous availability, capacity, successful inference, model quality, or SLA |
| Model actual invocation verified | Mandatory post-dispatch fact and mandatory in the P1 end-to-end acceptance chain; cannot be a prerequisite to the first invocation | Execution-owned typed Model Resource Use/Evidence; exact Attempt, binding snapshot, authorization decision, Model/Provider/Endpoint/Profile revisions, dispatch and provider correlation/outcome facts | Immutable historical fact for that invocation. It does not expire, but it is never reused as current liveness; uncertain recovery remains `OUTCOME_UNKNOWN` | current connection, future success, response quality, business outcome, policy suitability, or continuous availability |

The P1 admission sequence uses the first three guarantees. The fourth is written
after dispatch. P1 end-to-end acceptance requires a single traceable chain in
which all four are present and one bounded real inference reaches a provider-
confirmed technical success. Negative acceptance must also prove denial causes
zero provider calls and ambiguous recovery stays unknown. A successful call is
only one historical technical result.

Connection verification may use a provider-supported authenticated health/model
metadata operation that confirms the exact native model identity. A TCP/TLS
handshake alone is insufficient. If no non-inference operation can prove the
exact model, one separately authorized minimal inference may emit both a
connection observation and invocation Evidence, but the two facts and meanings
remain separate. No external call is performed by this candidate.

The substantive alternative is a fresh probe before every invocation. It is not
recommended because it adds provider traffic or cost, still cannot guarantee
availability after the probe, and can turn a read-only admission check into an
extra inference. An unbounded provider-selected TTL is also rejected because it
makes P1 verification incomparable. The proposed bounded profile value permits
stricter provider-specific freshness while keeping a common five-minute ceiling.

### 5.2 Minimum typed Evidence additions

The provider adapter owns the native observation; Model Governance validates and
records this allowlisted connection fact:

```text
ModelConnectionObservation(
  observation_id, scope,
  model_id, model_revision_id, model_digest,
  provider_id, provider_revision_id, provider_digest,
  endpoint_id, endpoint_revision_id, endpoint_digest,
  profile_id, profile_revision_id, profile_digest,
  credential_reference_id, credential_reference_version,
  adapter_id, adapter_revision,
  probe_kind, result, provider_correlation_id?,
  observed_at, expires_at, evidence_reference, limitation_codes
)
```

Execution remains the owner of actual use. **Recommend Human accept** an
additive `MODEL` kind in the existing typed Attempt Resource Use/Evidence
boundary rather than a standalone competing invocation store:

```text
ModelInvocationEvidence(
  resource_use_id, attempt_id, binding_snapshot_id,
  authorization_decision_id,
  exact Model/Provider/Endpoint/Profile revision identities and digests,
  requested_at, dispatch_recorded_at,
  provider_accepted_at?, terminal_observed_at?,
  provider_correlation_id?,
  technical_state, response_digest?, limitation_codes
)
```

The allowed technical progression reuses existing Resource Use meanings:
`REQUESTED -> DISPATCH_RECORDED -> ACCEPTED -> RUNNING -> SUCCEEDED/FAILED`,
with `OUTCOME_UNKNOWN`, `REJECTED`, and `NOT_EXECUTED` preserved. Dispatch does
not prove acceptance; technical success does not prove business success.

This is a **new architecture responsibility** because the current Resource Kind
set and Execution Evidence payload do not contain Model or its exact revisions.
It is smaller and safer than inventing a parallel Model invocation history and
lets existing append-only identity, persist-before-dispatch, restart, reducer,
high-water, redaction, and projection rules remain authoritative. Full health
history, evaluation, quality, policy routing, fallback, token/cost governance,
continuous optimization, and provider certification remain Model Control V2 P2.

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
    -> ConnectionVerification

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
  -> Attempt + current INVOKE_MODEL authorization + fresh connection observation
  -> durable MODEL Resource Use / DISPATCH_RECORDED
  -> Runtime provider adapter / native model
  -> connection observation + invocation Evidence
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
5. keep connection verification and invocation Evidence outside
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
- Disable, deprecate, revoke, stale connection, or authorization revocation
  blocks new consumption. It does not rewrite a published binding, an already
  dispatched invocation, or historical Evidence.
- Retry creates a successor Attempt and a new Model Resource Use, reauthorizes,
  re-resolves exact identities, and rechecks connection freshness. Late provider
  observations remain attached to the original invocation.
- BFF Product and Technical projections read the same backend snapshot and show
  the four guarantees independently; missing Evidence stays not verified, not
  false success or inferred zero.

## 9. Acceptance-after-decision implementation path

Human acceptance of this candidate would permit planning, not silently perform,
these bounded steps in order:

1. revise the internal 308 types/tests to the accepted exact references,
   authorization metadata, typed eligibility, and purpose-specific flows;
2. add Model Governance domain values, canonicalization, lifecycle service, and
   typed repository ports with in-memory conformance adapter;
3. allocate a new additive PostgreSQL migration after the then-current migration,
   implement repository/restart compatibility, and prove no fallback;
4. add the exact grant target builder and authority adapter without changing
   305-owned BFF/session/grant files until their owner accepts the handoff;
5. add the bounded connection observation writer/reducer and a fake adapter for
   deterministic tests; no real provider call yet;
6. add `MODEL` to the Execution-owned Resource Use/Evidence contract and
   persist-before-dispatch flow under its owner;
7. wire Agent validation first, then Digital Employee provenance and Runtime
   invocation only after 310/shared-path ownership confirms exact files;
8. wire BFF read projections through 305's trusted context and keep Evidence
   dereference separately authorized;
9. run focused unit/conformance/restart/security tests, then one separately
   authorized real-provider P1 acceptance with bounded cost and redacted Evidence;
10. keep PR Draft until implementation evidence and Human review are complete.

No step authorizes Ready, merge, deployment, production readiness, provider
certification, or Human acceptance by an agent.

## 10. Validation matrix after acceptance

| Boundary | Required positive proof | Required negative proof |
| --- | --- | --- |
| Canonical Model owner | restart-stable exact Definition/Revision/digest and provider configuration readback | conflicting digest, cross-scope lookup, implicit latest, missing store, and memory fallback fail |
| Lifecycle/history | exact-digest review/publication, successor, disable/enable and immutable history | unpublished/disabled/deprecated/revoked revision cannot be newly bound or used; history is not deleted |
| Authorization | exact `READ_MODEL`, `BIND_MODEL`, `INVOKE_MODEL`, and management resources bind current principal/scope/policy | denial, expiry, revocation, wrong purpose/resource/scope produce nondisclosing result and zero downstream calls |
| Resolver | exact Model/Provider/Endpoint/Profile identities/digests and eligibility high-water returned | any reference/digest/status mismatch fails; no display-name/first/default/environment inference |
| Connection | exact authenticated native-model probe records current observation within `30..300s` TTL | stale/newer-failed/ref-changed/credential-version-changed observation cannot claim current verification |
| Invocation | one real exact Attempt persists request/dispatch before call and records provider-confirmed technical success | dispatch is not accepted/success; timeout/restart ambiguity is unknown; denial is zero-call |
| Compatibility | opaque history remains visible as unverified; explicit successor gains exact binding | no historical auto-upgrade, Evidence rewrite, silent fallback, or old binding head-following |
| Security/redaction | only allowlisted IDs/digests/times/status/limitations persist | no secret value, auth header, raw prompt/response, environment dump, foreign count, or timing disclosure |
| Projection | Product/Technical/BFF show four independent guarantees from one snapshot | no frontend authority, synthetic Evidence, success color from selection alone, or business-outcome inference |

## 11. Interface handoff without shared-path modification

### 11.1 Handoff to 305

305 retains ownership of BFF, browser session, principal, grant administration,
and shared authority wiring. The accepted handoff would be:

- input: `TrustedRequestContext` / verified principal with trusted
  `AuthorityScope`, credential/session identity, policy version, and expiry;
- adapter: build the four exact Model grants/resources defined in Section 4 and
  return an opaque current decision to the Model application service;
- ordering: BFF calls application service with trusted context; authorization
  happens before Model repository/Evidence access; caller headers never set
  scope or `authorized=true`;
- output: disclosure-safe Model projection with exact IDs/digests, lifecycle,
  four independent verification states, timestamps/expiry, and authorized
  Evidence references; no credential, raw provider payload, or foreign count;
- no 305 file is modified by this proposal. 305 owner approval is required for
  exact integration paths and tests.

### 11.2 Handoff to 310

310/shared Agent–Digital Employee–Runtime ownership receives only typed facts:

- Agent: `ExactModelBinding` plus binding decision and owner validation snapshot;
- Digital Employee: exact source Agent Definition revision/digest and its Model
  binding snapshot identity; no inferred or direct P1 override;
- Attempt: binding snapshot, current invocation decision, exact resolved refs,
  and connection observation identity/expiry;
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
| `H308-01` | Accept Model Governance as owner of Model identity/revision/digest plus typed Provider/Endpoint/Profile metadata, with PostgreSQL primary persistence and external Secret References | supplies the missing restart-stable authority without promoting a runtime adapter or creating duplicate native state |
| `H308-02` | Accept the four exact grant mappings in Section 4; do not add P1 `SELECT_MODEL` or redundant read grants inside bind/invoke | fits current exact-grant mechanics while preserving independent bind, use, inspection, and management authority |
| `H308-03` | Accept the four independent verified guarantees, connection TTL range `30..300s` with default/max `300s`, and the rule that P1 end-to-end acceptance requires one real provider-confirmed invocation | preserves all P1 obligations without claiming continuous availability or turning historical success into admission authority |
| `H308-04` | Accept additive `MODEL` Resource Use/Evidence under Execution ownership and the typed port/data-flow adjustments in Sections 6–8 | reuses append-only execution authority and avoids a competing invocation store; this is the minimum new Evidence ownership needed |

Acceptance of `H308-01` and `H308-04` is explicit approval of new internal
architecture responsibilities, not approval of a public Contract, CRD, API
group, migration, production deployment, or complete Model Control V2. If any
item is amended, implementation must use the amended value and keep the other
inherited constraints unchanged.

## 13. Candidate terminal state

```text
PARTIAL_DRAFT
MODEL_CONTRACT_PROPOSED
AWAITING_HUMAN_CONTRACT_DECISION
SESSION_OPEN
```

This document cannot mark itself Accepted. Only a Human decision may change the
contract status and authorize the next bounded implementation plan.
