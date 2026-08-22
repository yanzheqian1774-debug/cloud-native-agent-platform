# Checkpoint C — Runtime Contract synthesis

> **CANDIDATE · NOT FROZEN · HERMES-DERIVED**
>
> Architecture evidence only. This document is not an API, specification,
> production design, ADR, or authorization to implement a Runtime Contract.

Evidence labels used below:

- **LIVE** — observed in Checkpoint A.2 or B against Hermes v0.20.4.
- **UPSTREAM** — verified pinned Hermes documentation/source.
- **STATIC** — experimental boundary/source test evidence.
- **INFERENCE** — architecture interpretation that requires falsification.

## Evidence baseline

Checkpoint A established repeatable provisioning, a real gateway interaction
path, Provider isolation, distinct infrastructure/runtime/dependency/execution
signals, and false-positive health/result behavior. Checkpoint B established
native process recovery, substrate-dependent workload recovery, persistent
runtime-local state, restart-versus-recovery, and non-universal
container/profile mappings.

Limits: ED-S5-001 remains open; no successful real-model completion occurred.
No multi-profile, horizontal-scale, external-runtime, upgrade, cancellation, or
streaming experiment was executed. Hermes is the only runtime studied.

## E8 — Hermes Runtime Capability Matrix

| Capability | Status | Evidence | Recovery/execution owner | Contract implication | S5-SPIKE-002? |
|---|---|---|---|---|---|
| Managed Provision | SUPPORTED | **LIVE:** three Docker provisions and one Kubernetes Deployment | Provider translates; substrate creates | Provision is optional managed-lifecycle capability, not universal operation | Yes |
| Configuration | SUPPORTED | **LIVE:** env/Secret binding; invalid key separated gateway from API | Provider translates; Hermes consumes | Core needs opaque/config-reference semantics, not Hermes fields | Yes |
| Start | SUPPORTED | **LIVE:** entrypoint and gateway start sequence | Substrate starts workload; Hermes starts gateway | Express desired availability, not universal imperative `start()` | Yes |
| Runtime Interaction | LIMITED | **LIVE/STATIC:** generic request reached real gateway; no model completion | Provider translates; Hermes executes | Mandatory only for executable runtimes; normalize semantic result/error | Yes |
| Health Observation | LIMITED | **LIVE:** container, gateway, API observable; native checks ambiguous | Provider observes/translates | Observation and interaction must remain separate | Yes |
| Dependency Readiness | LIMITED | **LIVE:** `model.status=ok` with no usable provider | Provider must derive; Hermes signal insufficient | Tri-state dependency condition; optional if no dependencies are exposed | Yes |
| Task Readiness | UNKNOWN | **LIVE:** no real model; HTTP 200 contained failure | Execution layer/Provider interpretation | Do not make a mandatory Runtime condition | Yes |
| Native Process Recovery | SUPPORTED | **LIVE:** s6 PID 123→244 in 7.904 s | Hermes/s6 | Declare optional native-recovery capability and observe outcome | Yes |
| Workload Recovery | LIMITED | **LIVE:** Deployment recovered; plain Docker did not | Kubernetes or Provider | Substrate/provider capability, not intrinsic runtime promise | Yes |
| Persistent Runtime State | SUPPORTED | **LIVE:** named-volume inventory survived replacement | Hermes writes; substrate stores; Provider binds | Declare storage requirements and persistence capability | Yes |
| Recreate | SUPPORTED | **LIVE:** same-volume and fresh-volume recreation | Provider/substrate/Hermes bootstrap | Recreate must state ownership and continuity expectations | Yes |
| Cancel | UNKNOWN | **UPSTREAM:** capability endpoint advertises stop; not exercised | Unknown | Optional declaration; exclude from mandatory v0 | Yes |
| Streaming | UNKNOWN | **UPSTREAM:** API documents SSE; not exercised | Hermes/Provider | Optional declaration; exclude from mandatory v0 | Yes |
| Multiple Runtime Instances | LIMITED | **LIVE:** separate clean containers; not concurrent shared state | Provider/substrate | Cardinality and isolation are capability/placement concerns | Yes |
| Multiple Profiles | LIMITED | **UPSTREAM:** profiles documented; not tested live | Hermes/s6 | Hermes-specific realization; never a Core requirement | Yes |
| Horizontal Scale | UNKNOWN | **UPSTREAM:** concurrent-writer constraint; no scale test | Unknown | Must be explicit capability with state constraints | Yes |
| External Runtime Mode | UNKNOWN | No live evidence | External owner/Provider | Architecturally plausible mode; needs second-runtime attack | Yes |
| Runtime Upgrade | UNKNOWN | Image replacement concept only; not exercised | Provider/substrate/runtime | Defer lifecycle semantics beyond version/package identity | Yes |
| State Portability | UNKNOWN | **LIVE:** persistence only; no cross-runtime transfer | Unknown | Explicit non-goal for v0 | Yes |

