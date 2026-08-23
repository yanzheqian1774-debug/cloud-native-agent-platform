# S5-ARCH-005 — v0.2 Core Schema Draft & Compatibility Map v1

SESSION

ID: S5-ARCH-005
TITLE: v0.2 Core Schema Draft & Compatibility Map
PHASE: S5 / v0.2 CONNECT & MANAGE
TRACK: Core Architecture / Contract
MODE: Architecture / Schema Draft
LIFECYCLE: REVIEW
AUTHORIZATION: AUTHORIZED
STATUS: PASS
CHECKPOINT: B — RESOURCE_SCHEMA_DRAFT
RESULT: **RESOURCE_SCHEMA_DRAFT_RECOMMENDED**

> Checkpoint A established the compatibility and design baseline. The Human
> Checkpoint A Gate passed and accepted A01-A14 for Schema Draft use. Checkpoint
> B adds implementation-neutral logical schema candidates. It does not approve
> a Kubernetes CRD, freeze a Contract/schema/vocabulary, change an ADR,
> authorize implementation, or begin Checkpoint C.

## 1. Source-of-Truth Baseline

| Source | Baseline and use |
| --- | --- |
| `origin/main` | `c8e1768d8cbd014b7eb243531a40bbecb7895586`, validated 2026-08-23; exactly the required baseline |
| S5-ARCH-004 | `S5-ARCH-004-CORE-CONTRACT-BOUNDARY-V1.md` on main; closed, passed, and the accepted boundary for this work |
| S5-SPIKE-003 | Durable Checkpoint A-C and closeout evidence under `docs/evidence/s5/capability-contract/` on main |
| S5-SPIKE-004 | Durable Checkpoint A-C and closeout evidence under `docs/evidence/s5/agent-instance-routing/` on main |
| S5-ARCH-001/002/003 | Reviewed from repository refs/worktrees because their named artifacts are absent from the validated main tree; used only as supporting provenance where S5-ARCH-004 durably carries their accepted conclusions |
| Accepted ADRs | `adr/ADR-0001.md` through `adr/ADR-0006.md`, interpreted through `adr/README.md` and `docs/engineering/DECISION_STATUS.md` |
| Current behavior | CRDs, Operator, Runtime, Console, tests, and examples at the validated main commit |

The baseline remains Kubernetes as the current Control Plane source of truth.
The absence of the named S5-ARCH-001/002/003 artifacts from the main tree is
evidence-traceability debt, not a semantic contradiction: S5-ARCH-004 records
their relevant accepted decisions, sources, constraints, and unresolved debt.
No recommendation below promotes a non-durable, superseded, or pending
decision over S5-ARCH-004.

## 2. Checkpoint A Boundary and Method

The inspection followed this order:

```text
Accepted architecture semantics
  -> current logical/API behavior
    -> tests and examples that consume it
      -> compatibility classification
        -> principles for a later logical schema
```

The classification vocabulary is:

- **KEEP** — preserve the concept and current behavior in the compatibility
  baseline.
- **EXTEND** — preserve current behavior while a later approved representation
  may add optional semantics.
- **MODIFY** — a semantic or representation change is likely required and must
  carry an explicit migration and Human Gate.
- **DEPRECATE** — retain during a bounded compatibility window while directing
  new use to a replacement.
- **DEFER** — do not design beyond a thin boundary in Checkpoints B-D.
- **REMOVE_CANDIDATE** — removal may be evaluated later, but is not authorized
  by this Checkpoint.

These classifications are recommendations for later drafting. They do not
modify an existing artifact.

## 3. Current Schema and API Inventory

### 3.1 Kubernetes resource inventory

All three current resources are namespaced, served and stored as
`agentos.io/v1alpha1`, and use the Kubernetes `status` subresource.

| Artifact | Current durable surface | Consumers/evidence | Classification |
| --- | --- | --- | --- |
| Agent CRD | `metadata`; required `spec.runtime` and `spec.model`; optional capabilities, replicas, resources, identity, instructions; infrastructure-oriented status | `manifests/crd/agents.agentos.io.yaml`; Agent manifests; Operator create/update/timer handlers; resource and operator tests | **EXTEND**, with likely **MODIFY** of conflated semantics only through a migration |
| Task CRD | required `agentRef.name` and `input.prompt`; optional timeout; phase/result/reason/retry/attempt/time status | `manifests/crd/tasks.agentos.io.yaml`; CRD tests; Task controller/retry tests; Workflow controller; examples | **EXTEND** |
| Workflow CRD | non-empty embedded task DAG; task names, Agent refs, prompt/result sources, dependencies, timeout; aggregate and per-node execution status | `manifests/crd/workflows.agentos.io.yaml`; extensive CRD/graph/controller tests; Console; examples | **KEEP** for v0.2 compatibility and **EXTEND** only additively; definition/execution split **DEFER** |

No Agent Instance, Capability Definition, Runtime Binding, Capability Binding,
Platform Execution Identity, Runtime Provider Registry, Capability Provider
Registry, or Runtime Package production schema exists on main.

### 3.2 Agent API details

Current Agent semantics are both definition-like and realization-oriented:

- Kubernetes `metadata.name` and namespace identify the Agent.
- `spec.identity.role`, `spec.identity.displayName`, and
  `spec.instructions.systemPrompt` describe logical definition intent.
- `spec.runtime.type` accepts `native`, `hermes`, or `external`; optional
  `spec.runtime.image` directly affects the generated Deployment.
- `spec.model.provider`, `name`, endpoint/base URL, and Secret reference embed
  Provider-specific model configuration.
- `spec.capabilities` is an array of untyped strings.
- `spec.replicas` directly determines Deployment replicas.
- the Operator creates one same-named Deployment and Service, injects Agent,
  Runtime, Model, identity, and instruction environment variables, and patches
  high-level readiness phase/replica status.

Durability is demonstrated by multiple checked-in Agent manifests and by
`operator/tests/test_operator.py` and `operator/tests/test_resources.py`.
There is no dedicated repository-level Agent CRD schema test, which weakens
field-level compatibility evidence but does not make the API unused.

Compatibility conclusion: treat the current Agent API as a public alpha
surface whose identity, namespaced scope, desired `spec`, observed `status`,
instructions, role/display identity, replica intent, resources, and current
controller behavior must not disappear silently. Its direct Runtime and Model
configuration predates the accepted Binding/Provider architecture. The schema
draft must distinguish preservation of serialized input from endorsement of
those fields as the target logical Contract.

### 3.3 Task API details

Current Task is one durable requested-work object and one current execution:

- `metadata` provides namespaced resource identity.
- `spec.agentRef.name` selects a current Agent by name in the Task namespace.
- `spec.input.prompt` is the complete input shape.
- `spec.timeoutSeconds` defaults to 300.
- create-time execution invokes the Agent's same-named Kubernetes Service at
  `/v1/invoke`.
- retry happens inside one Task lifecycle; `status.attempts` counts attempts.
- status phases are `Pending`, `Running`, `Succeeded`, `Failed`, and
  `TimedOut`; result is a string and reason has a tested error taxonomy.

Tests pin required fields, phases, error reasons, retryability, attempts,
timestamps, initial Running persistence, retries, timeouts, and terminal
results. Workflow reconciliation creates and observes Task resources, so Task
names, Agent reference semantics, phase values, result presence, and labels
also have cross-resource compatibility weight.

Compatibility conclusion: retain Task identity and lifecycle. Platform
Execution Identity may later be an additive embedded value, but Task identity
must not be reinterpreted as native invocation identity. Outcome restructuring
or a change to attempt/retry meaning would be breaking unless dual-read/write
or versioned migration is approved.

### 3.4 Workflow API details

Current Workflow stores a DAG definition and the state of one execution in the
same resource:

- each embedded task has a stable local `name`, Agent reference, prompt,
  optional data-source references, dependency names, and timeout;
- Workflow creates owned Task CRs named `<workflow>-<node>` and labels them with
  Workflow and node identity;
- graph validation rejects missing dependencies, cycles, invalid result
  sources, self-reference, and duplicate sources;
- controllers preserve parallelism, fan-in, result passing, failure/timeout
  propagation, transitive skip, independent siblings, idempotent
  reconciliation, and aggregate Workflow completion;
- Workflow status embeds per-node phase, Task reference, reason, and message;
- the read-only Console projects Workflow and owned Task objects into list and
  detail REST responses.

The Workflow definition/execution conflation is explicitly accepted as v0.2
evolution debt by S5-ARCH-004. No `WorkflowExecution` Core resource or CRD is
authorized. The Console's class named `WorkflowExecutionDetail` is a read-only
projection, not a Core execution schema.

Compatibility conclusion: preserve existing DAG and execution semantics
through v0.2. Any future reusable-definition/run split is a separate G2
decision and migration, not an additive field exercise in Checkpoint B.

### 3.5 Non-CRD API and implementation inventory

| Artifact | Current semantics | Target relationship | Classification |
| --- | --- | --- | --- |
| Console REST API | `GET /api/v1/workflows` and `GET /api/v1/workflows/{namespace}/{name}` expose read-only run projections | API representation derived from current Kubernetes resources; not a logical Contract owner | **KEEP** |
| Console Pydantic schemas | Workflow summaries, nodes, edges, Agent refs, upstream results, and node execution detail; extra fields forbidden | Compatibility consumer/projection; domain-specific Workflow view | **EXTEND** only when backing semantics are approved |
| Native Runtime invoke API | `POST /v1/invoke` with `{input}` and `{output, agent, model}`; `/v1/info`, health, readiness | Current Runtime-specific implementation API; not the Runtime Contract | **KEEP** as current implementation, **DEFER** from Core schema |
| Runtime-local ModelProvider | ABC `generate(prompt)` plus mock and OpenAI-compatible implementations selected by environment | Runtime implementation detail; not Runtime Provider and not ADR-0005 platform Model Provider | **KEEP** internally; **DEFER** from Core schema |
| Agent Operator runtime construction | Direct Deployment/Service construction from Agent fields | Predates Runtime Binding/Provider architecture | **MODIFY** only in later authorized implementation/migration; unchanged here |
| Task-to-Runtime invocation | Direct same-name Service URL and string request/result | Current Runtime-specific interaction | **KEEP** for compatibility; do not universalize |
| Workflow routing | Embedded nodes reference Agent names; generated Tasks retain that Agent ref | Current logical Definition-like targeting, not Agent Instance routing | **MODIFY** only after Agent Instance routing schema and compatibility decision |
| Kubernetes labels/owner refs | Workflow-created Task naming and labels establish ownership and projection joins | Persistence/implementation representation | **KEEP** unless a versioned migration proves an alternative |
| Runtime/Capability Provider abstractions | No production interfaces or registries implementing S5-ARCH-004 exist | Later Provider interfaces/internal metadata | **DEFER** to their authorized draft/implementation phases |

### 3.6 Status, conditions, identifiers, and references

