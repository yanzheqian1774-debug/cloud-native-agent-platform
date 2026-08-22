# S5-ARCH-003 — v0.2 Core Contract Convergence Review v1

SESSION

ID: S5-ARCH-003
TITLE: v0.2 Core Contract Convergence Review
PHASE: S5 / v0.2 CONNECT & MANAGE
TRACK: Core Architecture
MODE: Architecture / Convergence
LIFECYCLE: REVIEW
AUTHORIZATION: AUTHORIZED
STATUS: PASS
CHECKPOINT: ARCHITECTURE_CONVERGENCE

RESULT: **ARCHITECTURE_CONVERGENCE_RECOMMENDED**

> Architecture recommendation only. Human Architecture Final Gate decision is
> pending. No Contract, schema, CRD, ADR, or production implementation is
> created, changed, or frozen by this artifact.

## 1. Executive Architecture Conclusion

The S5-ARCH-002, S5-SPIKE-003, and S5-SPIKE-004 evidence forms a coherent
v0.2 Agent Control Plane semantic model without changing the Shared Semantic
Baseline.

The smallest stable Core surface should own:

- logical Agent Definition and Agent Instance identity;
- desired state and domain Binding identity;
- provider-independent Provider References and resolution decisions;
- logical Agent Instance routing;
- one platform Execution Identity for one logical execution of requested work;
- minimal cross-domain execution primitives for correlation, acceptance,
  terminality, normalized result category, and bounded diagnostics;
- normalized Condition primitives while leaving condition types and recovery
  predicates domain-owned;
- normalized Outcome primitives while leaving Runtime, Capability, Task, and
  Workflow outcome meaning domain-owned;
- recovery intent, required semantic predicates, and the final Control Plane
  recovery assessment.

Replaceable Providers should own validation, translation, native interaction,
observation, error interpretation, and supported native reconciliation.
Runtime/native systems should own execution mechanics, native identities,
protocols, state formats, and native supervision.

Recommendations are `ACCEPT_RECOMMENDED` for D30, D31, D33, D34, D35, and
D36. D32 recommends **Option C**: share only minimal Control Plane execution
primitives; do not create a universal Shared Execution Contract or merge the
Runtime and Capability Contracts.

No new Spike blocks architecture convergence. Focused evidence remains
required before Contract freeze, Provider certification, or production
readiness. `G-S5-RUNTIME-FREEZE-01` remains unchanged and `FAIL`.

## 2. Evidence Inputs

Authoritative and accepted inputs:

- S5-ARCH-002, `CLOSED / PASS`: D22–D29 and AP-S5-005–AP-S5-009;
- Runtime Provider Architecture v1 and Runtime Contract Candidate v1.1,
  accepted as architecture baseline and **NOT FROZEN**;
- S5-SPIKE-003, `CLOSED / PASS`: H-CAP-01, Capability Contract Candidate v0,
  shared execution candidate, Provider isolation, explicit pre-invocation
  denial, inline/deferred outcomes, and normalized failures;
- S5-SPIKE-004, `CLOSED / PASS`: H-INS-01–H-INS-05, logical routing,
  realization replacement, shared Gateway topology, and semantic recovery;
- current source and tests: current production resources remain Agent, Task,
  and Workflow; Agent Instance, Bindings, Provider registries, and stable
  Runtime/Capability Contracts are not implemented;
- accepted ADR-0003, ADR-0004, and ADR-0005, each partially implemented and
  carrying recorded architecture drift or future architecture intent.

Evidence limitations are preserved rather than converted into architecture
claims: no successful combined Runtime-Provider-plus-Capability-Provider path,
no durable deferred Capability proof, no state portability proof, no
out-of-process Provider proof, and no production Agent Instance schema.

## 3. Proposed v0.2 Core Semantic Model

```text
LOGICAL OBJECTS

  Agent Definition 1 -------- N Agent Instance
          |                         |
          | declares                | has Desired State
          |                         | and logical lifecycle
          |                         |
          +---- Capability Binding  +---- Runtime Binding
          +---- Model Binding       |        |
                                    |        v
  Workflow 1 ---- N Task            |   Runtime Provider Reference
                       |             |        |
                       +--- creates/coordinates --- Execution
                                                   |
                                                   | logical routing selects
                                                   v
                                            Agent Instance
                                                   |
                                                   | selected Binding translated by
                                                   v
                                                Provider
                                                   |
                                                   v
                                      opaque native realization(s)

  Capability Binding -> Capability Provider Reference -> Capability Provider
  Model Binding      -> Model Provider Reference      -> Model Provider

  Desired State -> domain reconciliation -> domain Conditions
  Execution      -> domain interaction    -> Normalized Outcome
```

Classification:

| Class | Semantics |
| --- | --- |
| Logical Object | Agent Definition, Agent Instance, Task, Workflow, Execution |
| Binding | Runtime Binding, Capability Binding, Model Binding |
| Provider | Registry-resolved, domain-specific adapter behind a Contract |
| Native Realization | Opaque Provider/runtime-owned target; not a universal platform resource |
| Execution | One logical execution of requested work, correlated across routing and Provider boundaries |

An Agent Definition describes logical Agent intent. An Agent Instance is the
platform-managed logical running identity created from one Definition version.
A Task represents requested work and lifecycle; a Workflow coordinates Task or
node lifecycle. An Execution represents one logical performance of requested
work and may be initiated by a Task or Workflow node. This does not change the
current Task or Workflow contracts.

Bindings associate platform semantics with domain-specific desired
configuration and Provider-selection intent. A Binding is not a generic bag,
Provider instance, permission grant, or native realization.

## 4. Cross-Cutting Ownership Matrix

`Persistence Owner` identifies the authoritative persistence domain, not a
required new database or CRD. Kubernetes remains the current Control Plane
source of truth.

| Semantic | Semantic Owner | Lifecycle Owner | Persistence Owner | Translation Owner | Native Owner |
| --- | --- | --- | --- | --- | --- |
| Agent Definition | Control Plane | Domain Control Plane | Control Plane | Provider for domain-specific realization inputs | Runtime / Native System for consumed native form |
| Agent Instance | Control Plane | Domain Control Plane | Control Plane | Runtime Provider after Instance selection | Runtime / Native System owns realization, not Instance |
| Runtime Binding | Domain Control Plane | Domain Control Plane | Control Plane | Runtime Provider | Runtime / Native System |
| Capability Binding | Domain Control Plane | Domain Control Plane | Control Plane | Capability Provider | Runtime / Native System or external capability system |
| Model Binding | Domain Control Plane | Domain Control Plane | Control Plane | Model Provider / gateway adapter | Model native system |
| Execution Identity | Control Plane | Task / Workflow Layer | Control Plane | Providers propagate; never replace | Native IDs remain subordinate |
| Desired State | Domain Control Plane | Domain Control Plane | Control Plane | Provider for native desired form | Infrastructure / Kubernetes or Runtime / Native System acts |
| Condition | Domain Control Plane | Domain reconciler | Control Plane status | Provider normalizes native evidence | Native system emits evidence only |
| Normalized Outcome | Owning execution domain | Task / Workflow Layer or domain interaction owner | Owning Control Plane domain | Provider normalizes native result | Native system owns raw result |
| Logical Routing | Control Plane | Domain Control Plane | Control Plane policy/configuration | Runtime Provider translates selected Binding | Runtime chooses native target only within selected Binding |
| Recovery | Control Plane owns promised semantic assessment | Domain Control Plane coordinates | Control Plane condition/event history; exact schema UNRESOLVED | Provider acts/observes within declared ownership | Infrastructure / Kubernetes and native system perform lowest-level actions |
| Provider Registry | Domain Control Plane | Domain Control Plane | Domain-specific registry metadata | Not applicable; registry resolves | Provider supplies descriptors/evidence |
| Compatibility | Domain Control Plane | Domain Control Plane | Domain registry/conformance records | Provider validates native facts | Native system supplies version/platform facts |
| Credential Projection | Policy Layer owns reference/governance | Policy Layer | Secret system; never status | Provider projects reference | Native system resolves/consumes |
| Policy / Authorization | Policy Layer | Policy Layer | Policy system / Control Plane references | Provider enforces only delegated native controls | Native system cannot expand authority |
| Native Realization | Provider semantics are opaque to Core | Provider or declared external owner | Runtime / Native System; bounded refs in Control Plane | Provider | Runtime / Native System or Infrastructure / Kubernetes |

Unresolved details include Binding cardinality during migration, the exact
Execution persistence schema, recovery history representation, and registry
storage mechanics. These ambiguities do not change semantic ownership.

## 5. D30 — Agent Instance as Core Semantic

**Recommendation: ACCEPT_RECOMMENDED.**

Agent Instance should be a formal stable v0.2 Control Plane semantic, subject
to Human Gate approval, because heterogeneous routing and recovery cannot be
expressed faithfully with Agent Definition or native realization identity
alone.

- identity owner: Control Plane;
- lifecycle owner: Agent Instance domain reconciler;
- Definition-to-Instance: `1:N`;
- Instance-to-realization over time: `1:N`;
- active realization cardinality: zero, one, or many, Provider-dependent;
- Runtime Binding: identifies desired runtime association for the Instance;
- Desired State: declares the logical lifecycle intent, not a native action;
- routing: selects an eligible logical Instance before Provider translation;
- recovery: preserves Instance identity and verifies its promised semantics
  after native change.