### Mandatory versus optional capabilities

Universally mandatory candidates are deliberately small:

1. Provider identification and compatibility declaration (**INFERENCE**).
2. Translation of a logical binding into a runtime realization or connection
   (**LIVE/STATIC**, though external connection remains untested).
3. Normalized observation of what the Provider can know, including UNKNOWN
   (**LIVE**).
4. Provider-specific error/result interpretation when interaction is supported
   (**LIVE**: HTTP 200 failure).
5. Cleanup/ownership semantics for resources the Provider creates
   (**LIVE/INFERENCE**).

Optional Provider-declared behavior: managed provision, managed lifecycle,
invoke, stream, cancel, native recovery, workload recovery, persistent state,
recreate, multiple instances, external mode, horizontal scale, and upgrade.

Substrate capabilities—not runtime capabilities by themselves—include workload
scheduling/creation, replica reconciliation, container restart, storage
attachment, network publication, and Secret projection. A Provider may declare
that it can realize runtime semantics using those substrate capabilities.

Unknown: whether every useful runtime must support direct invocation, whether
observation alone is sufficient for connected runtimes, and the minimum cleanup
operation for externally owned realizations.

## E9 — Responsibility Matrix

| Responsibility | Platform / Control Plane | Runtime Provider | Infrastructure / Kubernetes | Runtime Native / Hermes |
|---|---|---|---|---|
| Runtime Definition interpretation | OWNS SEMANTIC | TRANSLATES | — | — |
| Runtime Package resolution | Selects compatible intent (**INFERENCE**) | TRANSLATES/resolves | Fetches image/artifact | Publishes distribution |
| Runtime Binding | OWNS SEMANTIC (**INFERENCE**) | REALIZES | Hosts realization | Supplies native identity |
| Provision request | OWNS desired semantic | TRANSLATES | EXECUTES resource creation | Bootstraps runtime |
| Workload creation | — | Requests | EXECUTES/OWNS infrastructure | — |
| Storage binding | Declares continuity need | TRANSLATES requirements | EXECUTES attachment | DECLARES/uses paths |
| Credential binding | OWNS governance intent | TRANSLATES reference | Projects/injects | Consumes credential |
| Configuration translation | Defines opaque/portable intent only | TRANSLATES | Transports config | INTERPRETS native config |
| Runtime startup | OWNS desired availability | Selects command/mode | Starts workload | Starts gateway/runtime |
| Process supervision | OBSERVES normalized outcome | OBSERVES/translates | Container supervision only | SUPERVISES gateway via s6 |
| Interaction translation | Defines normalized semantics | TRANSLATES | Network transport | EXECUTES native API |
| Result interpretation | OWNS success/error categories | TRANSLATES/classifies | — | Emits native response |
| Infrastructure observation | OWNS normalized condition | TRANSLATES | OBSERVES/reports | — |
| Runtime observation | OWNS normalized meaning | TRANSLATES | Provides reachability | OBSERVES native state |
| Dependency observation | OWNS normalized meaning | TRANSLATES/derives | May expose dependency network | Native signal may participate |
| Task outcome interpretation | Execution semantic, not lifecycle | TRANSLATES native result | — | Emits native outcome |
| Failure detection | OWNS semantic violation | OBSERVES/translates | OBSERVES infrastructure | OBSERVES native failure |
| Recovery decision | OWNS desired semantic; triggers only if needed | Chooses supported action | Reconciles declared workload | Native supervisor decides locally |
| Concrete recovery action | Usually not executor | EXECUTES when no lower owner | EXECUTES workload recovery | EXECUTES process recovery |
| Semantic recovery verification | OWNS definition | OBSERVES/translates evidence | Supplies infrastructure signal | Supplies native signal |
| Persistent runtime state | Defines continuity policy only | TRANSLATES/binds | STORES/attaches | OWNS native format/use |
| Upgrade coordination | OWNS desired version/compatibility (**INFERENCE**) | TRANSLATES | Rolls workload | Handles native migration; UNKNOWN |
| Capability declaration | Defines vocabulary | DECLARES support/constraints | Advertises substrate features | Native facts inform declaration |
| Audit/trace emission | OWNS governance semantics | TRANSLATES/emits boundary events | Emits infrastructure events | Emits native telemetry |

