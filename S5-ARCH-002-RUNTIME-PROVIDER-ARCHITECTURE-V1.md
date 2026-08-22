# S5-ARCH-002 — Runtime Provider Architecture v1

SESSION
ID: S5-ARCH-002
TITLE: Runtime Provider & Certified Runtime Package Architecture
PHASE: S5 / v0.2 CONNECT & MANAGE
TRACK: Runtime
MODE: Architecture
STATUS: PASS
CHECKPOINT: FINAL

## 1. Status and scope

This document proposes **Runtime Provider Plugin Architecture v1** and a
**Runtime Contract Candidate v1.1** for Human Final Gate review. It is an
architecture artifact, not an implementation authorization, accepted ADR, or
frozen Contract.

The proposal applies the accepted human direction D22–D29:

- Runtime Provider is a first-class, independently evolving module;
- Core and Provider remain isolated;
- Core resolves Providers through a registry;
- Runtime Package and Runtime Provider are separate concepts;
- compatibility and certification are evaluated by explicit combination;
- the architecture is pluggable before it is dynamically loadable;
- conformance and certification are separate;
- the boundary remains compatible with a future out-of-process Provider.

Production/Core source, CRDs, APIs, Operator behavior, Runtime production
implementation, Console, accepted ADRs, and frozen Contracts are outside this
session. No Kubernetes CRD is proposed for Provider or Package metadata.

## 2. Executive decision

Adopt a small Core-facing Runtime Contract and place all Runtime-family
adaptation behind a registry-resolved `RuntimeProviderModule`.

```text
Agent Control Plane
  -> Runtime Contract Candidate v1.1
    -> Runtime Provider Registry
      -> RuntimeProviderModule
        -> Runtime-native realization
```

The invariant is:

> Core owns semantics. Provider owns adaptation. Runtime owns execution.

Core may branch on Contract vocabulary—declared capability, ownership mode,
compatibility result, or normalized observation—but never on Runtime family or
Provider ID. The following is prohibited in Core:

```text
if runtime_family == "hermes": ...
if provider_id == "openclaw": ...
```

The Registry is a resolver, not a service locator for arbitrary Provider code.
It selects an eligible Provider version from declared metadata. Core then uses
only the versioned Contract boundary.

## 3. Semantic invariants

The architecture preserves these separate identities:

```text
Agent Definition
  -> Agent Instance
    -> Runtime Binding
      -> Runtime Provider + Runtime Package
        -> opaque Runtime-native realization(s)
```

- **Agent Definition** is the logical definition.
- **Agent Instance** is the platform-managed running identity.
- **Runtime Binding** is the logical association between an Agent Instance and
  Provider/Package selection, ownership mode, and configuration, credential,
  state, and workspace references.
- **Runtime Provider** translates platform semantics to a Runtime family.
- **Runtime Package** identifies a deployable Runtime distribution/version.
- **Runtime-native realization** is an opaque Provider-specific endpoint,
  Gateway, profile, process, Pod, container, service, Agent, or Session.

There is no universal Runtime Instance in Candidate v1.1. A stable Binding,
opaque realization references, and execution correlation cover the proven
cross-runtime needs without inventing a false common lifecycle object.

A Provider never owns platform Agent identity, enterprise Model identity,
enterprise Capability identity, Workspace ownership, enterprise Policy, or
enterprise Credential governance.

## 4. Runtime Provider architecture v1

### 4.1 Core responsibilities

Core:

1. owns Contract vocabulary and normalized semantics;
2. owns Runtime Binding identity and desired state;
3. requests registry resolution using constraints, not Runtime branches;
4. rejects unresolved, incompatible, or policy-ineligible combinations;
5. invokes only declared Provider components/capabilities;
6. persists normalized observations and outcomes, not secret or unbounded
   native payloads;
7. evaluates whether the semantics promised by a Binding are satisfied;
8. preserves Kubernetes as the current Control Plane source of truth.

### 4.2 Provider responsibilities

A Provider:

1. declares identity, Contract compatibility, Runtime-family compatibility,
   capabilities, ownership modes, and limitations;
2. validates and translates a Runtime Binding;
3. realizes or connects to the selected Runtime Package;
4. computes and reconciles Runtime-native configuration where required;
5. projects credential references without taking governance ownership;
6. translates optional lifecycle and interaction operations;
7. normalizes observations and terminal outcomes;
8. exposes bounded, sanitized opaque realization references;
9. respects resource and state ownership during recovery and cleanup;
10. remains independently versionable from Core and Runtime Packages.

### 4.3 Runtime responsibilities

The Runtime owns native execution, native configuration interpretation,
native process/session behavior, native state formats, native supervision, and
native protocol behavior. Native facts are evidence to a Provider; they do not
become platform semantics automatically.

### 4.4 Deployment boundary

Architecture v1 requires interface isolation, version negotiation, deterministic
errors, timeouts, cancellation-safe calls where declared, and serializable
request/response semantics. It does **not** require dynamic loading or a
particular transport.

An in-process Provider is valid for v0.2. The same logical boundary must remain
implementable out of process later without changing Core semantics. Runtime-
specific objects, callbacks, exceptions, paths, or client types must therefore
not cross the boundary.

## 5. Core / Provider / Runtime ownership matrix

| Concern | Core / Platform | Runtime Provider | Runtime / substrate |
|---|---|---|---|
| Agent identity | Owns | References | Does not own |
| Runtime Binding | Owns semantic and desired state | Validates and realizes | Supplies native facts |
| Provider selection | Supplies constraints and policy | Declares eligibility | Does not select |
| Package selection | Selects compatible declared identity | Validates/translates | Publishes/distributes runtime |
| Compatibility | Defines dimensions and decision semantics | Declares and validates facts | Supplies version/platform facts |
| Native configuration | Defines desired portable/opaque inputs | Computes, diffs, reconciles, verifies | Interprets and stores |
| Credentials | Owns reference/governance semantics | Projects reference to native mechanism | Resolves and client consumes |
| Model | Owns enterprise identity/policy | Translates binding | Executes native model route |
| Capabilities | Owns enterprise identity/policy | Translates binding and declares support | Executes native mechanism |
| Workspace | Owns platform ownership semantics | Binds reference | Uses native workspace |
| Runtime state | Declares continuity/ownership constraints | Maps storage and observes requirements | Owns native format/use |
| Lifecycle desired state | Owns requested semantic | Adapts if capability declared | Runtime/substrate performs native action |
| Interaction | Owns normalized request/outcome semantics | Translates and correlates | Executes native protocol |
| Observation | Owns normalized vocabulary | Observes, classifies, sanitizes | Emits native evidence |
| Recovery | Defines promised recovered state | Chooses supported adaptation and verifies evidence | Lowest capable owner performs action |
| Cleanup | Defines ownership constraints | Removes only Provider-owned realization | Removes only natively owned artifacts |
| Certification policy | Owns levels and acceptance | Supplies subject and evidence | Supplies pinned test subject |

Layered participation is intentional. Semantic ownership does not imply that
Core performs each concrete action.

## 6. Runtime Provider component model

`RuntimeProviderModule` is the versioned aggregation boundary.

| Component | Requirement | Responsibility |
|---|---|---|
| Descriptor | REQUIRED | Provider identity/version, Contract range, Runtime family/ranges, ownership modes, component availability, constraints |
| Binding Validator | REQUIRED | Validate references, requested capability/mode, Package compatibility, and Provider-specific constraints without side effects |
| Binding Translator | REQUIRED | Produce Provider-native desired realization input; native details remain opaque to Core |
| Configuration Reconciler | CONDITIONAL | Compute, observe, diff, apply, re-observe, and validate effective native configuration |
| Credential Projector | CONDITIONAL | Safely project platform CredentialRefs into a declared Runtime resolution mechanism |
| Lifecycle Adapter | CONDITIONAL | Implement only declared managed lifecycle operations; no universal start/stop/scale/upgrade |
| Observation Adapter | REQUIRED | Produce normalized, timestamped observations with honest unknown/not-applicable semantics |
| Interaction Adapter | CONDITIONAL | Submit execution and return terminal outcome or durable correlation for later observation |
| Outcome Normalizer | CONDITIONAL | Required when Interaction is present unless normalization is inseparable from that adapter |
| Capability Declaration | REQUIRED | Declare supported, unsupported, limited, or unknown capabilities and constraints |
| Compatibility Validator | REQUIRED | Evaluate the concrete Platform/Contract/Provider/Package combination |