The minimal semantic is identity, exact Definition reference, desired
lifecycle, current Binding reference(s), and normalized domain conditions.
Tenancy, schema shape, deletion, rollout history, and multi-Binding behavior
remain for schema planning.

Explicit rejections:

```text
Agent Instance != Pod
Agent Instance != Runtime process
Agent Instance != Gateway
Agent Instance != Provider-native session
```

This introduces deliberate logical state, not duplicate native state. The
counterexample is a shared Gateway: multiple Instances share one native
Gateway yet remain independently routable. The converse counterexample is
replacement: one Instance survives multiple native realizations.

Planning tension: ROADMAP.md places broad Agent Instance lifecycle capability
in v0.3, while this authorized v0.2 review finds a minimal Instance semantic
necessary for multi-runtime routing and recovery. The recommendation is only
the minimal Control Plane contract foundation, not the v0.3 Factory, Catalog,
or full lifecycle product experience. Human approval should record this scope
clarification before implementation.

## 6. D31 — Platform Execution Identity

**Recommendation: ACCEPT_RECOMMENDED.**

One Execution Identity identifies **one logical execution of requested work**.
It is created before routing or Provider invocation and is stable across:

- logical Agent Instance selection;
- Runtime Binding and Runtime Provider translation;
- Capability Provider invocation;
- inline or deferred completion;
- native realization replacement;
- transport-level retries or Provider-native request/run IDs that remain part
  of the same logical execution.

It does not identify an Agent Instance, Task, Workflow, Provider request,
Capability definition, or native realization.

Use a minimal hierarchy rather than new identity types:

- a Task or Workflow node owns/initiates an Execution;
- `executionId` identifies the logical execution;
- `attempt` is a subordinate ordinal/record under that Execution, not another
  peer identity type;
- Provider-native request/run IDs are opaque correlation references under the
  relevant attempt;
- a Capability invocation that is part of the same logical work correlates to
  the Execution and uses domain-local invocation/operation context;
- true fan-out or independently retryable child work creates child Executions
  with an optional `parentExecutionId`, rather than overloading attempts.

A Task may therefore have one or more Executions across explicit re-execution,
while retries that preserve the same logical intent remain attempts of one
Execution. Exact replay/idempotency rules remain Contract-freeze debt.

This boundary avoids overlap with Task identity: Task is a durable work/lifecycle
object; Execution is a correlated performance of that work.

## 7. D32 — Shared Execution Semantics

**Recommendation: ACCEPT_RECOMMENDED — OPTION C.**

Share only minimal Control Plane primitives. Runtime Interaction and Capability
Invocation retain domain-specific Contracts and lifecycle meaning.

Smallest useful shared surface:

| Primitive | Shared meaning |
| --- | --- |
| Execution reference | Platform Execution Identity plus optional parent and attempt context |
| Correlation context | Bounded propagation metadata; native IDs remain opaque |
| Submission disposition | rejected before handoff, or accepted by responsible Provider/domain |
| Completion disposition | inline terminal result or deferred observation reference |
| Terminality | terminal versus non-terminal, without universal progress states |
| Result category | success, failure, cancelled, timeout, or unknown candidate families; vocabulary not frozen |
| Error/diagnostic shape | stable reason category, bounded safe message, optional opaque evidence reference |

Do not share business payloads, authorization meaning, Runtime availability,
Capability input/output schema, Provider handles, retry policy, cancellation
semantics, streaming, progress, or domain outcomes.

Option A is rejected for now because it would couple Runtime and Capability
versioning and prematurely imply identical lifecycles. Option B is rejected
because duplicated identity, correlation, terminality, and bounded-error rules
would create avoidable inconsistency for Workflow integration. Option C
preserves the proven common core without producing a universal abstraction.

No Production Contract or schema is created here.

## 8. D33 — Binding + Provider Pattern

**Recommendation: ACCEPT_RECOMMENDED.**

Adopt this as a cross-domain ownership pattern:

```text
Platform Semantic
  -> domain Binding
    -> domain Provider resolution
      -> domain Provider
        -> native system
```

Common architecture-level rules:

- platform semantic identity is independent from Provider identity;
- Binding identity and desired portable configuration are domain-owned;
- `providerRef` or selection constraints are explicit and version-aware;
- compatibility is evaluated, not assumed;
- `credentialRef` and `policyRef` remain references to governance-owned data;
- Provider-native configuration remains opaque/bounded and Provider-translated;
- status uses normalized domain conditions, never raw Provider status;
- Provider replacement cannot redefine platform semantics or bypass policy.

Bindings are not schema-identical. Runtime Binding owns realization/lifecycle
association; Capability Binding owns semantic use/operation association;
Model Binding owns governed model-selection association. A generic Binding
base schema is not recommended without further evidence.

Use **domain-specific registries sharing a common architectural pattern**, not
one universal registry. Each registry resolves its domain Contract,
compatibility dimensions, Provider metadata, and policy eligibility. A
universal registry would become a service locator and erase meaningful domain
differences.