Layered participation is intentional. “OWNS SEMANTIC” does not imply execution
of every action.

## Recovery model synthesis

Candidate sequence:

`Desired semantic state → platform reconciliation → Provider translation →
appropriate recovery owner → native/substrate action → normalized observation
→ semantic verification`

Assessment: **SUPPORTED CANDIDATE**.

- Recovery trigger: a normalized desired semantic is violated; the detecting
  layer may be Hermes, Kubernetes, Provider, or platform observer.
- Recovery action: performed by the lowest appropriate capable owner. E4 used
  Hermes/s6; Kubernetes E5 used ReplicaSet; plain Docker E5 required Provider.
- Recovery observation: Provider combines substrate/native evidence.
- Recovery verification: platform semantics decide whether the promised state
  is restored. Infrastructure/process existence alone is insufficient.

The platform can own recovery semantics without performing the concrete
recovery action. E4 and Kubernetes E5 directly support this.

### AP-S5-001 — Restart is not Recovery

Assessment: **SUPPORTED**.

Restarted candidate: the required infrastructure object or runtime process
exists again.

Recovered candidate: the desired normalized runtime semantics promised for
that binding have been re-established and verified.

E4 showed a new PID before API verification. E5 showed a running replacement
Pod before readiness. Checkpoint A showed runtime availability without usable
model/task execution.

## Condition model

| Candidate | Fact represented | Observed by | Semantic owner | Level | UNKNOWN? | Mandatory? | Candidate v0? |
|---|---|---|---|---|---|---|---|
| InfrastructureAvailable | Owned workload/resource exists and meets substrate availability | Substrate→Provider | Platform for managed mode | Infrastructure | Yes, especially external mode | Only managed realizations | Yes, conditional |
| RuntimeAvailable | Provider interaction/observation surface is reachable and runtime responds as expected | Provider/native probe | Platform normalized semantic | Runtime | Yes | Yes where interaction/observation promised | Yes |
| DependencyReady | Required runtime dependency is usable, not merely reported healthy | Provider-derived/native evidence | Platform vocabulary; Provider mapping | Dependency | Yes | Only when declared dependency exists | Yes, conditional |
| TaskReady | A task can realistically execute now | Invocation/execution layer | Execution semantics | Execution | Yes | No | No as core Runtime condition |

Attack result: the four-condition model should not survive unchanged.
`TaskReady` conflates runtime observation with execution outcome and was not
proven independently of an invocation. Candidate v0 should separate:

- Runtime observation: conditional InfrastructureAvailable, RuntimeAvailable,
  and declared DependencyReady conditions.
- Interaction/execution: normalized invocation outcome and errors.

Task readiness may later be derived by scheduling/execution policy, but it is
not a mandatory Runtime condition based on Hermes evidence.

Condition values need at least **TRUE / FALSE / UNKNOWN**. Missing model proof,
ambiguous native health, and external runtimes without visible infrastructure
cannot be represented honestly by boolean defaults. UNKNOWN is not FALSE and
must not silently imply READY.

## Agent Instance, Runtime Binding, Runtime Instance, realization

- Agent Instance candidate: platform logical running identity with lifecycle
  independent of any one runtime object (**INFERENCE**, not implemented).
- Runtime Binding candidate: versioned logical association selecting a Provider,
  runtime descriptor/package, mode, configuration/state/credential references,
  and observed realization (**INFERENCE supported by LIVE replacement evidence**).
- Runtime Instance candidate: Provider-recognized runtime identity to which
  lifecycle/interaction/observation apply. It may outlive a workload but its
  exact identity is Provider-specific (**INFERENCE**).
