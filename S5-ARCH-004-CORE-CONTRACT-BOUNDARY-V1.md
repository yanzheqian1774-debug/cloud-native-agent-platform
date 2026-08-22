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
CHECKPOINT: D — V0_2_API_SURFACE_AND_FINAL_CONVERGENCE

RESULT: **CORE_CONTRACT_BOUNDARY_RECOMMENDED**

> The Human Checkpoint A Gate passed with representation constraints, the Human
> Checkpoint B Gate passed with semantic constraints, and the Human Checkpoint
> C Gate passed with freeze constraints. This artifact now records Checkpoint D
> final convergence. Human Final Contract Boundary Gate is pending. It does not
> define fields or schemas, freeze Contracts, change an ADR, or authorize
> implementation.

## 1. Executive Conclusion

The accepted v0.2 architecture translates into a deliberately small set of
first-class Control Plane resources and domain-specific extension boundaries.
Agent Definition, Agent Instance, Task, Workflow, and Capability Definition are
strongly accepted first-class logical resources. Runtime Binding and Capability
Binding were accepted at Checkpoint A only as semantic boundaries and remained
representation candidates; the seven-resource count was a preliminary
candidate budget, not an approved CRD count or target. Of the strongly accepted
resources, Agent Definition, Task, and Workflow already exist in current
source; this recommendation does not change their schemas.

Agent Instance requires first-class identity because logical routing and
semantic recovery must survive changes in Pods, containers, Gateways,
processes, and Provider-native sessions. Checkpoint B finds that neither
Runtime Binding nor Capability Binding has proven independent lifecycle,
reconciliation, sharing, or authorization sufficient for another public
resource. Both are recommended as domain-specific `EMBEDDED_BINDING`
structures, with desired policy/template intent owned at Definition scope and
effective resolution owned at the appropriate Instance or invocation scope.
They are not instances of a generic Binding schema.

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
| Binding | Runtime Binding | Instance-to-runtime desired association | BINDING | EMBEDDED_BINDING (Checkpoint B recommendation) | V0_2_REQUIRED |
| Binding | Capability Binding | Governed semantic-use association | BINDING | EMBEDDED_BINDING (Checkpoint B recommendation) | V0_2_REQUIRED |
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
| Execution | Execution Correlation | Bounded propagated correlation context | REFERENCE | Relationship primitive (Checkpoint C recommendation) | V0_2_REQUIRED |
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
| CORE_VALUE_OBJECT | Platform Execution Identity | Embedded platform-owned semantic with no independently reconciled desired state |
| BINDING | Runtime Binding, Capability Binding, Model Binding | Domain-owned associations; no generic Binding schema |
| REGISTRY_METADATA | Runtime Provider Registry, Runtime Package, Capability Provider Registry | Immutable/versioned resolver facts; repository/startup metadata is sufficient for v0.2 |
| PROVIDER_INTERFACE | Runtime Provider, Capability Provider, future Model Provider | Replaceable translation boundary; never a platform semantic resource |
| STATUS | Agent Instance Status, Recovery Assessment | Observed/derived projections; no desired state or independent lifecycle |
| CONDITION | Agent Instance Condition, Runtime Condition | Domain-owned truth assertions using only minimal shared shape candidates |
| OUTCOME | Task, Workflow, and Capability Outcomes | Domain-owned results using only minimal normalized envelope candidates |
| REFERENCE | Execution correlation/native references and Workspace, State, and Knowledge references | Identifies or links without importing another lifecycle; correlation does not require a separate object |
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
| Runtime Binding | N | N | Y | As part of Instance | N | As part of owner | As part of Instance | Y | N | EMBEDDED_BINDING |
| Capability Definition | Y | Y | Y | Y | Y | Y | Y | Y | Y | FIRST_CLASS_RESOURCE |
| Capability Binding | N | N | Y | As part of owner | N | As part of owner/invocation | As part of owner | Y | N | EMBEDDED_BINDING |
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
| Runtime Binding | Definition owns desired template; Instance owns effective projection | Agent Instance reconciler using Runtime Provider | Embedded in owning Control Plane objects | Ownership-mode aware; never delete external artifacts implicitly |
| Capability Definition | Capability domain Control Plane | Capability reconciler/validator | Kubernetes Control Plane | No Provider-native deletion implied |
| Capability Binding | Agent Definition owns desired governed intent | Agent/Capability-domain reconciliation and per-invocation authorization | Embedded in owning Control Plane object | Revoke use association; native cleanup only if explicitly owned |
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

## 10. Preliminary Candidate API Surface Budget

| Proposed first-class resource | Why identity/lifecycle is required | Reconciler / authorizer | Why embedding is insufficient | API complexity introduced |
| --- | --- | --- | --- | --- |
| Agent Definition | Stable reusable logical definition and desired policy | Agent Control Plane / platform governance | Instances, Tasks, and Bindings reference it independently | Existing API surface; no Checkpoint A schema change |
| Agent Instance | Identity survives realization replacement and shared Gateways; independently routed/recovered | Agent Instance reconciler / platform policy | Embedding in Definition cannot represent N Instances or independent lifecycle | New identity, lifecycle, status, deletion, reference, and authorization questions |
| Task | Durable requested work, retry, and outcome lifecycle | Task reconciler / task authorization | Must be independently observed and coordinated | Existing API surface; unchanged |
| Workflow | Durable DAG and aggregate lifecycle | Workflow reconciler / workflow authorization | Nodes/tasks and aggregate result require independent coordination | Existing API surface; unchanged |
| Capability Definition | Reusable enterprise semantic independent of Provider/protocol | Capability domain / capability governance | Embedding in Agent prevents reuse, portability, and independent authorization | New version/operation/risk/reference questions |

At Checkpoint A, Runtime Binding and Capability Binding remained candidates,
not approved resources. Checkpoint B removes both from the recommended
first-class budget because relationship evidence does not establish independent
lifecycle or reconciliation. Provider records and Runtime Packages gain
versioned metadata, not CRDs. Model Binding remains embedded until S5-SPIKE-005
establishes enough semantics. Execution Identity has independent identity but
not independent desired state or reconciliation.

## 11. Preliminary v0.2 Disposition

### V0_2_REQUIRED

- Agent Definition, Agent Instance, Task, and Workflow;
- Runtime Binding, Runtime Provider interface, Runtime Provider Registry
  metadata, and Runtime Package metadata;
- Capability Definition, Capability Binding, Capability Provider interface,
  and Capability Provider Registry metadata;
- Platform Execution Identity, Execution correlation relationship, and
  Execution Reference;
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

1. Record the Checkpoint A Human Gate correction: five strongly accepted
   first-class logical resources and two Binding representation candidates;
   this is not an approved CRD count or target.
2. Approve Agent Instance as a first-class Core resource boundary for the
   minimal v0.2 routing/recovery foundation, not the broad v0.3 product
   lifecycle.
3. Preserve Runtime Binding and Capability Binding as distinct semantic
   boundaries and carry their representation constraints into Checkpoint B;
   prohibit a generic Binding schema.
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
**Human Decision:** ACCEPT.

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
**Human Decision:** ACCEPT.

### A03 — Runtime Binding primary classification

**Recommendation:** BINDING; semantic boundary accepted, with
FIRST_CLASS_RESOURCE only a candidate for Checkpoint B analysis.
**Why:** It independently owns desired Provider/Package association, ownership
mode, configuration/reference intent, compatibility, and observed realization
relationship.
**Evidence:** D33; accepted S5-ARCH-002 Runtime Provider architecture.
**Alternative:** Embed runtime configuration in Agent Instance.
**Trade-off:** Additional API/reconciler versus decoupled rebinding,
compatibility, authorization, and Provider replacement.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None; Runtime Contract and Binding schema remain unfrozen.
**Human Decision:** ACCEPT WITH REPRESENTATION CONSTRAINT.

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
**Human Decision:** ACCEPT.

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
**Human Decision:** ACCEPT.

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
**Human Decision:** ACCEPT.

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
**Human Decision:** ACCEPT.

### A08 — Capability Binding primary classification

**Recommendation:** BINDING; semantic boundary accepted, with
FIRST_CLASS_RESOURCE only a candidate for Checkpoint B analysis.
**Why:** It independently associates governed semantic use with Provider
selection constraints; discovery and Binding presence must not grant
invocation permission.
**Evidence:** D33 and S5-SPIKE-003 authorization/Provider isolation.
**Alternative:** Embed Provider/tool details in Agent Definition or Capability.
**Trade-off:** Additional reconciliation and authorization surface versus
portable Provider replacement and explicit revocation.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None.
**Human Decision:** ACCEPT WITH REPRESENTATION CONSTRAINT.

### A09 — Capability Provider representation

**Recommendation:** PROVIDER_INTERFACE / PROVIDER_INTERFACE_ONLY.
**Why:** It translates and normalizes semantic operations across MCP, REST,
gRPC, or native mechanisms without owning Capability identity or policy.
**Evidence:** S5-SPIKE-003 REST/MCP and Provider-isolation evidence.
**Alternative:** Provider resource or protocol-specific Capability semantics.
**Trade-off:** Replaceable interface boundary versus deferred dynamic loading.
**v0.2 disposition:** V0_2_REQUIRED.
**Freeze impact:** None; interface details remain unfrozen.
**Human Decision:** ACCEPT.

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
**Human Decision:** ACCEPT.

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
**Human Decision:** ACCEPT.

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
**Human Decision:** ACCEPT.

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
**Human Decision:** ACCEPT.

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
**Human Decision:** ACCEPT.

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
**Human Decision:** ACCEPT.

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
**Human Decision:** ACCEPT.

## 17. Relationship Map

Only the following relationship vocabulary is used: `OWNS`, `REFERENCES`,
`BINDS_TO`, `RESOLVES_THROUGH`, `REALIZES`, `OBSERVES`, `ROUTES_TO`, `INVOKES`,
and `CORRELATES_WITH`.

```text
Agent Definition
  OWNS desired Runtime Binding template
  OWNS desired Capability Bindings
  OWNS desired Model Binding foundation
  REFERENCES Workspace / State / Knowledge / Policy

Agent Instance
  REFERENCES Agent Definition
  OWNS one effective Runtime Binding
  OBSERVES Runtime Conditions and Recovery Assessment
  ROUTES_TO opaque Runtime realization only through Runtime Provider translation

Runtime Binding
  RESOLVES_THROUGH Runtime Provider Registry
  REFERENCES Runtime Package metadata
Runtime Provider Registry
  REFERENCES eligible Runtime Provider interfaces
Runtime Provider
  REALIZES the selected Instance Binding in a native system

Capability Binding
  BINDS_TO one Capability Definition
  RESOLVES_THROUGH Capability Provider Registry
  REFERENCES Policy / Permission / Human Gate as applicable
Capability Provider Registry
  REFERENCES eligible Capability Provider interfaces
Capability Provider
  INVOKES the native capability endpoint/tool

Task / Workflow node
  OWNS logical Execution Identity
  ROUTES_TO one selected Agent Instance for one execution attempt/context
Execution Identity
  CORRELATES_WITH Runtime-native and Capability-native IDs
```

The inverse `Agent Definition -> Agent Instance` relation is a referenced-by
set, not lifecycle ownership: Instances reference exactly one Definition
identity/version, while one Definition may be referenced by many Instances.
The Agent Control Plane owns both resource lifecycles. A Definition does not
silently cascade-delete independently managed Instances.

### Required relationship decisions

| Source | Type | Target | Ownership meaning |
| --- | --- | --- | --- |
| Agent Definition | referenced by | Agent Instance | Definition does not own Instance lifecycle |
| Agent Definition | OWNS | desired Runtime Binding template | Embedded desired policy; not the effective native association |
| Agent Definition | OWNS | desired Capability Bindings | Embedded governed capability intent |
| Agent Definition | OWNS | desired Model Binding | Thin embedded foundation only |
| Agent Definition | REFERENCES | Workspace / State / Knowledge | Target lifecycle remains external/domain-owned |
| Agent Instance | REFERENCES | Agent Definition | Exact logical definition relationship; no ownership inversion |
| Agent Instance | OWNS | effective Runtime Binding | One authoritative effective Binding; no duplicate desired configuration |
| Agent Instance | OBSERVES | Runtime Conditions | Provider-normalized evidence recorded by Control Plane |
| Agent Instance | OBSERVES | Recovery Assessment | Instance reconciler owns final assessment |
| Task/Workflow Execution | ROUTES_TO | Agent Instance | Platform logical routing; selection precedes Provider translation |
| Runtime Binding | RESOLVES_THROUGH | Runtime Provider Registry | Registry selects eligible Provider/package combination |
| Runtime Binding | REFERENCES | Runtime Package | Immutable/versioned metadata identity |
| Runtime Provider Registry | REFERENCES | Runtime Provider | Metadata selects interface implementation/version |
| Runtime Provider | REALIZES | effective Runtime Binding | Provider adapts; it does not own Instance identity |
| Capability Binding | BINDS_TO | Capability Definition | Binding governs semantic use of exactly one Capability Definition/version |
| Capability Binding | RESOLVES_THROUGH | Capability Provider Registry | Selection occurs in the Capability domain under policy |
| Capability Provider Registry | REFERENCES | Capability Provider | Metadata selects interface implementation/version |
| Capability Provider | INVOKES | native capability | Protocol/tool remains Provider-owned |
| Task / Workflow node | OWNS | Execution Identity | Identity lifecycle follows logical work |
| Execution Identity | CORRELATES_WITH | Provider-native IDs | Native IDs are subordinate evidence and never replace platform identity |

## 18. Cardinality Matrix

`Desired` describes platform intent. `Observed/runtime` describes realizations
or evidence and may differ without redefining Core semantics.