Future Workspace, Knowledge, and State domains may adopt the pattern only
after evidence proves a replaceable Provider boundary; this decision does not
pre-authorize them.

## 9. D34 — Logical Routing Ownership

**Recommendation: ACCEPT_RECOMMENDED.**

The Platform Control Plane owns selection of the logical Agent Instance. The
Runtime Provider receives a Binding already associated with that Instance and
translates it to native target semantics.

Control Plane selection inputs may include desired replicas, Instance desired
state, normalized eligibility/health conditions, explicit Instance target,
policy/authorization, and routing policy. Native realization identity is not a
caller-visible selector.

The Runtime Provider may choose among multiple native realizations only within
the already selected Binding. A shared Gateway does not become the logical
router. Explicit Instance targeting remains subject to authorization and must
not bypass eligibility or policy.

Future load balancing may change selection strategy but not semantic
ownership. No scheduling or load-balancing algorithm is proposed.

## 10. D35 — Recovery Semantics

**Recommendation: ACCEPT_RECOMMENDED.**

Recovery means restoration **and verification** of promised platform
semantics. It is not native restart, recreation, or transport retry.

| Layer | Owner | Meaning |
| --- | --- | --- |
| Process Supervision | Infrastructure / Kubernetes or Runtime / Native System | Maintain/restart native processes and workloads |
| Runtime Reconciliation | Runtime Provider within declared ownership | Reconcile/observe Binding against native runtime semantics |
| Agent Instance Reconciliation | Agent Control Plane | Detect divergence and assess whether the same logical Instance satisfies required semantics |
| Execution Retry | Task / Workflow Layer | Start another attempt under policy while preserving or changing logical Execution according to replay semantics |
| Execution Recovery | Task / Workflow Layer with domain evidence | Decide whether in-flight work resumed, restarted, failed, or became unknown |

Recovery verification is predicate-based and scoped. Depending on the Instance
class, it may require:

- desired-state convergence;
- required Instance and Runtime conditions;
- Binding and Provider-resolution verification;
- logical routing verification;
- declared Model, Capability, Workspace, and Policy binding verification;
- state verification only where continuity was explicitly promised;
- execution verification only for in-flight work whose contract promises it.

The Control Plane defines required predicates and owns the final Agent Instance
recovery assessment. Providers perform supported native actions and normalize
evidence. Kubernetes/native systems own lowest-level action. Task/Workflow
owns retry and in-flight execution disposition.

No state portability is inferred. External/observe-only Runtimes may support
observation and assessment without platform-initiated recovery.

## 11. D36 — Condition / Outcome Ownership

**Recommendation: ACCEPT_RECOMMENDED.**

Do not create one universal Status object.

| Semantic | Owner | Shared primitive | Domain-specific meaning |
| --- | --- | --- | --- |
| Runtime Condition | Runtime domain Control Plane, Provider-normalized | type, truth value, reason, message, observed time/generation | availability, configuration, binding, infrastructure applicability |
| Agent Instance Condition | Agent Instance Control Plane | same condition shape | bound, eligible, available, recovered/degraded candidates |
| Execution Outcome | Execution-owning Task/Workflow domain | terminality, category, reason, safe diagnostics | logical work completion and attempt aggregation |
| Capability Outcome | Capability domain, Provider-normalized | outcome envelope | business output contract and Capability-specific failure |
| Task Outcome | Task / Workflow Layer | outcome envelope | Task phase/result/retry exhaustion |
| Workflow Outcome | Task / Workflow Layer | outcome envelope | DAG/node aggregation, failure, skip semantics |

Condition truth values may share `TRUE`, `FALSE`, `UNKNOWN`, and
`NOT_APPLICABLE` candidates. Condition types remain domain-owned. `TaskReady`
is not a Runtime condition.

Normalized Outcome may share terminality, broad category, stable reason,
bounded message, time, retryability when safely knowable, and opaque diagnostic
reference. Domain payloads and detailed failure taxonomies remain separate so
normalization does not erase meaning.

Recovery is a combination:

1. a reconciliation result for one assessment attempt;
2. an event/record of actions and observed evidence;
3. a derived Agent Instance Condition when recovery state must remain
   observable over time;
4. an Execution Outcome only when the subject is an execution.

`RECOVERED`, `NOT_RECOVERED`, and `RECOVERY_UNKNOWN` remain useful spike-local
result candidates and are not frozen vocabulary.

## 12. AP-S5-001 — Restart is not Recovery

**Disposition recommendation: ACCEPT_RECOMMENDED.**

Strong cross-runtime and Instance evidence falsified restart as sufficient for
recovery. Preserve the layering and require semantic verification. Do not
ADR-freeze the wording in this session.

