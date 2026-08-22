# S5-ARCH-004 — v0.2 Core Contract Boundary & Schema Map v1

SESSION

ID: S5-ARCH-004
TITLE: v0.2 Core Contract Boundary & Schema Map
PHASE: S5 / v0.2 CONNECT & MANAGE
TRACK: Core Contract
MODE: Architecture -> Engineering Contract Translation
LIFECYCLE: REVIEW
AUTHORIZATION: AUTHORIZED
STATUS: PASS
CHECKPOINT: A — OBJECT_TAXONOMY_AND_OWNERSHIP

RESULT: **OBJECT_TAXONOMY_RECOMMENDED**

> Checkpoint A recommendation only. Human Checkpoint A Gate is pending. This
> artifact classifies object boundaries and ownership; it does not define field
> schemas, freeze Contracts, change an ADR, or authorize implementation.

## 1. Executive Conclusion

The accepted v0.2 architecture translates into a deliberately small set of
first-class Control Plane resources and domain-specific extension boundaries.
The recommended first-class resources are Agent Definition, Agent Instance,
Task, Workflow, Runtime Binding, Capability Definition, and Capability Binding.
Of these, Agent Definition, Task, and Workflow already exist in current source;
this recommendation does not change their schemas.

Agent Instance requires first-class identity because logical routing and
semantic recovery must survive changes in Pods, containers, Gateways,
processes, and Provider-native sessions. Runtime Binding and Capability Binding
also warrant first-class representation because they have independently
referenced desired state, authorization, compatibility, and reconciliation
boundaries. They remain domain-specific and are not instances of a generic
Binding schema.

Runtime Provider and Capability Provider are versioned Provider interfaces.
Their registries and Runtime Package records are metadata, not new services or
CRDs. Platform Execution Identity is a Core value object carried by references;
it does not justify a universal Execution resource. Conditions, outcomes, and
recovery assessments remain owned by their domains and share only the minimal
unfrozen primitives accepted by D32 Option C and D36.

Model Binding is a thin v0.2 Binding boundary whose semantics must be completed
by S5-SPIKE-005. Workspace, State/Memory, and Knowledge remain thin references;
their strategic importance does not prove independent lifecycle. No state
portability is claimed. Agent Factory, Catalog, broad v0.3 lifecycle experience,
HA, and detailed field/cardinality design remain out of scope.

## 2. Source Baseline

| Source | State used by this checkpoint |
| --- | --- |
| `origin/main` | `2ed9707ddc6390fbf3ffe35e09b36a8797066e1e`, verified before work began |
| S5-REL-001 | `CLOSED / COMPLETED / PASS`; architecture and evidence integrated |
| S5-REL-002 | Task-supplied baseline: `CLOSED / COMPLETED / PASS`; no separate durable artifact was present at the verified baseline |
| S5-ARCH-002 | Runtime Provider Architecture v1 accepted; Runtime Contract not frozen |
| S5-SPIKE-003 | Capability identity, Binding, Provider isolation, authorization, and outcome evidence |
| S5-SPIKE-004 | Agent Instance identity, logical routing, realization replacement, and recovery evidence |
| S5-ARCH-003 | D30–D36 and AP-S5-001/AP-S5-010/AP-S5-011 accepted |
| Current source/tests | Current resources are Agent, Task, and Workflow; proposed v0.2 objects are not implemented |

The source baseline remains Kubernetes as the current Control Plane source of
truth. Persistence ownership in this artifact does not introduce another
database or source of truth.

## 3. Accepted Architecture Constraints

- D30: Agent Instance is a platform-managed Core semantic.
- D31: Platform Execution Identity identifies one logical execution and is
  stable across routing and Provider boundaries.
- D32 Option C: share only minimal execution primitives; Runtime Interaction
  and Capability Invocation remain domain-specific.
- D33: use domain Binding -> domain Provider resolution -> domain Provider;
  do not create universal Binding, Provider, or Registry abstractions.
- D34: the Control Plane selects a logical Agent Instance; a Runtime Provider
  translates the already-selected Runtime Binding.
- D35 and AP-S5-001: restart is not recovery; recovery requires restoration
  and semantic verification.
- D36: conditions and outcomes retain domain ownership; only proven minimal
  shapes may be shared.
- Core owns semantics, Providers own adaptation, and native systems own
  execution. Providers may replace implementation but may not replace
  platform semantics or policy.
- The Runtime Contract, Capability Contract, Agent Instance schema, shared
  execution schema, condition vocabulary, and recovery vocabulary are not
  frozen.

## 4. Candidate Object Inventory

The inventory uses exactly one primary classification per candidate.
`Representation` is the independent Resource Test conclusion and does not
change the candidate's primary semantic class.