| Relationship | Desired cardinality | Observed/runtime cardinality | Constraint |
| --- | --- | --- | --- |
| Agent Definition -> Agent Instance | 1:N | 1:N | Each Instance references exactly one Definition identity/version; one Definition may have zero or many Instances |
| Agent Definition -> desired Runtime Binding template | 1:1 | Not applicable | One authoritative desired runtime selection template in v0.2; absence is invalid when instantiation requires runtime execution |
| Agent Definition -> desired Capability Binding | 1:N | 1:N effective projections | Zero or many distinct Capability Bindings; no generic Binding sharing implied |
| Agent Definition -> desired Model Binding | 0:1 | 0:1 resolved model route | Thin foundation; detailed routing/fallback awaits S5-SPIKE-005 |
| Agent Definition -> Workspace Reference | 0:1 | 0:1 available target | Optional thin reference; target lifecycle external |
| Agent Definition -> State Reference | 0:1 | 0:1 available target | Optional thin reference; continuity/portability not promised |
| Agent Definition -> Knowledge Reference | 1:N | 0:N available targets | Optional source references; no Knowledge resource lifecycle implied |
| Agent Instance -> Agent Definition | N:1 | N:1 | Exact Definition identity/version; no mutable duplicated definition authority |
| Agent Instance -> effective Runtime Binding | 1:1 | 1:1 resolved Binding or 1:0 while unresolved | Effective Binding is Instance-owned and derived from desired template plus authorized resolution |
| Agent Instance -> Runtime realization | 1:N temporal | 0:N active | Multiple active realizations are Provider-capability bounded; identity remains logical |
| Agent Instance -> Runtime Condition | 1:N | 0:N current conditions | Condition types are Runtime-domain owned |
| Agent Instance -> Recovery Assessment | 1:1 current | 0:1 current plus optional history deferred | Assessment is derived status, not a resource |
| Agent Instance -> Task execution | 1:N | 0:N | One Execution routes to one selected Instance at a time; a Task may own multiple Executions over time |
| Agent Instance -> Workflow execution | 1:N | 0:N | Relationship is through routed node/execution, not Workflow ownership |
| Runtime Binding -> Runtime Provider Registry | N:1 | N:1 resolution domain | One domain registry view may resolve many Bindings |
| Runtime Binding -> Runtime Package | N:1 | N:1 selected package per effective resolution | Many Bindings may reference the same immutable package metadata |
| Runtime Provider Registry -> Runtime Provider | 1:N | 1:N eligible records/interfaces | Exactly one Provider version is selected for one resolution result |
| Runtime Provider -> native realization | 1:N | 0:N | Provider may manage/connect to many realizations across Bindings |
| Capability Definition -> Capability Binding | 1:N | 1:N | Many Agent-owned Bindings may bind to one Capability Definition |
| Capability Binding -> Capability Provider Registry | N:1 | N:1 resolution domain | Resolution is domain-specific and policy constrained |
| Capability Provider Registry -> Capability Provider | 1:N | 1:N eligible records/interfaces | Exactly one Provider version is selected for one invocation/resolution context unless future policy explicitly defines fallback |
| Capability Provider -> native capability | N:N possible | N:N possible | A Provider may adapt many native operations; one semantic Capability may have multiple Provider implementations |
| Task / Workflow node -> Execution Identity | 1:N temporal | 1:N temporal | Re-execution may create another Execution; attempts remain subordinate context |
| Execution Identity -> Runtime-native IDs | 1:N | 0:N | Retries/replacements may yield multiple native IDs |
| Execution Identity -> Capability-native invocation IDs | 1:N | 0:N | One execution may invoke multiple capabilities or attempts |
| Multiple Agent Instances -> shared Gateway | N:1 possible | N:1 possible | Gateway identity is opaque topology, never logical routing identity |

The `1:1` Definition templates above mean one authoritative current desired
association per Definition in the minimal model, not a decision about field
serialization. Migration history, staged rollout, and multi-Binding switching
remain later schema/Contract questions.

## 19. Desired vs Effective Binding Model

Use a two-level model without duplicating authoritative configuration:

```text
Agent Definition
  OWNS desired Binding policy/template
        |
        | Instance creation or reconciliation
        v
Agent Instance
  OWNS effective/resolved Binding projection
        |
        | RESOLVES_THROUGH domain registry
        v
Provider version + compatible package/native target
```

### Desired Binding

- Definition-owned, portable semantic intent.
- Runtime intent identifies requirements, ownership mode, selection
  constraints, and reference intent without native topology.
- Capability intent identifies Capability Definition/version/operation use,
  Provider constraints, and governance references without protocol details.
- Model intent remains thin and carries requirements/policy association only.
- It is the sole authoritative desired configuration; Instances do not own a
  second mutable copy.

### Effective / resolved Binding

- Instance-owned observed/resolved projection for Runtime.
- Instance/invocation-context projection for Capability; authorization remains
  explicit at invocation and is never cached as permanent authority merely
  because resolution succeeded.
- Records the selected compatible Provider metadata, Runtime Package where
  applicable, normalized conditions, and bounded opaque references.
- Derived from the exact Definition identity/version plus policy and registry
  facts. Reconciliation refreshes the projection when an allowed dependency
  changes; it does not mutate Definition intent.
- Provider-native configuration stays opaque and Provider-owned.

Definition updates do not silently rewrite the authoritative intent of an
existing Instance. Whether an Instance follows a new Definition version is an
explicit lifecycle/reconciliation decision whose mechanics remain outside
Checkpoint B.

## 20. Runtime Binding Representation Analysis

| Resource-test question | Finding |
| --- | --- |
| Multiple Definitions reference one Binding? | No need proven. Definitions may express equivalent templates without sharing Binding identity. Shared Provider/package metadata supplies reuse. |
| Multiple Instances reference one Binding? | No. Each Instance needs its own effective resolution, conditions, realization ownership, and recovery context. |
| Independent lifecycle? | No. Desired template follows Definition; effective Binding follows Instance. |
| Independent desired state? | No. Desired runtime intent is owned by Definition and materialized for an Instance. |
| Independently reconciled? | No evidence. Agent Instance reconciliation coordinates Provider resolution, realization, conditions, and recovery. |
| Independent authorization? | No evidence. Authorization applies to Definition/Instance lifecycle, Provider/package eligibility, credentials, and policy references. |
| Independent observability? | No. Binding observations are meaningful in Instance context. |
| Independent versioning? | Provider, Package, Contract, and Definition versions already carry required version axes; a Binding resource version is not independently justified. |
| External Runtime ownership value? | It strengthens explicit ownership mode and opaque reference semantics, not independent Binding identity. |
| Would embedding prevent portability? | No. Portability depends on semantic Binding vocabulary and Provider isolation, not a separate API object. |
| First-class indirection cost? | Yes. It adds naming, sharing, RBAC, deletion, watch/reconcile, and stale-reference semantics without proven independent lifecycle. |

**Conclusion: EMBEDDED_BINDING.**

The Definition owns the desired Runtime Binding template; each Instance owns
one effective resolved Runtime Binding projection. Runtime Provider Registry
and Runtime Package remain referenced metadata. This conclusion uses existing
S5-ARCH-002 and S5-SPIKE-004 evidence and requires no new Runtime evidence.

## 21. Capability Binding Representation Analysis

| Resource-test concern | Finding |
| --- | --- |
| Reuse across Agents | Reuse belongs to Capability Definition and Provider metadata. A Binding expresses Agent-specific governed use and should not be shared as authority. |
| Per-Agent permissions | Policy/Permission references belong in the Agent-owned Binding context; actual authorization is re-evaluated per invocation. |
| Risk classification | Capability/operation owns semantic risk classification; Binding may narrow use but must not redefine it. |
| Policy / Human Gate attachment | References can be embedded without importing governance lifecycle. Gate satisfaction is not permanent Binding state. |
| Provider selection | Capability domain resolves through its registry after semantic and authorization checks. |
| Provider configuration | Provider-specific configuration remains bounded/opaque and Provider-translated. |
| Credential references | Governance owns the reference/value lifecycle; Binding only references it. |
| Capability Definition relationship | Each Binding binds to exactly one Capability Definition/version context; many Agent Definitions may independently bind to the same Capability. |
| Agent-specific override | May narrow desired use within policy; cannot expand Capability or governance authority. |
| Independent lifecycle/reconciliation | Not proven. Binding lifecycle follows Agent Definition intent; effective resolution follows Instance/invocation context. |
| Independent sharing/authorization | Sharing a Binding would risk sharing authority. Authorization remains explicit per actor/invocation. |
| First-class indirection cost | Adds identity, RBAC, deletion, sharing, and reconciliation semantics without evidence of independent ownership. |

**Conclusion: EMBEDDED_BINDING.**

Capability Binding is embedded governed intent owned by Agent Definition and
resolved into an effective Instance/invocation projection. This differs from
Runtime Binding: it may be one of many Definition-owned capability associations
and permission is always re-evaluated before invocation. The conclusion uses
existing S5-SPIKE-003 evidence and requires no new Capability evidence.

## 22. Logical Routing Relationship Model

```text
Agent Definition
  referenced by 1:N eligible Agent Instances
        |
Logical Router (Control Plane ownership)
  ROUTES_TO one eligible Agent Instance for the Execution context
        |
Agent Instance
  OWNS one effective Runtime Binding
        |
Runtime Binding RESOLVES_THROUGH Runtime Provider Registry
        |
selected Runtime Provider
  REALIZES / translates only the selected Binding
        |
0:N opaque native realizations
```

- Platform routing inputs may include desired Instance state, normalized
  eligibility/health, explicit authorized target, and policy.
- The Provider does not choose the logical Instance. It may select among
  multiple native realizations only within the selected Instance Binding.
- A shared Gateway is an `N:1` possible native topology. It does not become a
  router, Agent Instance, or caller-visible selector.
- A replacement realization preserves Agent Instance identity and may produce
  another opaque realization reference.
- No load-balancing algorithm, scheduler internals, or native topology schema
  is defined.

## 23. Execution Identity Propagation Map

```text
Task / Workflow node
  OWNS Execution Identity
        |
        | propagated in routing context
        v
Logical Router ROUTES_TO Agent Instance
        |
        v
Runtime Provider -> Runtime-native execution ID
        |                 CORRELATES_WITH
        +---------------- Execution Identity
        |
        | capability invocation context
        v
Capability Provider -> Capability-native invocation ID
                          CORRELATES_WITH
                          Execution Identity
```

- Execution Identity is created before logical routing or Provider invocation.
- It remains stable across Provider translation, native retries that preserve
  logical intent, realization replacement, and inline/deferred completion.
- Attempts and domain-local invocation context are subordinate, not peer
  platform identities.
- True independently retryable child work may receive a child Execution
  Identity correlated to its parent; exact hierarchy/schema is unfrozen.
- Runtime-native and Capability-native IDs are `0:N` opaque evidence. They are
  never accepted as platform identity or logical routing input.

## 24. Lifecycle / Deletion Consequence Matrix

Only the task-authorized consequence vocabulary is used.

| Event | Classification | Required semantic consequence |
| --- | --- | --- |
| Delete Agent Definition while Instances reference it | BLOCK / ORPHAN_NOT_ALLOWED | An Instance may not lose its exact Definition relationship silently; explicit Instance termination/migration is required first |
| Delete Agent Definition with no dependent Instances | CASCADE | Embedded desired Runtime/Capability/Model Bindings disappear with their owner; referenced external targets are not deleted |
| Terminate Agent Instance | RECONCILE | Stop routing new work; Provider removes only Provider-owned realizations or detaches from external ones; in-flight execution disposition remains Contract debt |
| Change desired Runtime Binding template | RECONCILE | Produce an authorized effective resolution; verify new semantics before eligibility; exact rollout/rebinding mechanics deferred |
| Effective Runtime Provider becomes unavailable | DEGRADED | Instance loses affected eligibility/condition; Provider substitution occurs only through allowed resolution policy |
| Referenced Runtime Package unavailable/incompatible | DEGRADED | Resolution fails honestly; unknown compatibility is not accepted |
| Remove Capability Binding | RECONCILE | Future invocation becomes ineligible/denied; previously granted discovery does not preserve authority; in-flight side-effect semantics deferred |
| Delete Capability Definition while Bindings reference it | BLOCK / ORPHAN_NOT_ALLOWED | Binding cannot silently retarget or become an untyped native tool reference |
| Delete Capability Definition with no references | CASCADE | Definition-owned metadata may be removed; Providers/native endpoints are not deleted |
| Capability Provider unavailable | DEGRADED | Resolution/invocation fails with Capability-domain normalized semantics; no silent protocol fallback |
| Workspace/State/Knowledge/Policy target unavailable | DEGRADED | Owner records an honest unresolved/degraded condition appropriate to the domain; target is never recreated implicitly |
| Provider Registry metadata entry removed | RECONCILE | Affected effective resolutions are re-evaluated; existing native object ownership does not transfer automatically |
| External native realization disappears | RECONCILE | Provider normalizes evidence and Instance reconciler performs recovery assessment; restart alone is not recovery |
| Delete opaque native ID/evidence target | DETACH | Bounded correlation may become unavailable; platform identity remains intact |

`CASCADE` applies only to embedded values owned by the deleted object, not to
independently owned Agent Instances, Providers, Packages, external references,
or native systems. Implementation mechanics, grace periods, finalizers, and
in-flight cancellation are intentionally undefined.

## 25. Golden Demo Relationship Traceability

| Proof | Relationship evidence required |
| --- | --- |
| P1 Business task execution | Task/Workflow OWNS Execution Identity; router ROUTES_TO Instance; Runtime Provider realizes selected Binding; Capability Provider invokes semantic Capability |
| P2 Capability portability | Agent Definition-owned Capability Binding BINDS_TO stable Capability Definition and RESOLVES_THROUGH domain registry; Provider/native endpoint can change without Agent-side semantic change |
| P3 Runtime portability | Definition desired Runtime Binding yields Instance effective Binding that RESOLVES_THROUGH registry; Provider/package/realization can change without Core or Digital Employee role change |
| P4 Stable logical Agent Instance identity | Instance REFERENCES Definition and remains stable across `1:N temporal` realizations and `N:1` shared Gateway topology |
| P5 Human Gate / governance | Capability Binding REFERENCES Policy/Permission/Human Gate; authorization is evaluated before each Provider invocation |
| P6 Failure -> verified Recovery | Provider OBSERVES native evidence; Instance reconciler owns Recovery Assessment; replacement/restart alone cannot satisfy recovery |
| P7 Observability | Execution Identity CORRELATES_WITH all native IDs; domain Conditions/Outcomes remain attributable without exposing native topology as Core identity |