## 13. AP-S5-010 — Logical Routing Ownership

**Disposition recommendation: ACCEPT_RECOMMENDED.**

The principle works for dedicated realization, shared Gateway, replacement,
and multiple Instances without leaking native topology into Core routing.

## 14. AP-S5-011 — Platform Execution Identity

**Disposition recommendation: ACCEPT_RECOMMENDED.**

The principle is strongly supported across routing, Runtime translation,
Capability invocation, deferred outcomes, failure, and recovery. The precise
identity meaning is narrowed by D31 to one logical execution. Combined
Runtime/Capability propagation remains Contract-freeze evidence debt.

## 15. Runtime / Capability Semantic Comparison

| Concern | Runtime Interaction | Capability Invocation | Shared? |
| --- | --- | --- | --- |
| Primary question | How is Agent execution carried? | What business capability is invoked? | No |
| Identity | Runtime Binding/Provider/Package context | Capability identity/version/operation | No |
| Authorization | Runtime eligibility/ownership/policy | Explicit per-invocation authorization | Only common policy precedence |
| Submission | Provider handoff | Provider handoff after authorization | Minimal disposition only |
| Deferred work | Optional Runtime correlation | Optional Capability observation | Minimal correlation/terminality only |
| Availability | Runtime conditions | Provider feasibility is not Capability success | No |
| Outcome | Runtime interaction result | Contract-conforming business result | Envelope shape only |
| Failure taxonomy | Runtime/config/transport/native execution | policy/input/protocol/business execution | Broad category/diagnostic shape only |
| Lifecycle | Runtime realization and reconciliation | operation invocation | No |
| Versioning | Runtime Contract + Provider + Package | Capability Contract + Capability version + Provider | No |

The serious counterexample to a universal envelope is an authorized Capability
call denied before Provider handoff versus an unavailable Runtime that cannot
accept interaction: both are failures, but ownership, retry safety, audit, and
business meaning differ.

## 16. Binding / Provider Architecture Comparison

| Concern | Runtime | Capability | Model |
| --- | --- | --- | --- |
| Platform semantic | Agent Instance runtime association | Enterprise Capability use | Governed model requirements |
| Binding owns | desired runtime/package/mode/config refs | Capability/version/operation and use constraints | model requirements/policy association |
| Provider owns | realization, native lifecycle/config/observation | native endpoint/tool invocation and result interpretation | provider protocol/inference translation |
| Compatibility focus | Platform/Contract/Provider/Package/mode/platform | Contract/Capability version/Provider/operation | Contract/provider/model/capabilities/policy |
| Registry | Runtime-specific | Capability-specific | Model-specific |
| Native object | process, Pod, Gateway, session, service | REST endpoint, MCP tool, enterprise system operation | model endpoint/deployment/request |

The pattern is stable at ownership and resolution level. Identical schemas,
cardinality, lifecycle, and registries are not supported by evidence.

## 17. Extension Architecture Assessment

| Claim | Assessment | Evidence |
| --- | --- | --- |
| Provider can replace implementation but cannot replace platform semantics | **SUPPORTED** | REST/MCP replacement and heterogeneous Runtime adaptation preserve semantic identity |
| Extension can extend capability but cannot bypass platform governance | **SUPPORTED** | explicit Capability denial before Provider invocation; registry/policy eligibility direction |
| Stable Contracts | **PARTIALLY_SUPPORTED** | coherent candidates exist; none are frozen and conformance gaps remain |
| Pluggable Providers | **SUPPORTED** at architecture boundary | Runtime and Capability Providers remain isolated; production SDK/loading remains unimplemented |
| Governed Extensions | **PARTIALLY_SUPPORTED** | ownership, registry, compatibility, authorization, and certification model exist; production governance and supply-chain controls remain debt |

Runtime Provider and Capability Provider do not duplicate responsibilities.
The first adapts execution carrier/lifecycle; the second adapts enterprise
Capability invocation. A Runtime may internally call tools, but this does not
transfer platform Capability identity or authorization ownership to the Runtime
Provider.

## 18. Product Semantic Sanity Check

The model supports the bounded product chain:

```text
Digital Employee          business/product concept
  -> Agent Definition     managed technical definition
    -> Agent Instance     logical running identity
      -> Work/Execution   correlated performance of requested work
        -> Capability     governed business ability
          -> Runtime      execution carrier
```

- **PE-01 Business / Technical Semantic Separation: PASS.** Digital Employee
  is not a Pod, process, Runtime, Agent Instance, or single execution.
- **PE-02 Progressive Disclosure: PASS.** Product users may reason from Digital
  Employee and work; operators may inspect Bindings, Providers, and native
  evidence without exposing those details as business identity.
- **PE-03 No Architecture Fiction: PASS WITH DISCLOSURE.** The semantic model
  is proposed architecture. Current production implements Agent, Task,
  Workflow, Operator, and Native Runtime only; the new semantics are not
  presented as current.