| Concern | Current | Evidence and compatibility consequence |
| --- | --- | --- |
| Resource identity | Kubernetes name/namespace/UID/version/generation are available; code chiefly uses name/namespace | preserve current namespaced lookup; do not assume name alone is globally stable |
| Agent reference | `{name}` only and implicitly same namespace | durable in Task/Workflow schemas, tests, builders, and examples; richer logical reference must be additive or versioned |
| Workflow node reference | local string name; Task resource link in status | durable DAG-local identity; not interchangeable with resource or execution identity |
| Task/native execution identity | no Platform Execution Identity; HTTP/native request IDs are not modeled | later Platform identity is additive; native IDs remain opaque evidence |
| Agent conditions | Kubernetes-like array with type/status/reason/message/lastTransitionTime; vocabulary untested | structural precedent only; vocabulary is not frozen |
| Task status/outcome | phase, string result, reason, message, retryable, attempts, timestamps | strongly used and tested; domain-owned Task outcome/status |
| Workflow status/outcome | aggregate phase/times/count plus node map | strongly used; domain-owned Workflow aggregation |
| Evidence freshness | no explicit observed-at/freshness field | additive candidate, not evidence to infer current freshness guarantees |
| `observedGeneration` | Agent status schema declares it; current controller does not visibly patch it | useful structural precedent with implementation gap; do not claim current enforcement |

## 4. Existing Resource Map

```text
CURRENT

Agent CR (definition + deployment/runtime/model intent)
  -> Operator-created Deployment (1)
  -> Operator-created Service (1)
  <- readiness-derived Agent.status

Workflow CR (DAG definition + one run state)
  -> owned Task CR per scheduled node (0..N)
       -> AgentRef{name} (1)
       -> same-named Agent Service invocation
       <- Task status/result
  <- aggregate and per-node Workflow.status
  -> read-only Console projection

TARGET LOGICAL BOUNDARY (accepted, not implemented)

Agent Definition (1) -> Agent Instance (N)
  Agent Definition owns desired Runtime/Capability/Model Binding intent
  Agent Instance owns effective Runtime Binding and routing/recovery state
Task / Workflow own execution context and Platform Execution Identity
Capability Definition is first-class
Runtime/Capability Providers are interfaces
Registries/Runtime Package are internal metadata
```

The target does not authorize replacing the current tree. It identifies where
current meanings align, where compatibility adapters or versioned evolution
may be required, and which new logical concepts have no current serialized
representation.

## 5. Compatibility Baseline

### 5.1 Major-concept matrix

| Concept | CURRENT | TARGET | COMPATIBILITY | CHANGE_TYPE | RISK | RECOMMENDATION |
| --- | --- | --- | --- | --- | --- | --- |
| Agent identity | Namespaced Agent CR; identity also carries role/display name | Agent Definition resource identity distinct from Agent Instance | Partial alignment | Compatible extension plus bounded migration | High | Preserve current Agent identity; decide whether it is the v0.2 Definition representation or a legacy facade before fields are drafted |
| Agent desired definition | instructions, role/display, capabilities, resources mixed with runtime/model/replicas | authoritative logical Definition and Binding intent | Partial alignment | Compatible extension / migration | High | Evolve over replace; do not silently reinterpret fields |
| Agent running identity | Agent name maps to Deployment/Service; replicas are not logical Instances | stable first-class Agent Instance, Definition `1:N` | Missing | New logical resource candidate; API/CRD undecided | High | Draft logical Contract first; preserve legacy one-Agent endpoint behavior through an explicit compatibility strategy |
| Runtime Binding | embedded `runtime.type/image` on Agent | domain-specific desired template plus derived effective binding | Predates target | Migration; some additive scaffolding possible | High | Keep legacy input readable; Provider-specific image/config must not become stable Core semantics |
| Model Binding | embedded provider/name/endpoint/base URL/Secret ref | thin embedded Binding only, details deferred | Predates target and ADR-0005 | Migration / defer | High | Do not elaborate before S5-SPIKE-005; avoid freezing current Provider fields as Core |
| Capability Binding | array of capability strings | `1:N` governed embedded Bindings to Capability Definitions | Weak semantic overlap | Additive then migration/deprecation | High | Preserve legacy strings during compatibility window; do not equate them with approved bindings |
| Capability Definition | absent | first-class logical resource candidate | New | Additive logical/API candidate; CRD undecided | Medium | Draft independently of MCP/REST/provider details |
| Task | first-class CR and synchronous create-triggered execution | first-class durable requested-work lifecycle with embedded execution identity and Task outcome | Strong alignment | Additive preferred | Medium | Preserve required fields, phases, retry/attempt meaning, and result compatibility |
| Task Agent reference | same-namespace Agent name | Definition and/or Instance references under logical routing rules | Ambiguous | Migration or additive reference alternative | High | Human decision required; never change existing `agentRef.name` meaning in place |
| Workflow | first-class CR with embedded DAG and one run | first-class orchestration lifecycle; definition/run conflation retained for v0.2 | Strong alignment with recorded debt | Additive only in v0.2 | Medium | Keep DAG semantics; defer split and reusable Workflow Definition work |
| Workflow node Task | owned Task name/labels and local node name | Task/Workflow domain execution context | Strong alignment | Additive | Medium | Preserve node naming/reference semantics or provide an explicit projection migration |
| Execution identity | Task/Workflow/resource/native identifiers only | Platform-owned embedded value with `0:N` native refs | Missing | Additive | Medium | Define separately from resource, attempt, and native identity |
| Runtime interaction | direct HTTP request/response | Runtime-specific Contract semantics | Current implementation only | Defer / future migration | Medium | Do not turn current payload into universal Execution/Outcome |
| Task outcome | phase/result/error/retry/attempt/time status | Task-owned outcome/status | Strong domain alignment | Compatible extension; vocabulary changes potentially breaking | High | Preserve domain ownership and existing wire values |
| Workflow outcome | aggregate phase and node statuses | Workflow-owned aggregate outcome | Strong domain alignment | Compatible extension | High | Preserve status projection and current phase behavior |
| Conditions | Agent-only Kubernetes-like shape; Task/Workflow use domain status | domain-owned conditions/outcomes with minimal shared structure | Partial structural alignment | Additive structure; vocabulary deferred | Medium | Reuse proven structural concepts, not one universal object |
| Runtime abstraction | Operator directly builds Deployment/Service; Native Runtime API | Binding -> Registry -> Runtime Provider -> native realization | Architecture drift | Later migration/implementation | High | Schema must not encode current direct construction as target architecture |
| Provider abstraction | runtime-local model ABC only | distinct Runtime and Capability Provider interfaces | Missing / name collision risk | Additive interfaces; internal rename may later help | Medium | State explicitly that current ModelProvider is not either Core Provider interface |
| CRD representation | Agent, Task, Workflow only | five logical resource candidates, not five CRD commitments | Compatible if representation remains separate | G2 for any public CRD change | High | Logical Contract before API and CRD; no CRD decision in Checkpoint B by default |

### 5.2 Additive, breaking, and deferred change map

Likely additive if separately approved and collision-free:

- optional Platform Execution Identity embedded in Task/Workflow execution
  context;
- optional logical reference metadata alongside an unchanged legacy reference;
- optional provenance for desired-to-effective resolution;
- optional observed/freshness timestamps and safe evidence metadata;
- new logical Agent Instance and Capability Definition Contract candidates,
  provided their API/CRD representation is decided separately;
- internal Runtime/Capability Provider descriptor metadata that does not alter
  public APIs;
- read-only Console projection fields after backing semantics exist.

Breaking or migration-requiring:

- changing API group, version, kind, scope, resource identity, or required
  fields of current CRDs;
- changing `agentRef.name` from current same-namespace Agent meaning to an
  Instance or Provider-native target in place;
- replacing current Agent with separate Definition/Instance objects without a
  compatibility facade and identity mapping;
- removing or renaming current Runtime/Model/Capability fields;
- changing Task phase/reason/result/retry/attempt semantics or wire types;
- splitting Workflow definition from execution while existing clients expect
  one resource;
- replacing Workflow-created Task naming/labels or Console response fields
  without versioning/migration;
- using a native run/session/Pod/Gateway ID as Platform identity;
- collapsing Runtime, Task, Workflow, or Capability results into one universal
  status/outcome vocabulary.

Deferred:

- Workflow Definition versus Workflow Execution split;
- detailed Model Binding/routing/fallback until S5-SPIKE-005 or equivalent
  accepted evidence;
- State/Memory portability and first-class resource design;
- Workspace and Knowledge lifecycle/resource promotion;
- Policy, Permission, Human Gate, Tenant, RBAC, audit, and approval lifecycles;
- universal Execution, Status, Result, Provider, Binding, Registry, or
  RuntimeInstance abstractions;
- Provider marketplaces, dynamic registry services, new databases, and
  high-frequency execution history in Kubernetes;
- Hermes-specific fields or Core accommodation of ED-S5-001.

## 6. Backward-Compatibility Policy Recommendation

v0.2 should attempt to preserve:

1. readability and validation of existing `agentos.io/v1alpha1` Agent, Task,
   and Workflow manifests;
2. current namespaced resource identity and Kubernetes source-of-truth model;
3. current Task and Workflow lifecycle behavior and machine wire values;
4. current Operator behavior until a separately approved migration replaces a
   path;
5. current Workflow-to-Task ownership, node correlation, result passing, and
   Console projections;
6. existing examples as compatibility fixtures even if new examples later use
   richer logical references;
7. an explicit, bounded translation for legacy Agent Runtime/Model/Capability
   fields if the target logical Contract no longer treats them as canonical.

Compatibility does not require declaring every current field to be a stable
Core semantic forever. The preferred order is:

```text
additive representation
  -> dual-read / deterministic translation
    -> observable migration
      -> deprecation with exit criteria
        -> removal only in an approved version boundary
```

Unknown fields, defaults, omission behavior, list/map ordering, and Kubernetes
conversion/storage details must be evaluated once an API representation is
proposed. No removal is recommended at Checkpoint A.

## 7. Schema Design Principles for Checkpoints B-D

1. **Logical Contract precedes representation.** Draft semantic owners,
   invariants, identities, relationships, and compatibility before JSON/YAML,
   OpenAPI, Pydantic, or CRD mechanics.
2. **Resource does not mean CRD.** Each first-class logical resource requires
   a separate representation and lifecycle test before Kubernetes persistence
   is proposed.
3. **Evolve current APIs over replacement.** Current Agent, Task, and Workflow
   usage must be mapped field by field before a replacement is recommended.
4. **Preserve domain ownership.** Runtime interaction, Capability invocation,
   Task outcome, Workflow outcome, Runtime condition, Agent Instance condition,
   and Recovery Assessment remain distinct.
5. **No generic noun families.** Do not introduce universal Execution,
   ExecutionStatus, ExecutionResult, Provider, Binding, Registry, or
   RuntimeInstance objects.
6. **Desired authority is singular.** A derived effective projection must
   identify its desired source and must not become a second desired-state
   authority.
7. **Observed data is evidence, not intent.** Provider/native observations may
   inform status but cannot replace platform policy, selection, or identity.
8. **Native details are opaque and bounded.** Provider-specific configuration
   and IDs stay in extension/native areas unless a portable Core semantic is
   proven across runtimes.
9. **Unknown is first-class truth.** `UNKNOWN` must not be encoded as false,
   absent, failed, or not applicable; freshness and evidence sufficiency matter.
10. **Compatibility is explicit.** Every candidate field or relationship in
    Checkpoint B must state whether it is new, maps from a current field,
    aliases a current field, or requires migration.