Strong portability proof remains possible without first-class Binding resources:
switch the Runtime Provider by resolving the same semantic desired Runtime
Binding, or switch the Capability Provider by resolving the same Capability
Definition/Binding, without changing Control Plane Core or Agent-side business
semantics.

## 26. Checkpoint B Recommendations

1. Fix Agent Definition -> Agent Instance at `1:N`; each Instance references
   exactly one Definition identity/version, and Definition does not own Instance
   lifecycle.
2. Adopt the two-level Binding model: Definition owns authoritative desired
   policy/template; Instance or invocation context owns derived effective
   resolution. Never duplicate authoritative desired configuration.
3. Represent Runtime Binding as `EMBEDDED_BINDING`, with one effective Binding
   owned by each Agent Instance.
4. Represent Capability Binding as `EMBEDDED_BINDING`, with `0:N` governed
   desired Bindings owned by Agent Definition and authorization re-evaluated at
   invocation.
5. Preserve `Agent Instance -> realization` as `1:N temporal`, `0:N active`
   bounded by Provider capability; preserve shared Gateway as opaque `N:1`
   possible topology.
6. Resolve Providers only through domain registries. Runtime and Capability
   resolution are analogous patterns, not one universal registry or schema.
7. Preserve Control Plane ownership of logical Instance routing and Provider
   ownership of translation within the selected Binding.
8. Propagate embedded Platform Execution Identity end to end; native IDs only
   `CORRELATE_WITH` it.
9. Apply conservative deletion: block orphaning of independently owned logical
   objects, cascade only embedded values, reconcile changed Bindings, and mark
   unavailable dependencies degraded.
10. Carry field serialization, rollout mechanics, in-flight disposition,
    condition vocabulary, and detailed schema into later authorized work.

## 27. Human Decision Table — Checkpoint B

### B01 — Agent Definition -> Agent Instance cardinality

**Recommendation:** `1:N`; each Instance `REFERENCES` exactly one Definition
identity/version, and Definition does not own Instance lifecycle.
**Evidence:** D30 and S5-SPIKE-004 H-INS-03.
**Alternatives:** `1:1`; native-derived Instance identity.
**Trade-off:** Independent Instance lifecycle adds coordination but is required
for scaling, routing, and recovery.
**Schema impact:** Later schema must express exact Definition reference; no
field is defined here.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### B02 — Definition vs Instance Binding ownership

**Recommendation:** Two-level model: Definition `OWNS` authoritative desired
Binding policy/template; Instance or invocation context owns the derived
effective/resolved projection.
**Evidence:** D33, D34, S5-ARCH-002, and S5-SPIKE-003/004.
**Alternatives:** Definition-only effective Binding; Instance-owned duplicate
desired configuration.
**Trade-off:** Derived projection requires provenance but avoids duplicated
authority and supports Provider resolution.
**Schema impact:** Later schema must separate desired intent from effective
observation; serialization is undecided.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### B03 — Runtime Binding final representation

**Recommendation:** `EMBEDDED_BINDING`.
**Evidence:** No independent sharing, lifecycle, reconciliation, authorization,
or observability is proven; portability follows semantic vocabulary and
Provider isolation.
**Alternatives:** `FIRST_CLASS_RESOURCE`; `REFERENCE_TO_CONFIGURATION`;
`INSUFFICIENT_EVIDENCE`.
**Trade-off:** Smaller API and direct Instance ownership versus no independent
Binding reuse/history object.
**Schema impact:** Later Definition and Instance schemas require distinct
desired/effective placement, not a RuntimeBinding CRD.
**Freeze impact:** None; Runtime Contract remains unfrozen.
**Human Decision:** ACCEPT.

### B04 — Capability Binding final representation

**Recommendation:** `EMBEDDED_BINDING`.
**Evidence:** Binding expresses Agent-specific governed use; shared identity
could incorrectly share authority, and no independent reconciler is proven.
**Alternatives:** `FIRST_CLASS_RESOURCE`; `REFERENCE_TO_CONFIGURATION`;
`INSUFFICIENT_EVIDENCE`.
**Trade-off:** Clear Agent ownership and smaller API versus no independently
managed reusable grant object.
**Schema impact:** Later Agent Definition schema must support `0:N` semantic
Bindings and effective resolution without protocol leakage.
**Freeze impact:** None; Capability Contract remains unfrozen.
**Human Decision:** ACCEPT.

### B05 — Agent Instance -> Runtime realization cardinality

**Recommendation:** `1:N temporal`, with `0:N active` bounded by declared
Runtime Provider capability.
**Evidence:** S5-SPIKE-004 replacement and multi-realization evidence.
**Alternatives:** Permanent `1:1`; universal Runtime Instance wrapper.
**Trade-off:** Faithful heterogeneous topology versus more complex observation
and recovery correlation.
**Schema impact:** Later status must allow bounded opaque references; no native
schema enters Core.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### B06 — Shared Gateway relationship

**Recommendation:** `N:1 possible` opaque native topology; Gateway never owns
or replaces logical Instance identity.
**Evidence:** S5-SPIKE-004 shared-Gateway proof and D30/D34.
**Alternatives:** Gateway-as-Instance; expose Gateway as logical router.
**Trade-off:** Preserves semantics across runtimes while limiting native
topology visibility.
**Schema impact:** At most bounded opaque realization evidence later.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### B07 — Runtime Provider resolution relationship

**Recommendation:** Runtime Binding `RESOLVES_THROUGH` Runtime Provider Registry;
the selected Provider `REALIZES` only that Binding and `REFERENCES` compatible
Runtime Package metadata.
**Evidence:** Accepted S5-ARCH-002 registry/provider/package model.
**Alternatives:** Core branches on Runtime family; Binding directly embeds
Provider code/native target.
**Trade-off:** Explicit compatibility and replaceability versus registry
metadata/versioning overhead.
**Schema impact:** Later Contract must express resolution inputs/results; none
are defined here.
**Freeze impact:** None.
**Human Decision:** ACCEPT WITH CONSTRAINT — registry remains INTERNAL_METADATA,
not a public API resource.

### B08 — Capability Provider resolution relationship

**Recommendation:** Capability Binding `RESOLVES_THROUGH` the domain Capability
Provider Registry after authorization; selected Provider `INVOKES` native
Capability.
**Evidence:** D33 and S5-SPIKE-003 discovery/permission/Provider isolation.
**Alternatives:** Universal Provider Registry; Agent selects MCP/tool directly.
**Trade-off:** Semantic portability and policy enforcement versus explicit
domain resolution metadata.
**Schema impact:** Later Capability Contract work; no registry CRD implied.
**Freeze impact:** None.
**Human Decision:** ACCEPT WITH CONSTRAINT — registry remains INTERNAL_METADATA,
not a public API resource.

### B09 — Capability Definition -> Binding relationship

**Recommendation:** One Capability Definition is targeted by `1:N` Agent-owned
Capability Bindings; each Binding `BINDS_TO` one Definition/version context.
**Evidence:** S5-SPIKE-003 semantic identity and reuse boundary.
**Alternatives:** Embed Capability implementation in Agent; share one Binding
as a permission grant across Agents.
**Trade-off:** Reuse without shared authority versus repeated Agent-specific
Binding intent.
**Schema impact:** Later version/reference/cardinality representation only.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### B10 — Execution Identity propagation relationship

**Recommendation:** Task/Workflow node `OWNS` and propagates one embedded
Execution Identity through routing, Runtime Provider, and Capability Provider.
**Evidence:** D31 and AP-S5-011 cross-track evidence.
**Alternatives:** Universal Execution resource; separate unrelated identities
per domain.
**Trade-off:** End-to-end correlation with small surface versus deferred
standalone execution lifecycle/query API.
**Schema impact:** Later shared primitive placement; no Execution CRD.
**Freeze impact:** None; shared execution schema remains unfrozen.
**Human Decision:** ACCEPT.

### B11 — Native ID correlation relationship

**Recommendation:** Runtime-native and Capability-native IDs `CORRELATE_WITH`
Execution Identity at `0:N`; they never replace it.
**Evidence:** D31, S5-SPIKE-003, and S5-SPIKE-004.
**Alternatives:** Native ID as platform execution/routing identity.
**Trade-off:** Stable portability and correlation versus bounded mapping and
retention needs.
**Schema impact:** Later bounded opaque-reference shape only.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### B12 — Logical routing ownership relationship

**Recommendation:** Control Plane router `ROUTES_TO` one eligible logical Agent
Instance; Runtime Provider translates only the selected effective Binding.
**Evidence:** D34 and AP-S5-010.
**Alternatives:** Provider/Gateway chooses logical Instance; caller selects
native realization.
**Trade-off:** Governance and stable semantics versus later need for explicit
platform routing policy.
**Schema impact:** No algorithm or scheduler schema is defined.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### B13 — Runtime Binding lifecycle/deletion consequence

**Recommendation:** `RECONCILE` changes through owning Definition/Instance;
termination cleans Provider-owned realizations and `DETACH`es external ones.
**Evidence:** S5-ARCH-002 ownership-mode and cleanup boundary; D35.
**Alternatives:** Independent Binding deletion lifecycle; unconditional cascade
of native objects.
**Trade-off:** Ownership-safe behavior versus deferred rollout/in-flight
mechanics.
**Schema impact:** Later ownership/provenance semantics; no fields here.
**Freeze impact:** None.
**Human Decision:** ACCEPT WITH CONSTRAINT — reconciliation belongs to the
owning platform object; no RuntimeBinding resource or controller is implied.

### B14 — Capability Binding lifecycle/deletion consequence

**Recommendation:** Removal triggers `RECONCILE`; future invocations are
ineligible/denied, while native Provider/Capability lifecycle is unaffected.
**Evidence:** S5-SPIKE-003 explicit authorization and discovery separation.
**Alternatives:** Independent Binding resource deletion; implicit native tool
deletion.
**Trade-off:** Immediate semantic revocation boundary versus deferred in-flight
side-effect rules.
**Schema impact:** Later policy and invocation semantics only.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### B15 — Agent Definition deletion consequence

**Recommendation:** `BLOCK / ORPHAN_NOT_ALLOWED` while Instances reference it;
when unreferenced, `CASCADE` only its embedded Binding values.
**Evidence:** Independent D30 lifecycle and exact Definition relationship.
**Alternatives:** Cascade-delete Instances; allow orphaned Instances.
**Trade-off:** Preserves explicit lifecycle safety at the cost of ordered
retirement.
**Schema impact:** Later deletion/reference policy; implementation mechanics
remain undefined.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### B16 — Agent Instance termination consequence

**Recommendation:** `RECONCILE`: remove routing eligibility, assess/settle
semantic state, remove only owned realizations, and detach external ones.
**Evidence:** D30, D35, S5-ARCH-002 ownership boundaries, S5-SPIKE-004 recovery.
**Alternatives:** Treat Pod/process deletion as Instance termination; always
cascade native state.
**Trade-off:** Correct ownership and recovery semantics versus deferred
in-flight execution and grace-period policy.
**Schema impact:** Later lifecycle/deletion vocabulary; no implementation here.
**Freeze impact:** None.
**Human Decision:** ACCEPT WITH CONSTRAINT — external realizations default to
DETACH or Provider-specific safe cleanup and are never unconditionally deleted.

## 28. Execution Semantic Map

```text
Desired State (domain owner)
        |
        v
Task / Workflow execution state
  OWNS Platform Execution Identity
        |
        | ROUTES_TO
        v
Agent Instance
  OBSERVES Instance Conditions
  OWNS effective Runtime Binding
        |
        v
Runtime Provider interaction
  normalizes Runtime Conditions / interaction result
  CORRELATES native Runtime IDs
        |
        | optionally invokes
        v
Capability Provider invocation
  authorizes before handoff
  normalizes Capability Outcome
  CORRELATES native invocation IDs
        |
        v
Task Outcome / Workflow Outcome

Native change or failure
  -> Provider-normalized evidence
  -> Agent Instance reconciliation
  -> Recovery Assessment
```

Execution state, observed conditions, outcomes, and recovery assessments are
not synonyms. Acceptance and running describe execution progress. Conditions
describe observed propositions. Outcomes describe domain completion meaning.
Recovery Assessment answers whether promised logical semantics were restored
and verified.

## 29. Execution Identity Boundary

Platform Execution Identity remains `CORE_VALUE_OBJECT / EMBEDDED_VALUE`.

| Responsibility | Boundary |
| --- | --- |
| Generation ownership | Execution-owning Task/Workflow Control Plane creates it before routing or Provider handoff |
| Scope | One logical performance of requested work, not Task, Workflow, Agent Instance, Provider request, or native realization identity |
| Stability | Stable across logical routing, Provider translation, native retries that preserve intent, realization replacement, and inline/deferred completion |
| Task relationship | A Task may own multiple logical Executions over explicit re-execution; an Execution belongs to one owning Task or Workflow-node context |
| Workflow relationship | Workflow/node coordinates Execution identity and preserves node/aggregate ownership; Workflow identity does not replace it |
| Agent Instance relationship | Execution is routed to one logical Instance at a time; Instance does not own Execution identity |
| Parent/child | Independently retryable or fan-out child work may have a child identity related to a parent; attempts remain subordinate context |
| Runtime propagation | Runtime Provider propagates the identity and returns subordinate native correlation evidence |
| Capability propagation | Capability Provider receives the same identity plus domain-local invocation context and returns subordinate native correlation evidence |
| Authorization | Identity enables correlation but grants no authority; every domain applies its own authorization/policy |
| Persistence | Embedded with the owning execution context; no independent desired state or reconciler |