No product contradiction was found.

## 19. Evidence Debt Classification

| Evidence debt | Classification | Rationale |
| --- | --- | --- |
| ED-S5-001 Hermes Provider Certification Debt | BLOCKS_PROVIDER_CERTIFICATION; BLOCKS_PRODUCTION_READINESS for Hermes | successful certified Hermes path absent |
| unchanged-consumer Contract Conformance gap | BLOCKS_CONTRACT_FREEZE; BLOCKS_PROVIDER_CERTIFICATION | generic consumer not proven unchanged across Providers |
| third-party MCP evidence | BLOCKS_PROVIDER_CERTIFICATION for that MCP Provider; BLOCKS_PRODUCTION_READINESS for claimed MCP support | local deterministic server is insufficient certification evidence |
| long-running Capability | BLOCKS_CONTRACT_FREEZE if long-running is included; otherwise DEFERRED_BEYOND_V0_2 | lifecycle/durability unproven |
| side-effecting Capability | BLOCKS_CONTRACT_FREEZE for retry/idempotency claims; BLOCKS_PRODUCTION_READINESS for such operations | replay safety unproven |
| deferred outcome durability | BLOCKS_CONTRACT_FREEZE for deferred profile; BLOCKS_PROVIDER_CERTIFICATION; BLOCKS_PRODUCTION_READINESS | process-restart durability unproven |
| Runtime/Capability combined execution correlation | BLOCKS_CONTRACT_FREEZE | AP-S5-011 architecture converges, combined conformance does not |
| Binding cardinality | BLOCKS_CONTRACT_FREEZE | migration/rollout/current-history rules affect schema |
| routing eligibility | BLOCKS_CONTRACT_FREEZE; BLOCKS_PRODUCTION_READINESS | minimum normalized inputs and staleness rules required |
| explicit targeting authorization | BLOCKS_PRODUCTION_READINESS | semantic ownership is clear; exposed authorization policy is not |
| multi-realization selection | BLOCKS_PROVIDER_CERTIFICATION for Providers claiming it; BLOCKS_PRODUCTION_READINESS | Provider-local policy and failure behavior unproven |
| UNKNOWN-state timeout | BLOCKS_CONTRACT_FREEZE; BLOCKS_PRODUCTION_READINESS | escalation/terminal transition owner is unresolved |
| in-flight execution during recovery | BLOCKS_CONTRACT_FREEZE; BLOCKS_PRODUCTION_READINESS | execution disposition and retry safety unresolved |
| stateful/external Runtime recovery | BLOCKS_PROVIDER_CERTIFICATION; BLOCKS_PRODUCTION_READINESS | no portability claim; ownership-mode evidence required |
| out-of-process Provider deployment | BLOCKS_PRODUCTION_READINESS for third-party isolation; DEFERRED_BEYOND_V0_2 as mandatory deployment mode | architecture-compatible direction remains unproven |
| upgrade | DEFERRED_BEYOND_V0_2; BLOCKS_PROVIDER_CERTIFICATION when claimed | not universal v0.2 semantic |
| scale | BLOCKS_PROVIDER_CERTIFICATION when claimed; basic manual scale SHOULD evidence | not universal Provider capability |
| cancellation | DEFERRED_BEYOND_V0_2; BLOCKS_PROVIDER_CERTIFICATION when claimed | not required in minimal Contract |
| streaming | DEFERRED_BEYOND_V0_2; BLOCKS_PROVIDER_CERTIFICATION when claimed | not required in minimal Contract |
| state portability | DEFERRED_BEYOND_V0_2; BLOCKS_PRODUCTION_READINESS before any portability claim | no supporting evidence |

No listed debt blocks architecture convergence. Debt blocks only the relevant
Contract profile, Provider claim, or production capability; unsupported
optional behavior must be declared honestly rather than delaying the minimal
architecture.

## 20. Runtime Freeze Gate Analysis

`G-S5-RUNTIME-FREEZE-01`: **UNCHANGED / FAIL**.

| Question | Blocks? | Reason |
| --- | --- | --- |
| A. Core architecture convergence | **No** | accepted evidence is sufficient to assign semantics and ownership without certification |
| B. Runtime Contract schema drafting | **No** | drafting is how unresolved vocabulary and compatibility rules become reviewable; draft must remain unfrozen and non-production |
| C. Runtime Contract freeze | **Yes** | the unchanged gate explicitly remains failed and required conformance/evidence is incomplete |
| D. Runtime Provider certification | **Yes** | certification requires a versioned Contract/conformance baseline and combination-scoped live evidence |
| E. Production implementation | **Yes, for stable Contract-dependent Runtime/Provider implementation** | production cannot claim the unfrozen Contract or certified compatibility; bounded experiments remain possible only under separate authorization |