| Domain | Candidate | Semantic identity | Primary classification | Representation | v0.2 disposition |
| --- | --- | --- | --- | --- | --- |
| Core | Agent Definition | Logical definition/version intent | CORE_RESOURCE | FIRST_CLASS_RESOURCE | V0_2_REQUIRED |
| Core | Agent Instance | Stable logical running identity | CORE_RESOURCE | FIRST_CLASS_RESOURCE | V0_2_REQUIRED |
| Core | Task | Durable requested-work lifecycle | CORE_RESOURCE | FIRST_CLASS_RESOURCE | V0_2_REQUIRED |
| Core | Workflow | Durable orchestration/DAG lifecycle | CORE_RESOURCE | FIRST_CLASS_RESOURCE | V0_2_REQUIRED |
| Binding | Runtime Binding | Instance-to-runtime desired association | BINDING | FIRST_CLASS_RESOURCE | V0_2_REQUIRED |
| Binding | Capability Binding | Governed semantic-use association | BINDING | FIRST_CLASS_RESOURCE | V0_2_REQUIRED |
| Binding | Model Binding | Governed model-selection association | BINDING | EMBEDDED_VALUE initially | V0_2_THIN_FOUNDATION |
| Workspace | Workspace Binding | Where work occurs | REFERENCE | REFERENCE | V0_2_THIN_FOUNDATION |
| State | State Binding | Memory/state continuity intent | REFERENCE | REFERENCE | V0_2_THIN_FOUNDATION |
| Knowledge | Knowledge Binding | Governed knowledge source association | REFERENCE | REFERENCE | V0_2_THIN_FOUNDATION |
| Capability | Capability Definition | Enterprise capability/version/operation semantics | CORE_RESOURCE | FIRST_CLASS_RESOURCE | V0_2_REQUIRED |
| Capability | Capability Provider | Translation and invocation adapter | PROVIDER_INTERFACE | PROVIDER_INTERFACE_ONLY | V0_2_REQUIRED |
| Capability | Capability Provider Registry | Versioned resolution and compatibility facts | REGISTRY_METADATA | INTERNAL_METADATA | V0_2_REQUIRED |
| Runtime | Runtime Provider | Translation, realization, and observation adapter | PROVIDER_INTERFACE | PROVIDER_INTERFACE_ONLY | V0_2_REQUIRED |
| Runtime | Runtime Provider Registry | Versioned resolution and compatibility facts | REGISTRY_METADATA | INTERNAL_METADATA | V0_2_REQUIRED |
| Runtime | Runtime Package | Deployable distribution/version facts | REGISTRY_METADATA | INTERNAL_METADATA | V0_2_REQUIRED |
| Model | Model Provider | Model protocol/inference adapter | PROVIDER_INTERFACE | PROVIDER_INTERFACE_ONLY | DEFERRED |
| Model | Model Gateway / Router | Model routing implementation boundary | DEFERRED | DEFER_V0_3_PLUS | DEFERRED |
| Model | Model Policy | Enterprise routing/fallback intent | POLICY_REFERENCE | REFERENCE | V0_2_THIN_FOUNDATION |
| Execution | Platform Execution Identity | One logical execution of requested work | CORE_VALUE_OBJECT | EMBEDDED_VALUE | V0_2_REQUIRED |
| Execution | Execution Correlation | Bounded propagated correlation context | CORE_VALUE_OBJECT | EMBEDDED_VALUE | V0_2_REQUIRED |
| Execution | Execution Reference | Reference to Execution Identity plus subordinate context | REFERENCE | REFERENCE | V0_2_REQUIRED |
| Observation | Agent Instance Status | Current normalized observed projection | STATUS | EMBEDDED_VALUE | V0_2_REQUIRED |
| Observation | Agent Instance Condition | Instance-domain condition | CONDITION | EMBEDDED_VALUE | V0_2_REQUIRED |
| Observation | Runtime Condition | Runtime-domain, Provider-normalized condition | CONDITION | EMBEDDED_VALUE | V0_2_REQUIRED |
| Observation | Task Outcome | Task-owned terminal/non-terminal result | OUTCOME | EMBEDDED_VALUE | V0_2_REQUIRED |
| Observation | Workflow Outcome | Workflow-owned aggregate result | OUTCOME | EMBEDDED_VALUE | V0_2_REQUIRED |
| Observation | Capability Outcome | Capability-domain business result | OUTCOME | EMBEDDED_VALUE | V0_2_REQUIRED |
| Observation | Recovery Assessment | Instance reconciliation assessment | STATUS | EMBEDDED_VALUE | V0_2_REQUIRED |
| Governance | Policy Reference | Link to governance-owned policy | POLICY_REFERENCE | REFERENCE | V0_2_THIN_FOUNDATION |
| Governance | Permission Reference | Link to authorization-owned grant/decision | POLICY_REFERENCE | REFERENCE | V0_2_THIN_FOUNDATION |
| Governance | Human Gate Reference | Link to approval state/evidence | POLICY_REFERENCE | REFERENCE | V0_2_THIN_FOUNDATION |
| Native | Runtime Realization ID | Provider-native realization correlation | OPAQUE_NATIVE_ID | REFERENCE | V0_2_REQUIRED |
| Native | Provider-native Run ID | Native run correlation evidence | OPAQUE_NATIVE_ID | REFERENCE | V0_2_REQUIRED |
| Native | Provider-native Session ID | Native session correlation evidence | OPAQUE_NATIVE_ID | REFERENCE | V0_2_REQUIRED |
| Native | Pod ID | Infrastructure realization evidence | OPAQUE_NATIVE_ID | REFERENCE | V0_2_REQUIRED |
| Native | Container ID | Infrastructure realization evidence | OPAQUE_NATIVE_ID | REFERENCE | V0_2_REQUIRED |
| Native | Gateway ID | Shared/native endpoint evidence | OPAQUE_NATIVE_ID | REFERENCE | V0_2_REQUIRED |
| Native | Capability-native Invocation ID | Native invocation correlation evidence | OPAQUE_NATIVE_ID | REFERENCE | V0_2_REQUIRED |

