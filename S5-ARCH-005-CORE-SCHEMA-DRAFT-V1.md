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
CHECKPOINT: A — SCHEMA_PRINCIPLES_AND_COMPATIBILITY_BASELINE
RESULT: **SCHEMA_BASELINE_RECOMMENDED**

> This Checkpoint establishes constraints for later Schema Draft work. It does
> not draft resource fields, approve a Kubernetes CRD, freeze a Contract or
> vocabulary, change an ADR, authorize implementation, or begin Checkpoint B.

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