Architecture convergence is not Runtime certification. This session does not
adopt the previously proposed Gate Amendment.

## 21. ADR Disposition Recommendations

| ADR | Recommendation | Rationale |
| --- | --- | --- |
| ADR-0003 Operator responsibilities | **CLARIFY_LATER** | retain reconciliation and Kubernetes ownership principles; clarify separation among infrastructure, Runtime, Instance, and Task/Workflow reconciliation and address already recorded controller drift |
| ADR-0004 Runtime abstraction | **AMEND_LATER** | preserve pluggability and managed/remote/external ownership, but update `Agent.runtimeClass -> Resolver -> Adapter` toward `Agent Instance -> Runtime Binding -> domain Registry -> Runtime Provider -> opaque realization`; do not amend before Human Gate |
| ADR-0005 Model abstraction | **CLARIFY_LATER** | Provider/policy/gateway direction aligns with domain Binding + Provider pattern; later clarify Model Binding, domain registry, and execution correlation without prematurely redesigning Model architecture |

No ADR is edited or superseded in this session.

## 22. v0.2 MUST / SHOULD / DEFER Scope

These classifications describe the minimum architecture/contract planning
scope after Human approval, not implementation authorization.

| Capability | v0.2 | Boundary |
| --- | --- | --- |
| Agent Definition | MUST | preserve logical definition semantics; no Factory/Catalog expansion |
| Agent Instance | MUST | minimal identity, desired lifecycle, Binding and condition semantics |
| Runtime Binding | MUST | domain-specific, Provider/package/mode/config references |
| Runtime Provider Registry | MUST | deterministic metadata-backed resolution; no new service/database |
| Capability | MUST | provider-independent identity/version/input/output meaning |
| Capability Binding | MUST | Definition association, operation/use constraints, Provider intent |
| Capability Provider | MUST | REST/MCP-capable replaceable boundary |
| Execution Identity | MUST | one logical execution, propagated end to end |
| Logical Routing | MUST | Instance selection ownership and basic eligibility semantics |
| Managed Runtime lifecycle | MUST | bounded lifecycle profile; unsupported operations explicit |
| Condition normalization | MUST | shared shape/truth primitives, domain condition types |
| Recovery semantics | MUST | layered ownership and semantic verification |
| Manual replica/basic scaling | SHOULD | only for Providers declaring support; no autoscaling/scheduler |
| Capability authorization | MUST | explicit authorization before Provider invocation |
| Capability Registry | SHOULD | minimal metadata/discovery/resolution foundation, not marketplace |
| Model Binding thin foundation | SHOULD | references and ownership only; no full Model Plane rebuild |
| Workspace thin foundation | SHOULD | opaque reference/ownership/continuity only; no portability claim |
| Human Feedback thin foundation | DEFER | no convergence evidence; avoid v0.3/v0.4 expansion |
| Observability | MUST | Execution correlation, normalized conditions/outcomes, safe diagnostics |
| Provider certification framework | MUST | separate conformance and combination-scoped certification planning |

## 23. Contradictions and Falsification Results

No `ARCHITECTURE_BASELINE_CHANGE_CANDIDATE`, accepted-architecture conflict,
or blocking architecture contradiction was found.

Serious challenges and results:

| Challenge | Result |
| --- | --- |
| Agent Instance duplicates native state | Falsified by shared Gateway and realization replacement; it owns logical identity only |
| Execution Identity overlaps Task identity | Avoided by defining Task as work/lifecycle object and Execution as one performance of that work |
| Shared envelope over-generalizes | Valid concern; Option A rejected and Option C bounded to primitives |
| Binding becomes empty generic abstraction | Avoided by domain-specific meaning and schemas; only ownership pattern is shared |
| Provider Registry becomes service locator | Avoided by domain registries, declarative metadata, deterministic resolution, and Contract-only consumption |
| Logical routing belongs to Provider | Falsified: Provider selection among platform Instances leaks semantics; Provider selects only within selected Binding |
| Recovery conflicts with Kubernetes | Avoided by separating native supervision from semantic reconciliation |
| Capability Provider duplicates Runtime Provider | Falsified by business-Capability versus execution-carrier ownership |
| Normalized Outcome erases semantics | Valid risk; share envelope primitives only and retain domain payload/taxonomy |
| Dedicated and shared Gateway models | Both fit because Instance and realization cardinalities are not collapsed |
| Managed and connected Runtime models | Both fit through declared ownership modes; connected mode may be observe-only |

The v0.2/v0.3 Agent Instance roadmap placement is a scope tension recorded in
D30, not a baseline contradiction. Human approval is required before changing
release commitments or implementing the semantic.

## 24. Unresolved Questions

1. What exact schema and compatibility rules represent Agent Instance,
   Binding history, rebinding, migration, and rollout?