“Conditional” means required when the Provider declares the corresponding
capability or its selected Package/ownership mode requires it. Unsupported
operations are absent or return a normalized `CAPABILITY_UNSUPPORTED` decision;
they are never successful no-ops.

### 6.1 Component result envelope

Every callable component returns a Contract-defined result containing:

- operation and correlation identity;
- normalized status/category;
- stable reason code;
- bounded human-readable message;
- observation time;
- retryability only when safely knowable;
- optional sanitized native evidence reference.

Provider-native exceptions and raw secret-bearing diagnostics never cross into
Core status.

## 7. Configuration reconciliation

Hermes demonstrated that imperative mutation of only the requested fields can
leave stale native fields that alter effective routing. Therefore a Provider
with native configuration responsibility follows this convergence loop:

```text
Desired Runtime Binding
  -> compute complete desired native configuration
  -> observe current native configuration
  -> semantic diff (including incompatible stale values)
  -> reconcile through supported native mechanisms
  -> re-observe
  -> validate effective realization
```

Rules:

- the desired computation must define which prior fields are incompatible and
  therefore must be removed, not merely which fields are added;
- reconciliation should use Runtime-supported native operations when available;
- the Provider owns idempotency and redaction;
- Core sees normalized convergence/violation, not a Runtime-native schema;
- a successful write is not proof of effective configuration;
- effective validation may require a Runtime-native resolution probe, but a
  real external model call is certification evidence, not a universal
  reconciliation requirement;
- Provider-controlled fields, Runtime-controlled fields, and user/external-
  owner-controlled fields must be declared to avoid destructive convergence.

## 8. Credential boundary

The credential path has five distinct stages:

| Stage | Owner | Contract obligation |
|---|---|---|
| Platform CredentialRef | Platform governance | Stable opaque reference, authorization and non-disclosure |
| Provider Credential Projection | Provider | Map reference to declared native mechanism; never persist value in status/evidence |
| Runtime Credential Resolution | Runtime/native mechanism | Resolve projected credential for the selected profile/service/context |
| Runtime Client Consumption | Runtime client | Actually use the resolved credential for the intended dependency |
| Certification/Test Harness Credential | Harness operator | Preflight presence and authorization; isolate and redact test material |

Platform Contract v1.1 covers reference semantics, projection intent,
non-disclosure, normalized resolution/consumption observations when available,
and ownership. Provider implementation and certification cover whether a
specific Runtime/version actually resolves and consumes the credential in the
tested path.

Environment presence alone proves none of resolution, client consumption, or
successful authentication.

## 9. Runtime Provider Registry model v1

The Registry contains immutable versioned Provider records. It may initially
be repository metadata loaded at startup; no network service, database, or CRD
is implied.

### 9.1 Provider record

| Field | Requirement | Meaning |
|---|---|---|
| `providerId` | REQUIRED | Stable ecosystem-qualified identity, not Runtime family |
| `providerVersion` | REQUIRED | Immutable semantic version/build identity |
| `contractVersions` | REQUIRED | Supported Runtime Contract range(s) |
| `runtimeFamily` | REQUIRED | Family adapted by this Provider |
| `runtimeVersions` | REQUIRED | Supported/tested ranges with exclusions allowed |
| `ownershipModes` | REQUIRED | Supported modes such as managed or external |
| `capabilities` | REQUIRED | Versioned declarations with constraints |
| `components` | REQUIRED | Components present and boundary/transport metadata |
| `platformCompatibility` | REQUIRED | Supported Platform versions/ranges |
| `packageSelectors` | REQUIRED | Package constraints; never an implicit “latest” for certification |
| `certification` | REQUIRED | References to combination-scoped records; status is not inferred |
| `integrity` | REQUIRED | Artifact digest/signature/provenance as available |
| `limitations` | REQUIRED | Known bounded limitations and evidence debt |