11. **Defaults are behavior.** Defaults, optionality, immutability, and update
    semantics are Contract decisions, not serialization trivia.
12. **References do not import lifecycle.** Referring to Workspace, State,
    Knowledge, Policy, Permission, Human Gate, or a Provider does not make Core
    own that domain.
13. **No high-frequency payload persistence in Core resources.** Preserve the
    ADR-0002 boundary against conversation history, streams, large outputs,
    traces, and execution-history databases in CRDs.
14. **Provider switching preserves Core meaning.** OpenClaw, Hermes, Native,
    and future Providers must not require different Core identities,
    conditions, or routing ownership.
15. **Schema Draft is not freeze.** Names, fields, enums, and serialization
    remain candidates until Human Contract Gate and required conformance.

## 8. Layer Placement Principles

| Candidate | Primary layer for Checkpoint B | Possible later representation | Excluded placement |
| --- | --- | --- | --- |
| Agent Definition | Logical Contract resource | API representation; CRD only after G2 decision | Runtime/native object |
| Agent Instance | Logical Contract resource | API representation; CRD undecided | Pod, Deployment, Gateway, session |
| Task | Existing logical/API/CRD resource compatibility baseline | Additive versioned representation | universal Execution |
| Workflow | Existing logical/API/CRD resource compatibility baseline | Additive representation; split deferred | Console-owned record |
| Capability Definition | Logical Contract resource | API representation; CRD undecided | MCP tool/REST endpoint identity |
| Runtime Binding | Logical Contract embedded Binding | owner-embedded API value | generic Binding CRD |
| Capability Binding | Logical Contract embedded Binding | owner-embedded API value | permission grant or generic Binding CRD |
| Model Binding | Thin embedded logical value | minimal reference/intent only | full routing schema before evidence |
| Platform Execution Identity | Embedded Core value object | owner-carried API value | standalone Execution CRD/native ID |
| Execution Correlation | Relationship primitive | propagated references/evidence | lifecycle resource |
| Runtime/Capability Provider | Provider interface | SDK/interface/transport later | Core semantic resource |
| Provider registries / Runtime Package | Internal Provider metadata | immutable repository/startup descriptors | public registry/marketplace CRD |
| Conditions/outcomes/recovery | Domain-owned embedded status/value | owner-specific API representation | universal Status/Outcome resource |
| Native references/configuration | Provider extension or implementation detail | opaque evidence/extension data | stable Core semantics |
| Thin foundations | Logical reference boundary only | external/domain-owned APIs later | new v0.2 first-class resources |

## 9. Identity Model Principles

### 9.1 Identity classes

| Identity | Owner | Stability and rule |
| --- | --- | --- |
| Resource identity | Platform/API owner | Identifies Agent Definition, Agent Instance, Task, Workflow, or Capability Definition; stable across Provider/native replacement |
| Execution identity | Platform execution context | Identifies one logical execution; distinct from Task/Workflow resource identity and from an attempt unless later rules explicitly relate them |
| Provider identity | Provider registry/metadata owner | Identifies a versioned adapter/interface implementation; never Agent or execution identity |
| Binding reference | Logical owner | Identifies or embeds desired association intent; not a native realization |
| Runtime realization identity | Runtime Provider/native system | Opaque evidence for a process, Pod, session, service, Gateway, or other realization; temporal `1:N` per Instance |
| Native invocation identity | Capability/Runtime native system | Opaque correlation for a request/run/tool invocation; `0:N` per Platform Execution Identity |
| Correlation identity | Platform relationship context | Relates execution, attempt, parent/child context, and native evidence without creating a lifecycle resource |

### 9.2 Rules

- Platform-generated identity must remain authoritative for platform resources
  and executions.
- Names are human-addressable identifiers within an explicit scope; names are
  not assumed globally unique or immutable across deletion/recreation.
- Kubernetes UID/resourceVersion/generation may support a Kubernetes
  representation but must not define the implementation-neutral logical
  Contract.
- Native IDs must never become routing keys for logical Agent Instance
  selection.
- Provider switching or Runtime realization replacement must preserve logical
  Definition, Instance, Task/Workflow, and Execution identities as applicable.
- Attempts, retries, replay, and child execution relationships remain an open
  Checkpoint B/C question; current Task `attempts` semantics must be preserved.
- Identity fields must never carry credentials, mutable endpoint discovery, or
  Provider-specific topology.

## 10. Desired / Effective / Observed Principles

The three-plane discipline is appropriate where resolution or reconciliation
creates a meaningful distinction. It is not a requirement to serialize three
identical subobjects on every resource.

| Owner/domain | DESIRED | EFFECTIVE | OBSERVED | Recommendation |
| --- | --- | --- | --- | --- |
| Agent Definition | authoritative logical definition and desired Binding/reference intent | optional validation/default projection only; no Instance-effective authority | definition reconciliation/validation status | Use separation; do not copy Instance observations into Definition intent |
| Agent Instance | desired lifecycle and Definition association | resolved Runtime Binding, eligible routing projection, effective version/provenance | Instance conditions, realization refs, Recovery Assessment | Strong three-plane fit |
| Runtime Binding | Definition-owned template/intent | Instance-owned derived resolved binding | Runtime Provider-normalized conditions/evidence | Strong fit, embedded under different owners; no duplicated desired authority |
| Capability Binding | Definition-owned governed use intent | invocation-time resolved Provider/operation/authorization context where needed | Capability-domain outcome/native evidence | Use selectively; authorization is re-evaluated, not cached as desired truth |
| Task | requested work, input, target intent, timeout | resolved Instance/execution/routing context if introduced | Task-owned phase/outcome/attempt/times | Fit without forcing a generic status shape |
| Workflow | declared DAG and node intent | resolved runnable graph/node execution context | aggregate Workflow and node outcomes | Preserve current combined resource in v0.2; keep planes conceptually distinct |

Effective values must carry enough provenance to answer which desired
generation/version, resolver/Provider descriptor, and policy decision produced
them. Observed values must carry freshness or observation time when staleness
changes meaning. Provider observations cannot overwrite desired fields.

## 11. Reference Principles

1. A logical reference identifies a platform/domain object; a native reference
   identifies opaque Provider/substrate evidence. They must use distinguishable
   types or locations.
2. Every logical reference defines its scope and resolution owner. A bare name
   is acceptable only where the enclosing Contract fixes the scope, as current
   same-namespace `agentRef.name` does.
3. A stable logical ID and a human-readable name serve different purposes.
   Checkpoint B must decide whether both are needed per resource without
   assuming Kubernetes metadata.
4. Namespace/scope is a logical tenancy/ownership question first and a
   Kubernetes namespace mapping second. Current resources remain namespaced.
5. Resource version and generation serve different concerns: schema/API
   compatibility versus desired-state revision. Neither is Provider version.
6. Definition, Instance, Capability, Binding, and Provider references require
   domain-specific types; a generic `ObjectRef` must not erase ownership or
   compatibility rules.
7. Binding references express desired association or effective provenance;
   they do not identify Runtime realizations.
8. Provider references resolve through domain-specific internal metadata and
   compatibility checks; they do not form a universal registry relation.
9. Native references are `0:N`, opaque, safely displayable/redactable, and
   never required to establish Platform logical identity.
10. Cross-version references require an explicit compatibility rule: exact,
    range, channel, or resolver policy. No choice is frozen here.
11. Deletion, dangling-reference, adoption, and rebinding behavior must be
    defined per relationship rather than inherited accidentally from
    Kubernetes owner references.
12. Existing `agentRef.name`, Workflow local task names, `dependsOn`, input
    source names, Task refs, labels, and owner refs are compatibility inputs.

## 12. Status and Condition Structural Principles

Vocabulary remains unfrozen. Structural candidates may include:

| Field/concern | Principle |
| --- | --- |
| `type` | Domain-owned condition/outcome assertion; not one cross-domain enum |
| `status` | Three-valued truth where applicable: true, false, unknown; not applicable remains distinct |
| `reason` | Stable machine-readable domain reason; current Task reason values require compatibility treatment |
| `message` | Safe human-readable diagnostic; optional, bounded, redactable, and not machine control flow |
| `observedGeneration` | Relates observation to desired revision where the owner is reconciled |
| `lastTransitionTime` | Changes when semantic truth changes, not on every observation |
| `observedAt` | Records evidence observation time independently of transition time |
| evidence freshness | Explicit enough to distinguish fresh false, stale/unknown, and not applicable |
| source/provenance | Identifies domain/Provider evidence source without importing raw native payloads |

Domain rules:

- Runtime Condition belongs to the Runtime domain/Provider-normalized
  observation.
- Agent Instance Condition belongs to Agent Instance reconciliation.
- Recovery Assessment belongs to Agent Instance and evaluates semantic
  predicates; restart alone cannot produce recovered=true.
- Task Outcome remains Task-owned and preserves current lifecycle/result/error
  meaning.
- Workflow Outcome remains Workflow-owned aggregate meaning.
- Capability Outcome remains Capability-specific business/operation meaning.
- Runtime interaction state remains Runtime-specific.
- absence of evidence produces unknown when truth cannot be established; it
  must not be coerced to false or success.

## 13. Product and Demo Traceability

| Future behavior | Required schema property, not a field proposal | Compatibility note |
| --- | --- | --- |
| Create Agent Definition | stable provider-independent definition identity and desired intent | current Agent identity/instructions should map deterministically |
| Create multiple logical Instances | Definition `1:N`; each Instance has stable identity | current replicas are infrastructure count, not proven Instance objects |
| Bind different Runtime Providers | domain Binding/Provider separation and compatibility decision | current runtime type/image needs legacy translation, not Core adoption |
| OpenClaw Runtime | Provider-specific extension outside Core | stronger evidence must not bias Core fields |
| Hermes if certified | same Core boundary with package/Provider-scoped certification debt | no Hermes fields; ED-S5-001 remains open |
| Future Native Runtime | Provider switching without Core semantic change | current Native API is implementation evidence, not final Contract |
| Capability protocols/providers | provider-independent Capability identity and per-invocation authorization | current string capabilities are insufficient but remain compatibility input |
| Logical routing | Control Plane selects Instance; Provider translates selected Binding | current Agent Service lookup requires migration design |
| Stable execution identity | Platform-owned identity propagated across Provider boundaries | additive to current Task/Workflow contexts |
| Realization replacement | Instance and execution identities survive `1:N` temporal realizations | native references remain opaque evidence |
| Recovery assessment | Instance-owned, predicate-based, unknown-aware | current readiness/restart signals are insufficient alone |
| Digital Employee projection | business view projects stable Definition/Instance/work semantics | never add a DigitalEmployee CRD or demo-only Core fields |

## 14. Multi-Runtime Compatibility Constraints

- Core-facing schemas must describe logical intent, identity, policy
  association, execution correlation, and normalized domain evidence without
  OpenClaw-, Hermes-, Native-, Pod-, Gateway-, or protocol-specific fields.
- Runtime Provider-specific configuration belongs in an extension boundary or
  referenced configuration whose compatibility/version owner is explicit.
- The Runtime Provider consumes an effective Runtime Binding after the Control
  Plane has selected the logical Instance. It may select among realizations
  within that Binding; it may not replace logical routing.