- Runtime Realization: concrete container, Pod, profile, gateway, or endpoint.

Workload replacement preserved the logical experimental binding and volume
while container/Pod/PID identities changed. Container, PID, and profile are
Provider/runtime identities, not universal Agent identities.

Runtime Binding assessment: **SUPPORTED CANDIDATE**. It prevents Core from
equating Agent Instance with replaceable/Hermes-specific realizations and gives
Provider/package/version/mode/status a logical join point. It becomes needless
indirection if a second runtime cannot distinguish binding from its single
runtime endpoint, so S5-SPIKE-002 must attack it.

Unknown cardinalities: Agent Instance↔Binding, Binding↔Runtime Instance,
Runtime Instance↔realizations, profile↔gateway, and shared runtime↔multiple
Agents.

## State boundary

| Classification | Hermes examples | Evidence |
|---|---|---|
| Runtime-local | `config.yaml`, gateway metadata, logs, skill copies | **LIVE** persistent volume inventory |
| Infrastructure-local | container/Pod identity, `emptyDir`, volume attachment | **LIVE** E5/E6 |
| Potential Agent-semantic | sessions, memories, possibly profile identity | Directories observed; semantics **UNKNOWN** |
| Credential/governance | injected API key; `.env` absent | **LIVE** mechanism-only observation |
| Unknown | portability, migration, shared profile/state ownership | Not tested |

Checkpoint B proved that `/opt/data` persistence preserves measured
runtime-local artifacts across workload replacement and fresh storage loses
prior artifacts. It did not prove Agent ownership, semantic completeness,
portability, cross-runtime compatibility, or migration.

Invariant candidate: `Persistent Runtime State != Agent-owned State != Portable
State`.

## Runtime Contract decomposition

| Component | Classification | Evidence/need | If omitted | S5-SPIKE-002 attack |
|---|---|---|---|---|
| Runtime Descriptor | REQUIRED | **INFERENCE** from Provider selection, identity and capability differences | Core cannot discover compatibility without runtime-specific branching | Can a different runtime declare enough without Hermes fields? |
| Runtime Package Metadata | MERGE WITH descriptor as a distinct versioned distribution section | **LIVE:** immutable image/digest, ports, storage, command; identity differs from distribution | Version/realization facts become untracked Provider code | Does non-container runtime need “package” metadata? |
| Lifecycle Semantics | REQUIRED, minimal | **LIVE:** desired availability separate from action owner | Core either embeds actions or cannot express managed outcome | Can non-supervised/external runtime use same desired semantics? |
| Runtime Provider Boundary | REQUIRED | **STATIC/LIVE:** Hermes isolation and layered recovery | Hermes paths/config/errors leak into Core | Can second Provider integrate with zero Core runtime branches? |
| Runtime Interaction Contract | OPTIONAL capability, REQUIRED when `invoke` declared | **LIVE:** generic request; HTTP 200 semantic failure | Callers depend on native APIs and misclassify results | Can different API/error/async model normalize minimally? |
| Runtime Observation Contract | REQUIRED | **LIVE:** distinct and ambiguous signals | READY/recovery become raw runtime booleans | Can different health model map to tri-state conditions? |
| Runtime Capability Declaration | REQUIRED | **LIVE/UNKNOWN:** recovery/state/interaction vary | Every Provider is forced into unsupported operations | Can missing features be declared without fake implementations? |
| Runtime Binding | REQUIRED candidate, subject to falsification | **LIVE/INFERENCE:** logical continuity across replaceable realization | Agent identity collapses into container/profile or scattered refs | Is binding useful without profiles or managed workload? |

The old universal imperative interface is **REJECTED AS CANDIDATE V0**. It
mixes platform semantics, Provider translation, substrate action, runtime-native
action, interaction, and observation; it also forces unsupported operations.

## Runtime Package recommendation

Recommendation: retain package/distribution metadata as a distinct versioned
section associated with the Runtime Descriptor, not as a standalone universal
resource yet.

Evidence: Hermes identity/version and Provider compatibility are conceptually
different from the immutable image digest, entrypoint, port, storage path,
health mechanism, and architecture. These facts were required for reproducible
experiments. However, only a container distribution was tested.