### 9.2 Resolution semantics

Resolution input is Platform version, Contract version, requested Runtime
family or Package identity, ownership mode, required capabilities, architecture,
and applicable policy constraints.

Resolution:

1. filters records by exact/range compatibility;
2. rejects unknown compatibility rather than assuming it;
3. rejects capability or ownership-mode mismatch;
4. applies platform policy such as minimum certification maturity;
5. deterministically selects only when policy defines a unique preference;
6. returns the Provider ID/version, Package identity/digest, selected Contract
   version, and compatibility/certification evidence references.

Ambiguity is a normalized resolution failure. Registry order is not a hidden
priority. Certification status may affect policy eligibility but cannot change
Contract conformance semantics.

## 10. Runtime Package model v1

A Runtime Package answers which distribution/version is deployable. It does
not contain Provider executable code and does not imply that every Provider is
compatible.

| Metadata | Requirement / rule |
|---|---|
| Identity | Stable package ID and immutable package revision |
| Runtime family/version | Exact upstream family and version/build/source revision where known |
| Distribution | Image, binary, chart, service endpoint class, or other declared kind |
| Digest/integrity | Immutable digest and provenance/signature facts where applicable |
| Architecture/platform | OS, CPU architecture, Kubernetes/runtime prerequisites |
| Provider compatibility | Explicit Provider ID/version ranges and exclusions |
| Contract compatibility | Contract versions for which the combination was evaluated |
| Platform compatibility | Platform versions/ranges evaluated |
| Deployment mode | Managed workload, external service, host process, or declared extension |
| Config schema/mechanism | Schema/version and native configuration mechanism reference |
| Health | Native probes/signals and their limits; not normalized status itself |
| Ports/endpoints | Named native endpoints, protocols, exposure requirements |
| Storage | Paths/classes, persistence and continuity characteristics |
| State characteristics | Native state categories, replacement/upgrade limitations, no portability claim |
| Capabilities | Native/package facts that constrain Provider declarations |
| Known limitations | Explicit unsupported combinations and evidence gaps |

For v0.2 this is metadata/registry representation. A Package may describe an
external distribution with no downloadable image. Package capability facts do
not automatically become platform capabilities; the Provider declares the
translated Contract capability.

## 11. Compatibility matrix model

Compatibility is a decision over a complete tuple:

```text
Platform Version
x Runtime Contract Version
x Provider ID and Version
x Runtime Package ID and Runtime Version
x Deployment Mode
x OS/Architecture (when relevant)
```

Each cell records:

- `compatible`, `incompatible`, `unknown`, or `not-applicable`;
- source: declared, conformance-tested, certification-tested, or inferred;
- evaluated constraints and capability profile;
- evidence reference and evaluation time;
- known limitations;
- expiry/supersession rule.

`unknown` is never treated as compatible. A version range declaration is
eligibility metadata, not proof that every tuple is certified. Certification
must point to an exact or tightly bounded tested cell.

## 12. Contract conformance model

Contract conformance asks whether a Provider implementation obeys the Runtime
Contract independently of whether a particular Runtime Package works in a
real environment.

The shared conformance suite uses a deterministic fake Runtime/native boundary
and tests:

1. descriptor completeness and schema/version negotiation;
2. Binding validation and rejection reason stability;
3. capability honesty, including unsupported operation behavior;
4. normalized observation values and freshness/timestamp requirements;
5. terminal versus deferred interaction and correlation behavior;
6. semantic failure independent of transport success;
7. bounded/redacted errors and native evidence;
8. idempotency and ownership-safe cleanup where declared;
9. configuration convergence where the component is declared;
10. compatibility decisions, exclusions, and unknown handling;
11. out-of-process-safe serialization and timeout/failure semantics;
12. absence of Runtime-family assumptions in generic Contract consumers.