- Dedicated realization, multiple realizations, shared Gateway, connected
  external Runtime, and future Provider topologies must fit without changing
  Core cardinality or identity meaning.
- Provider identity, Provider package identity/version, Contract version, and
  native Runtime identity are distinct.
- Unsupported optional operations must be declared honestly. Cancellation,
  streaming, upgrade, scale, state portability, and deferred durability are
  not universal v0.2 promises.
- Runtime conditions and interaction results remain Runtime-domain values;
  translation must not fabricate availability, recovery, or semantic success.
- Credentials, endpoints, package signing, supply-chain data, and native
  topology must not leak into stable Core fields.

## 15. Thin-Foundation Boundaries

| Boundary | Minimal v0.2 treatment | Prohibited expansion in Checkpoint B |
| --- | --- | --- |
| Model | thin embedded Binding/reference for enterprise requirements/policy association | routing, fallback, gateway, provider credentials, or full Model resource before dedicated evidence |
| Workspace | opaque logical reference expressing where work occurs | Workspace lifecycle, portability, filesystem/native layout |
| State / Memory | thin continuity/reference intent only | portability claims, state payload, Memory service/resource |
| Knowledge | governed source reference only | index, retrieval, ingestion, or Knowledge resource lifecycle |
| Policy | governance-owned reference and precedence boundary | embedded policy language or Core policy engine |
| Permission | authorization-owned grant/decision reference | reusable Capability Binding as permission, or cached authority expansion |
| Human Gate | governance decision/evidence reference; Task/Workflow owns wait/resume state | approval resource/lifecycle, Human Feedback system, or approval=execution-success |

Promotion of any thin foundation to a first-class resource requires new
accepted evidence and an architecture decision.

## 16. Compatibility and Migration Risks

| Risk | Severity | Why it matters | Required mitigation before schema/implementation approval |
| --- | --- | --- | --- |
| Current Agent conflates Definition, deployment, Runtime, Model, and replica intent | High | target separates Definition, Instance, Bindings, Providers, and realizations | field-level map, legacy translation, identity/default/update semantics, rollout plan |
| Agent Instance target conflicts with current one-name Service routing model | High | logical routing cannot simply reinterpret current Agent ref | explicit reference policy, compatibility facade, selection and authorization semantics |
| Current `replicas` may be mistaken for Instance cardinality | High | Pods/replicas are not logical Instances | preserve infrastructure meaning until an approved migration states otherwise |
| Workflow definition/run conflation | High | future reusable definitions may need separate executions | defer in v0.2; separate G2 decision and migration later |
| Task status taxonomy is already machine-consumed | High | changing phases/reasons/results breaks tests, controllers, Console, and users | preserve wire values or introduce versioned/dual representation |
| Bare same-namespace references are under-specified for future scopes | Medium | richer scope/version may be needed | additive reference alternative; never reinterpret in place |
| Provider-specific Agent model/runtime fields may look like target Core | High | freezing them would violate accepted Provider/Binding separation | label as legacy representation and keep target semantics implementation-neutral |
| Capability strings lack identity/version/operation/governance | High | cannot safely become Capability Bindings by assertion | deterministic legacy mapping or explicit unmapped state; no silent upgrade |
| Console forbids extra response fields | Medium | backend model changes can be consumer-visible | version or add approved optional fields carefully with tests |
| No current Platform Execution Identity | Medium | later correlation must not disturb Task identity/retry semantics | define identity/attempt relationship and additive persistence first |
| Status freshness and observed-generation behavior are incomplete | Medium | stale evidence may appear authoritative | structural draft plus controller conformance plan; no current claim inflation |
| ADR-0003/0004/0005 implementation drift | High | schema could accidentally resolve accepted architecture through documentation alone | keep drift explicit; later ADR/implementation work separately authorized |
| S5-ARCH-001/002/003 artifacts absent from main | Medium | weakens durable provenance | future evidence integration/registry; ARCH-004 remains current durable authority |
| Contract vocabularies are unfrozen | High | premature enums create accidental compatibility commitments | keep candidates open through conformance and Human Contract Gate |

No breaking change is currently required to complete Checkpoint A. A later
draft may identify a breaking candidate, but it must be bounded, versioned,
and returned to the Human Gate before implementation.

## 17. Human Decisions Required

All decisions remain **PENDING**.

### A01 — Logical Contract before CRD

**Recommendation:** approve the implementation-neutral logical Contract as the
mandatory precursor to API and persistence representation.
**Decision:** PENDING.

### A02 — Compatibility policy

**Recommendation:** treat current `agentos.io/v1alpha1` Agent, Task, and
Workflow as supported alpha compatibility inputs; prefer additive evolution,
dual-read/translation, explicit migration, then bounded deprecation.
**Decision:** PENDING.

### A03 — Identity strategy

**Recommendation:** separate resource, Platform execution, Provider, Binding,
realization, native invocation, and correlation identities; never use native
IDs as Platform logical identity.
**Decision:** PENDING.

### A04 — Desired / effective / observed separation

**Recommendation:** require the separation where resolution/reconciliation is
meaningful, especially Agent Instance and Runtime Binding, without forcing
identical serialization on every resource.
**Decision:** PENDING.

### A05 — Logical versus native references

**Recommendation:** domain-type logical references with explicit scope and
resolution; opaque, `0:N`, correlation-only native references in observation
or extension boundaries.
**Decision:** PENDING.

### A06 — Status and condition structural policy

**Recommendation:** share only minimal structural primitives for truth,
reason, safe diagnostics, generation, transition, observation, and freshness;
retain domain ownership and leave vocabulary unfrozen.
**Decision:** PENDING.

### A07 — Resource scope strategy

**Recommendation:** preserve current namespaced API behavior; define logical
scope independently before mapping new candidates to Kubernetes namespaces;
do not decide cluster scope or multi-tenancy in Checkpoint B.
**Decision:** PENDING.

### A08 — Provider-specific extension policy

**Recommendation:** keep Provider/native configuration in versioned extension
or referenced configuration boundaries; stable Core contains only proven
portable semantics. Hermes certification debt stays package/Provider-scoped.
**Decision:** PENDING.

### A09 — Schema evolution and versioning policy

**Recommendation:** classify every later field as existing, additive,
translated, deprecated, or breaking; treat requiredness/defaults/update
semantics as Contract; require version/conversion and migration plans before
breaking public representation changes.
**Decision:** PENDING.

### A10 — Existing Agent API treatment

**Recommendation:** evolve over replace. Preserve current manifests and
identity while Checkpoint B evaluates whether the current Agent representation
can serve as an Agent Definition compatibility facade; do not equate replicas
with Instances or freeze current Provider fields as Core.
**Decision:** PENDING.

### A11 — Existing Task API treatment

**Recommendation:** retain the first-class Task and its current lifecycle;
introduce Execution Identity and richer logical targeting only additively or
through a versioned migration that preserves phase/result/retry meaning.
**Decision:** PENDING.

### A12 — Existing Workflow API treatment

**Recommendation:** retain the current first-class combined DAG/run resource
for v0.2 and defer a Workflow Definition/Execution split; preserve controller,
Task ownership, result passing, skip, aggregation, and Console behavior.
**Decision:** PENDING.

### A13 — Agent reference evolution

**Recommendation:** do not reinterpret `agentRef.name` in place. Checkpoint B
must compare Definition-targeted, Instance-targeted, and policy-routed
references and propose a compatibility-preserving representation.
**Decision:** PENDING.

### A14 — New resource representation budget

**Recommendation:** keep five first-class logical resource candidates, but
make no CRD-count commitment. Agent Instance and Capability Definition require
separate API/persistence justification.
**Decision:** PENDING.

## 18. Contradictions and Stop-Condition Review

| Stop condition | Result |
| --- | --- |
| Durable main contradicts S5-ARCH-004 | Not found |
| Five-resource boundary cannot be reconciled with current APIs | Not found; Agent and Workflow require explicit migration/debt treatment |
| Deferred domain must become first-class | Not required |
| Unbounded breaking change | Not required at Checkpoint A |
| Current API behavior cannot be established | Not found; CRDs, source, tests, examples, and Console establish the material behavior |
| Accepted ADR materially contradicts the accepted boundary | No new contradiction; recorded ADR-0003/0004/0005 implementation drift remains explicit |
| Model Binding detail required before evidence | Not required; thin boundary is sufficient |
| Contract Freeze required | No |

The accepted ADRs and current implementation do contain known drift. It does
not block this documentation-only baseline because the artifact neither
changes the implementation nor resolves the drift. Any later public schema or
lifecycle change remains subject to G2.

## 19. Evidence Debt

- S5-ARCH-001/002/003 named artifacts are not present in the validated main
  tree even though S5-ARCH-004 durably cites and carries their accepted
  conclusions.
- The Agent CRD lacks a dedicated field-level repository test comparable to
  Task and Workflow CRD tests.
- Exact current handling of Kubernetes unknown-field pruning, defaulting on
  persisted legacy objects, upgrade conversion, and deletion/recreation
  identity has not been validated for a proposed new version because no new
  version is proposed yet.
- Current Agent `observedGeneration` and conditions are schema precedents but
  are not backed by equivalent controller/test evidence.
- Platform Execution Identity, logical Agent Instance routing, effective
  Binding provenance, and Capability Definition have spike/architecture
  evidence but no production conformance.
- Runtime and Capability Contracts, status/outcome/recovery vocabularies, and
  Provider certification remain unfrozen.
- ED-S5-001 remains open and affects Hermes certification/readiness only.

## 20. Checkpoint B Proposed Scope

If and only if the Human Checkpoint A Gate passes, Checkpoint B should draft
implementation-neutral logical schema candidates for:

1. Agent Definition;
2. Agent Instance;
3. Task compatibility-aware logical additions;
4. Workflow compatibility-aware logical additions without a definition/run
   split;
5. Capability Definition;
6. embedded Runtime Binding;
7. embedded Capability Binding;
8. thin embedded Model Binding;
9. embedded Platform Execution Identity;
10. only the thin references and owner boundaries accepted here.

Every candidate must include semantic owner, identity, desired/effective/
observed placement, cardinality, mutability, compatibility mapping to current
fields, and unresolved decisions. Checkpoint B should not draft CRDs, Provider
transport/SDK details, universal primitives, frozen vocabularies, migrations,
or production implementation.

Checkpoint B is not authorized by this artifact and has not begun.

## 21. Checkpoint State

CONTRACT_FREEZE: **NO**
SCHEMA_FREEZE: **NO**
RUNTIME_CONTRACT: **NOT_FROZEN**
CAPABILITY_CONTRACT: **NOT_FROZEN**
CONDITION_VOCABULARY: **NOT_FROZEN**
OUTCOME_VOCABULARY: **NOT_FROZEN**
RECOVERY_VOCABULARY: **NOT_FROZEN**
`G-S5-RUNTIME-FREEZE-01`: **FAIL / UNCHANGED**
PRODUCTION_CORE_CHANGE: **0**
ADR_CHANGE: **0**
EXISTING_SCHEMA_CHANGE: **0**
CRD_CHANGE: **0**
NEXT_ACTION: **WAIT_FOR_HUMAN_DECISION**
NEXT_GATE: **Human Checkpoint A Gate**