## 5. Classification Matrix

| Classification | Members | Boundary rule |
| --- | --- | --- |
| CORE_RESOURCE | Agent Definition, Agent Instance, Task, Workflow, Capability Definition | Independently identified Control Plane semantics; first-class resource recommendation does not define a CRD schema |
| CORE_VALUE_OBJECT | Platform Execution Identity, Execution Correlation | Embedded platform-owned semantics with no independently reconciled desired state |
| BINDING | Runtime Binding, Capability Binding, Model Binding | Domain-owned associations; no generic Binding schema |
| REGISTRY_METADATA | Runtime Provider Registry, Runtime Package, Capability Provider Registry | Immutable/versioned resolver facts; repository/startup metadata is sufficient for v0.2 |
| PROVIDER_INTERFACE | Runtime Provider, Capability Provider, future Model Provider | Replaceable translation boundary; never a platform semantic resource |
| STATUS | Agent Instance Status, Recovery Assessment | Observed/derived projections; no desired state or independent lifecycle |
| CONDITION | Agent Instance Condition, Runtime Condition | Domain-owned truth assertions using only minimal shared shape candidates |
| OUTCOME | Task, Workflow, and Capability Outcomes | Domain-owned results using only minimal normalized envelope candidates |
| REFERENCE | Execution, Workspace, State, and Knowledge references | Identifies or links to another owner without importing its lifecycle |
| OPAQUE_NATIVE_ID | Realization, run, session, Pod, container, Gateway, invocation IDs | Bounded correlation evidence only; never routing or platform identity |
| POLICY_REFERENCE | Policy, Permission, Human Gate, and Model Policy references | Governance/routing owner remains outside the referring object |
| DEFERRED | Model Gateway / Router | Boundary requires S5-SPIKE-005 evidence |
| REJECTED_ABSTRACTION | Universal execution/status/provider/binding families; Digital Employee CRD | Would merge distinct semantics or duplicate a business projection |

## 6. Resource Test Matrix

Legend: `Y` supports first-class representation; `N` does not; `P` is partial
or not yet proven. Authorization and observability columns ask whether the
candidate needs those boundaries independently of its parent.

| Candidate | Identity | Lifecycle | Desired state | Reconciled | Independently referenced | Authorization | Observability | Coupling reduced | API cost acceptable | Recommendation |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | --- |
| Agent Definition | Y | Y | Y | Y | Y | Y | Y | Y | Y | FIRST_CLASS_RESOURCE |
| Agent Instance | Y | Y | Y | Y | Y | Y | Y | Y | Y | FIRST_CLASS_RESOURCE |
| Task | Y | Y | Y | Y | Y | Y | Y | Y | Y | FIRST_CLASS_RESOURCE |
| Workflow | Y | Y | Y | Y | Y | Y | Y | Y | Y | FIRST_CLASS_RESOURCE |
| Runtime Binding | Y | Y | Y | Y | Y | Y | Y | Y | Y | FIRST_CLASS_RESOURCE |
| Capability Definition | Y | Y | Y | Y | Y | Y | Y | Y | Y | FIRST_CLASS_RESOURCE |
| Capability Binding | Y | Y | Y | Y | Y | Y | Y | Y | Y | FIRST_CLASS_RESOURCE |
| Model Binding | P | P | Y | P | P | Y | P | P | N | EMBEDDED_VALUE |
| Workspace Binding | N | N | P | N | P | P | N | N | N | REFERENCE |
| State Binding | N | N | P | N | P | P | N | N | N | REFERENCE |
| Knowledge Binding | N | N | P | N | P | P | N | N | N | REFERENCE |
| Runtime Provider | Y | Independent software release, not domain lifecycle | N | N | Y | Y | Y | Y | N | PROVIDER_INTERFACE_ONLY |
| Runtime Provider Registry | N | Metadata publication | N | N | Y | Y | Y | Y | N | INTERNAL_METADATA |
| Runtime Package | Y | Package release, not Control Plane lifecycle | N | N | Y | Y | Y | Y | N | INTERNAL_METADATA |
| Capability Provider | Y | Independent software release, not domain lifecycle | N | N | Y | Y | Y | Y | N | PROVIDER_INTERFACE_ONLY |
| Capability Provider Registry | N | Metadata publication | N | N | Y | Y | Y | Y | N | INTERNAL_METADATA |
| Platform Execution Identity | Y | Owned under Task/Workflow execution lifecycle | N | N | Y | P | Y | Y | N | EMBEDDED_VALUE |
| Recovery Assessment | N | Derived per reconciliation | N | Y | N | N | Y | N | N | EMBEDDED_VALUE |

The API-cost conclusion is intentionally conservative. A unique ID or useful
metadata is not enough to justify a Control Plane resource.

## 7. Semantic Ownership Matrix