Candidate contents—not schema—include runtime/version identity, artifact/image
digest, Provider compatibility, deployment mode, native configuration/health
metadata, ports, storage requirements, architecture compatibility, and known
scaling/concurrency constraints.

Unknown: source/service/SaaS distributions, who publishes metadata, trust and
signature model, schema ownership, and whether S5-SPIKE-002 makes “package” an
incorrect term.

## Interaction Contract candidate

Must normalize when interaction capability is declared:

- request/input intent without native paths or profile concepts;
- correlation identifier propagated or mapped by Provider;
- semantic completion versus failure independent of transport status;
- transport, runtime-native, dependency, and execution/task error categories;
- result payload and completion status;
- observed latency and available usage metadata;
- cancellation/stream references only when declared.

Runtime-specific metadata may include native request/response identifiers,
session/profile references, native finish reasons, tool events, raw bounded
diagnostics, and capability-specific extensions. It must remain Provider-owned
and must not redefine normalized success.

ED-S5-001 limitation: successful result shape, usage fidelity, correlation
propagation through a real model, model errors after authentication, and
successful task semantics remain unproven.

## Observation Contract candidate

Minimum semantics:

- named normalized condition;
- TRUE/FALSE/UNKNOWN value;
- reason suitable for stable platform interpretation;
- bounded human-readable message;
- observation time;
- last known transition time when available;
- optional reference to sanitized native evidence;
- observed runtime/package/realization identity where known.

Candidate conditions are conditional InfrastructureAvailable,
RuntimeAvailable, and declared DependencyReady. Observation is evidence, not
the recovery action and not task success. “Recovered” is a platform projection
over the conditions promised by a particular binding/mode/capability set.

Unknown: freshness/staleness policy, condition vocabulary, aggregation rules,
high-frequency event boundary, and external-runtime infrastructure visibility.

## Managed versus External Runtime

Managed: platform participates in desired lifecycle semantics; Provider and
substrate/runtime realize and recover the owned resources. **SUPPORTED BY
HERMES EVIDENCE**.

External: platform binds/connects, authenticates, interacts, and observes but
does not own underlying workload lifecycle. **ARCHITECTURALLY PLAUSIBLE; NEEDS
S5-SPIKE-002**.

Shared semantics: descriptor/capabilities, binding, compatibility, interaction
when supported, observation, normalized errors, and ownership metadata.

Different responsibilities: InfrastructureAvailable may be UNKNOWN/not owned;
provision/recreate/delete/upgrade may be unsupported; external lifecycle and
recovery owners remain outside platform authority.

Assessment: one decomposed candidate can plausibly support modes through
ownership and capabilities; separate contracts are not yet justified.

## E10 — Runtime Contract Candidate v0

> **CANDIDATE · NOT FROZEN · HERMES-DERIVED**

### 1. Platform-owned semantics

- Logical binding identity and desired mode/lifecycle outcome.
- Minimal capability vocabulary and compatibility expectations.
- Normalized conditions with tri-state truth.
- Interaction success/error categories when interaction is declared.
- Resource ownership and semantic recovery criteria.

Evidence: **LIVE/STATIC/INFERENCE**, as identified above.

### 2. Mandatory Provider responsibilities

- Declare identity, compatibility, supported capabilities, constraints, and
  ownership mode.
- Realize or connect a binding without runtime-specific Core branches.
- Translate configuration, state/storage, credential references, interaction,
  and observations only where applicable.
- Classify native/transport/dependency/execution failures rather than trusting
  HTTP status.
- Observe and report UNKNOWN when evidence is insufficient.
- Respect ownership during cleanup/recreation.

### 3. Optional Provider capabilities

Managed provision/lifecycle, invoke, stream, cancel, native recovery,
workload recovery, persistent state, recreate, multiple instances, external
mode, horizontal scale, and upgrade. Unsupported capabilities are declared,
not implemented as misleading no-ops.

### 4. Runtime Descriptor candidate

Logical runtime identity, supported contract range, Provider compatibility,
deployment/ownership modes, declared capabilities, constraints, and reference
to versioned distribution metadata. No Hermes paths/profiles in Core.

### 5. Package/distribution metadata candidate