# Checkpoint B — Resource Schema Draft

## 22. Human Checkpoint A Gate Record

HUMAN DECISION: **PASS**

| Dimension | Checkpoint B authority |
| --- | --- |
| A01-A14 | `ACCEPTED_FOR_SCHEMA_DRAFT` |
| Contract | `NOT_CONTRACT_FROZEN` |
| Schema | `NOT_SCHEMA_FROZEN` |
| CRDs | `NOT_CRD_APPROVED` |
| Traceability gap | `TRACEABILITY_DEBT / DOES_NOT_BLOCK_CHECKPOINT_B` |
| Authorized result | `LOGICAL_SCHEMA_CANDIDATE` only |

Checkpoint A Sections 1-21 remain the historical baseline. The Gate did not
authorize reconstruction of S5-ARCH-001/002/003, reopening a closed session,
or implementation. This section and those below are the distinct Checkpoint B
record.

## 23. Logical Schema Notation

The pseudo-schemas below describe meaning, not JSON, OpenAPI, Protobuf,
Pydantic, Kubernetes metadata, storage, or generated code.

Field classifications:

- `R` — **REQUIRED_V0_2**: needed to preserve the accepted semantic boundary.
- `O` — **OPTIONAL_V0_2**: useful in v0.2, but absence has defined meaning.
- `T` — **THIN_FOUNDATION**: establishes ownership/reference only.
- `D` — **DEFERRED**: excluded pending evidence or a later architecture gate.
- `P` — **PROVIDER_EXTENSION**: owned outside stable Core.
- `C` — **COMPATIBILITY_ONLY**: retained or translated for existing API
  compatibility; not target Core meaning.

Cardinalities are logical. `?` means optional, `[]` means zero or more, and
`[1..N]` means one or more. `Ref<T>` is a logical reference from Section 31;
it does not imply a Kubernetes object reference.

## 24. Agent Definition Logical Schema Candidate

**Purpose:** authoritative, reusable logical definition of what an Agent is
and which governed Binding intent it requests. It is not a running Agent.

**Layers:** primarily `IDENTITY + DESIRED + REFERENCES`; observed definition
validation may exist, but Runtime realization and execution observation do
not.

```text
AgentDefinition {
  identity: ResourceIdentity<AgentDefinition>                 R
  schemaVersion: ContractSchemaVersion                       R
  revision: ResourceRevision                                 R
  generation: DesiredGeneration                              R

  display: {
    displayName?: Text                                       O
    description?: Text                                       O
    labels?: Map<Text, Text>                                 O
  }

  desired: {
    roleOrPurpose: Text                                      R
    instructions?: InstructionReferenceOrInline              O
    runtimeBinding: DesiredRuntimeBinding                    R
    capabilityBindings: CapabilityBinding[]                  O
    modelBinding?: ThinModelBinding                          T
    workspaceRef?: Ref<Workspace>                            T
    stateRef?: Ref<StateOrMemory>                            T
    knowledgeRefs?: Ref<Knowledge>[]                         T
    policyRefs?: Ref<Policy>[]                               T
    permissionRefs?: Ref<Permission>[]                       T
  }

  status?: {
    observedGeneration?: DesiredGeneration                   O
    validationConditions?: DefinitionCondition[]             O
  }
}
```

### 24.1 Agent Definition field semantics

| Field | Class | Ownership and constraint |
| --- | --- | --- |
| `identity` | R | Platform-owned logical resource identity, stable across Instance and realization replacement |
| `schemaVersion` | R | Logical Contract schema version; not Kubernetes `apiVersion` |
| `revision` | R | Identifies this immutable/mutable resource representation revision; exact mechanics pending B14 |
| `generation` | R | Monotonic desired-state generation used by effective/observed provenance |
| `display.*` | O | Human/product presentation only; not identity or routing |
| `roleOrPurpose` | R | Provider-independent semantic purpose; current `identity.role` maps here |
| `instructions` | O | Desired logical instructions; inline form is compatibility-sensitive and size-bounded |
| `runtimeBinding` | R | Desired template/constraints only; no realization or Provider-native configuration |
| `capabilityBindings` | O | `1:N` governed intent; empty means no declared Capability use |
| `modelBinding` | T | Thin model requirements/reference only; routing/fallback excluded |
| thin references | T | Do not import lifecycle of Workspace, State, Knowledge, Policy, or Permission |
| `status` | O | Definition validation/reconciliation only; no running state |

### 24.2 Ownership and lifecycle

- Core/Agent Definition owns identity, desired definition, desired Binding
  intent, and desired generation.
- Each Agent Instance references exactly one Definition and records the
  Definition version/generation from which its effective state was derived.
- Definition update does not silently mutate an executing Instance without an
  explicit adoption/rollout rule. The exact adoption policy is deferred to a
  lifecycle decision; provenance is required now.
- Deletion is blocked while live Instances reference the Definition unless an
  explicit, authorized cascading/orphaning policy exists.
- Pod, container, Gateway, Runtime session, native configuration, realization
  status, routing eligibility, and recovery are prohibited here.

## 25. Agent Instance Logical Schema Candidate

**Purpose:** stable platform-managed identity for one logical running Agent,
surviving replacement of all native realizations.

**Layers:** `IDENTITY + DESIRED + EFFECTIVE + OBSERVED + STATUS + REFERENCES +
LIFECYCLE`.

```text
AgentInstance {
  identity: ResourceIdentity<AgentInstance>                   R
  schemaVersion: ContractSchemaVersion                       R
  revision: ResourceRevision                                 R
  generation: DesiredGeneration                              R

  desired: {
    definitionRef: Ref<AgentDefinition>                      R
    lifecycleState: DesiredInstanceLifecycle                 R
  }

  effective: {
    definitionRevision: ReferencedRevision                   R
    definitionGeneration: DesiredGeneration                  R
    runtimeBinding: EffectiveRuntimeBinding                  R
    modelBinding?: EffectiveThinModelProjection              T
    resolution: ResolutionProvenance                         R
  }

  status: {
    observedGeneration?: DesiredGeneration                   O
    routingEligibility: RoutingEligibility                   R
    instanceConditions: AgentInstanceCondition[]             O
    runtimeConditions: RuntimeCondition[]                    O
    recoveryAssessment?: RecoveryAssessment                  O
    realizationSummary: RealizationSummary                   R
    nativeReferences: NativeReference[]                      O
    executionCorrelations?: ExecutionCorrelationRef[]        O
    observedAt: Instant                                      R
  }
}
```

### 25.1 Agent Instance field semantics

| Field | Class | Ownership and constraint |
| --- | --- | --- |
| `identity` | R | Stable logical Instance identity; never copied from a native realization |
| `definitionRef` | R | Exactly one Agent Definition; Definition-to-Instance is `1:N` |
| `lifecycleState` | R | Desired logical existence/availability state; vocabulary remains a candidate |
| effective Definition provenance | R | Exact Definition revision/generation resolved for this Instance |
| `effective.runtimeBinding` | R | Derived from authorized Definition intent and resolution metadata; not desired authority |
| effective Model projection | T | Only if needed to convey resolved thin requirements; no model-routing design |
| `routingEligibility` | R | Control Plane-owned decision/projection with reason, evidence freshness, and observed time |
| `instanceConditions` | O | Instance-domain assertions; vocabulary unfrozen |
| `runtimeConditions` | O | Runtime-domain Provider-normalized assertions, kept structurally/domain distinct |
| `recoveryAssessment` | O | Instance-owned semantic assessment; restart is evidence, not recovery |
| `realizationSummary` | R | Counts and high-level observation only; no native topology authority |
| native refs | O | `0:N` opaque evidence across temporal/active realizations |
| execution correlations | O | Bounded links to active/recent logical executions where operationally required; not execution history storage |

`RoutingEligibility` logically contains a decision (`ELIGIBLE`, `INELIGIBLE`,
or `UNKNOWN`), stable reason, evidence freshness, and observation time. The
vocabulary and timeout/escalation policy remain unfrozen. A Provider may supply
evidence but cannot select among platform Agent Instances.

`RealizationSummary` contains at most active count, temporal/observed count if
bounded, desired/available summary where portable, and freshest observation.
It cannot imply that one Instance equals one Pod or that zero observed native
objects means the Instance never existed.

### 25.2 Recovery Assessment candidate

```text
RecoveryAssessment {
  status: TRUE | FALSE | UNKNOWN | NOT_APPLICABLE             R
  reason: StableDomainReason                                  R
  assessedAt: Instant                                         R
  bindingVerified: TriState                                   R
  identityContinuityVerified: TriState                        R
  routingVerified: TriState                                   R
  runtimeSemanticsVerified: TriState                          R
  message?: SafeDiagnostic                                   O
}
```

The predicates are structural candidates, not a frozen universal checklist.
Applicable predicates may vary by declared Runtime ownership/profile.
`UNKNOWN`, `FALSE`, and `NOT_APPLICABLE` are not interchangeable.

## 26. Current Agent Compatibility Projection

### 26.1 Field/semantic map

| Current `Agent` field/behavior | Target owner | Difference | Classification | Draft interpretation |
| --- | --- | --- | --- | --- |
| `metadata.name/namespace` | Definition identity | Current object also anchors Service/Deployment | KEEP + MIGRATION_REQUIRED | Preserve as Definition-facing compatibility identity; Instance identity is new and separate |
| `metadata.uid/resourceVersion/generation` | API representation | Kubernetes-specific | KEEP in current API | May map to representation revision/generation, not implementation-neutral identity |
| `spec.identity.role` | Definition | Direct alignment | KEEP | Maps to `roleOrPurpose` |
| `spec.identity.displayName` | Definition display | Direct alignment | KEEP | Maps to `display.displayName` |
| `spec.instructions.systemPrompt` | Definition desired | Inline and Runtime-env realization today | KEEP / COMPATIBILITY_ALIAS | Maps to logical instructions; translation remains compatibility behavior |
| `spec.capabilities[]` strings | Definition desired Capability intent | Lacks Definition/version/operation/policy | COMPATIBILITY_ALIAS + MIGRATION_REQUIRED | Translate only through explicit legacy capability mapping; unmapped strings remain visible/invalid, never silently upgraded |
| `spec.runtime.type` | Definition desired Runtime Binding | Current enum mixes runtime family and selection | COMPATIBILITY_ALIAS | Maps to legacy runtime class constraint, not Provider identity |
| `spec.runtime.image` | Provider/package configuration | Native packaging detail | PROVIDER_OWNED + COMPATIBILITY_ONLY | Legacy translator may create package/config reference; prohibited as target Core field |
| `spec.model.provider/name` | Thin Model Binding / Provider-owned detail | Over-specifies current selection | COMPATIBILITY_ALIAS + MIGRATION_REQUIRED | Preserve legacy read; map only to thin reference/requirement supported by model evidence |
| `spec.model.endpoint/baseUrl/secretRef` | Provider/configuration/credential owner | Provider-specific and security-sensitive | PROVIDER_OWNED + COMPATIBILITY_ONLY | Referenced legacy configuration; never copied into stable Core schema |
| `spec.resources.cpu/memory` | Definition/runtime constraint intent | Current simplified Kubernetes values | KEEP concept / MIGRATION_REQUIRED representation | Map to portable constraints only if semantics proven; raw representation remains compatibility input |
| `spec.replicas` | Current deployment realization intent | Not logical Instance count by accepted semantics | UNRESOLVED + COMPATIBILITY_ONLY | Preserve current behavior; do not create N Agent Instances from this field without a later decision |
| `status.phase` | Current Agent infrastructure observation | Does not equal Instance condition or recovery | COMPATIBILITY_ALIAS | Preserve legacy projection; derive only from approved Instance/Runtime observations later |
| `status.readyReplicas` | Native realization summary | Infrastructure-specific count | COMPATIBILITY_ALIAS | May project from bounded realization summary; not routing identity |
| `status.observedGeneration` | Definition/legacy reconciliation | Schema-declared but weak implementation evidence | KEEP concept | Must have conformance before target claim |
| `status.conditions` | Definition/legacy infrastructure status | Kubernetes-like structural precedent only | KEEP structure / MIGRATION_REQUIRED vocabulary | Do not merge with Runtime or Instance conditions |
| same-name Deployment/Service | Provider/implementation realization | Current direct Operator behavior | MIGRATION_REQUIRED | Retain until later Provider implementation migration; never target logical identity |