No universal Execution resource or TaskExecution resource is justified. Exact
generation algorithm, serialized representation, uniqueness scope, replay, and
retention remain later Contract work.

## 30. Execution Correlation Analysis

Execution Correlation is a **relationship primitive**, not another Core value
object. Platform Execution Identity plus bounded opaque native correlation
references are sufficient for the proven needs.

```text
Platform Execution Identity
  CORRELATES_WITH 0:N Runtime realization/run/session references
  CORRELATES_WITH 0:N Capability invocation/job references
  may relate to parent/child Platform Execution Identity
```

Creating a separate Execution Correlation object would duplicate identity and
introduce lifecycle, ownership, retention, and consistency questions without
independent semantics. Correlation context may carry bounded propagation
metadata, but it does not create authority, guarantee native idempotency, or
import Provider-native structure into Core.

## 31. Task Outcome Boundary

Task Outcome remains `OUTCOME / EMBEDDED_VALUE`, owned by the Task domain.

- Submission accepted and execution running are mutable **execution states**,
  not terminal Task Outcomes.
- Terminal success means the Task's requested work satisfied Task-domain
  completion semantics, not merely that a Provider call returned successfully.
- Terminal failure means Task-domain completion failed after applying its
  applicable attempt/retry semantics.
- Cancellation and timeout are distinct Task-domain dispositions only where
  their Contracts support them.
- Unknown is legitimate when the platform cannot determine terminal
  disposition; it must not be silently converted to failure or success.
- Provider results and native exit states are evidence. The Task domain owns
  the normalized Task meaning.

No exact category names are frozen. A Task may have multiple logical Executions
over explicit re-execution, but this does not create a TaskExecution resource.

## 32. Workflow Outcome Boundary

Workflow Outcome remains `OUTCOME / EMBEDDED_VALUE`, owned by the Workflow
domain. It is not a generic Execution Outcome and cannot be derived by merely
copying the last Task Outcome.

| Concern | Workflow-domain meaning |
| --- | --- |
| Node outcomes | Inputs to DAG/coordination semantics; each retains Task/node ownership |
| Aggregate outcome | Workflow's conclusion over dependency, skip, failure, and completion policy |
| Partial completion | Some nodes may complete while the aggregate remains running, blocked, failed, or otherwise unresolved |
| Human Gate | Waiting is mutable Workflow execution state; approval/rejection is governance evidence consumed by Workflow policy |
| Retry/recovery | Node re-execution and recovery evidence affect aggregation but do not replace Workflow ownership |
| Unknown | Used when aggregate disposition cannot be determined from available evidence |

Exact aggregation, partial-completion, retry, and Human Gate vocabularies remain
unfrozen and are not expanded into workflow-engine design here.

## 33. Runtime Condition Boundary

Runtime Condition is an embedded observed proposition owned by the Runtime
domain Control Plane and normalized by the Runtime Provider from native
evidence.

Candidate concepts supported by existing evidence include Runtime availability,
infrastructure availability where relevant, dependency readiness where the
Provider can establish it, Binding/configuration usability, and applicability.
`TaskReady` remains rejected as a Runtime Condition because Task readiness is
owned by the Task/Workflow domain.

Runtime Condition does not expose Provider-native health vocabulary and does
not equate Pod readiness, Gateway liveness, or process existence with platform
Runtime availability. The Provider observes and normalizes; the platform owns
the semantic condition type and its interpretation.

The candidate truth meanings `TRUE`, `FALSE`, `UNKNOWN`, and `NOT_APPLICABLE`
are semantically useful but not frozen names or representation.

## 34. Agent Instance Condition Boundary

Agent Instance Condition is an embedded observed proposition owned by the Agent
Instance Control Plane. It derives logical meaning from desired state, effective
Binding resolution, Runtime Conditions, routing policy, governance, and recovery
evidence without simply mirroring native health.

It must be able to answer, at semantic level:

- whether the logical Instance is eligible to participate in routing;
- whether its effective Runtime Binding is usable;
- whether required realization evidence is available;
- whether promised Instance semantics are degraded;
- whether recovery is required, unresolved, or verified.

An alive Pod, Gateway, or runtime process is neither necessary nor sufficient
for every Agent Instance condition. Provider evidence is input; the Agent
Instance reconciler owns the final condition meaning.

## 35. Capability Outcome Boundary

Capability Outcome remains `OUTCOME / EMBEDDED_VALUE`, owned by the Capability
domain and normalized by the Capability Provider where native interaction
occurs.

| Failure stage | Ownership boundary |
| --- | --- |
| Authorization denial | Platform governance/Capability domain before Provider or native handoff; proves no native execution occurred |
| Input validation failure | Capability Contract/domain before or during Provider validation; not a Runtime failure |
| Provider unavailable | Capability resolution/Provider boundary; Capability invocation cannot be handed off |
| Provider protocol failure | Provider normalizes transport/protocol evidence into Capability-domain failure |
| Remote execution failure | Provider normalizes native business/execution evidence without exposing protocol types |
| Timeout | Capability-domain disposition subject to handoff and cancellation knowledge; retry safety is not assumed |
| Unknown | Platform cannot determine native or terminal business disposition from available evidence |

Business output and Capability-specific failure meaning never become Runtime
Outcome. Candidate normalized error categories from S5-SPIKE-003 remain
unfrozen.

## 36. Runtime Interaction vs Capability Invocation

| Concern | Runtime Interaction | Capability Invocation | Shared? |
| --- | --- | --- | --- |
| Primary semantic | Carry/observe Agent execution through selected Runtime Binding | Invoke a governed enterprise Capability operation | No |
| Submission | Handoff to resolved Runtime Provider/realization context | Handoff only after Capability authorization and validation | Minimal submission disposition only |
| Acceptance | Runtime domain accepts responsibility for interaction | Capability domain/Provider accepts responsibility for invocation | Minimal accepted/rejected-before-handoff distinction only |
| Inline/deferred | May complete inline or return Runtime observation correlation | May return business result inline or deferred observation correlation | Completion disposition only |
| Observation | Runtime conditions and interaction state | Capability invocation/business outcome state | No |
| Streaming | Runtime/session semantics, if declared | Capability operation/protocol semantics, if declared | DOMAIN_SPECIFIC / DEFERRED |
| Cancellation | Runtime/native lifecycle semantics | Capability side-effect and operation semantics | No |
| Authorization | Runtime eligibility, Instance selection, Binding/policy | Explicit Capability/operation permission before handoff | Policy precedence only; decisions remain domain-specific |
| Native correlation | Runtime realization/run/session evidence | Invocation/request/job evidence | Opaque correlation-reference semantics only |
| Terminal outcome | Runtime interaction result/observation | Capability business outcome | No |
| Retry safety | Runtime interaction/replay knowledge | Capability idempotency/side-effect knowledge | No |

D32 Option C is preserved: structurally similar envelopes do not imply shared
lifecycle, authorization, cancellation, retry, streaming, payload, or outcome
meaning.

## 37. Recovery Assessment Boundary

Recovery Assessment remains `STATUS / EMBEDDED_VALUE`, owned by the Agent
Instance Control Plane. It answers whether the platform-owned logical workload
has restored and verified its promised semantics. It does not answer merely
whether a native process restarted.

### Evidence layers

| Evidence | Owner | What it proves |
| --- | --- | --- |
| Process restarted | Kubernetes/runtime-native supervision | A native process action occurred; not semantic recovery |
| Infrastructure restored | Infrastructure/Kubernetes | Required substrate became available; not Instance usability |
| Runtime available | Runtime Provider normalization / Runtime domain | Runtime-domain predicates are satisfied to the supported evidence level |
| Effective Binding usable | Instance reconciler using registry/Provider evidence | Selected Instance association can be translated and observed |
| Agent Instance semantically usable | Agent Instance Control Plane | Required logical routing and promised Instance predicates are satisfied |
| Execution state recovered | Task/Workflow domain | In-flight work resumed, restarted, failed, or remains unknown according to its Contract |
| State restored | State owner/Provider where explicitly supported | Promised continuity predicate only; no universal portability implication |

### Minimum assessment evidence

The Control Plane may conclude recovery only when applicable evidence supports:

1. desired logical state is restored;
2. the same stable Agent Instance identity is retained;
3. effective Runtime Binding is resolved and usable;
4. required Runtime and Agent Instance conditions are acceptable;
5. logical routing eligibility is restored;
6. execution identity continuity/disposition is established where in-flight
   execution is within the recovery promise; and
7. state continuity is verified only when that Instance/Provider explicitly
   promised it.

If applicable evidence disproves a predicate, the assessment is not recovered.
If required evidence cannot be obtained, the assessment remains unknown. The
spike-local labels `RECOVERED`, `NOT_RECOVERED`, and `RECOVERY_UNKNOWN` describe
useful meanings but remain unfrozen vocabulary.

## 38. Unknown / N/A Semantics

Unknown is a legitimate platform state, not an error-handling shortcut.

| Meaning | Semantic rule |
| --- | --- |
| True | Available evidence establishes the proposition |
| False | Available evidence establishes that the proposition is not satisfied |
| Unknown | The platform cannot currently determine the proposition from available/fresh evidence |
| Not applicable | The proposition does not apply to the selected Provider, ownership mode, or domain context |

The four-way condition truth meaning is safe as a minimal shared primitive
because its epistemic semantics are identical across Runtime and Agent Instance
conditions. Condition types and causes remain domain-owned. Outcome `unknown`
uses the same evidence-insufficiency principle but remains a domain outcome
category rather than a universal Status value. Not-applicable is not a substitute
for unsupported behavior, and unknown is never coerced into false.

Exact names, representation, transition rules, and staleness thresholds remain
unfrozen.

## 39. Human Gate Thin Execution Boundary

Human Gate remains a thin governance foundation split across two owners:

- Policy/Governance `OWNS` the gate reference, decision authority, decision
  evidence, and approved/rejected meaning.
- Task/Workflow `OWNS` mutable execution state such as waiting for a referenced
  decision, resuming after approval, or applying domain policy after rejection.

Waiting for human decision is not a terminal Task or Workflow Outcome. Approval
is not execution success. Rejection is governance evidence that may cause a
Task/Workflow-domain terminal or non-terminal transition according to policy.
The platform must not invoke a gated Capability before authorization is
satisfied.

This boundary creates no Human Feedback architecture, new Workflow subsystem,
gate resource, or detailed approval lifecycle.

## 40. Desired / Execution / Observation / Outcome Matrix

| Concept | Owner | Source of truth | Nature | Control Plane responsibility | Provider responsibility |
| --- | --- | --- | --- | --- | --- |
| Desired State | Owning domain Control Plane | Kubernetes Control Plane | Mutable intent until lifecycle policy fixes it | Validate, authorize, reconcile toward semantics | Translate supported intent; never redefine it |
| Execution State | Task/Workflow or domain interaction owner | Owning Control Plane execution context | Mutable progress; may reach terminal disposition | Coordinate submission, routing, waiting, retry/recovery policy | Report handoff/observation evidence within declared capability |
| Observed Condition | Runtime or Agent Instance domain | Control Plane status from observed evidence | Mutable truth assertion with freshness/applicability | Define type/meaning and record honest truth | Observe, normalize, timestamp, and bound native evidence |
| Outcome | Task, Workflow, or Capability domain | Owning domain record/status | Domain completion meaning; terminality explicitly known or unknown | Interpret domain semantics and persist normalized result | Normalize native result only for its domain |
| Recovery Assessment | Agent Instance Control Plane | Embedded Instance status/evidence boundary | Mutable derived assessment; may remain unknown | Evaluate promised predicates and own final logical assessment | Perform declared native actions and normalize evidence |

Desired state is not inferred from observation. Provider acceptance is not Task
success. A condition is not an outcome. A recovery assessment may depend on
conditions and execution evidence but does not replace either.

## 41. Provider Normalization Boundary

### Runtime Provider

```text
native health / events / interaction results
  -> Runtime Provider translation, redaction, classification
  -> platform Runtime Conditions / Runtime interaction result
  -> Agent Instance reconciler consumes evidence
```

The Runtime Provider owns native observation, freshness reporting, translation,
bounded safe diagnostics, and opaque references. The platform owns Runtime
condition meaning, Instance condition derivation, routing eligibility, and
Recovery Assessment.

### Capability Provider

```text
native protocol / result / error
  -> Capability Provider translation, redaction, classification
  -> Capability Outcome
  -> Task / Workflow consumes domain result
```

The Capability Provider does not process an invocation denied before handoff
and cannot broaden permission. It normalizes protocol and remote evidence but
does not redefine Capability identity, business success, or Task/Workflow
completion.

For both domains, raw exceptions, secret-bearing diagnostics, native schemas,
and unbounded payloads do not cross into Core status.

## 42. Shared Primitive Matrix