| Semantic | Platform/Core owns | Provider owns | Native/infrastructure owns | Must remain opaque or external |
| --- | --- | --- | --- | --- |
| Agent Definition | Identity, purpose, declared Binding/reference intent, desired Instance policy | Translation of relevant declared intent | Consumed native representation | Digital Employee business projection |
| Agent Instance | Stable identity, desired state, eligibility, routing semantics, final recovery assessment | Binding translation and normalized evidence | Realizations and execution mechanics | Native topology and IDs |
| Runtime Binding | Desired association, ownership mode, Provider/Package constraints, references | Validation, translation, configuration reconciliation | Native configuration and realization | Provider-native configuration |
| Capability Definition | Enterprise identity/version/operation meaning and risk boundary | Protocol/tool mapping | Native endpoint/tool behavior | MCP/REST/gRPC details |
| Capability Binding | Allowed semantic use, Provider constraints, policy/permission references | Validation and invocation translation | Native invocation | Endpoint/tool identity |
| Model Binding | Enterprise model requirements and policy association | Runtime/Model Provider translation | Provider-native model route | Credentials and native routing configuration |
| Workspace reference | Meaning of where the Agent works | Reference projection only when declared | Native workspace mechanics | Native path/layout |
| State reference | Continuity intent only where explicitly promised | Maps declared reference | Native state format and use | State payload/format; portability unproven |
| Knowledge reference | Meaning of governed knowledge source | Retrieval/protocol translation when later defined | Native index/source mechanics | Native index and retrieval schema |
| Execution Identity | Creation, meaning, hierarchy/correlation rules | Propagation without replacement | Native runs/requests/sessions | Native identifiers |
| Conditions/outcomes | Minimal normalized primitives and domain ownership rules | Native evidence normalization | Raw status/result/error | Raw payloads and diagnostics |
| Policy/permission/gate | Reference and precedence semantics; authorization owner decides | Enforce delegated controls only | Cannot expand authority | Policy data and secret material |

Agent Definition owns classification-level references to Runtime Binding,
Capability Binding, Model Binding, Workspace, State/Memory, Knowledge, Policy,
and desired Instance policy. This statement assigns semantic ownership only;
it does not decide whether fields are inline, named, singular, plural, or
versioned.

## 8. Lifecycle / Reconciliation Ownership Matrix

| Candidate | Lifecycle owner | Reconciliation owner | Authoritative persistence | Cleanup boundary |
| --- | --- | --- | --- | --- |
| Agent Definition | Agent Definition Control Plane | Existing/future Agent reconciler | Kubernetes Control Plane | Control Plane policy; native cleanup delegated through Bindings |
| Agent Instance | Agent Instance Control Plane | Agent Instance reconciler | Kubernetes Control Plane | Preserve identity rules; Provider cleans only Provider-owned realizations |
| Task | Task/Workflow layer | Task reconciler | Kubernetes Control Plane | Task policy and owned execution records |
| Workflow | Task/Workflow layer | Workflow reconciler | Kubernetes Control Plane | Workflow/node policy |
| Runtime Binding | Runtime domain Control Plane | Runtime Binding reconciler using Runtime Provider | Kubernetes Control Plane | Ownership-mode aware; never delete external artifacts implicitly |
| Capability Definition | Capability domain Control Plane | Capability reconciler/validator | Kubernetes Control Plane | No Provider-native deletion implied |
| Capability Binding | Capability domain Control Plane | Capability Binding reconciler using Capability Provider metadata | Kubernetes Control Plane | Revoke use association; native cleanup only if explicitly owned |
| Model Binding | Model domain Control Plane, thin in v0.2 | Not finalized; Provider translation only | Parent/Control Plane representation | No model-provider resource deletion |
| Workspace/State/Knowledge refs | Owning external/domain systems | No Core lifecycle reconciliation in v0.2 | Reference only | External owner controls cleanup |
| Provider registries/packages | Registry metadata publisher | Deterministic resolution/validation, not resource reconciliation | Repository/startup metadata | Supersede records; no native lifecycle implied |
| Platform Execution Identity | Task/Workflow execution owner | Not independently reconciled | Embedded with owning execution context | Retention follows owning domain |
| Agent Instance Status/Conditions | Agent Instance Control Plane | Agent Instance reconciler | Resource status | Derived and replaceable |
| Runtime Conditions | Runtime domain Control Plane | Runtime Provider normalizes; Control Plane records | Binding/Instance status boundary, schema pending | Derived and replaceable |
| Outcomes | Owning Task/Workflow/Capability domain | Owning interaction/reconciler | Owning domain record/status | Retention follows domain policy |
| Recovery Assessment | Agent Instance Control Plane | Agent Instance reconciler using Provider evidence | Status/event boundary, schema pending | Assessment history policy deferred |

Recovery layers remain separate: Kubernetes/native supervision maintains
processes; Runtime Provider reconciliation restores and observes native
semantics; Agent Instance reconciliation assesses promised Instance semantics;
Task/Workflow owns execution retry and in-flight execution disposition.

## 9. Provider Responsibility Boundary

### 9.1 Runtime Provider

| Boundary | Responsibility |
| --- | --- |
| Platform-owned input semantics | Selected Agent Instance, Runtime Binding desired intent, Provider/Package constraints, ownership mode, Execution reference, Model/Capability/Workspace/State/Policy references |
| Provider-owned translation | Validate Binding; resolve declared compatibility; compute native configuration; translate lifecycle/interaction only when declared |
| Native-system interaction | Realize or connect, configure, submit, observe, cancel/recover only where supported |
| Provider-owned normalization | Convert native observations, failures, and outcomes into bounded Runtime-domain semantics; redact sensitive/native payloads |
| Platform-owned normalized result | Runtime conditions, submission/completion disposition, bounded diagnostics, realization references, evidence for recovery assessment |
| Opaque native IDs | Realization, run, session, Pod, container, Gateway, endpoint/profile IDs |
| Credential boundary | Platform owns reference, authorization, and governance; Provider projects it; native system resolves and consumes it; values never enter status |
| Configuration boundary | Platform owns desired portable/opaque intent; Provider computes/reconciles effective native configuration; native system interprets it |
| Policy boundary | Platform decides eligibility and authority; Provider may enforce delegated native controls but cannot broaden authority |