### 26.2 Recommended strategy

**Recommend OPTION B: current Agent evolves toward Agent Definition and Agent
Instance is introduced separately**, with a bounded compatibility translation
rather than a rename.

Rationale:

1. current Agent already owns durable definition-like role, instructions,
   Capability intent, resource intent, and desired Runtime/Model inputs;
2. preserving its identity and manifests minimizes unnecessary replacement;
3. Agent Instance requires independent identity and cannot be derived from a
   Pod, Service, or replica index;
4. Option A would perpetuate Definition/Instance ambiguity indefinitely;
5. Option C remains the required representation mechanism if additive
   evolution cannot preserve existing wire semantics, but logical versioning
   should not pre-decide the Kubernetes version transition.

The compatibility phase would conceptually keep current Agent behavior while a
deterministic interpreter produces Definition intent and one legacy execution
projection. It must not fabricate first-class Instance identity from
`spec.replicas`. Exit criteria require explicit Instance creation/adoption,
legacy field translation, observable warnings for unmapped values, rollback,
and an approved API migration. No migration is implemented here.

## 27. Task Logical Schema Candidate

**Purpose:** durable request to perform bounded work, owning submission,
execution observation, retry accounting, and Task-specific terminal outcome.
It carries Platform Execution Identity but is not a universal Execution.

```text
Task {
  identity: ResourceIdentity<Task>                            R
  schemaVersion: ContractSchemaVersion                       R
  revision: ResourceRevision                                 R

  request: {
    executionIdentity: PlatformExecutionIdentity             R
    target: AgentTarget                                      R
    input: InputValueOrReference                             R
    routingIntent?: RoutingIntent                            O
    authorizationRefs?: Ref<AuthorizationDecisionOrPolicy>[] T
    timeout?: Duration                                       O
    cancellationIntent?: CancellationIntent                  D
    retryPolicy?: TaskRetryPolicy                            O
  }

  status: {
    submission: SubmissionState                              R
    execution: TaskExecutionState                            R
    attempts: AttemptSummary                                 R
    outcome?: TaskOutcome                                    O
    selectedInstanceRef?: Ref<AgentInstance>                 O
    nativeReferences?: NativeReference[]                     O
    submittedAt?: Instant                                    O
    startedAt?: Instant                                      O
    completedAt?: Instant                                    O
    observedAt: Instant                                      R
  }
}
```

### 27.1 State separation

| Layer | Meaning | Compatibility |
| --- | --- | --- |
| Submission | accepted/rejected/pending Provider handoff or routing disposition | New logical distinction; current Pending/initial Running must remain projectable |
| Execution | not started/running/terminal observation of this Task | Current phase values remain compatibility wire values; candidate vocabulary unfrozen |
| Outcome | Task-owned success/failure/timeout/cancel result and safe diagnostic | Current result/reason/retryable map here; no universal Outcome |

`TaskOutcome` logically includes terminal disposition, optional output value or
reference, stable Task-domain reason, retryability assessment where meaningful,
and safe message. Result payload/reference representation remains open; current
string `status.result` must remain readable/projectable.

`AttemptSummary` preserves current meaning: attempts belong to one Task
execution unless an approved replay/idempotency rule creates another Platform
Execution Identity. It contains total attempts and optionally bounded latest
attempt metadata. It is not an attempt-history database.

### 27.2 Target semantics

```text
AgentTarget =
  DefinitionTarget { definitionRef, routingIntent? }
  | InstanceTarget { instanceRef, targetingAuthorizationRef }
  | LegacyAgentTarget { name, impliedScope }                  C
```

The union is logical, not a proposed wire union. Definition targeting asks the
Control Plane to choose an eligible Instance. Explicit Instance targeting is
privileged/authorized and still cannot name a native realization. Current
`agentRef.name` keeps its exact legacy meaning until a representation decision
maps it; it is not reinterpreted in place.

Cancellation is `DEFERRED` as an operative Contract behavior because current
source has no cancellation semantics and Providers have no universal evidence.
The schema may reserve a future intent boundary only after Checkpoint C; it is
not a v0.2 required field here.

## 28. Workflow Logical Schema Candidate

**Purpose:** durable DAG/orchestration resource that currently combines
declarative graph definition/request with one execution observation/outcome.

**Checkpoint B conclusion:** separation is semantically useful but a sixth
first-class `WorkflowExecution` is neither necessary nor authorized. Use two
embedded structures inside the existing first-class Workflow boundary.

```text
Workflow {
  identity: ResourceIdentity<Workflow>                        R
  schemaVersion: ContractSchemaVersion                       R
  revision: ResourceRevision                                 R

  definition: {
    nodes: WorkflowNodeDefinition[1..N]                      R
    graphConstraints?: WorkflowGraphConstraints              O
  }

  execution: {
    executionIdentity: PlatformExecutionIdentity             R
    requestRevision: ResourceRevision                        R
    submission: SubmissionState                              R
    nodeExecutions: Map<NodeIdentity, WorkflowNodeExecution> R
    outcome?: WorkflowOutcome                                O
    startedAt?: Instant                                      O
    completedAt?: Instant                                    O
    observedAt: Instant                                      R
  }
}
```

```text
WorkflowNodeDefinition {
  nodeIdentity: LocalLogicalName                              R
  taskRequest: EmbeddedTaskRequest                           R
  dependsOn: NodeIdentity[]                                  O
  inputSources: NodeOutputReference[]                        O
}

WorkflowNodeExecution {
  taskRef?: Ref<Task>                                        O
  executionIdentity?: PlatformExecutionIdentity              O
  state: TaskExecutionProjection                            R
  outcomeSummary?: TaskOutcomeProjection                     O
}
```

The embedded definition/execution distinction prevents semantic conflation in
the logical Contract while preserving one current Workflow resource. Current
Workflow-created Task resources remain the authoritative Task lifecycles; the
node execution entry is an aggregate/projection, not a duplicate desired Task.

### 28.1 Future promotion trigger

`WorkflowExecution` becomes a **FUTURE_PROMOTION_CANDIDATE** only if accepted
evidence requires multiple independently identified, retained, authorized,
reconciled executions of one reusable Workflow definition, with independent
lifecycle and references that cannot be represented without overloading the
Workflow resource. Promotion requires a new architecture decision, API budget,
compatibility/migration plan, and must not be inferred merely from the Console
class name `WorkflowExecutionDetail`.

## 29. Capability Definition Logical Schema Candidate

**Purpose:** provider- and transport-independent enterprise identity and
versioned semantic definition of a governed ability.

**Layers:** `IDENTITY + DESIRED/DECLARATIVE + REFERENCES`; invocation outcomes
belong to Capability invocation context, not Definition status.

```text
CapabilityDefinition {
  identity: ResourceIdentity<CapabilityDefinition>            R
  schemaVersion: ContractSchemaVersion                       R
  revision: ResourceRevision                                 R
  generation: DesiredGeneration                              R

  display?: {
    displayName?: Text                                       O
    description?: Text                                       O
    labels?: Map<Text, Text>                                 O
  }

  semantics: {
    operationIdentity: LogicalOperationIdentity              R
    inputSchemaRef: SchemaReference                          R
    outputSchemaRef: SchemaReference                         R
    riskClassification: RiskClassification                  R
    authorizationRequirements: AuthorizationRequirements    R
    executionCharacteristics: ExecutionCharacteristics      R
    supportedDispositions: InteractionDisposition[1..N]      R
  }

  compatibility: {
    capabilityVersion: SemanticVersion                       R
    compatibilityPolicy: CompatibilityPolicyReference       R
  }

  policyRefs?: Ref<Policy>[]                                 T
}
```

`ExecutionCharacteristics` describes only semantic properties required for
safe use, such as side-effect profile, idempotency declaration, and whether an
inline or deferred disposition is supported. Exact vocabulary and retry/cancel
guarantees remain unfrozen and must not exceed spike evidence.

Capability identity is not an MCP tool, REST endpoint, SDK function, CLI
command, Provider descriptor, or native invocation. Those are Provider/native
realizations mapped by a Capability Provider after authorization.

## 30. Embedded Binding and Execution Value Candidates

### 30.1 Desired Runtime Binding

```text
DesiredRuntimeBinding {
  providerRef?: ProviderRef<RuntimeProvider>                  O
  runtimePackageRef?: RuntimePackageRef                      O
  runtimeClass: LogicalRuntimeClass                          R
  configurationRef?: ProviderConfigurationRef                P
  declaredRuntimeCapabilities?: RuntimeCapabilityRequirement[] O
  constraints?: RuntimeConstraint[]                         O
  compatibilityRequirement: ProviderCompatibilityRequirement R
  extensionRef?: ProviderExtensionRef                        P
}
```

At least one deterministic resolution input among Provider reference, package
reference, and runtime class/constraints must be sufficient under the future
resolution policy. The exact exclusivity rule is pending. `configurationRef`
and `extensionRef` are opaque references whose targets are Provider-owned;
Core does not inspect Hermes/OpenClaw/Native fields.

### 30.2 Effective Runtime Binding

```text
EffectiveRuntimeBinding {
  desiredSource: { definitionRef, generation }                R
  providerRef: ProviderRef<RuntimeProvider>                   R
  runtimePackageRef?: RuntimePackageRef                      O
  runtimeClass: LogicalRuntimeClass                          R
  resolvedConfigurationRef?: ProviderConfigurationRef        P
  declaredCompatibility: CompatibilityDecision              R
  resolvedConstraints?: RuntimeConstraint[]                 O
  extensionRef?: ProviderExtensionRef                        P
  resolvedAt: Instant                                        R
}
```

This is a derived Instance-owned projection. It cannot be edited as a second
desired source. Capability declarations here concern Runtime Contract support,
not enterprise Capability Bindings.

### 30.3 Capability Binding