Conformance result is `PASS`, `FAIL`, or `NOT_EVALUATED` for one Provider
version and Contract version. Conditional test profiles are selected only from
declared capabilities. Conformance PASS is necessary but insufficient for
certification.

## 13. Runtime Provider certification model

Certification asks whether a conformant Provider and pinned Runtime Package
actually deliver their declared behavior on a supported Platform combination.

### 13.1 Maturity levels

| Level | Meaning |
|---|---|
| Community | Published integration; no platform validation claim |
| Validated | Reproducible evidence for a bounded combination; may retain limitations |
| Certified | Required conformance and live certification profiles pass for the exact supported combination |
| Official | Certified combination with platform-owned maintenance, release, security, and support commitments |

Levels are not automatically inherited by newer Platform, Contract, Provider,
or Runtime versions. “Official” is a support/governance decision, not a test
synonym.

### 13.2 Certification record

A record pins:

- Platform version/build;
- Runtime Contract version;
- Provider ID/version/artifact integrity;
- Runtime Package ID, Runtime version, distribution digest;
- deployment mode and host architecture;
- declared capability profile tested;
- conformance result/evidence;
- live test profile, results, time, environment class, and redacted evidence;
- known limitations, waivers, expiry, and issuing authority.

Certification profiles test only declared capability surfaces but include
configuration effectiveness, credential resolution **and client consumption**,
semantic interaction outcome, observation, state continuity, lifecycle,
recovery, cancellation, streaming, scaling, or upgrade when claimed.

Hermes currently remains **EXPERIMENTAL / NOT CURRENTLY CERTIFIABLE**. This is
not equivalent to “Hermes Unsupported.” S5-TEST-004 is closed as `FAIL —
PREFLIGHT STOP`; `HERMES_SPIKE_API_KEY` was absent, model requests and retries
were zero, real Kimi inference was not performed, ED-S5-001 remains open, and
no S5-TEST-005 is authorized.

## 14. Runtime Contract Candidate v1 to v1.1 delta

Candidate v1.1 remains **NOT FROZEN**.

| Change | v1 | v1.1 disposition |
|---|---|---|
| Descriptor/package | Package/distribution metadata nested in Descriptor candidate | Separate Runtime Provider and Runtime Package identities linked by compatibility |
| Provider boundary | Required concept | Formal first-class `RuntimeProviderModule` aggregation with required/conditional components |
| Registry | Implied discovery need | Defines immutable Provider records and deterministic constraint-based resolution |
| Compatibility | Declared generally | Defines tuple, four-state result, evidence source, exact combination semantics |
| Configuration | Translation responsibility | Adds complete desired-state compute/diff/reconcile/re-observe/effective-validation loop |
| Credentials | Reference/projection boundary | Separates reference, projection, Runtime resolution, client consumption, and harness credential |
| Conformance | Not fully separated | Provider/Contract fake-native conformance is distinct from live combination certification |
| Certification | Evidence need | Defines four maturity levels and immutable combination-scoped records |
| Process boundary | Provider isolation | Adds serializable, timeout/error-safe semantics compatible with future out-of-process Providers |
| Capability components | Declared capabilities | Maps declarations to component presence and conditional conformance profiles |
| Observation | Normalized four-state model | Retained; adds freshness/evidence and Registry/certification use constraints |
| Runtime Instance | Removed | Remains removed; no new universal lifecycle object |
| Interaction | Conditional submit/outcome model | Retained; no universal invoke, wait, stream, cancel, lifecycle, scale, or upgrade |

No v1 semantic is frozen by this delta. Human review must decide whether v1.1
becomes the next Contract candidate baseline.

## 15. Hermes and OpenClaw falsification

### 15.1 Core-facing fit