Versioned realization facts: upstream runtime version, immutable artifact,
platform architecture, startup/config/health mechanisms, ports, storage and
credential requirements, Provider version compatibility, and concurrency
constraints. Kept as a descriptor section until cross-runtime evidence proves
separate lifecycle/ownership.

### 6. Lifecycle semantics candidate

Express desired availability and ownership, plus convergence/cleanup intent,
without prescribing imperative provision/start/stop methods. Concrete actions
belong to Provider, substrate, or native runtime according to declared mode and
capabilities.

### 7. Interaction semantics candidate

Optional capability normalizing request intent, correlation, result,
completion/failure, error category, usage/latency when available, and optional
stream/cancel handles. Native payloads and extensions remain Provider metadata.

### 8. Observation semantics candidate

Tri-state normalized conditions with reason, bounded message, observation and
transition times, and optional sanitized native evidence. It separates
infrastructure, runtime, dependency, and execution outcome.

### 9. Binding/Instance candidate

Agent Instance is not equated to Runtime Instance. Runtime Binding is the
logical join between Agent Instance intent and Provider realization. Runtime
Instance/realization identity is Provider-specific and replaceable. Exact
cardinality is unknown.

### 10. Recovery semantics candidate

Platform owns desired semantic recovery criteria. Trigger, action, observation,
and verification are separate. The lowest appropriate declared owner performs
the action; Provider translates evidence; platform verifies promised semantics.

### 11. State boundary

Declare storage/persistence requirements and ownership references without
claiming runtime-local state is Agent-owned or portable. State migration and
State Contract are non-goals.

### 12. Compatibility/version boundary

Descriptor, Provider, distribution/package, and candidate Contract versions
must be distinguishable. Exact negotiation and compatibility policy require
cross-runtime evidence.

### 13. Explicit non-goals

- Final API/schema/SDK or frozen operation names.
- Agent Instance implementation.
- State portability or State Service.
- Capability Contract implementation.
- Universal Kubernetes/container assumption.
- Universal managed lifecycle, invocation, streaming, cancellation, scaling,
  upgrade, or recovery behavior.
- High-frequency task/event/telemetry contract.
- Hermes profiles/configuration in Core.

### 14. Unknowns

Successful real-model semantics, cross-runtime vocabulary, external mode,
async/long-running execution, cancellation/streaming, scale/cardinality,
upgrade, state migration, condition freshness, compatibility negotiation, and
governance details.

### 15. Falsification questions

The S5-SPIKE-002 plan below is part of Candidate v0. Any answer that requires
runtime-specific Core changes weakens or falsifies the candidate.

## Open-source extension test

Result: **SUPPORTED BY HERMES EVIDENCE, PARTIAL CROSS-RUNTIME**.

| Test | Candidate result |
|---|---|
| Core source modification required? | No for experimental Hermes; unproven for second runtime |
| Runtime-specific semantics leak into Core? | No Hermes paths/profiles/commands in generic boundary |
| Capability differences expressible? | Yes as candidate declarations; names not frozen |
| Package/version differences expressible? | Yes for Hermes artifact; other distribution forms untested |
| Health differences expressible? | Tri-state conditions and native evidence are plausible |
| Recovery differences expressible? | Yes: s6, Kubernetes, Provider action distinguished |
| Managed versus external differences expressible? | Plausible through mode/ownership/capabilities; external untested |
| Unsupported capabilities representable? | Yes as unsupported/absent declarations, not fake methods |

A third party could theoretically implement a Provider without modifying Core,
but only S5-SPIKE-002 can test whether the abstractions are genuinely
cross-runtime.

## S5-SPIKE-002 falsification plan

- **F01:** Can Provider isolation survive a materially different execution
  model without Core runtime branches?
- **F02:** Does Runtime Binding remain useful without Hermes profiles and with
  a different instance identity?
- **F03:** Can lifecycle semantics represent a runtime without native process
  supervision?
- **F04:** Can tri-state observation represent a different health model without
  inventing runtime-specific Core conditions?
- **F05:** Can interaction normalize a non-OpenAI, asynchronous, queued, or
  callback API?
- **F06:** Can capability declaration represent absent lifecycle/recovery
  features without meaningless no-ops?
- **F07:** Does the Managed Runtime definition survive different recovery
  ownership?