```text
CapabilityBinding {
  capabilityRef: Ref<CapabilityDefinition>                   R
  capabilityVersionRequirement: VersionRequirement          R
  operationConstraints?: LogicalOperationIdentity[]          O
  providerRef?: ProviderRef<CapabilityProvider>              O
  policyRefs?: Ref<Policy>[]                                 T
  authorizationRequirements?: AuthorizationRequirements      O
  configurationRef?: ProviderConfigurationRef                P
  constraints?: CapabilityUseConstraint[]                   O
  compatibilityRequirement: ProviderCompatibilityRequirement R
}
```

The Binding is desired Agent Definition-owned governed intent. Discovery may
identify a Capability or feasible Provider but never grants authority.
Invocation-time effective resolution revalidates authorization and
compatibility. `DENY` terminates before Provider invocation and produces a
Capability-domain disposition/evidence, not a Runtime failure.

### 30.4 Thin Model Binding

```text
ThinModelBinding {
  modelRef?: Ref<Model>                                      T
  providerClassRef?: Ref<ModelProviderClass>                 T
  policyRef?: Ref<ModelPolicy>                               T
  configurationRef?: ProviderConfigurationRef                P
}
```

At least one reference would be required only after the Model Contract defines
resolution rules. For now the entire value is optional and thin. Fallback,
ranking, cost/quota/context routing, Provider selection algorithms, credential
shape, and gateway behavior are `DEFERRED` pending S5-SPIKE-005 or equivalent
accepted evidence.

### 30.5 Platform Execution Identity

```text
PlatformExecutionIdentity {
  logicalId: PlatformGeneratedId                              R
  scope: ExecutionScope                                      R
  rootId?: PlatformGeneratedId                               O
  parentId?: PlatformGeneratedId                             O
}
```

Minimum semantics:

- `logicalId` is created by the Platform once for one logical execution and is
  immutable throughout Provider routing, Runtime realization replacement, and
  Capability calls attributable to that execution.
- `scope` prevents accidental global/name ambiguity and is Platform-owned.
- `rootId`/`parentId` are optional correlation relationships, not proof of a
  universal execution tree or lifecycle.
- attempt/retry/replay rules determine whether the same or a related identity
  is used; those rules remain domain-specific and unfrozen.
- no native identifier may populate any of these fields.

## 31. Logical Reference Model

Use a small bounded family rather than one structure that pretends all
relationships resolve identically.

```text
ResourceRef<T> {
  domain: LogicalDomain                                      R
  kind: LogicalResourceKind                                 R
  logicalId?: PlatformResourceId                             O
  name?: LogicalName                                         O
  scope: LogicalScope                                        R
  revisionRequirement?: RevisionRequirement                 O
  generationExpectation?: DesiredGeneration                  O
}

ProviderRef<P> {
  domain: RUNTIME | CAPABILITY | MODEL                       R
  providerId: ProviderId                                     R
  compatibilityVersion: ProviderCompatibilityVersion         R
}

SchemaReference {
  schemaId: LogicalSchemaId                                  R
  schemaVersion: ContractSchemaVersion                       R
}
```

Rules:

- a `ResourceRef` must contain a resolvable logical ID or name under its scope;
  whether both may coexist and mismatch handling are representation decisions;
- `kind/domain` prevent a name from resolving across semantic domains;
- revision requirements express exact/range/channel intent without confusing
  desired generation;
- current same-namespace `agentRef.name` is a `COMPATIBILITY_ONLY` shorthand
  whose scope is fixed by the current API;
- Provider refs are resolved through domain-specific internal metadata and do
  not imply a public Provider resource;
- schema refs identify semantic input/output schemas, not transport endpoints.

## 32. Native Reference Model

```text
NativeReference {
  domain: RUNTIME | CAPABILITY | INFRASTRUCTURE              R
  providerRef?: ProviderRef                                  O
  nativeKind: OpaqueKindLabel                                R
  opaqueId: OpaqueText                                       R
  observedAt: Instant                                        R
  executionRef?: PlatformExecutionIdentity                  O
  realizationRole?: OpaqueRoleLabel                         O
  freshness?: EvidenceFreshness                             O
}
```

`nativeKind` and `realizationRole` are diagnostic labels, not Core enums that
encode Provider topology. `opaqueId` is never parsed, selected, generated, or
treated as authoritative by Core. References are bounded, redactable evidence;
raw payloads, credentials, endpoints, and Provider-native state machines stay
outside Core. A single Platform execution may correlate with `0:N` native
references, and one Instance may have `1:N` temporal and `0:N` active Runtime
realizations.

## 33. Desired / Effective / Observed Placement

| Candidate | Desired | Effective | Observed/status | Reason |
| --- | --- | --- | --- | --- |
| Agent Definition | authoritative definition and Binding intent | no Runtime-effective authority; optional validation/default view | validation conditions only | Definition is what the Agent is, not where it runs |
| Agent Instance | Definition association and desired lifecycle | Definition revision, Runtime Binding, thin Model projection, resolution provenance | routing eligibility, domain conditions, recovery, realization evidence | Instance bridges logical lifecycle to Provider realization |
| Task | work request, target/routing intent, timeout/retry intent | selected Instance/routing decision may be recorded in status | submission, execution, attempts, Task Outcome, correlations | requested work and observed performance remain distinguishable |
| Workflow | embedded graph definition/request | runnable graph/node resolution may be an internal projection | embedded execution identity, node Task projections, aggregate outcome | preserves current one-resource compatibility while separating semantics |
| Capability Definition | authoritative semantic operation and compatibility declaration | none in Definition; effective Provider resolution is invocation-time | validation only | Definition does not own invocation lifecycle |
| Runtime Binding | Definition-owned desired template | Instance-owned derived projection | Runtime conditions/native evidence outside Binding itself | prevents duplicate desired authority |
| Capability Binding | Definition-owned governed intent | invocation-time Provider/authorization resolution | Capability outcome/native invocation evidence outside Binding | discovery and authorization remain separate |
| Model Binding | thin desired references only | optional thin projection | no model-routing status in v0.2 draft | evidence does not justify more |

No candidate is forced into identical `spec/status` containers. These are
semantic planes; representation comes later.

## 34. Versioning Strategy

| Version concept | Meaning | Owner | Must not be confused with |
| --- | --- | --- | --- |
| Contract schema version | version of logical field/semantic contract | Contract owner/Human Gate | Kubernetes API version |
| Kubernetes API version | served/stored representation and conversion boundary | API/CRD owner | logical resource revision |
| Resource revision/version | particular resource content/release identity | resource owner | desired generation |
| Desired generation | monotonic change to desired intent used for observation provenance | reconciled resource owner | semantic release version |
| Capability semantic version | compatibility of Capability operation/input/output meaning | Capability owner | Capability Provider version |
| Provider compatibility version | descriptor/interface compatibility understood by domain resolver | Provider/Contract ecosystem | native runtime version |
| Runtime Package version | deployable package/distribution version | Runtime package publisher | Runtime Provider interface version |
| Native runtime version | opaque native software/system version evidence | Provider/native owner | Core Contract version |

Recommendations:

1. every logical resource carries a Contract schema version independently of
   its API representation;
2. incompatible logical schema changes require a new schema version and
   documented conversion/migration; additive optional fields still require
   default/absence semantics;
3. resource revision and desired generation remain distinct so an Instance can
   prove which Definition it resolved;
4. references may state revision/version requirements, but implicit "latest"
   adoption is prohibited unless an explicit policy defines it;
5. Provider compatibility is decided by domain-specific registry metadata;
   Core never compares opaque native versions as Contract versions;
6. existing `agentos.io/v1alpha1` remains a compatibility representation. This
   draft does not select its successor or approve conversion webhooks/CRDs.

## 35. Logical Invariants

### 35.1 Cross-resource

1. A logical resource identity belongs to exactly one resource kind/domain and
   cannot be a native identifier.
2. An Agent Definition may own desired Binding intent but never running
   realization state.
3. Each Agent Instance references exactly one resolvable Agent Definition.
4. One Agent Definition may have zero or many Agent Instances.
5. A live Agent Instance records the Definition revision/generation used by
   its effective projection.
6. Deleting a referenced Agent Definition is blocked while live Instances
   exist unless an explicit approved lifecycle policy handles them.
7. Effective Runtime Binding derives from authorized Definition intent and
   records provenance; it is never independently edited as desired state.
8. Control Plane routing selects a logical Agent Instance. Runtime Provider
   translation cannot replace that selection.
9. Native realization replacement cannot change Agent Instance identity.
10. Platform Execution Identity is immutable for one logical execution and is
    propagated without replacement across Providers.
11. Native references are `0:N` evidence and cannot be authoritative resource,
    routing, or execution identity.
12. `UNKNOWN`, `FALSE`, and `NOT_APPLICABLE` remain semantically distinct.

### 35.2 Task and Workflow

13. A Task owns one requested-work lifecycle and Task-specific outcome; retries
    follow current attempt semantics until a new rule is accepted.
14. Task submission, execution state, and terminal outcome cannot contradict;
    exact transition vocabulary remains a Checkpoint C concern.
15. A Task target resolves only to a logical Definition/Instance under Control
    Plane policy, never directly to a Pod/Gateway/session.
16. Explicit Instance targeting requires authorization independent of target
    existence or Runtime feasibility.
17. A Workflow node has a unique local identity and may reference only declared
    nodes under an acyclic graph.
18. Workflow node execution projects an owned Task lifecycle and cannot become
    a duplicate desired Task authority.
19. Workflow aggregate outcome is derived from its node semantics and remains
    distinct from Task outcomes.
20. Current failure/timeout/skip, independent-sibling, fan-in, result-passing,
    and idempotent reconciliation semantics remain compatibility constraints.

### 35.3 Capability and Provider

21. Capability identity/version/operation is independent of transport,
    endpoint, tool, command, and Provider.
22. Discovery, compatibility, authorization, and invocation are distinct
    decisions/stages.
23. Authorization is evaluated before Capability Provider invocation; `DENY`
    may terminate with zero native invocation references.
24. A Capability Provider may translate an authorized invocation but cannot
    expand operation, permission, policy, or Platform identity.
25. Provider-specific configuration is referenced opaquely and cannot become
    stable Core semantics through widespread use.
26. Runtime Provider and Capability Provider registries/interfaces remain
    distinct; no universal Provider/Binding/Registry schema is implied.

## 36. Field-Level Compatibility Map

### 36.1 Current Task to draft Task

| Current semantic | Draft semantic | Change | Classification |
| --- | --- | --- | --- |
| metadata identity/scope | Task resource identity | direct conceptual mapping | KEEP |
| `spec.agentRef.name` | legacy Agent target | exact current meaning retained | KEEP + COMPATIBILITY_ALIAS |
| `spec.input.prompt` | request input | string remains supported input representation | KEEP |
| `spec.timeoutSeconds` | request timeout | preserve default 300 and minimum in current representation | KEEP |
| create handler acceptance | submission/execution transition | logical separation makes implicit state explicit | ADDITIVE |
| `status.phase` | execution/outcome projection | wire enum remains; target domains distinguish state/outcome | KEEP + COMPATIBILITY_ALIAS |
| `status.result` string | Task Outcome output value/reference | string compatibility projection required | KEEP + ADDITIVE |
| reason/message/retryable | Task Outcome diagnostic/retry assessment | domain ownership preserved | KEEP |
| `status.attempts` | Attempt Summary total | direct semantic mapping | KEEP |
| start/completion times | Task status timestamps | direct mapping | KEEP |
| no execution ID | embedded Platform Execution Identity | new stable correlation | ADDITIVE |
| no selected Instance | selected logical Instance reference | new routing evidence | ADDITIVE |
| no cancellation | deferred cancellation intent/state | insufficient evidence | DEFERRED |