| Candidate | Disposition | Minimum shared semantic | Explicitly not shared |
| --- | --- | --- | --- |
| Platform Execution Identity | SHARED_CORE_PRIMITIVE | One stable logical execution identity propagated end to end | Independent resource, authorization, domain payload |
| Correlation reference | SHARED_CORE_PRIMITIVE | Relationship from platform identity to bounded opaque evidence reference | Separate Correlation object, native schema |
| Timestamp semantics | SHARED_CORE_PRIMITIVE | Observation/decision time and evidence freshness meaning | Domain transition policy, clock/storage representation |
| Condition truth state | SHARED_CORE_PRIMITIVE | True, false, unknown, and not-applicable meanings | Condition types, predicates, reason taxonomy |
| Error category | DOMAIN_SPECIFIC | Runtime and Capability classify errors under their own semantics | Universal error taxonomy; only bounded safe diagnostic shape is shared |
| Terminality | SHARED_CORE_PRIMITIVE | Whether a result/disposition is terminal, non-terminal, or not determinable | Domain success/failure meaning and progress states |
| Outcome status | DOMAIN_SPECIFIC | Task, Workflow, Capability, and Runtime retain their own result meaning | Universal Outcome/Result object or exact enum |
| Retry metadata | DOMAIN_SPECIFIC | Owner records retryability only when safely knowable | Cross-domain retry promise, idempotency assumption |
| Native reference | SHARED_CORE_PRIMITIVE | Bounded opaque reference semantics for correlation/evidence/cleanup | Native value structure, routing identity, authority |
| Submission disposition | SHARED_CORE_PRIMITIVE | Rejected before handoff versus accepted by responsible domain | Authorization reason, Runtime/Capability acceptance meaning |
| Completion disposition | SHARED_CORE_PRIMITIVE | Inline terminal result versus deferred observation relationship | Deferred durability/availability guarantee |
| Safe diagnostic shape | SHARED_CORE_PRIMITIVE | Stable bounded reason, safe message, observation context, optional opaque evidence reference | Domain reason vocabulary, raw native diagnostics |
| Streaming | DEFERRED | No proven identical cross-domain semantics | Universal stream abstraction |
| Cancellation | DOMAIN_SPECIFIC | Runtime and Capability define effects independently | Universal cancellation guarantee |

### D32 special review

**D32 Option C remains COHERENT.** Existing evidence supports only the minimal
shared set above. It does not require a universal execution abstraction.

The final Checkpoint C shared set is:

1. Platform Execution Identity;
2. opaque correlation/native reference semantics;
3. observation/decision time and freshness semantics;
4. four-way condition truth meaning;
5. submission disposition;
6. inline/deferred completion disposition;
7. terminality;
8. bounded safe diagnostic shape.

Runtime Interaction and Capability Invocation retain distinct authorization,
payload, observation, cancellation, retry, streaming, and terminal outcome
semantics. Exact vocabulary and serialization remain unfrozen.

## 43. Checkpoint C Recommendations

1. Keep Platform Execution Identity embedded and owned by the Task/Workflow
   execution context; do not create Execution or TaskExecution resources.
2. Treat Execution Correlation as a relationship primitive, not another value
   object. Use Execution Identity plus bounded opaque native references.
3. Keep Task, Workflow, and Capability Outcomes embedded and domain-owned.
   Acceptance/running are execution states, not terminal outcomes.
4. Keep Runtime and Agent Instance Conditions distinct. Share only four-way
   truth meaning and minimal observation semantics; never mirror native health
   directly as Instance readiness.
5. Keep Runtime Interaction and Capability Invocation separate. Share only the
   D32 minimal primitives; keep authorization, payload, retry, cancellation,
   streaming, observation, and result meaning domain-specific.
6. Keep Recovery Assessment embedded in Agent Instance status and require
   predicate-based semantic verification. Restart or replacement is evidence,
   not recovery.
7. Preserve unknown and not-applicable as honest meanings; never coerce missing
   evidence into false or success.
8. Keep Human Gate decision authority in Governance and waiting/resumption in
   Task/Workflow execution state. Do not create Human Feedback architecture.
9. Preserve native IDs as `0:N` opaque correlation evidence with no authority
   or routing role.
10. Confirm D32 Option C as coherent and carry exact vocabularies,
    serialization, retry/idempotency, deferred durability, and state continuity
    into later authorized Contract work.

## 44. Human Decision Table — Checkpoint C

### C01 — Platform Execution Identity responsibility

**Recommendation:** Execution-owning Task/Workflow Control Plane creates and
owns one embedded identity for one logical execution before routing; Providers
propagate but never replace it.
**Evidence:** D31, AP-S5-011, S5-SPIKE-003/004.
**Alternatives:** Provider-native identity; universal Execution resource.
**Trade-off:** Stable end-to-end correlation with a small API surface versus no
independent execution resource lifecycle.
**Schema impact:** Later placement/generation rules only; no fields defined.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C02 — Execution Correlation representation

**Recommendation:** Relationship primitive, not a separate Core value object;
Execution Identity plus bounded opaque native references is sufficient.
**Evidence:** `0:N` native correlation accepted at Checkpoint B.
**Alternatives:** Separate Execution Correlation object; Provider-native graph.
**Trade-off:** Avoids duplicate lifecycle and consistency surface while leaving
retention/query mechanics for later.
**Schema impact:** Later bounded reference semantics only.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C03 — Task Outcome ownership

**Recommendation:** Task-domain `OUTCOME / EMBEDDED_VALUE`; acceptance/running
remain execution state and Provider results remain evidence.
**Evidence:** D36 and current Task lifecycle separation.
**Alternatives:** Generic Execution Outcome; TaskExecution resource.
**Trade-off:** Preserves Task retry/completion meaning versus duplicated minimal
envelope concepts.
**Schema impact:** Exact categories and representation remain later work.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C04 — Workflow Outcome ownership

**Recommendation:** Workflow-domain `OUTCOME / EMBEDDED_VALUE`, aggregating
node/dependency semantics without becoming generic Execution Outcome.
**Evidence:** D36 and current Workflow DAG/failure/skip behavior.
**Alternatives:** Copy final Task Outcome; universal Outcome.
**Trade-off:** Correct aggregate meaning versus domain-specific aggregation
rules.
**Schema impact:** No aggregation enum or fields defined.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C05 — Runtime Condition ownership

**Recommendation:** Runtime-domain embedded condition, Provider-normalized from
native evidence and platform-defined in meaning; `TaskReady` excluded.
**Evidence:** D36, S5-ARCH-002, Runtime evidence.
**Alternatives:** Raw Provider health; universal Status.
**Trade-off:** Honest portability versus normalization effort and unknown states.
**Schema impact:** Condition vocabulary remains unfrozen.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C06 — Agent Instance Condition ownership

**Recommendation:** Agent Instance Control Plane owns embedded logical
conditions for routing eligibility, effective Binding usability, degradation,
and recovery; native readiness is evidence only.
**Evidence:** D30, D34–D36, S5-SPIKE-004.
**Alternatives:** Mirror Pod/Gateway/Runtime condition directly.
**Trade-off:** Accurate logical health versus derived reconciliation complexity.
**Schema impact:** Names and predicates remain unfrozen.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C07 — Capability Outcome ownership

**Recommendation:** Capability-domain `OUTCOME / EMBEDDED_VALUE`; Provider
normalizes only after handoff, while authorization denial remains a pre-handoff
platform result.
**Evidence:** D36 and S5-SPIKE-003 denial/inline/deferred/failure evidence.
**Alternatives:** Runtime Outcome; universal Provider Result.
**Trade-off:** Preserves business and authorization meaning versus separate
domain normalization.
**Schema impact:** Error and result vocabulary remains unfrozen.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C08 — Shared Condition truth primitive

**Recommendation:** `SHARED_CORE_PRIMITIVE` for true, false, unknown, and
not-applicable meanings; exact names/representation not frozen.
**Evidence:** D36 and cross-runtime observation evidence.
**Alternatives:** Per-domain incompatible truth models; Boolean only.
**Trade-off:** Honest consistent epistemic state versus an additional primitive
requiring careful applicability/freshness rules.
**Schema impact:** Semantic meaning only.
**Freeze impact:** None.
**Human Decision:** ACCEPT WITH FREEZE CONSTRAINT — architecture-level truth
semantics only; exact names, representation, and compatibility are unfrozen.

### C09 — Shared error category

**Recommendation:** `DOMAIN_SPECIFIC`; share only a bounded safe diagnostic
shape, not one Runtime/Capability/Task error taxonomy.
**Evidence:** D32 Option C and pre-handoff Capability denial counterexample.
**Alternatives:** Universal error enum; completely unstructured diagnostics.
**Trade-off:** Preserves retry/authorization meaning while retaining consistent
safe observability envelope.
**Schema impact:** Exact categories and diagnostic representation unfrozen.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C10 — Terminality sharing

**Recommendation:** `SHARED_CORE_PRIMITIVE` limited to terminal, non-terminal,
or not-determinable meaning and inline/deferred completion disposition.
**Evidence:** D32 Option C, S5-SPIKE-003/004.
**Alternatives:** Universal progress state; duplicated terminality rules.
**Trade-off:** Consistent orchestration boundary without shared domain outcomes.
**Schema impact:** Exact representation unfrozen.
**Freeze impact:** None.
**Human Decision:** ACCEPT WITH FREEZE CONSTRAINT — semantic boundary only;
exact vocabulary and representation are unfrozen.

### C11 — Runtime Interaction boundary

**Recommendation:** Runtime-domain interaction Contract owns Binding/realization
context, observation, cancellation, retry, streaming, and terminal Runtime
meaning; only minimal D32 primitives are shared.
**Evidence:** S5-ARCH-002 and D32 comparison.
**Alternatives:** Universal Runtime/Capability interaction.
**Trade-off:** Runtime portability without erasing lifecycle semantics.
**Schema impact:** Runtime Contract remains future/unfrozen.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C12 — Capability Invocation boundary

**Recommendation:** Capability-domain Contract owns authorization, semantic
input/output, operation, Provider handoff, side-effect/retry, observation, and
terminal business meaning.
**Evidence:** S5-SPIKE-003 and D32/D36.
**Alternatives:** Runtime Interaction alias; protocol-native invocation in Core.
**Trade-off:** Governance and business portability versus separate Contract
evolution.
**Schema impact:** Capability Contract remains future/unfrozen.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C13 — Recovery Assessment responsibility

**Recommendation:** Agent Instance Control Plane owns embedded predicate-based
assessment of restored logical semantics; Providers supply normalized evidence.
**Evidence:** D35, D36, AP-S5-001, S5-SPIKE-004.
**Alternatives:** Restart success; Provider-owned recovery status; resource.
**Trade-off:** Honest semantic recovery versus multi-layer evidence gathering.
**Schema impact:** Vocabulary/history representation unfrozen.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C14 — Recovery evidence minimum

**Recommendation:** Require desired state, stable Instance identity, usable
effective Binding, acceptable Runtime/Instance conditions, restored routing
eligibility, and applicable execution continuity; State only when explicitly
promised.
**Evidence:** D35 and S5-SPIKE-004 recovery predicates.
**Alternatives:** Pod/process replacement alone; universal State restoration.
**Trade-off:** Verifiable promises without false portability versus potentially
unknown assessment where evidence is incomplete.
**Schema impact:** Predicate serialization deferred.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C15 — UNKNOWN semantics

**Recommendation:** Preserve unknown as insufficient evidence, distinct from
false and not-applicable; never coerce it into failure or success.
**Evidence:** D36 observation model and heterogeneous Provider limits.
**Alternatives:** Boolean conditions; fail-closed semantic conflation.
**Trade-off:** Honest uncertainty versus consumers needing explicit handling.
**Schema impact:** Exact names/transitions/staleness unfrozen.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C16 — Human Gate execution-state boundary

**Recommendation:** Governance owns reference/decision evidence; Task/Workflow
owns waiting and resumption execution state. Approval is not success, and
rejection is consumed under domain policy.
**Evidence:** Thin v0.2 governance direction and D36 ownership separation.
**Alternatives:** Human Gate as Outcome; broad Human Feedback subsystem.
**Trade-off:** Minimal enforceable gate boundary versus deferred feedback and
approval lifecycle.
**Schema impact:** No gate resource or state enum defined.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C17 — Native ID representation

**Recommendation:** `OPAQUE_NATIVE_ID / REFERENCE`, stored only as bounded
`0:N` correlation, debugging, observability, or ownership-safe cleanup evidence.
**Evidence:** D31, AP-S5-011, Checkpoint B B11.
**Alternatives:** Platform identity; routable native target in Core.
**Trade-off:** Useful diagnostics without native coupling versus bounded mapping
and retention obligations.
**Schema impact:** Native structures never enter Core; reference shape deferred.
**Freeze impact:** None.
**Human Decision:** ACCEPT.

### C18 — Final D32 shared primitive set

**Recommendation:** Share only Execution Identity, opaque correlation/native
reference semantics, observation/decision time and freshness, four-way
condition truth, submission disposition, inline/deferred completion
disposition, terminality, and bounded safe diagnostic shape.
**Evidence:** D32 Option C and combined S5-ARCH-002/S5-SPIKE-003/004 evidence.
**Alternatives:** Universal execution/result Contract; no shared primitives.
**Trade-off:** Consistent Control Plane integration without coupling Runtime and
Capability lifecycle or versioning.
**Schema impact:** Semantic set only; all names and serialization unfrozen.
**Freeze impact:** None; D32 remains coherent and Contracts remain unfrozen.
**Human Decision:** ACCEPT WITH FREEZE CONSTRAINT — architecture boundary
acceptance only; no fields, enums, schema, serialization, or Contract freeze.

## 45. Final Executive Conclusion

S5-ARCH-004 converges the accepted v0.2 architecture into a preliminary Core
Contract boundary with five first-class resource candidates:

1. Agent Definition;
2. Agent Instance;
3. Task;
4. Workflow; and
5. Capability Definition.

Runtime Binding and Capability Binding remain first-class semantic boundaries
but are `EMBEDDED_BINDING`, not API resources. Model Binding is a thin embedded
foundation. Runtime and Capability Provider registries plus Runtime Package are
internal metadata; Providers are interfaces. Platform Execution Identity is an
embedded Core value object. Conditions, outcomes, and Recovery Assessment are
embedded and domain-owned. Workspace, State/Memory, Knowledge, Policy,
Permission, and Human Gate remain thin references or decision evidence.

This is object-boundary, semantic-ownership, relationship, and shared-primitive
boundary acceptance. It is not an approved CRD count, schema freeze, Contract
freeze, Provider certification, or implementation authorization. The next
Schema Draft may design only within the handoff in Section 59 and must return to
a Human/Architecture Gate before public API or Contract approval.

## 46. Final Core Object Map