### 9.2 Capability Provider

| Boundary | Responsibility |
| --- | --- |
| Platform-owned input semantics | Capability identity/version/operation, Capability Binding, validated input contract, Execution reference, permission/policy decision |
| Provider-owned translation | Map semantic operation to REST/MCP/gRPC/tool/native request after authorization |
| Native-system interaction | Invoke and, where declared, observe/cancel a native operation |
| Provider-owned normalization | Interpret protocol, business, transport, and deferred results without leaking protocol types |
| Platform-owned normalized result | Capability Outcome, submission/completion disposition, safe error category, bounded evidence reference |
| Opaque native IDs | Invocation/request/tool/job/session IDs and deferred observation handles |
| Credential boundary | Governance owns credential reference and authorization; Provider projects it; native client consumes it |
| Configuration boundary | Binding owns semantic selection and constraints; Provider owns endpoint/tool/protocol configuration translation |
| Policy boundary | Authorization is explicit before invocation; discovery, Provider resolution, or Binding presence never grants permission |

Any Core branch on Runtime family, Provider ID, MCP/REST protocol, endpoint
shape, native error class, or native topology is Core/Provider leakage.

## 10. Preliminary API Surface Budget

| Proposed first-class resource | Why identity/lifecycle is required | Reconciler / authorizer | Why embedding is insufficient | API complexity introduced |
| --- | --- | --- | --- | --- |
| Agent Definition | Stable reusable logical definition and desired policy | Agent Control Plane / platform governance | Instances, Tasks, and Bindings reference it independently | Existing API surface; no Checkpoint A schema change |
| Agent Instance | Identity survives realization replacement and shared Gateways; independently routed/recovered | Agent Instance reconciler / platform policy | Embedding in Definition cannot represent N Instances or independent lifecycle | New identity, lifecycle, status, deletion, reference, and authorization questions |
| Task | Durable requested work, retry, and outcome lifecycle | Task reconciler / task authorization | Must be independently observed and coordinated | Existing API surface; unchanged |
| Workflow | Durable DAG and aggregate lifecycle | Workflow reconciler / workflow authorization | Nodes/tasks and aggregate result require independent coordination | Existing API surface; unchanged |
| Runtime Binding | Independently evolves and reconciles Provider/Package association and realization ownership | Runtime Binding reconciler / runtime eligibility policy | Embedding couples Instance lifecycle to Provider resolution and migration | New reference, compatibility, conditions, ownership-mode, and deletion questions |
| Capability Definition | Reusable enterprise semantic independent of Provider/protocol | Capability domain / capability governance | Embedding in Agent prevents reuse, portability, and independent authorization | New version/operation/risk/reference questions |
| Capability Binding | Independently governed association between Agent/use context and Capability Provider | Capability Binding reconciler / capability authorization | Embedding conflates discovery with permission and hinders Provider replacement | New compatibility, policy, reference, and revocation questions |

No other candidate currently clears the API budget. Provider records and
Runtime Packages gain versioned metadata, not CRDs. Model Binding remains
embedded until S5-SPIKE-005 establishes enough semantics. Execution Identity
has independent identity but not independent desired state or reconciliation.

## 11. Preliminary v0.2 Disposition

### V0_2_REQUIRED

- Agent Definition, Agent Instance, Task, and Workflow;
- Runtime Binding, Runtime Provider interface, Runtime Provider Registry
  metadata, and Runtime Package metadata;
- Capability Definition, Capability Binding, Capability Provider interface,
  and Capability Provider Registry metadata;
- Platform Execution Identity, Execution Correlation, and Execution Reference;
- Agent Instance Status/Condition, Runtime Condition, Task/Workflow/Capability
  Outcomes, and Recovery Assessment;
- bounded opaque native ID references required for correlation and evidence.

`V0_2_REQUIRED` means required in the v0.2 engineering Contract map. It does
not authorize immediate schema or production implementation.

### V0_2_THIN_FOUNDATION

- Model Binding and Model Policy reference;
- Workspace, State/Memory, and Knowledge references;
- Policy, Permission, and Human Gate references.

These foundations carry ownership and reference boundaries only. They do not
claim full provider ecosystems, lifecycle services, portability, or frozen
vocabularies.

### DEFERRED

- Model Provider representation details and Model Gateway/Router design until
  S5-SPIKE-005;
- independent Workspace, State/Memory, and Knowledge resources;
- state portability, durable deferred execution guarantees, dynamic Provider
  loading/marketplaces, HA, scheduling algorithms, multi-tenancy, and broad
  v0.3 lifecycle product capabilities.

### REJECTED

- Universal Execution/Status/Provider/Binding abstractions;
- Runtime Package, Provider Registry, Provider, Execution Identity, Recovery
  Assessment, or opaque native ID as a new Control Plane resource;
- Digital Employee CRD;
- Runtime Instance defined as a universal native realization wrapper.