No immediate breaking Task change is necessary. A richer target representation
must coexist with or version the legacy Agent name; reinterpreting that field
is a `BREAKING_CANDIDATE` and is not recommended.

### 36.2 Current Workflow to draft Workflow

| Current semantic | Draft semantic | Change | Classification |
| --- | --- | --- | --- |
| metadata identity/scope | Workflow resource identity | direct mapping | KEEP |
| `spec.tasks[]` | embedded `definition.nodes[]` | semantic grouping only | KEEP + COMPATIBILITY_ALIAS |
| task `name` | local node identity | direct mapping | KEEP |
| node `agentRef/input/timeout` | embedded Task request | direct/compatibility mapping | KEEP |
| `dependsOn` | graph dependency refs | direct mapping | KEEP |
| `input.from[].task` | node output refs | direct mapping | KEEP |
| generated Task CR | authoritative node Task lifecycle | preserved | KEEP |
| Task naming/labels/owner ref | API/implementation correlation | current compatibility behavior | KEEP / future MIGRATION_REQUIRED only if changed |
| `status.phase` | Workflow Outcome/execution projection | preserve wire values | KEEP + COMPATIBILITY_ALIAS |
| status task map | embedded node execution projections | direct mapping | KEEP |
| no execution ID | embedded Workflow Platform Execution Identity | additive | ADDITIVE |
| combined definition/run | two embedded logical structures | no new resource | ADDITIVE semantic clarification |
| reusable definition with many runs | future promoted resource boundary | not proven/authorized | DEFERRED |

No immediate breaking Workflow change is necessary. The draft preserves
Workflow-to-Task behavior and does not create a sixth resource.

### 36.3 Current Runtime abstraction to target boundary

| Current | Target interpretation | Classification |
| --- | --- | --- |
| Agent `runtime.type` | legacy desired Runtime class constraint | COMPATIBILITY_ALIAS |
| Agent `runtime.image` | Provider/package configuration input | PROVIDER_EXTENSION + COMPATIBILITY_ONLY |
| Operator direct Deployment/Service construction | current Native realization implementation | MIGRATION_REQUIRED later |
| same-name Service routing | legacy Runtime interaction route | MIGRATION_REQUIRED later |
| Native `/v1/invoke` | Runtime-specific Provider/native protocol | KEEP implementation; not Core Contract |
| runtime-local model Provider ABC | Runtime implementation detail | KEEP; not Runtime Provider |
| no Runtime Binding/Provider registry | accepted target boundaries | ADDITIVE logical/internal metadata |

## 37. Golden Demo Traceability

```text
Digital Employee (business projection; not Core resource)
  -> Agent Definition
       identity + role/purpose + instructions
       desired Runtime Binding
       Capability Bindings
       thin Model/Workspace/State/Knowledge/Policy refs
  -> Agent Instances [1..N]
       stable logical identity
       effective Runtime Binding
       routing eligibility + conditions + recovery
       native realization evidence [0..N]
       -> OpenClaw Runtime Provider
       -> Hermes Runtime Provider (only if certified; ED-S5-001 remains)
       -> Native Runtime Provider
  -> Workflow
       embedded DAG definition + execution identity
       -> Tasks
            Definition target or authorized Instance target
            Platform Execution Identity
            Task-specific outcome
  -> Capability Binding
       Capability Definition + governed use
       discovery -> compatibility -> authorization
       -> REST Provider | MCP Provider | future Provider
       -> opaque native invocation evidence
```

Provider switching changes effective Binding/realization evidence, not Agent
Definition, Instance, Task/Workflow, Capability, or Platform execution identity.
The same projection supports multiple Instances, logical routing, realization
replacement, semantic recovery, and different Capability protocols without a
DigitalEmployee API or demo-specific Core fields.

## 38. Human Decisions Required — Checkpoint B

All decisions remain **PENDING** until the Human Checkpoint B Gate.

### B01 — Agent Definition logical schema

**Recommendation:** accept Section 24 as the authoritative desired logical
definition with Binding intent and thin references, excluding running/native
state.
**Decision:** PENDING.

### B02 — Agent Instance logical schema

**Recommendation:** accept Section 25 as stable running logical identity with
desired lifecycle, effective Binding provenance, routing eligibility,
domain-owned conditions/recovery, and opaque realization evidence.
**Decision:** PENDING.

### B03 — Current Agent compatibility strategy

**Recommendation:** OPTION B—evolve current Agent toward Agent Definition and
introduce Agent Instance separately, using bounded compatibility translation;
do not rename or reinterpret current fields in place.
**Decision:** PENDING.

### B04 — Task logical schema

**Recommendation:** retain first-class Task, embed Platform Execution Identity,
distinguish submission/execution/outcome, preserve current attempt and wire
semantics, and add richer logical targeting only compatibly.
**Decision:** PENDING.

### B05 — Workflow logical schema

**Recommendation:** retain one first-class Workflow for v0.2 with embedded
definition and execution structures; preserve owned Task behavior and defer
WorkflowExecution promotion to the trigger in Section 28.1.
**Decision:** PENDING.

### B06 — Capability Definition logical schema

**Recommendation:** accept provider/transport-independent identity, operation,
input/output schema refs, risk/authorization/execution characteristics, and
semantic compatibility version.
**Decision:** PENDING.

### B07 — Runtime Binding shape

**Recommendation:** accept separate desired Definition-owned template and
effective Instance-owned projection with provenance; Provider configuration is
opaque extension/reference only.
**Decision:** PENDING.

### B08 — Capability Binding shape

**Recommendation:** accept Agent Definition-owned governed intent with
Capability/version/operation constraints and invocation-time Provider and
authorization resolution.
**Decision:** PENDING.

### B09 — Thin Model Binding

**Recommendation:** accept only optional model, Provider-class, policy, and
opaque configuration references; defer all routing/fallback algorithms.
**Decision:** PENDING.

### B10 — Platform Execution Identity

**Recommendation:** accept Platform-generated logical ID plus scope and
optional root/parent correlation; exact retry/replay hierarchy remains
domain-specific and unfrozen.
**Decision:** PENDING.

### B11 — Logical reference family

**Recommendation:** accept bounded Resource, Provider, and Schema reference
families with explicit domain/kind/scope/version semantics instead of one
universal reference.
**Decision:** PENDING.

### B12 — Native reference model

**Recommendation:** accept separate opaque, bounded, timestamped,
domain/Provider-attributed evidence that can correlate to Platform execution
but never becomes logical identity or routing authority.
**Decision:** PENDING.

### B13 — Desired/effective/observed placement

**Recommendation:** accept Section 33; semantic planes apply selectively and
must not become identical Kubernetes-like serialization.
**Decision:** PENDING.

### B14 — Versioning strategy

**Recommendation:** distinguish Contract schema, API, resource revision,
desired generation, Capability semantic, Provider compatibility, Runtime
Package, and native Runtime versions.
**Decision:** PENDING.

### B15 — Compatibility strategy

**Recommendation:** classify existing fields explicitly; prefer keep/additive/
alias, require migration for ownership changes, and treat in-place reference
reinterpretation or wire-semantic changes as breaking candidates.
**Decision:** PENDING.

### B16 — Agent target model

**Recommendation:** support Definition-targeted logical routing and authorized
Instance targeting while retaining current `agentRef.name` as a legacy target;
do not target native realizations.
**Decision:** PENDING.

### B17 — Workflow execution separation

**Recommendation:** accept embedded definition/execution separation for v0.2;
promotion requires independently identified multi-run lifecycle evidence and a
new architecture decision.
**Decision:** PENDING.

## 39. Contradictions and Stop-Condition Review — Checkpoint B

| Stop condition | Result |
| --- | --- |
| Sixth first-class resource necessary | Not found; Workflow separation is embedded and promotion deferred |
| Definition/Instance requires breaking architecture | Not found; logical separation fits S5-ARCH-004 and compatibility strategy B |
| Immediate Task/Workflow break required | Not found; current semantics can be preserved/projected |
| Model Binding requires unperformed routing evidence | Not found; draft remains deliberately thin |
| Provider-specific fields necessary in Core | Not found; opaque extension/config refs suffice |
| Logical Contract cannot remain implementation-neutral | Not found; no Kubernetes/transport representation is selected |
| Accepted S5-ARCH-004 semantics contradicted | Not found |

No blocking contradiction was found. Current implementation/ADR drift and
future migration cost remain recorded; this draft does not resolve either.

## 40. Evidence Debt — Checkpoint B

Carry forward all Checkpoint A debt, plus:

- exact Agent Definition revision/adoption/rollout semantics are not proven;
- desired Instance lifecycle vocabulary, deletion/finalization, and explicit
  Instance targeting authorization are unfrozen;
- Runtime Binding resolution exclusivity, compatibility algorithm, and
  effective projection conformance are unproven;
- routing eligibility inputs, staleness, and `UNKNOWN` escalation remain open;
- retry/replay/idempotency relationships to Platform Execution Identity remain
  unresolved, especially for side effects;
- Task output inline/reference size and retention policy remain open;
- Workflow embedded execution identity migration and reusable-definition
  promotion evidence remain absent;
- Capability risk, authorization, interaction disposition, side-effect, and
  deferred-operation vocabularies remain unfrozen;
- logical reference ID/name coexistence, revision requirement, dangling ref,
  deletion, and rebinding mechanics require Checkpoint C/API work;
- schema version conversion rules have no representation or conformance plan;
- no combined production Runtime/Capability path proves unchanged Platform
  Execution Identity propagation;
- ED-S5-001 still blocks Hermes Provider certification/readiness only.

These debts block relevant schema/Contract freeze, API approval, Provider
certification, or production claims. They do not falsify this logical resource
candidate set.

## 41. Checkpoint B State

LIFECYCLE: **REVIEW**
AUTHORIZATION: **AUTHORIZED**
STATUS: **PASS**
CHECKPOINT: **B — RESOURCE_SCHEMA_DRAFT**
RESULT: **RESOURCE_SCHEMA_DRAFT_RECOMMENDED**

CONTRACT_FREEZE: **NO**
SCHEMA_FREEZE: **NO**
RUNTIME_CONTRACT: **NOT_FROZEN**
CAPABILITY_CONTRACT: **NOT_FROZEN**
CONDITION_VOCABULARY: **NOT_FROZEN**
OUTCOME_VOCABULARY: **NOT_FROZEN**
RECOVERY_VOCABULARY: **NOT_FROZEN**
`G-S5-RUNTIME-FREEZE-01`: **FAIL / UNCHANGED**
PRODUCTION_CORE_CHANGE: **0**
ADR_CHANGE: **0**
EXISTING_SCHEMA_CHANGE: **0**
CRD_CHANGE: **0**
NEXT_ACTION: **WAIT_FOR_HUMAN_DECISION**
NEXT_GATE: **Human Checkpoint B Gate**

Checkpoint C has not begun and is not authorized by this result.