```text
Digital Employee (product/business projection only)
  projects
    Agent Definition (technical desired logical definition)
      OWNS embedded desired Runtime Binding intent
      OWNS 1:N embedded Capability Binding intents
        each BINDS_TO one Capability Definition
      OWNS thin embedded Model Binding
      REFERENCES Workspace / State / Knowledge / Policy
      referenced by 1:N Agent Instances
        each Agent Instance
          REFERENCES one exact Agent Definition identity/version
          OWNS derived effective Runtime Binding projection
          OBSERVES Agent Instance Conditions
          OBSERVES embedded Recovery Assessment
          CORRELATES_WITH 0:N opaque native realization references

Task / Workflow node
  OWNS embedded Platform Execution Identity
  OWNS domain execution state and Outcome
  may wait on Human Gate decision evidence
  ROUTES_TO one eligible Agent Instance
    effective Runtime Binding RESOLVES_THROUGH internal Runtime Registry
      Runtime Provider REALIZES/addresses opaque native realization
    Capability Binding RESOLVES_THROUGH internal Capability Registry
      Capability Provider INVOKES opaque native capability
      Capability Outcome remains Capability-domain owned

Platform Execution Identity
  CORRELATES_WITH 0:N Runtime-native IDs
  CORRELATES_WITH 0:N Capability-native invocation IDs
```

The corrected map makes logical routing precede Runtime Provider translation
and places Capability invocation in Task/Workflow execution context. Runtime
Provider does not own Capability invocation, Agent identity, or enterprise
Model/Capability semantics.

## 47. Final Classification Matrix

| Candidate | Final classification | Representation | v0.2 disposition |
| --- | --- | --- | --- |
| Agent Definition | CORE_RESOURCE | FIRST_CLASS_RESOURCE | V0_2_REQUIRED |
| Agent Instance | CORE_RESOURCE | FIRST_CLASS_RESOURCE | V0_2_REQUIRED |
| Task | CORE_RESOURCE | FIRST_CLASS_RESOURCE | V0_2_REQUIRED |
| Workflow | CORE_RESOURCE | FIRST_CLASS_RESOURCE | V0_2_REQUIRED |
| Capability Definition | CORE_RESOURCE | FIRST_CLASS_RESOURCE | V0_2_REQUIRED |
| Runtime Binding | BINDING | EMBEDDED_BINDING | V0_2_REQUIRED |
| Capability Binding | BINDING | EMBEDDED_BINDING | V0_2_REQUIRED |
| Model Binding | BINDING | THIN EMBEDDED BINDING | V0_2_THIN_FOUNDATION |
| Platform Execution Identity | CORE_VALUE_OBJECT | EMBEDDED_VALUE | V0_2_REQUIRED |
| Execution Correlation | REFERENCE | Relationship primitive | V0_2_REQUIRED |
| Runtime Provider Registry | REGISTRY_METADATA | INTERNAL_METADATA | V0_2_REQUIRED |
| Capability Provider Registry | REGISTRY_METADATA | INTERNAL_METADATA | V0_2_REQUIRED |
| Runtime Package | REGISTRY_METADATA | INTERNAL_METADATA | V0_2_REQUIRED |
| Runtime / Capability Provider | PROVIDER_INTERFACE | PROVIDER_INTERFACE_ONLY | V0_2_REQUIRED |
| Agent Instance Status | STATUS | EMBEDDED_VALUE | V0_2_REQUIRED |
| Runtime / Agent Instance Condition | CONDITION | EMBEDDED_VALUE | V0_2_REQUIRED |
| Task / Workflow / Capability Outcome | OUTCOME | EMBEDDED_VALUE | V0_2_REQUIRED |
| Recovery Assessment | STATUS | EMBEDDED_VALUE | V0_2_REQUIRED |
| Workspace / State / Knowledge | REFERENCE | Thin reference | V0_2_THIN_FOUNDATION |
| Policy / Permission / Human Gate | POLICY_REFERENCE | Thin reference/evidence | V0_2_THIN_FOUNDATION |
| Provider/native identifiers | OPAQUE_NATIVE_ID | Bounded opaque reference | V0_2_REQUIRED |

## 48. Final API Surface Budget

Every first-class resource remains expensive. `Conditional` means the semantic
exists but details depend on lifecycle/policy rather than weakening identity.

| Candidate | Identity | Lifecycle | Desired state | Reconciled | Independent reference | Authorization | Observability | Embedding sufficient | Proof | Final recommendation |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | --- | --- |
| Agent Definition | YES | YES | YES | YES | YES | YES | YES | NO | P1, P2, P3, P4, P5 | FIRST_CLASS_RESOURCE |
| Agent Instance | YES | YES | YES | YES | YES | YES | YES | NO | P3, P4, P6, P7 | FIRST_CLASS_RESOURCE |
| Task | YES | YES | YES | YES | YES | YES | YES | NO | P1, P5, P6, P7 | FIRST_CLASS_RESOURCE |
| Workflow | YES | YES | YES | YES | YES | CONDITIONAL | YES | NO | P1, P5, P6, P7 | FIRST_CLASS_RESOURCE |
| Capability Definition | YES | YES | CONDITIONAL | YES | YES | YES | YES | NO | P1, P2, P5, P7 | FIRST_CLASS_RESOURCE |

The final public resource candidate count is five, not seven. This count is an
architecture recommendation, not a target and not approval to create or modify
five CRDs. Runtime/Capability Bindings, Provider registries, Runtime Package,
Execution Identity, status objects, and thin foundations fail independent
lifecycle/reconciliation or embedding-insufficiency tests and therefore do not
enter the public resource budget.

## 49. Agent Definition and Agent Instance Boundaries

### Agent Definition

Agent Definition owns desired logical identity, role/purpose, authoritative
desired Runtime/Capability/Model Binding intent, Workspace/State/Knowledge and
policy references, and desired Instance policy. It is independently reusable,
versionable, referenced, authorized, observed, and reconciled. Embedding it in
Instance or Task would duplicate authority and couple business semantics to
execution.

### Agent Instance

Agent Instance owns stable running logical identity, desired lifecycle,
effective Runtime Binding projection, logical routing eligibility, Instance
conditions, and Recovery Assessment. It derives effective resolution from one
exact Definition identity/version plus policy and registry facts. It observes
Provider/native realization evidence.

Agent Instance never owns Agent Definition authority, Provider implementation,
Runtime Package publication, native realization identity, native state format,
enterprise Model identity/routing policy, Capability identity, credentials, or
governance authority. Desired authority is not duplicated across Definition
and Instance.

## 50. Task and Workflow Boundary

### Task

Task retains first-class status because it has independent durable work
identity, desired/execution lifecycle, Control Plane reconciliation, routing,
retry/timeout semantics, outcome, authorization context, and observability.
Task embeds Platform Execution Identity per logical execution context; it does
not require a TaskExecution resource for v0.2.

### Workflow

Workflow retains first-class status because DAG intent, dependency coordination,
node creation/observation, aggregate lifecycle/outcome, independent references,
and observability cannot be faithfully embedded into one Task or Agent.

Current implementation places reusable-looking DAG definition in Workflow
desired state and one execution's aggregate/node status on the same resource.
This conflates Workflow definition and Workflow execution concerns and may
become a future schema/versioning problem when reuse, repeated runs, Catalog, or
publish lifecycle is required. It does not invalidate Workflow as a v0.2
resource and does not authorize a new WorkflowDefinition or WorkflowExecution
resource. Schema Draft must record the ambiguity and preserve current
compatibility unless a separate architecture decision authorizes a split.

## 51. Capability Definition Boundary

Capability Definition remains a first-class resource candidate because it owns:

- provider-independent enterprise semantic identity and version context;
- operation and input/output Contract ownership at semantic level;
- reuse across Agent Definitions;
- risk classification and policy-attachment boundary;
- independent discovery/Catalog identity without making discovery authority;
- authorization target and audit meaning; and
- stable Agent-side semantics across Capability Provider switching.

Embedding Capability definitions inside Agents would duplicate semantic and
version authority, prevent independent reuse/governance, couple Agents to
Provider/protocol configuration, and weaken Golden Demo P2. MCP, REST, gRPC,
endpoint, tool, and native result details remain behind Capability Providers.
Exact operation/version/schema rules remain Contract-freeze debt.

## 52. Binding Boundaries

| Binding | Owner and representation | Required semantics | Explicitly absent |
| --- | --- | --- | --- |
| Runtime Binding | Definition owns embedded desired intent; Instance owns derived effective projection | Runtime requirements, ownership mode, Provider/Package constraints, credential/workspace/state/policy references, opaque Provider extension point | RuntimeBinding CRD, independent controller, shared Binding authority, native topology in Core |
| Capability Binding | Agent Definition owns `1:N` embedded governed intents; Instance/invocation owns derived effective resolution | Capability target/version context, allowed semantic use, Provider constraints, risk/policy/permission/Human Gate/credential references, opaque Provider extension point | CapabilityBinding CRD, reusable permission grant, discovery-as-authority, protocol semantics |
| Model Binding | Definition owns thin embedded intent | Enterprise model requirements and policy association sufficient to prevent Runtime ownership leakage | Full Model Policy, routing/fallback, gateway design, Provider topology |

Runtime and Capability Bindings are first-class semantic boundaries but not
first-class API resources. Changing an embedded Binding reconciles the owning
platform object and does not imply a Binding controller.

## 53. Provider, Registry, and Runtime Package Boundaries

| Candidate | Final representation | Public v0.2 API exposure | Rationale |
| --- | --- | --- | --- |
| Runtime Provider | PROVIDER_INTERFACE_ONLY | NO resource | Versioned adaptation code, not desired platform state |
| Capability Provider | PROVIDER_INTERFACE_ONLY | NO resource | Versioned invocation/normalization code, not Capability identity |
| Runtime Provider Registry | INTERNAL_METADATA | NO | Deterministic domain resolution from immutable compatibility facts; no lifecycle service required |
| Capability Provider Registry | INTERNAL_METADATA | NO | Domain-specific Provider resolution and policy eligibility; no public Registry object required |
| Runtime Package | INTERNAL_METADATA | NO | Deployable distribution/version/integrity and compatibility facts; package release is not Control Plane lifecycle |

Schema Draft may define internal metadata/descriptor contracts only where
needed for deterministic v0.2 resolution. It may not create Registry or
RuntimePackage CRDs, a dynamic marketplace, or a universal Registry. Product
discoverability may consume curated projections without making metadata a new
source of truth.

## 54. Thin Foundation Boundaries

| Foundation | Why needed in v0.2 | Intentionally deferred | Over-design to avoid |
| --- | --- | --- | --- |
| Model Binding | Preserves enterprise model identity/policy ownership and prevents Runtime Provider from owning routing intent; supports P1/P3 | Full model identity catalog, routing, fallback, credentials, gateway/provider policy pending S5-SPIKE-005 | Model CRDs, universal gateway schema, Provider-native model fields in Core |
| Workspace Reference | Preserves “where Agent works” separate from Capability/State; supports P1 and scoped recovery predicates | Independent lifecycle, portability, sharing, Provider boundary | Workspace resource based only on strategic importance |
| State / Memory Reference | Preserves “what Agent remembers” separate from Runtime; bounds P6 claims | State Contract, lifecycle, migration, continuity classes, portability | Claiming restart/replacement restores portable state |
| Knowledge Reference | Preserves “what Agent knows” separate from Capability/State; supports governed P1 context | Knowledge lifecycle, indexing, retrieval Provider, versioning | Knowledge CRD or treating all knowledge as an MCP tool |
| Policy Reference | Keeps eligibility/governance authority external to Provider; supports P5/P7 | Full policy engine, tenancy, policy language | Embedding policy engine or Provider-owned authority |
| Permission Reference | Preserves explicit invocation authorization; supports P5 | Enterprise RBAC/grant lifecycle and multi-tenancy | Treating Binding/discovery as permission |
| Human Gate Reference / decision evidence | Supports thin wait/approve/reject flow for P5 | Advanced approval lifecycle, feedback, learning, escalation | Human Feedback subsystem or Gate CRD |

## 55. Execution Primitive Boundary

| Category | Members |
| --- | --- |
| SHARED_CORE_VALUE | Embedded Platform Execution Identity; four-way Condition truth meaning; submission/completion disposition; terminality; observation/decision time and freshness; bounded safe diagnostic semantics |
| DOMAIN_SPECIFIC_VALUE | Runtime Interaction result/conditions; Capability Invocation/Outcome; Task Outcome; Workflow Outcome; Recovery Assessment; domain error and retry meaning |
| OPAQUE_NATIVE_REFERENCE | Runtime realization/run/session, Pod/container/Gateway, Capability invocation/job, and deferred native observation references |
| INTERNAL_PROVIDER_METADATA | Provider identity/version, compatibility/capability declarations, Runtime Package facts, certification/evidence references |

Schema Draft may serialize the semantic categories above only as embedded
values/references within approved owners. It must not create Universal
Execution, Result, Status, Invocation, Error, or Provider Result objects. Exact
names, fields, enums, compatibility, and serialization are not approved here.

## 56. Final Status / Condition / Outcome Ownership

| Semantic | Owner | Class / representation | Terminal nature | Shared dependencies | v0.2 disposition |
| --- | --- | --- | --- | --- | --- |
| Agent Instance Status | Agent Instance Control Plane | STATUS / EMBEDDED_VALUE | Mutable projection | observation time, conditions, opaque refs | REQUIRED |
| Agent Instance Condition | Agent Instance Control Plane | CONDITION / EMBEDDED_VALUE | Mutable proposition | four-way truth, time/freshness, safe diagnostics | REQUIRED |
| Runtime Condition | Runtime domain; Provider-normalized | CONDITION / EMBEDDED_VALUE | Mutable proposition | four-way truth, time/freshness, safe diagnostics | REQUIRED |
| Task Outcome | Task domain | OUTCOME / EMBEDDED_VALUE | Domain terminal or honestly unknown | Execution Identity, terminality, safe diagnostics | REQUIRED |
| Workflow Outcome | Workflow domain | OUTCOME / EMBEDDED_VALUE | Aggregate terminal or honestly unknown | terminality, node references, safe diagnostics | REQUIRED |
| Capability Outcome | Capability domain; Provider-normalized after handoff | OUTCOME / EMBEDDED_VALUE | Invocation terminal/deferred/unknown under domain semantics | Execution Identity, completion disposition, terminality, safe diagnostics | REQUIRED |
| Recovery Assessment | Agent Instance Control Plane | STATUS / EMBEDDED_VALUE | Mutable derived assessment | condition truth, time/freshness, opaque evidence | REQUIRED |
| Human Gate decision evidence | Governance owner; consumed by Task/Workflow | POLICY_REFERENCE / embedded evidence reference | Decision evidence may be final; waiting state is mutable execution state | time/decision evidence; no universal Outcome | THIN FOUNDATION |