2. When does a retry remain an attempt of one Execution versus create a child
   or replacement Execution, especially for side effects?
3. What durability, authorization, expiry, and redaction rules apply to
   deferred handles and native diagnostic evidence?
4. Which normalized eligibility inputs and freshness rules may logical routing
   consume?
5. Is explicit Instance targeting public, privileged, internal, or layered?
6. What minimum recovery predicates apply to each ownership mode, and who
   times out `UNKNOWN`?
7. How are in-flight executions classified across realization replacement?
8. What is the minimal versioned schema for each domain Provider descriptor,
   Binding, compatibility decision, condition, and outcome?
9. Which party publishes, signs, revokes, and audits Provider/package metadata?
10. Which Workspace and State continuity references belong in v0.2 without
    implying portability?

These questions block relevant schema freeze or production claims, not the
architecture ownership recommendations.

## 25. Proposed Next Engineering Sequence

No new broad Spike is required before architecture convergence.

Recommended sequence after Human Architecture Final Gate:

```text
Human acceptance of D30-D36 and AP dispositions
  -> Contract Schema Drafts
       - Core execution primitives
       - Agent Instance minimum schema
       - Runtime and Capability domain schemas
       - domain Binding/Provider registry records
  -> Contract Conformance Plan
       - unchanged generic consumers
       - combined Runtime/Capability Execution Identity propagation
       - deferred durability and recovery profiles
  -> focused evidence runs required by the selected freeze profiles
  -> Human Contract Gate
  -> ADR-0003 clarification, ADR-0004 amendment, ADR-0005 clarification
  -> G1 implementation plan
  -> S5-DEV
```

The exact blocking falsification question for the combined-path evidence run
is:

> Can one unchanged Control Plane consumer create one logical Execution
> Identity, route it through a selected Agent Instance and Runtime Provider,
> invoke an authorized Capability through a different Capability Provider,
> and correlate inline/deferred success and semantic failure without exposing
> either Provider's native identity or changing domain-specific semantics?

This is a focused conformance/evidence activity, not authorization to start a
new Spike in this session.

## 26. Human Final Gate Decision Table

### D30 Agent Instance

Recommendation: **ACCEPT_RECOMMENDED**
Evidence: Definition-to-Instance `1:N`, Instance-to-realization `1:N`, shared
Gateway `N:1`, replacement, routing, and semantic recovery.
Risk: minimal v0.2 semantic must not expand into full v0.3 lifecycle product or
premature CRD design.
Human Decision: **PENDING**

### D31 Platform Execution Identity

Recommendation: **ACCEPT_RECOMMENDED**
Evidence: stable correlation across routing, Provider translation,
Capability success/failure, deferred observation, and realization recovery.
Risk: retry/replay/idempotency and combined Runtime/Capability propagation
remain unfrozen.
Human Decision: **PENDING**

### D32 Shared Execution Semantics

Recommendation: **ACCEPT_RECOMMENDED — OPTION C**
Evidence: repeated minimal identity, acceptance, terminality, correlation, and
safe-error primitives alongside materially different domain lifecycles.
Risk: a universal envelope would couple Contracts and erase authorization,
availability, payload, and failure meaning.
Human Decision: **PENDING**

### D33 Binding + Provider Pattern

Recommendation: **ACCEPT_RECOMMENDED**
Evidence: Runtime and Capability both preserve platform identity through
domain Binding, resolution, Provider translation, and opaque native systems.
Risk: generic schemas or a universal registry would become empty abstractions
or a service locator.
Human Decision: **PENDING**

### D34 Logical Routing Ownership

Recommendation: **ACCEPT_RECOMMENDED**
Evidence: multi-Instance, explicit targeting, replacement, and shared Gateway
tests preserved platform selection and Provider-local translation.
Risk: eligibility freshness, explicit-target authorization, and
multi-realization policy remain schema/production debt.
Human Decision: **PENDING**

### D35 Recovery Semantics

Recommendation: **ACCEPT_RECOMMENDED**
Evidence: negative case proved `RESTART_SUCCEEDED` while semantic recovery
failed; positive case required Binding, condition, routing, and identity
verification.
Risk: stateful/external recovery and in-flight execution disposition remain
unproven.
Human Decision: **PENDING**

### D36 Condition / Outcome Ownership

Recommendation: **ACCEPT_RECOMMENDED**
Evidence: Runtime conditions, Capability outcomes, Task/Workflow status, and
recovery assessments share shapes but have distinct owners and meanings.
Risk: premature vocabulary freeze or universal Status would erase domain
semantics.
Human Decision: **PENDING**

## Session Disposition

- Production/Core source changes: **0**
- ADR changes: **0**
- Contract frozen: **No**
- Next action: **WAIT_FOR_HUMAN_DECISION**
- Next gate: **Human Architecture Final Gate**