| Contract concern | Hermes | OpenClaw | Contradiction? |
|---|---|---|---|
| Binding | Can bind Provider/package/profile/config/state refs without exposing them to Core | Can bind Provider/package/Gateway/Agent/workspace refs opaquely | No |
| Ownership mode | Managed container/Pod evidence and possible external forms | Long-lived externally/operator-managed Gateway fits external or managed-by-declared-owner mode | No |
| Configuration | Requires native reconciliation, including stale `model.base_url` removal | Native Gateway/Agent/model configuration remains Provider-specific | No |
| Lifecycle | Layered s6/Kubernetes/Provider recovery; optional adapter | Long-lived Gateway restart ownership differs; no universal per-execution lifecycle | No; lifecycle remains conditional |
| Observation | API availability differs from dependency/task success | Gateway/protocol availability differs from deferred execution outcome | No; normalized scoped observations preserve distinction |
| Interaction | Blocking terminal response can complete inline | Deferred acceptance requires handle/correlation and later outcome observation | No; Contract supports inline or deferred outcome |
| State/workspace | Profile/home/storage categories are native and partially mixed | Session/workspace semantics are explicit and materially distinct | No; references/continuity only, no portable-state claim |
| Credentials | Projection, profile resolution, and model-client use are distinct | Gateway/model auth resolution and client use are distinct | No |
| Runtime realization | Container/Pod/profile/Gateway/process are non-universal | Shared Gateway/Agent/Session/run topology is non-universal | No; opaque realization model required |

### 15.2 Falsification result

Both runtimes fit behind the same Core-facing Candidate v1.1 **only because**
the Contract does not require a universal Runtime Instance, synchronous invoke,
per-Agent process, lifecycle adapter, streaming, cancellation, scaling, or
upgrade. Provider-specific topology, configuration, protocols, and state remain
behind the boundary.

No contradiction to the Shared Semantic Baseline was found. The strongest
remaining falsification risk is behavioral rather than conceptual: one
identical generic Contract consumer has not yet been executed unchanged against
both Provider implementations, and neither third-party Runtime has produced a
successful real-model completion in the available evidence.

## 16. Architecture principle candidate disposition

| Candidate | Disposition | Rationale |
|---|---|---|
| AP-S5-005 Runtime Provider Isolation | **RECOMMEND ACCEPT** | Both spikes required materially different native details while Core changes remained zero; boundary rules prevent leakage |
| AP-S5-006 Independent Provider Evolution | **RECOMMEND ACCEPT** | Provider and Runtime Package versions vary independently; Registry and compatibility tuple make that explicit |
| AP-S5-007 Governed Extension | **RECOMMEND ACCEPT** | Registry metadata, integrity, policy eligibility, conformance, and certification prevent arbitrary extensions from implying trust |
| AP-S5-008 Certification by Combination | **RECOMMEND ACCEPT** | Evidence cannot justify family-wide certification; exact Platform/Contract/Provider/Runtime tuple is required |
| AP-S5-009 Runtime Native Configuration Reconciliation | **RECOMMEND ACCEPT WITH QUALIFICATION** | Required when a Provider owns native configuration convergence; external/preconfigured Providers may declare no reconciler and reduced guarantees |

These are recommendations to the Human Final Gate. This document does not
freeze or promote them to accepted ADR principles.

## 17. Open questions

1. What is the minimum stable schema and compatibility policy for Provider and
   Package registry records?
2. Which party publishes and signs Provider and Package metadata, and how are
   revocation and compromised artifacts handled?
3. What is the v0.2 Provider loading mechanism, and what security boundary is
   required before enabling third-party code?
4. Which normalized capability vocabulary is small enough for v1.1, and which
   items remain extensions?
5. What are observation freshness, staleness, aggregation, and transition rules?
6. Which Binding fields are portable versus opaque Provider extensions?
7. How are Provider configuration-field ownership and conflicts declared?
8. What timeout, retry, idempotency, and backpressure semantics are mandatory
   at a future out-of-process boundary?
9. How are certification evidence expiry, CVE response, revocation, and
   recertification governed?
10. Does v0.2 require a Package catalog, or only repository-owned metadata for
    the small validated set?