## 57. Final Relationship, Lifecycle, and Provider Responsibility Map

The Checkpoint B cardinality model remains final for this session:

- Definition -> Instance: `1:N`; Instance references exactly one Definition
  identity/version.
- Definition -> desired Runtime Binding template: one authoritative current
  intent; Instance -> effective Runtime Binding: one derived current projection.
- Definition -> Capability Binding: `1:N`; each Binding targets one Capability
  Definition/version context.
- Instance -> realization: `1:N temporal`, `0:N active`; shared Gateway `N:1`
  is possible and opaque.
- Task/Workflow node -> logical Execution: `1:N temporal`; Execution -> native
  Runtime/Capability IDs: `0:N` correlation.

Lifecycle consequences remain:

- block Definition deletion while Instances reference it;
- cascade only embedded values after an owner is legitimately deleted;
- reconcile Binding changes through the owning object;
- deny future invocation when a Capability Binding is removed;
- mark unavailable Provider/package/reference dependencies degraded;
- terminate Instance through ownership-safe reconciliation;
- detach external realizations by default and never delete them unconditionally.

Providers validate/translate desired intent, interact with native systems,
normalize/redact evidence, and return bounded domain results. Core owns identity,
desired semantics, logical routing, policy precedence, domain condition/outcome
meaning, and final Recovery Assessment. Native systems own execution mechanics,
native identity/state/protocol, and native supervision. Providers never broaden
authority or redefine platform semantics.

## 58. Product / Technical Mapping and Golden Demo Traceability

```text
Business view                Technical view
Digital Employee role  -->  Agent Definition
running employee       -->  Agent Instance
business assignment    -->  Task / Workflow
enterprise ability     -->  Capability Definition + embedded Binding
execution environment  -->  embedded Runtime Binding -> Provider -> native Runtime
```

Digital Employee is a product projection and may compose catalog, ownership,
experience, and governance views. It is not a second technical identity and
does not justify a DigitalEmployee CRD.

| Proof | Required objects/primitives |
| --- | --- |
| P1 Business task execution | Agent Definition, Agent Instance, Task/Workflow, Execution Identity, Runtime Binding/Provider, Capability Definition/Binding/Provider |
| P2 Capability Provider portability | Capability Definition, embedded Capability Binding, internal registry, Provider interface, Capability Outcome |
| P3 Runtime Provider portability | Agent Definition/Instance, embedded Runtime Binding, internal Registry/Package metadata, Runtime Provider interface |
| P4 Stable logical Agent Instance identity | Agent Instance, `1:N temporal` opaque realizations, logical routing |
| P5 Human Gate/governance | Policy/Permission/Human Gate references, Task/Workflow waiting state, pre-invocation authorization |
| P6 Failure -> verified Recovery | Conditions, Execution Identity, opaque evidence, Agent Instance Recovery Assessment |
| P7 Observability | Domain status/conditions/outcomes, time/freshness, safe diagnostics, native correlation references |

Every v0.2 Required or Thin Foundation item supports at least one P1–P7 proof
or an accepted Control Plane invariant.

## 59. Final Three-Bucket Scope

### V0.2 REQUIRED

- five first-class resource candidates: Agent Definition, Agent Instance, Task,
  Workflow, Capability Definition;
- embedded Runtime and Capability Bindings;
- Runtime/Capability Provider interfaces, internal domain registry metadata,
  and internal Runtime Package metadata;
- embedded Platform Execution Identity and minimal D32 shared semantics;
- Agent Instance Status/Conditions, Runtime Conditions, Task/Workflow/Capability
  Outcomes, and Recovery Assessment;
- bounded opaque native correlation references.

### V0.2 THIN FOUNDATION

- thin embedded Model Binding;
- Workspace, State/Memory, and Knowledge references;
- Policy, Permission, and Human Gate references/decision evidence.

### DEFERRED

| Item | Reason now | Promotion trigger/evidence |
| --- | --- | --- |
| Full Model Policy/routing and fallback | S5-SPIKE-005 not complete; semantics would be invented | Authorized model spike establishing identity, routing, fallback, credential, gateway, and policy ownership |
| First-class Workspace resource | Independent lifecycle/reconciliation/sharing unproven | Cross-Agent/runtime workspace lifecycle and authorization evidence |
| First-class State resource / portability | State ownership, continuity classes, migration, and portability unproven | State Contract evidence across replacement/runtime boundaries |
| First-class Knowledge resource | Lifecycle, versioning, retrieval Provider, and authorization unproven | Multiple knowledge sources/providers requiring independent management |
| Human Feedback learning | Outside thin Human Gate proof | Authorized product/architecture work proving feedback/learning lifecycle |
| Advanced Human Gate lifecycle | v0.2 needs reference/decision boundary only | Multi-stage approval, escalation, expiry, audit, and reassignment evidence |
| Multi-tenancy | Requires identity/RBAC/persistence architecture | Authorized tenant/governance architecture decision |
| HA / fleet management | Not required for v0.2 contract proof | Scale/availability requirements and scheduler/control ownership evidence |
| Out-of-process Providers | Interface must remain serializable but transport not required | Isolation/deployment/security evidence requiring process boundary |
| Dynamic Provider marketplace | Internal metadata is sufficient | Publication, trust, install, update, policy, and lifecycle requirements |
| Runtime Package resource | Package metadata lacks Control Plane lifecycle | Independent desired-state/reconciliation/use cases beyond publication metadata |
| Public Provider Registry resource | Internal deterministic resolution is sufficient | External management/discovery requiring independent API lifecycle and authorization |
| Advanced scheduling / cross-cluster / GPU scheduling | Outside logical routing and v0.2 proof | v0.5-scale placement evidence and architecture decisions |

## 60. Rejected Abstractions

| Abstraction | Disposition | Reason |
| --- | --- | --- |
| Universal Execution | REJECT_ARCHITECTURALLY under D32 | Runtime/Capability/Task/Workflow lifecycles are not semantically identical |
| Universal Execution Status / Universal Result | REJECT_ARCHITECTURALLY under D36 | Erases condition/outcome ownership and retry/authorization meaning |
| Universal Provider | REJECT_ARCHITECTURALLY under D33 | Runtime realization and Capability invocation responsibilities differ |
| Universal Binding | REJECT_ARCHITECTURALLY under D33 | Runtime, Capability, and Model associations have different semantics |
| Universal Registry | REJECT_ARCHITECTURALLY under D33 | Domain compatibility/policy dimensions must remain explicit |
| Universal Runtime Instance | REJECT_ARCHITECTURALLY under D30 | Pod, process, Gateway, session, and endpoint do not share one logical lifecycle |
| Execution CRD | REJECT_V0_2 | Embedded identity has no independent desired state/reconciliation; future contrary evidence would require architecture review |
| RuntimeBinding CRD | REJECT_V0_2 | Binding lifecycle/reconciliation follows Definition/Instance owner |
| CapabilityBinding CRD | REJECT_V0_2 | Agent-owned governed intent lacks independent lifecycle and shared authority would be unsafe |
| RuntimePackage CRD | REJECT_V0_2 | Publication metadata is sufficient; no Control Plane lifecycle proven |
| DigitalEmployee CRD | REJECT_ARCHITECTURALLY under current product boundary | Business projection is not another technical semantic identity |
| MCP-as-Capability semantic | REJECT_ARCHITECTURALLY | MCP is one Provider/protocol mechanism, not enterprise Capability identity |

`REJECT_ARCHITECTURALLY` means contradictory to the accepted current baseline,
not impossible forever; reversing it requires an explicit future architecture
decision rather than incidental schema work.

## 61. Schema Draft Handoff

The next phase is authorized to **draft**, not freeze, the following boundaries:

| Owner/object | Schema Draft may design |
| --- | --- |
| Agent Definition | Technical identity/version relationship, role/purpose boundary, desired Instance policy, embedded desired Runtime/Capability/Model Binding boundaries, thin Workspace/State/Knowledge/Policy references |
| Agent Instance | Stable identity and Definition reference, desired lifecycle boundary, derived effective Runtime Binding projection, logical eligibility/status ownership, Conditions, Recovery Assessment, bounded opaque realization references |
| Task | Independent requested-work identity, Agent/Instance routing references, desired/execution-state separation, embedded Execution Identity, Task Outcome, policy/Human Gate references |
| Workflow | Independent identity, DAG/node relationship, execution-state and aggregate Outcome ownership, Task/Execution references, current definition/execution conflation disclosure |
| Capability Definition | Enterprise semantic identity/version/operation boundary, input/output Contract ownership boundary, risk/policy/authorization references, Provider-independent discovery identity |
| Runtime Binding | Embedded desired intent versus derived effective projection, Provider/Package constraints, ownership/configuration/credential/workspace/state/policy reference boundaries, opaque Provider extension point |
| Capability Binding | Embedded Capability reference and allowed-use boundary, Provider constraints, risk/policy/permission/Human Gate/credential references, opaque Provider extension point |
| Provider metadata | Internal version/compatibility/capability/limitation/integrity/certification-evidence descriptors needed for deterministic domain resolution |
| Execution primitives | Embedded identity, correlation/reference relationship, time/freshness, truth, submission/completion disposition, terminality, bounded safe diagnostics |
| Domain observation | Owner-specific status, Condition, Outcome, Recovery Assessment, and opaque native-reference placement without universalization |

Schema Draft must make desired/effective, semantic/native, and owner/reference
boundaries mechanically unambiguous. It must document compatibility with current
Agent, Task, and Workflow APIs and flag every proposed public API change for the
applicable Architecture Gate. It may not implement any draft.

## 62. Schema Draft Prohibitions

The next phase must not silently introduce:

- any first-class resource beyond the five candidates;
- Universal Execution, Status, Result, Invocation, Provider, Binding, Registry,
  or Runtime Instance abstractions;
- Execution, RuntimeBinding, CapabilityBinding, RuntimePackage,
  DigitalEmployee, Workspace, State, Knowledge, Provider, or Registry CRDs;
- public Provider Registry APIs or dynamic marketplace lifecycle;
- frozen Condition, Outcome, error, terminality, or recovery enums;
- frozen Runtime, Capability, State, Model, or shared Execution Contracts;
- full Model policy/routing/fallback or S5-SPIKE-005 work;
- State portability, universal recovery continuity, or unsupported HA claims;
- Provider-native topology/protocol/error/configuration fields in Core;
- Hermes-specific Core fields or Golden Demo dependence on Hermes
  certification;
- a Workflow definition/execution split without a separate architecture
  decision and compatibility plan;
- production CRD, controller, Provider, Runtime, frontend, database, or API
  implementation.

## 63. Contract Freeze Impact

| Acceptance dimension | State after S5-ARCH-004 |
| --- | --- |
| Object boundary | RECOMMENDED for Human Final Contract Boundary Gate |
| Semantic ownership | RECOMMENDED; A–C accepted constraints preserved |
| Relationship/cardinality | RECOMMENDED; detailed serialization absent |
| Shared primitive boundary | ARCHITECTURE BOUNDARY ACCEPTED at Checkpoint C |
| Schema | NOT DRAFTED / NOT FROZEN |
| Runtime Contract | NOT FROZEN |
| Capability Contract | NOT FROZEN |
| Condition/Outcome/Recovery vocabulary | NOT FROZEN |
| Provider certification | UNAFFECTED; combination-specific evidence still required |
| `G-S5-RUNTIME-FREEZE-01` | FAIL / UNCHANGED |

Architecture/object acceptance does not establish compatibility policy,
serialized fields, public API stability, implementation conformance, Provider
certification, or production readiness.

## 64. Final Evidence Debt

| Debt | Classification | Effect on next work |
| --- | --- | --- |
| ED-S5-001 Hermes Provider certification | PROVIDER_CERTIFICATION_BLOCKER; PRODUCTION_READINESS_BLOCKER for Hermes only | Does not block Schema Draft, Core boundary, Native/OpenClaw Golden Demo |
| Runtime Contract conformance | CONTRACT_FREEZE_BLOCKER; PRODUCTION_READINESS_BLOCKER | Draft may define testable boundary; freeze waits for conformance evidence |
| Third-party Managed Runtime certification | PROVIDER_CERTIFICATION_BLOCKER; PRODUCTION_READINESS_BLOCKER for that combination | Not a Core Schema Draft blocker |
| Third-party MCP evidence | CONTRACT_FREEZE_BLOCKER for broad Capability claims; PROVIDER_CERTIFICATION_BLOCKER | Deterministic spike supports boundary, not broad certification |
| Deferred/side-effecting Capability evidence | CONTRACT_FREEZE_BLOCKER; PRODUCTION_READINESS_BLOCKER for those profiles | Retry/cancel/idempotency vocabulary must remain unfrozen |
| Durable deferred execution | CONTRACT_FREEZE_BLOCKER; PRODUCTION_READINESS_BLOCKER | Completion disposition may be drafted without durability claim |
| In-flight execution behavior | CONTRACT_FREEZE_BLOCKER; PRODUCTION_READINESS_BLOCKER | Termination/rebinding/recovery semantics remain bounded |
| Recovery predicate completeness | CONTRACT_FREEZE_BLOCKER; PRODUCTION_READINESS_BLOCKER | Schema Draft may place Assessment but cannot freeze vocabulary |
| State portability | POST_V0_2; CONTRACT_FREEZE_BLOCKER for any portability claim | Thin State reference only |
| Multi-tenancy | POST_V0_2; PRODUCTION_READINESS_BLOCKER for enterprise multi-tenant claims | Do not invent tenant fields during Schema Draft |
| Human Feedback | POST_V0_2 | Thin Human Gate boundary only |
| Workspace boundary maturity | POST_V0_2; SCHEMA_DRAFT_BLOCKER only for promotion beyond thin reference | Thin reference is draftable now |
| State boundary maturity | POST_V0_2; SCHEMA_DRAFT_BLOCKER only for promotion beyond thin reference | Thin reference is draftable now |
| Model Binding/routing | POST_V0_2 for full routing; SCHEMA_DRAFT_BLOCKER beyond thin Binding | Requires S5-SPIKE-005 |
| Out-of-process Providers | POST_V0_2; CONTRACT_FREEZE_BLOCKER only if freeze promises that deployment mode | Keep interfaces serializable without transport commitment |