## 12. Golden Demo Traceability

| Candidate or boundary | Product proof | Control Plane invariant supported |
| --- | --- | --- |
| Agent Definition | P1, P2, P3 | Logical intent remains separate from runtime/capability implementation |
| Agent Instance | P3, P4, P6, P7 | Stable logical identity, routing, and recovery across native change |
| Task / Workflow | P1, P6, P7 | Durable work/DAG lifecycle, retry, failure, and outcome ownership |
| Runtime Binding + Provider + Registry/Package metadata | P3, P6, P7 | Runtime portability without Core family branching; compatibility is explicit |
| Capability Definition + Binding + Provider + Registry metadata | P1, P2, P5, P7 | Capability portability; discovery is separate from authorization/invocation |
| Execution Identity / references | P1, P2, P3, P6, P7 | One logical correlation chain across routing and Providers |
| Conditions, outcomes, Recovery Assessment | P1, P6, P7 | Honest domain observation and verified recovery |
| Policy/Permission/Human Gate references | P5, P7 | Extensions cannot bypass governance; decisions remain auditable |
| Model Binding thin foundation | P1 | Runtime does not own enterprise Model identity or routing policy |
| Workspace/State/Knowledge references | P1, P6 | Semantic separation without unsupported lifecycle or portability claims |

Native Runtime remains the Reference/Golden Path candidate. OpenClaw may prove
heterogeneous/shared-Gateway behavior. Hermes remains experimental and not
currently certifiable; ED-S5-001 remains open. Golden Demo success does not
depend on Hermes certification.

## 13. Rejected Abstractions

| Rejected abstraction | Reason |
| --- | --- |
| `UniversalExecution` / universal Execution resource | Execution Identity is valuable, but no independent desired state or reconciler is proven; Runtime and Capability lifecycles differ |
| `UniversalExecutionStatus` / generic Status | Erases condition/outcome ownership, retry safety, authorization timing, and domain meaning |
| `UniversalProvider` / `GenericRuntimeCapabilityProvider` | Runtime realization and Capability invocation have different responsibilities and versioning |
| `UniversalBinding` | Runtime, Capability, and Model Bindings associate different semantics and lifecycle concerns |
| Universal Provider Registry | Becomes a service locator and erases domain compatibility/policy dimensions |
| Runtime Instance wrapper | Falsely treats Gateway, process, Pod, endpoint, and session as one lifecycle object |
| Digital Employee CRD | Digital Employee is a product/business projection of Agent Definition, not a new technical identity |
| MCP Capability semantic | MCP is a Provider/protocol concern; Capability is the enterprise semantic |
| State-as-Runtime | Runtime-native state format does not establish enterprise State ownership or portability |

Structural similarity is insufficient evidence of semantic identity.

## 14. Evidence Gaps

1. Agent Instance production schema: tenancy, owner, generation, deletion,
   desired lifecycle vocabulary, exact status placement, and migration history.
2. Binding cardinality and rebinding/rollout history; detailed relationships
   belong to Checkpoint B.
3. Runtime and Capability Contract schemas, compatibility rules, stable error
   taxonomies, retry/idempotency, cancellation, and deferred durability.
4. Combined Runtime Provider -> Capability Provider propagation of one
   Platform Execution Identity.
5. Out-of-process Provider transport and dynamic loading; neither is required
   for v0.2 architecture correctness.
6. Third-party MCP, side-effecting, and long-running Capability evidence.
7. Model identity, routing, fallback, credential, and gateway boundaries await
   S5-SPIKE-005. This checkpoint intentionally stops at a thin Binding/policy
   reference and does not start that spike.
8. Workspace independent lifecycle is not proven. State portability is not
   proven. Knowledge lifecycle/provider semantics are not proven.
9. Stateful and external/observe-only recovery, in-flight recovery disposition,
   timeout/escalation, and durable recovery history.
10. Multi-tenant authorization, audit, credential projection, diagnostic
    access, and Human Gate enforcement evidence.
11. ED-S5-001 remains open; Hermes Provider certification is debt, not a
    blocker for this taxonomy or the Golden Demo.

None of these gaps requires reopening D30–D36 or accepted architecture
principles. They constrain later schema, Contract-freeze, certification, and
production-readiness claims.

## 15. Checkpoint A Recommendations

1. Approve the seven-resource preliminary API budget while recording that only
   Agent Definition, Task, and Workflow exist today.
2. Approve Agent Instance as a first-class Core resource boundary for the
   minimal v0.2 routing/recovery foundation, not the broad v0.3 product
   lifecycle.
3. Approve Runtime Binding and Capability Binding as distinct first-class
   resources; prohibit a generic Binding schema.
4. Keep Runtime/Capability Providers as interfaces and their registries plus
   Runtime Packages as versioned internal metadata for v0.2.
5. Approve Platform Execution Identity as a Core value object propagated by
   references; do not create a universal Execution resource.
6. Keep status, conditions, outcomes, and Recovery Assessment embedded and
   domain-owned. Defer shared primitive field design to Checkpoint C.
7. Approve only thin Model, Workspace, State/Memory, Knowledge, and governance
   reference boundaries. Do not infer Provider or portability semantics.
8. Carry all relationship/cardinality and field-level questions to Checkpoint
   B/C after the Human Checkpoint A Gate.

## 16. Human Decision Table — Checkpoint A