- **F08:** Does External Runtime use shared semantics with different ownership,
  or require a separate contract?
- **F09:** Are persistence requirements expressible without exposing native
  state schema or implying portability?
- **F10:** Can integration complete with zero runtime-specific Core source
  changes?
- **F11:** Is package/distribution metadata meaningful for a service, binary,
  serverless function, or source-deployed runtime?
- **F12:** Does separating TaskReady from Runtime conditions hold for runtimes
  with a native task queue/readiness concept?
- **F13:** Can semantic success/error be normalized when transport and execution
  are asynchronous or multi-stage?
- **F14:** Can recovery verification work when infrastructure is opaque?
- **F15:** Are Runtime Descriptor and Binding genuinely distinct, or unnecessary
  indirection for the second runtime?

This plan does not choose or start the second runtime.

## ADR impact analysis — no edits

### ADR-0003

Current statement: the Operator owns Agent infrastructure reconciliation and
uses a Runtime Adapter boundary; current implementation is partial/drifted.

Evidence: supports idempotent desired semantics and Provider isolation, but
clarifies that native process recovery and Kubernetes workload recovery should
not be reimplemented or attributed to the Control Plane. Task/execution
semantics remain outside infrastructure reconciliation.

Disposition candidate: **CLARIFY** recovery action versus semantic verification
and avoid equating Agent readiness with Deployment readiness.

### ADR-0004

Current statement: pluggable runtime architecture, managed/remote/external
modes, conceptual resolve/provision/update/delete/observe adapter operations.

Evidence: strongly supports pluggability, modes, configuration isolation, and
observe. Challenges one universal imperative adapter interface and Agent-level
provision mapping. Supports descriptor/capability/interaction/observation
decomposition and logical binding as candidates.

Disposition candidate: **AMEND** eventually, after S5-SPIKE-002 and human
contract decision; do not edit now.

### ADR-0005

Current statement: platform model abstraction/gateway is preferred, while
heterogeneous runtimes may use native model clients with reduced visibility.

Evidence: Hermes native model health falsely reported OK without a configured
provider, and invocation encoded provider failure in HTTP 200. This supports
separate dependency observation and normalized Provider error interpretation;
it also demonstrates reduced governance visibility for runtime-local model
access.

Disposition candidate: **KEEP**, likely **CLARIFY** the runtime/Model Plane
health and error boundary after cross-runtime evidence.

## Hermes hypothesis final state

- H1 Provider Isolation: **PASS**.
- H2 Managed Lifecycle: **PARTIAL**, sufficient for candidate synthesis.
- H3 Unified Invocation: **PARTIAL**; ED-S5-001 remains open.
- H4 Health Mapping: **PARTIAL/CHALLENGED**; infrastructure/runtime observable,
  dependency/execution ambiguous.
- H5 Responsibility Separation: **PASS**.
- H6 READY Semantic: **CHALLENGED**; replace raw READY with promised-condition
  projection.

## Consolidated rejected assumptions

- Container running, Pod Ready, gateway running, API reachable, dependency
  usable, and task success are equivalent.
- HTTP 200 invocation proves semantic success.
- Native detailed health proves model usability.
- Control Plane must perform every recovery action.
- Restart implies semantic recovery.
- Workload replacement automatically restores prior state.
- Runtime-local persistence proves Agent ownership or portability.
- Agent Instance universally equals container, profile, gateway, or Pod.
- Every Provider must implement one large imperative Runtime interface.
- Boolean health can honestly represent every observation.
- All runtime capabilities are mandatory or intrinsic rather than declared and
  sometimes substrate-dependent.

## Evidence debt, risks, and open questions

ED-S5-001 remains **OPEN**. It must close before S5-SPIKE-001 final and does not
invalidate lifecycle/state evidence.

Primary risks are Hermes overfitting, capability vocabulary becoming a second
large interface, Provider error classifiers depending on unstable native text,
runtime-local state being misrepresented as portable state, shared-profile
security/resource coupling, and untested scale/external behavior.

Open questions include the minimum cross-runtime condition vocabulary,
successful-result/error semantics, compatibility negotiation, binding
cardinality, external ownership, condition freshness, async interaction,
upgrade/migration, state ownership, horizontal scale, and third-party Provider
conformance/testing.