Debt is claim-scoped. Not every item blocks the next Schema Draft, and no item
is silently closed by this convergence.

## 65. Open Questions

1. Exact identity/version/reference and compatibility rules for all five
   candidate resources.
2. Whether current Workflow definition/execution conflation remains acceptable
   through v0.2 or requires a separately approved future migration.
3. Exact Instance lifecycle, deletion, rollout, and Definition-version adoption
   semantics.
4. Runtime/Capability Binding effective-projection provenance and migration
   history without duplicated desired authority.
5. Execution identity generation, hierarchy, retry/replay/idempotency,
   persistence, and retention.
6. Exact Condition, Outcome, diagnostic, terminality, and Recovery vocabulary.
7. Deferred observation durability, cancellation, streaming, and in-flight
   termination/recovery semantics.
8. Capability operation/version/input-output compatibility and risk granularity.
9. Model routing/fallback, State portability, and Workspace/Knowledge lifecycle
   pending their required evidence.
10. Multi-tenant policy, credential, audit, native evidence access, and advanced
    Human Gate lifecycle.

These are Schema Draft, Contract-freeze, certification, production-readiness,
or post-v0.2 questions. None requires reopening accepted A–C decisions for this
Checkpoint D recommendation.

## 66. Final Human Decision Table — Checkpoint D

### D01 — v0.2 first-class resource set

**Recommendation:** Agent Definition, Agent Instance, Task, Workflow, and
Capability Definition only.
**Evidence:** Final API Surface Budget; D30; current Task/Workflow lifecycle;
S5-SPIKE-003 Capability identity evidence.
**Alternatives:** Retain only current resources; add Binding/Execution/Registry
resources.
**Trade-off:** Minimum faithful semantic surface with five expensive resources;
new Agent Instance and Capability Definition still require later schema review.
**v0.2 disposition:** REQUIRED.
**Schema impact:** Draft boundaries only; no CRD count or schema approved.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D02 — Agent Definition boundary

**Recommendation:** First-class desired technical logical definition owning
authoritative Binding intent and thin references; Digital Employee remains a
product projection.
**Evidence:** Product principles, current Agent resource, A01/B02.
**Alternatives:** Instance/native-owned definition; DigitalEmployee API.
**Trade-off:** Stable reuse/governance versus version/migration design cost.
**v0.2 disposition:** REQUIRED.
**Schema impact:** Identity, references, desired boundaries may be drafted.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D03 — Agent Instance boundary

**Recommendation:** First-class stable running logical identity owning desired
lifecycle, effective Runtime Binding projection, conditions, routing eligibility,
and Recovery Assessment.
**Evidence:** D30, D34–D36, S5-SPIKE-004, A02/B01/B05.
**Alternatives:** Derive from Pod/Gateway/session; embed in Definition.
**Trade-off:** New lifecycle surface versus required routing/recovery identity.
**v0.2 disposition:** REQUIRED.
**Schema impact:** Draft only; no AgentInstance CRD authorized yet.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D04 — Task boundary

**Recommendation:** Retain first-class durable requested-work lifecycle with
embedded Execution Identity/state and Task Outcome.
**Evidence:** Current source/tests, D31/D36, P1/P6/P7.
**Alternatives:** Embed work in Workflow/Instance; introduce TaskExecution.
**Trade-off:** Independent orchestration/observation versus preserving current
compatibility while adding execution primitives later.
**v0.2 disposition:** REQUIRED.
**Schema impact:** Draft compatibility-aware semantic additions only.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D05 — Workflow boundary

**Recommendation:** Retain first-class DAG/coordination lifecycle and aggregate
Outcome; record current definition/execution conflation without redesign.
**Evidence:** Current CRD/controller/tests and D36.
**Alternatives:** Embed DAG in Task; split Definition/Execution now.
**Trade-off:** Preserves proven behavior and scope; future reuse may require an
approved migration.
**v0.2 disposition:** REQUIRED.
**Schema impact:** Draft must disclose ambiguity and preserve compatibility.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D06 — Capability Definition boundary

**Recommendation:** First-class provider-independent enterprise Capability
identity/version/operation and governance target.
**Evidence:** S5-SPIKE-003, D33/D36, P2 portability.
**Alternatives:** Embedded Agent tools; MCP-native semantics.
**Trade-off:** New versioned/governed API surface versus essential reuse and
Provider switching.
**v0.2 disposition:** REQUIRED.
**Schema impact:** Semantic Contract boundary may be drafted, not frozen.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D07 — Runtime Binding representation

**Recommendation:** First-class semantic `BINDING / EMBEDDED_BINDING`; desired
Definition intent plus derived Instance effective projection.
**Evidence:** B02/B03/B13 accepted.
**Alternatives:** RuntimeBinding resource; native configuration in Core.
**Trade-off:** Small API and clear ownership versus no independent Binding
history/resource.
**v0.2 disposition:** REQUIRED.
**Schema impact:** Embedded boundary only; no controller/CRD.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D08 — Capability Binding representation

**Recommendation:** Agent-owned `BINDING / EMBEDDED_BINDING`, `1:N`, with
authorization re-evaluated per invocation.
**Evidence:** B04/B09/B14 and S5-SPIKE-003.
**Alternatives:** CapabilityBinding resource; reusable permission grant.
**Trade-off:** Avoids shared authority and excess API surface versus repeated
Agent-specific intent.
**v0.2 disposition:** REQUIRED.
**Schema impact:** Embedded boundary only; no CRD.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D09 — Model Binding thin boundary

**Recommendation:** Thin embedded Binding carrying enterprise model
requirements/policy association only.
**Evidence:** D33 and Runtime/Core ownership; S5-SPIKE-005 remains pending.
**Alternatives:** Full routing schema; Runtime-owned model configuration.
**Trade-off:** Prevents ownership leakage without inventing model architecture.
**v0.2 disposition:** THIN FOUNDATION.
**Schema impact:** Only thin reference/intent boundary may be drafted.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D10 — Provider Registry representation

**Recommendation:** Separate Runtime and Capability `INTERNAL_METADATA`
registries with no public resource/API.
**Evidence:** D33, S5-ARCH-002, B07/B08 constraints.
**Alternatives:** Universal/public Registry; Core family branching.
**Trade-off:** Deterministic replaceability with low operations cost versus no
dynamic marketplace.
**v0.2 disposition:** REQUIRED internal foundation.
**Schema impact:** Internal descriptor/resolution metadata only.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D11 — Runtime Package representation

**Recommendation:** `INTERNAL_METADATA`; no RuntimePackage CRD.
**Evidence:** S5-ARCH-002 and A06.
**Alternatives:** Collapse into Provider; public resource.
**Trade-off:** Preserves Package/Provider compatibility separation without a
new lifecycle API.
**v0.2 disposition:** REQUIRED internal foundation.
**Schema impact:** Internal immutable package facts only.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D12 — Platform Execution Identity representation

**Recommendation:** `CORE_VALUE_OBJECT / EMBEDDED_VALUE`, owned by execution
context and correlated to `0:N` native references.
**Evidence:** D31, AP-S5-011, B10/B11, C01/C02/C17.
**Alternatives:** Execution CRD; Provider-native identity.
**Trade-off:** Stable correlation with minimal API versus no independent
execution resource.
**v0.2 disposition:** REQUIRED.
**Schema impact:** Embedded semantic boundary only.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D13 — Shared execution primitive set

**Recommendation:** D32 Option C minimal set from Section 55; all other
interaction/outcome semantics remain domain-specific.
**Evidence:** C08/C10/C18 accepted with freeze constraints.
**Alternatives:** Universal Execution Contract; no shared primitives.
**Trade-off:** Consistent Control Plane integration without cross-domain
version/lifecycle coupling.
**v0.2 disposition:** REQUIRED semantic boundary.
**Schema impact:** May be drafted only as embedded primitives; exact vocabulary
unfrozen.
**Freeze impact:** Architecture acceptance only; no Contract freeze.
**Human Decision:** PENDING.

### D14 — Condition ownership model

**Recommendation:** Runtime and Agent Instance Conditions remain domain-owned;
share only truth/time/freshness/safe-diagnostic semantics.
**Evidence:** D36, C05/C06/C08.
**Alternatives:** Raw native health; universal Status.
**Trade-off:** Honest portable observation versus derived condition work.
**v0.2 disposition:** REQUIRED.
**Schema impact:** Owner placement may be drafted; type/vocabulary unfrozen.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D15 — Outcome ownership model

**Recommendation:** Task, Workflow, and Capability Outcomes remain separate
embedded domain values; Runtime interaction result remains Runtime-specific.
**Evidence:** D32/D36 and C03/C04/C07/C09.
**Alternatives:** Universal Outcome/Provider Result.
**Trade-off:** Preserves business, retry, and authorization meaning versus
duplicate minimal envelope concepts.
**v0.2 disposition:** REQUIRED.
**Schema impact:** Owner/envelope boundary only; taxonomies unfrozen.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D16 — Recovery Assessment model

**Recommendation:** Agent Instance-owned `STATUS / EMBEDDED_VALUE`, derived from
applicable semantic predicates; restart is not recovery.
**Evidence:** D35/D36, AP-S5-001, C13/C14/C15.
**Alternatives:** Provider recovery status; Pod restart result; resource.
**Trade-off:** Verifiable logical semantics versus honest unknown when evidence
is incomplete.
**v0.2 disposition:** REQUIRED.
**Schema impact:** Placement/predicate boundary may be drafted; vocabulary
unfrozen.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D17 — Workspace / State / Knowledge thin references

**Recommendation:** Thin references only; independent resources and State
portability deferred to evidence triggers in Section 59.
**Evidence:** Product separation, A14–A16, D35 constraints.
**Alternatives:** Promote strategic concepts to resources; omit boundaries.
**Trade-off:** Preserves semantic ownership without unsupported lifecycle
claims.
**v0.2 disposition:** THIN FOUNDATION.
**Schema impact:** Reference boundary only.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D18 — Human Gate thin boundary

**Recommendation:** Governance owns decision reference/evidence; Task/Workflow
owns waiting/resumption state; approval is not execution success.
**Evidence:** C16 and P5.
**Alternatives:** Human Gate Outcome/resource; Human Feedback subsystem.
**Trade-off:** Minimum governable execution boundary versus deferred advanced
approval lifecycle.
**v0.2 disposition:** THIN FOUNDATION.
**Schema impact:** Thin references/evidence relationship only.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D19 — v0.2 API Surface Budget

**Recommendation:** Five first-class resource candidates, two embedded Binding
types, one embedded Core execution identity, domain-embedded status/outcomes,
internal registry/package metadata, Provider interfaces, and thin references.
**Evidence:** A–C accepted decisions and final resource tests.
**Alternatives:** Seven-resource candidate count; expansive Registry/Package/
Execution APIs; current resources only.
**Trade-off:** Minimum sufficient v0.2 portability/governance surface while
reserving later lifecycle domains.
**v0.2 disposition:** FINAL BOUNDARY RECOMMENDATION.
**Schema impact:** Defines draft budget, not approved public API.
**Freeze impact:** None.
**Human Decision:** PENDING.

### D20 — Schema Draft handoff boundary

**Recommendation:** Authorize only the owners/categories in Section 61 and
enforce all prohibitions in Section 62; every public API change returns through
Architecture Gates and Human approval.
**Evidence:** Final convergence and unresolved freeze/certification debt.
**Alternatives:** Implement directly; freeze Contracts from architecture prose;
restart open architecture domains during schema work.
**Trade-off:** Constrained, reviewable draft work versus additional gate before
implementation.
**v0.2 disposition:** NEXT-PHASE HANDOFF RECOMMENDATION.
**Schema impact:** Draft-only, compatibility-aware, no implementation.
**Freeze impact:** Explicitly none.
**Human Decision:** PENDING.

## Contract and Change Boundary

CONTRACT_FREEZE: **NO**
FREEZE_GATE: `G-S5-RUNTIME-FREEZE-01 = FAIL / UNCHANGED`
RUNTIME_CONTRACT: **NOT FROZEN**
CAPABILITY_CONTRACT: **NOT FROZEN**
CONDITION_VOCABULARY: **NOT FROZEN**
OUTCOME_VOCABULARY: **NOT FROZEN**
RECOVERY_VOCABULARY: **NOT FROZEN**
PRODUCTION_CORE_CHANGE: **0**
ADR_CHANGE: **0**
SCHEMA_CHANGE: **0**

Schema Draft is not Contract Freeze. This Checkpoint does not draft a schema.

## Checkpoint State

LIFECYCLE: REVIEW
AUTHORIZATION: AUTHORIZED
STATUS: PASS
CHECKPOINT: D — V0_2_API_SURFACE_AND_FINAL_CONVERGENCE
RESULT: CORE_CONTRACT_BOUNDARY_RECOMMENDED
NEXT_ACTION: WAIT_FOR_HUMAN_DECISION
NEXT_GATE: Human Final Contract Boundary Gate