### A01 — Agent Definition primary classification

**Recommendation:** CORE_RESOURCE / FIRST_CLASS_RESOURCE.
**Why:** It is the stable technical logical definition independently referenced
by Instances, Tasks, and Bindings. Digital Employee remains its business
projection.
**Evidence:** Current Agent CRD; Product principles; S5-ARCH-003 ownership.
**Alternative:** Embed definition data in every Instance or Task.
**Trade-off:** First-class versioning and authorization cost versus avoiding
duplication and runtime coupling.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None; current or future schema is not frozen.
**Human Decision:** PENDING.

### A02 — Agent Instance primary classification

**Recommendation:** CORE_RESOURCE / FIRST_CLASS_RESOURCE.
**Why:** Stable logical identity, desired lifecycle, routing eligibility, and
recovery survive native realization replacement and shared-Gateway topology.
**Evidence:** D30, D34, D35; S5-SPIKE-004 H-INS-01–H-INS-05.
**Alternative:** Derive Instance identity from Pod, Gateway, process, or
runtime-native session.
**Trade-off:** New public lifecycle surface versus the minimum faithful
multi-runtime identity.
**v0.2 disposition:** V0_2_REQUIRED, minimal foundation only.
**Freeze impact:** None; Agent Instance schema remains unfrozen.
**Human Decision:** PENDING.

### A03 — Runtime Binding primary classification

**Recommendation:** BINDING / FIRST_CLASS_RESOURCE.
**Why:** It independently owns desired Provider/Package association, ownership
mode, configuration/reference intent, compatibility, and observed realization
relationship.
**Evidence:** D33; accepted S5-ARCH-002 Runtime Provider architecture.
**Alternative:** Embed runtime configuration in Agent Instance.
**Trade-off:** Additional API/reconciler versus decoupled rebinding,
compatibility, authorization, and Provider replacement.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None; Runtime Contract and Binding schema remain unfrozen.
**Human Decision:** PENDING.

### A04 — Runtime Provider representation

**Recommendation:** PROVIDER_INTERFACE / PROVIDER_INTERFACE_ONLY.
**Why:** A Provider is independently versioned translation and adaptation code,
not desired Control Plane state.
**Evidence:** S5-ARCH-002 D22–D29 baseline and Core/Provider isolation.
**Alternative:** Runtime Provider CRD/resource.
**Trade-off:** Interface/metadata deployment is simpler but postpones dynamic
provider management.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None; Provider interface schema is not frozen.
**Human Decision:** PENDING.

### A05 — Runtime Provider Registry representation

**Recommendation:** REGISTRY_METADATA / INTERNAL_METADATA.
**Why:** Deterministic resolution needs immutable versioned compatibility facts,
not independent desired state or reconciliation.
**Evidence:** Accepted S5-ARCH-002 registry model permits repository/startup
metadata and implies no service/database/CRD.
**Alternative:** First-class registry service/resource.
**Trade-off:** Low v0.2 API/operations cost versus no dynamic marketplace.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None.
**Human Decision:** PENDING.

### A06 — Runtime Package representation

**Recommendation:** REGISTRY_METADATA / INTERNAL_METADATA.
**Why:** A package identifies a deployable distribution/version and
compatibility facts; its software release lifecycle is not a Control Plane
desired-state lifecycle.
**Evidence:** Accepted S5-ARCH-002 Runtime Package model.
**Alternative:** Runtime Package CRD/resource or collapse it into Provider.
**Trade-off:** Metadata preserves Provider/Package separation with minimal API
surface but does not manage package publication.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None.
**Human Decision:** PENDING.

### A07 — Capability Definition primary classification

**Recommendation:** CORE_RESOURCE / FIRST_CLASS_RESOURCE.
**Why:** Enterprise Capability identity, version/operation meaning, reuse, risk,
and authorization are independent of Agent and Provider protocol.
**Evidence:** S5-SPIKE-003 H-CAP-01 and Provider-isolation evidence; Product
Capability boundary.
**Alternative:** Embed MCP/tool declarations in Agent Definition.
**Trade-off:** New versioned API surface versus portability, reuse, and
governance.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None; Capability Contract remains unfrozen.
**Human Decision:** PENDING.

### A08 — Capability Binding primary classification

**Recommendation:** BINDING / FIRST_CLASS_RESOURCE.
**Why:** It independently associates governed semantic use with Provider
selection constraints; discovery and Binding presence must not grant
invocation permission.
**Evidence:** D33 and S5-SPIKE-003 authorization/Provider isolation.
**Alternative:** Embed Provider/tool details in Agent Definition or Capability.
**Trade-off:** Additional reconciliation and authorization surface versus
portable Provider replacement and explicit revocation.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None.
**Human Decision:** PENDING.

### A09 — Capability Provider representation

**Recommendation:** PROVIDER_INTERFACE / PROVIDER_INTERFACE_ONLY.
**Why:** It translates and normalizes semantic operations across MCP, REST,
gRPC, or native mechanisms without owning Capability identity or policy.
**Evidence:** S5-SPIKE-003 REST/MCP and Provider-isolation evidence.
**Alternative:** Provider resource or protocol-specific Capability semantics.
**Trade-off:** Replaceable interface boundary versus deferred dynamic loading.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None; interface details remain unfrozen.
**Human Decision:** PENDING.

