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
CHECKPOINT: B — RELATIONSHIP_AND_CARDINALITY

RESULT: **RELATIONSHIP_MODEL_RECOMMENDED**

> The Human Checkpoint A Gate passed with representation constraints. This
> artifact now records the Checkpoint B relationship and cardinality
> recommendation. Human Checkpoint B Gate is pending. It does not define field
> schemas, freeze Contracts, change an ADR, or authorize implementation.

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
**Human Decision:** PENDING.

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
**Human Decision:** PENDING.

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
**Human Decision:** PENDING.

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
**Human Decision:** PENDING.

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
**Human Decision:** PENDING.

### B06 — Shared Gateway relationship

**Recommendation:** `N:1 possible` opaque native topology; Gateway never owns
or replaces logical Instance identity.
**Evidence:** S5-SPIKE-004 shared-Gateway proof and D30/D34.
**Alternatives:** Gateway-as-Instance; expose Gateway as logical router.
**Trade-off:** Preserves semantics across runtimes while limiting native
topology visibility.
**Schema impact:** At most bounded opaque realization evidence later.
**Freeze impact:** None.
**Human Decision:** PENDING.

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
**Human Decision:** PENDING.

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
**Human Decision:** PENDING.

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
**Human Decision:** PENDING.

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
**Human Decision:** PENDING.

### B11 — Native ID correlation relationship

**Recommendation:** Runtime-native and Capability-native IDs `CORRELATE_WITH`
Execution Identity at `0:N`; they never replace it.
**Evidence:** D31, S5-SPIKE-003, and S5-SPIKE-004.
**Alternatives:** Native ID as platform execution/routing identity.
**Trade-off:** Stable portability and correlation versus bounded mapping and
retention needs.
**Schema impact:** Later bounded opaque-reference shape only.
**Freeze impact:** None.
**Human Decision:** PENDING.

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
**Human Decision:** PENDING.

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
**Human Decision:** PENDING.

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
**Human Decision:** PENDING.

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
**Human Decision:** PENDING.

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
CHECKPOINT: B — RELATIONSHIP_AND_CARDINALITY
RESULT: RELATIONSHIP_MODEL_RECOMMENDED
NEXT_ACTION: WAIT_FOR_HUMAN_DECISION
NEXT_GATE: Human Checkpoint B Gate