11. What exact unchanged-consumer contract test is the entry gate for S5-DEV?
12. Which successful real-model path is authorized to close third-party
    interaction evidence without reopening S5-TEST-004?

## 18. Evidence debt

| Debt | Impact |
|---|---|
| ED-S5-001 remains open; Hermes real-model completion absent | Hermes cannot be certified; successful outcome/usage/correlation path unproven |
| OpenClaw successful real-model completion absent | Deferred successful terminal outcome and dependency recovery remain unproven |
| Identical generic consumer not run unchanged against both Providers | Provider extension test is partial, not complete |
| No third Runtime family | Candidate may still contain two-runtime coincidences |
| No out-of-process prototype | Serialization/failure isolation is an architecture constraint, not demonstrated behavior |
| No signed registry/package artifacts | Supply-chain and revocation model remains conceptual |
| No upgrade, scale, cancel, or common streaming proof | These remain optional and must not be promoted to universal semantics |
| No cross-runtime state/workspace portability proof | Runtime Contract must remain reference/continuity-only |
| No credential-consumption success in final Hermes gate | Projection cannot be equated with effective client authentication |
| No production Provider SDK/conformance harness | Conformance model is proposed, not implemented |

## 19. Runtime Freeze Gate amendment proposal

Amend the future Runtime Contract freeze gate so freeze requires all of:

1. a human-accepted ADR for Provider/Core ownership and Contract scope;
2. an explicit Contract registry entry with version, status, owner,
   compatibility policy, and governing ADR;
3. frozen schemas for Descriptor, Binding, capability declaration,
   observation, interaction/outcome, compatibility decision, and error envelope;
4. Provider Registry and Runtime Package metadata schemas with deterministic
   resolution and immutable identity rules;
5. a shared conformance suite passing for Native Runtime and at least two
   materially distinct external Provider prototypes;
6. one identical generic consumer exercised unchanged across those Providers;
7. live successful and semantic-failure interaction evidence for the
   certification candidate combinations;
8. managed and external ownership-mode evidence, including cleanup safety;
9. configuration reconciliation evidence that detects/removes incompatible
   stale native state and validates effective realization;
10. credential evidence covering projection, Runtime resolution, and client
    consumption without secret disclosure;
11. compatibility, deprecation, negotiation, and migration policies;
12. Provider boundary security/threat review and out-of-process compatibility
    review;
13. all blocking evidence debt closed or explicitly accepted by the Human Gate.

Certification of every capability is not required to freeze a minimal
Contract; unsupported capabilities must instead be honestly declarable. A
single Provider or Runtime-family success is insufficient.

## 20. Recommendation for Human Final Gate

**Recommend PASS of S5-ARCH-002 as a non-frozen architecture proposal:** accept
Runtime Provider Architecture v1, accept the separation of Runtime Provider and
Runtime Package, adopt Candidate v1.1 as the next review baseline, and accept
AP-S5-005 through AP-S5-009 with the qualification recorded above.

Do **not** freeze the Runtime Contract or authorize broad S5-DEV yet. Authorize
one bounded next architecture/contract session to turn Candidate v1.1 into
reviewable schemas and a conformance test plan, with the unchanged-consumer
Hermes/OpenClaw test as an explicit entry gate. Hermes remains experimental and
not currently certifiable; do not reopen S5-TEST-004 or create S5-TEST-005.

## 21. Evidence basis

This proposal is derived from:

- `PRODUCT.md`, `ARCHITECTURE.md`, and `ROADMAP.md`;
- repository engineering authority and Architecture Gate documents;
- Hermes Checkpoint C synthesis and subsequent ED-S5-001 failure evidence;
- closed S5-TEST-004 final certification result supplied to this session;
- OpenClaw Checkpoints A–C supplied by S5-SPIKE-002;
- the explicit accepted human directions D22–D29 in the S5-ARCH-002 task.

Evidence from experiments is architecture input only. It is not a claim that
Hermes or OpenClaw is implemented or supported in Production/Core.