### A10 — Capability Provider Registry representation

**Recommendation:** REGISTRY_METADATA / INTERNAL_METADATA.
**Why:** Resolution needs domain-specific version, compatibility, capability,
and policy-eligibility facts, but no independent desired-state lifecycle is
proven.
**Evidence:** D33 domain-specific registry pattern; S5-SPIKE-003 open Provider
descriptor questions.
**Alternative:** Universal registry or Capability Provider CRD.
**Trade-off:** Small explicit metadata boundary versus later work for dynamic
publication and marketplace behavior.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None.
**Human Decision:** PENDING.

### A11 — Platform Execution Identity primary classification

**Recommendation:** CORE_VALUE_OBJECT / EMBEDDED_VALUE, exposed through
Execution References.
**Why:** One platform-owned logical identity must cross routing and Providers,
but it has no independent desired state or reconciler.
**Evidence:** D31, AP-S5-011, S5-SPIKE-003/004 correlation evidence.
**Alternative:** Universal Execution resource or Provider-native run ID.
**Trade-off:** Minimal durable correlation versus postponing independent
execution query/lifecycle API questions.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None; uniqueness, hierarchy, replay, and schema remain
unfrozen.
**Human Decision:** PENDING.

### A12 — Recovery Assessment primary classification

**Recommendation:** STATUS / EMBEDDED_VALUE.
**Why:** It is the Agent Instance reconciler's derived assessment of promised
semantic predicates, not desired state or an independent lifecycle object.
**Evidence:** D35, D36, AP-S5-001, S5-SPIKE-004 recovery evidence.
**Alternative:** Recovery resource or generic outcome.
**Trade-off:** Embedded status preserves ownership and API budget but leaves
history/retention design for later checkpoints.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None; recovery vocabulary remains unfrozen.
**Human Decision:** PENDING.

### A13 — Model Binding preliminary boundary

**Recommendation:** BINDING / EMBEDDED_VALUE, marked
DEFERRED_PENDING_MODEL_SPIKE for detailed semantics.
**Why:** Core must preserve enterprise model requirements/policy association,
while Runtime Provider only translates them. Evidence is insufficient for an
independent resource or routing schema.
**Evidence:** D33 Model pattern; accepted Core ownership; S5-SPIKE-005 not yet
performed.
**Alternative:** First-class Model Binding now, or runtime-owned model config.
**Trade-off:** Thin foundation prevents runtime ownership leakage while avoiding
invented model semantics.
**v0.2 disposition:** V0_2_THIN_FOUNDATION.
**Freeze impact:** None; no Model Contract or policy is frozen.
**Human Decision:** PENDING.

### A14 — Workspace preliminary boundary

**Recommendation:** REFERENCE / REFERENCE.
**Why:** Workspace means where an Agent works, but independent lifecycle and
Control Plane reconciliation are not proven.
**Evidence:** Product semantic separation; S5-ARCH-003 evidence gap.
**Alternative:** Workspace Binding/resource.
**Trade-off:** Thin reference avoids premature API while postponing workspace
portability and lifecycle guarantees.
**v0.2 disposition:** V0_2_THIN_FOUNDATION.
**Freeze impact:** None; first-class status remains not frozen.
**Human Decision:** PENDING.

### A15 — State preliminary boundary

**Recommendation:** REFERENCE / REFERENCE.
**Why:** State/Memory means what an Agent remembers; native formats and
continuity are unproven and must not be confused with Runtime.
**Evidence:** D35 no-portability constraint; S5-ARCH-003/S5-SPIKE-004 evidence
gaps.
**Alternative:** First-class State Binding/resource or runtime-owned state.
**Trade-off:** Honest thin boundary avoids false portability but cannot yet
promise migration or recovery continuity.
**v0.2 disposition:** V0_2_THIN_FOUNDATION.
**Freeze impact:** None; no State Contract is frozen.
**Human Decision:** PENDING.

### A16 — Knowledge preliminary boundary

**Recommendation:** REFERENCE / REFERENCE.
**Why:** Knowledge means what an Agent knows and remains separate from
Capability and State, but independent lifecycle/provider evidence is absent.
**Evidence:** Product architecture semantic separation; no v0.2 spike proves a
Knowledge resource.
**Alternative:** Knowledge Binding/resource or treat retrieval as Capability.
**Trade-off:** Semantic clarity with minimal API cost versus deferred indexing,
provider, and authorization lifecycle.
**v0.2 disposition:** V0_2_THIN_FOUNDATION.
**Freeze impact:** None.
**Human Decision:** PENDING.

## Contract and Change Boundary

CONTRACT_FREEZE: **NO**
FREEZE_GATE: `G-S5-RUNTIME-FREEZE-01 = FAIL / UNCHANGED`
PRODUCTION_CORE_CHANGE: **0**
ADR_CHANGE: **0**
SCHEMA_CHANGE: **0**

Schema Draft is not Contract Freeze. This Checkpoint does not draft a schema.

## Checkpoint State

LIFECYCLE: REVIEW
AUTHORIZATION: AUTHORIZED
STATUS: PASS
CHECKPOINT: A — OBJECT_TAXONOMY_AND_OWNERSHIP
RESULT: OBJECT_TAXONOMY_RECOMMENDED
NEXT_ACTION: WAIT_FOR_HUMAN_DECISION
NEXT_GATE: Human Checkpoint A Gate
