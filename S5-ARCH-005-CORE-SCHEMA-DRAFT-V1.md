# S5-ARCH-005 — v0.2 Core Schema Draft & Compatibility Map v1

SESSION

ID: S5-ARCH-005
TITLE: v0.2 Core Schema Draft & Compatibility Map
PHASE: S5 / v0.2 CONNECT & MANAGE
TRACK: Core Architecture / Contract
MODE: Architecture / Schema Draft
LIFECYCLE: CLOSING
AUTHORIZATION: AUTHORIZED
STATUS: PASS
CHECKPOINT: F — SESSION_FINALIZATION
RESULT: **READY_TO_CLOSE**

> Checkpoints A-E established and converged Core Schema Candidate v0. The Human
> Final Schema Candidate Gate passed with constraints. Checkpoint F records the
> accepted Candidate, preserves evidence debt and independent freeze/readiness
> states, and prepares the session for Human Close Confirmation. It does not
> close S5-ARCH-005, merge PR #42, or authorize implementation.

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

# Checkpoint C — References, Status, Conditions, and Execution

## 42. Human Checkpoint B Gate Record

HUMAN DECISION: **PASS WITH COMPATIBILITY CONSTRAINTS**

| Accepted dimension | Checkpoint C authority |
| --- | --- |
| B01-B17 | `ACCEPTED_FOR_SCHEMA_DRAFT` |
| Current Agent strategy | OPTION B: evolve toward Definition; introduce Instance separately |
| Workflow | one v0.2 resource; definition/execution conflation remains evolution debt |
| Bindings | embedded only; no Binding CRDs |
| Execution Identity | embedded Core value; no generic Execution resource |
| References | bounded logical families; native references structurally separate |
| Contract/schema | not frozen |
| CRD/API/production | not approved or authorized |

Checkpoint A and B Sections 1-41 remain unchanged historical records. The
Gate authorizes only a connected implementation-neutral logical model.

## 43. Connected Logical Contract Overview

```text
Agent Definition (desired authority)
  | 1:N definitionRef
  v
Agent Instance (desired lifecycle + effective resolution + observed status)
  ^
  | selectedInstanceRef after Control Plane routing
Task (logical Definition target + execution identity + Task outcome)
  ^
  | owned/referenced Task lifecycle
Workflow (embedded graph request + aggregate execution/outcome)

Agent Definition
  |- desired Runtime Binding ----------> effective Runtime Binding on Instance
  |- Capability Bindings --------------> invocation-time authorization/resolution
  |- thin Model Binding ----------------> optional effective thin projection
  `- thin Workspace/State/Knowledge/Policy/Permission refs

Platform Execution Identity
  Task/Workflow context
    -> logical routing decision
      -> selected Agent Instance
        -> Runtime Provider
          -> native Runtime correlation [0:N]
            -> Capability Provider
              -> native Capability correlation [0:N]
```

The arrows describe semantic relationships, not storage ownership or
Kubernetes `ObjectReference`. Only Agent Definition, Agent Instance, Task,
Workflow, and Capability Definition are first-class resource candidates.

## 44. Cross-Resource Reference Relationships

| Source | Relationship | Target | Cardinality | Owner/resolver | Lifecycle consequence |
| --- | --- | --- | --- | --- | --- |
| Agent Instance | `definitionRef` | Agent Definition | exactly `1` | Agent Control Plane | live Instance blocks ungoverned Definition deletion |
| Agent Instance effective state | Definition revision/generation provenance | Agent Definition revision | exactly `1` effective snapshot | Instance reconciler | update/adoption is explicit; no implicit latest |
| Task request | logical target | Agent Definition | `1` when Definition-targeted | Control Plane router | selects from eligible Instances |
| Task request | explicit target | Agent Instance | `0..1` alternative | Control Plane + authorization | target must belong to allowed Definition/set and be eligible |
| Task status | `selectedInstanceRef` | Agent Instance | `0..1` per routing attempt/current selection | Control Plane | observed/effective decision, not request authority |
| Workflow node | Task request/Task ref | Task | `1` logical request; `0..1` created resource until scheduled | Workflow domain | Task owns execution; Workflow owns aggregate projection |
| Agent Definition | embedded Capability Binding | Capability Definition | `0:N` | Capability domain resolver | reference does not grant invocation permission |
| Agent Definition | desired Runtime Binding | Runtime Provider/package metadata | embedded intent | Runtime resolver | no Provider/public Registry resource implied |
| Agent Instance | effective Runtime Binding | resolved Provider/package metadata | exactly `1` while runnable | Instance/Runtime resolution | derived from Definition generation and compatibility decision |
| Agent Definition | thin Model Binding | external Model/Policy/Class reference | `0..1` | future Model domain | no routing/fallback semantics imported |
| Task/Workflow context | Execution Identity | embedded Core value | exactly `1` per logical execution | Task/Workflow owner | stable through routing and Providers |
| Execution Identity | native references | Runtime/Capability/infrastructure evidence | `0:N` | observing domain | correlation only; correctness cannot require a native ID |

### 44.1 Reference resolution principles

1. resolution is domain-owned and produces either a typed logical target or a
   domain-specific failure/unknown disposition;
2. name lookup always occurs within an explicit scope; ID lookup cannot silently
   fall back to a same-named resource;
3. kind/domain mismatch is invalid even if an ID/name happens to exist;
4. version/revision requirements are checked before effective resolution;
5. a dangling desired reference prevents the dependent effective state from
   becoming usable but does not erase the desired reference;
6. references do not transfer lifecycle ownership except where a separately
   declared relationship rule, such as live Instance protection, says so;
7. current same-namespace `agentRef.name` remains a compatibility shorthand,
   not the canonical form of every future reference.

## 45. Task Targeting and Instance Selection

### 45.1 Logical placement

```text
Task.request.target =
  DefinitionTarget {
    definitionRef                                  REQUIRED_V0_2
    routingIntent?                                 OPTIONAL_V0_2
  }
  | InstanceTarget {
      instanceRef                                  OPTIONAL_V0_2
      targetingAuthorizationRef                    REQUIRED when explicit
    }
  | LegacyAgentTarget {
      name
      implied same-namespace scope
    }                                              COMPATIBILITY_ONLY

Task.status.routing = {
  targetInterpretation                             REQUIRED_V0_2
  candidateDefinitionRef                           REQUIRED_V0_2
  selectedInstanceRef?                             OPTIONAL_V0_2
  selectionDisposition                             REQUIRED_V0_2
  reason                                           REQUIRED_V0_2
  selectedAt?                                      OPTIONAL_V0_2
  evidenceFreshness?                               OPTIONAL_V0_2
}
```

### 45.2 Selection transition

```text
requested logical target
  -> resolve Definition scope/version
  -> determine authorized candidate Instance set
  -> evaluate Instance routing eligibility and freshness
  -> select one logical Agent Instance
  -> record selectedInstanceRef and decision provenance
  -> pass selected Instance's effective Runtime Binding to Runtime Provider
```

Control Plane owns every transition through Instance selection. The Runtime
Provider receives an already-selected Instance/Binding and may choose only
among native realizations within that effective Binding.

### 45.3 Consistency rules

- for a Definition target, the selected Instance must reference that Definition
  and satisfy the request's revision/policy constraints;
- for explicit Instance targeting, the Instance's Definition becomes the
  candidate Definition and authorization is mandatory;
- `selectedInstanceRef` is status/effective evidence and cannot overwrite the
  request target;
- selection may be absent while pending, denied, invalid, or unknown; absence
  does not mean a Runtime Provider may choose an Instance;
- a stale or `UNKNOWN` eligibility assessment cannot be interpreted as
  eligible without an explicitly approved risk policy;
- Task never contains Pod, Service, Gateway, session, endpoint, or native run
  identity as a routing target.

### 45.4 Current Task compatibility

Current `spec.agentRef.name` continues to mean the same-named current Agent in
the Task namespace. Under the compatibility interpreter it identifies the
Definition-facing legacy Agent and requests Control Plane selection of its
legacy-compatible execution projection. It is not silently converted into an
explicit Instance reference. A future additive target field or versioned API
may express Definition/Instance targeting; conflict with legacy `agentRef`
must be rejected rather than resolved by precedence hidden from users.

## 46. Desired, Effective, and Observed Transitions

| Domain | Desired/requested authority | Effective derived state | Observed/status evidence | Transition owner |
| --- | --- | --- | --- | --- |
| Agent Definition | definition, desired Bindings, thin refs | validated/defaulted projection only if needed | validation conditions + observed generation | Definition reconciler/validator |
| Agent Instance | Definition ref + desired lifecycle | Definition revision, Runtime Binding, thin Model projection, resolution provenance | eligibility, Instance/Runtime conditions, recovery, native refs | Agent Instance reconciler |
| Runtime Binding | Definition-owned intent/template | Instance-owned resolved Provider/package/config refs | Runtime Conditions and realization evidence outside Binding | Instance reconciler + Runtime Provider evidence |
| Capability Binding | Definition-owned governed intent | per-invocation Capability/Provider/version/authorization decision | Capability Outcome + native refs | Capability authorization/resolution owner |
| Task | input, target, routing/auth intent, timeout/retry intent | routing interpretation + selected Instance | submission, execution, attempts, Outcome, correlations | Task owner/Control Plane |
| Workflow | graph/node requests | runnable/blocked node interpretation | node Task projections + aggregate execution/outcome | Workflow owner |
| Capability Definition | operation/schema/risk/auth/compatibility declaration | validated definition only | validation status only | Capability Definition owner |

Transitions must preserve provenance:

- effective Definition/Binding values identify desired source generation;
- observed state identifies relevant generation plus observation/freshness time;
- a desired change invalidates, but does not falsify, observations of an older
  generation;
- Providers emit evidence and normalized domain observations; they do not edit
  desired Core values;
- `UNKNOWN` is the correct projection when required evidence is absent, stale,
  contradictory, or unsupported.

## 47. Agent Instance Status Boundary

```text
AgentInstanceStatus {
  observedDefinition: {
    definitionRef: ResourceRef<AgentDefinition>               R
    revision: ResourceRevision                                R
    generation: DesiredGeneration                             R
  }

  effectiveRuntime: {
    bindingSummary: EffectiveRuntimeBindingSummary            R
    sourceGeneration: DesiredGeneration                       R
    resolvedAt: Instant                                       R
  }

  routingEligibility: {
    truth: FourWayTruth                                       R
    reason: StableInstanceReason                              R
    message?: SafeMessage                                     O
    evaluatedAt: Instant                                      R
    freshness: EvidenceFreshness                              R
  }

  runtimeConditionSummary?: DomainConditionSummary            O
  instanceConditions: Condition<AgentInstanceDomain>[]        O
  runtimeConditions: Condition<RuntimeDomain>[]                O
  recoveryAssessment?: RecoveryAssessment                     O
  realizationSummary: {
    activeCount: NonNegativeInteger                           R
    availableCount?: NonNegativeInteger                       O
    observedAt: Instant                                       R
    freshness: EvidenceFreshness                              R
  }
  nativeReferences: NativeReference[]                         O
  executionCorrelations?: ExecutionCorrelationRef[]           O
  observedAt: Instant                                         R
}
```

`EffectiveRuntimeBindingSummary` exposes only Provider/package/class identity,
compatibility disposition, desired provenance, and safe extension references.
It does not duplicate Provider configuration or native topology.

`DomainConditionSummary` is a convenience projection such as worst/most
relevant truth and freshest observation. It cannot replace the underlying
domain Conditions or create one universal health verdict.

The status must not mirror Pod phase, restart count, container readiness,
Gateway health, or native sessions. Those may appear only as bounded native
evidence normalized into Runtime/Instance semantics.

## 48. Condition Model

### 48.1 Shared structural candidate

```text
Condition<Domain> {
  concept: DomainConditionConcept                              R
  truth: TRUE | FALSE | UNKNOWN | NOT_APPLICABLE              R
  reason: StableDomainReason                                   R
  message?: SafeMessage                                        O
  observedGeneration?: DesiredGeneration                       O
  observedAt: Instant                                           R
  lastTransitionAt?: Instant                                    O
  freshness: EvidenceFreshness                                  R
  evidenceRefs?: EvidenceReference[]                            O
}
```

This shares shape, not vocabulary or lifecycle. Exact names, serialization,
enums, transition rules, reason taxonomies, and freshness thresholds remain
unfrozen.

### 48.2 Four-way truth

| Truth | Meaning | Forbidden interpretation |
| --- | --- | --- |
| `TRUE` | sufficient fresh evidence supports the domain assertion | generic success in another domain |
| `FALSE` | sufficient fresh evidence contradicts the assertion | unknown or unavailable evidence |
| `UNKNOWN` | truth cannot be established from applicable evidence | healthy, false, or not applicable |
| `NOT_APPLICABLE` | concept does not apply to this declared profile/mode | unsupported because evidence is missing |

`lastTransitionAt` changes only when `truth` changes for the same concept and
semantic subject. `observedAt` changes when evidence is evaluated. Freshness
describes whether the observation may still support decisions. Safe messages
must be bounded and redacted; controllers cannot depend on message text.

## 49. Runtime Conditions

Runtime Condition remains Runtime-domain owned. A Runtime Provider normalizes
native evidence into portable Runtime assertions without importing native
health names into Core.

| Concept | v0.2 disposition | Meaning |
| --- | --- | --- |
| `RuntimeAvailable` | minimum meaningful candidate | effective Runtime can accept/continue the declared Runtime interaction profile |
| `InfrastructureAvailable` | conditional | applies only where the Runtime profile owns/observes infrastructure availability |
| `DependencyReady` | conditional | applies only for a declared dependency whose readiness is portable and relevant |
| `ProtocolAvailable` | Provider detail by default | expose only if later evidence proves it is a required platform Runtime semantic |
| `TaskReady` | prohibited | Task readiness is not a Runtime Condition |

Runtime availability is not Instance routing eligibility, Task success,
Capability authorization, or recovery. A Provider-native `healthy`, Pod
`Ready`, Hermes state, OpenClaw run status, or HTTP success is evidence from
which the Provider may derive a Runtime Condition; it is never copied as a Core
condition concept by default.

## 50. Agent Instance Conditions

Instance-domain conditions answer questions owned by Agent Instance
reconciliation. Candidate concepts are structural and unfrozen:

| Conceptual question | Candidate condition concept | Relation to other domains |
| --- | --- | --- |
| Is the Instance eligible for logical routing? | `RoutingEligible` | derived using policy, Binding, Runtime evidence, and freshness; not equal to RuntimeAvailable |
| Is effective Runtime Binding resolved and usable? | `RuntimeBindingUsable` | Instance owns conclusion; Runtime Provider supplies compatibility/evidence |
| Is a required realization available? | `RequiredRealizationAvailable` | conditional by ownership/profile; native evidence alone is insufficient |
| Is reconciliation converged to desired generation? | `ReconciliationCurrent` | compares desired/effective/observed provenance |
| Is the Instance degraded while still potentially routable? | `Degraded` | domain-specific policy conclusion, not inverse of availability |
| Is recovery semantically established? | `RecoveryResolved` | projects Recovery Assessment; restart is not enough |

These are logical concepts for review, not frozen names/enums. An Instance may
be RuntimeAvailable but ineligible due to policy, stale evidence, Definition
mismatch, unresolved recovery, or explicit lifecycle intent. It may also be
temporarily eligible under a profile where a conditional realization concept
is not applicable. No one Condition is a universal health status.

## 51. Task Execution Semantics

### 51.1 Domain structures

```text
TaskSubmissionDisposition {
  state: PENDING | ACCEPTED | REJECTED | UNKNOWN              candidate
  reason: TaskSubmissionReason
  decidedAt?: Instant
}

TaskExecutionState {
  state: NOT_STARTED | RUNNING | TERMINAL | UNKNOWN           candidate
  observedAt: Instant
  selectedInstanceRef?: ResourceRef<AgentInstance>
}

TaskOutcome {
  terminalDisposition: SUCCEEDED | FAILED | TIMED_OUT |
                       CANCELLED | UNKNOWN                    candidate
  output?: InlineValueOrOutputReference
  reason: StableTaskReason
  retryable?: Boolean
  message?: SafeMessage
  completedAt?: Instant
  evidenceRefs?: EvidenceReference[]
}
```

The candidate labels are explanatory, not frozen. Logical constraints:

- submission rejection can become a terminal Task-owned failure without
  Runtime invocation;
- accepted submission does not mean execution started or succeeded;
- execution `TERMINAL` requires a Task Outcome, but Outcome vocabulary remains
  Task-owned;
- Provider result is evidence. Task owner determines the Task Outcome after
  applying timeout, retry, validation, and Task semantics;
- Runtime or Capability failure evidence cannot directly overwrite Task state;
- current phase values remain the compatibility projection described below.

### 51.2 Current phase projection

| Current Task phase | Submission projection | Execution projection | Outcome projection |
| --- | --- | --- | --- |
| `Pending` | pending or not yet accepted | not started/unknown | absent |
| `Running` | accepted | running | absent |
| `Succeeded` | accepted | terminal | succeeded with current result |
| `Failed` | accepted or rejected, depending on reason | terminal or not started | failed with current reason/message/retryable |
| `TimedOut` | accepted | terminal | timed out |

This mapping is deliberately many-to-one/conditional. It preserves current
wire behavior while allowing a later additive representation to expose the
distinctions. Current `attempts` remains a Task-owned summary. Cancellation is
not added to the current phase enum and remains unsupported until separately
approved.

## 52. Workflow Execution Semantics

Workflow keeps one first-class resource with embedded execution semantics.

```text
WorkflowExecutionState {
  executionIdentity: PlatformExecutionIdentity                R
  submission: WorkflowSubmissionDisposition                   R
  aggregateState: WorkflowAggregateState                      R
  nodes: Map<NodeIdentity, WorkflowNodeExecution>              R
  outcome?: WorkflowOutcome                                    O
  humanGateWaits?: HumanGateWaitState[]                         T
  observedAt: Instant                                          R
}

WorkflowNodeExecution {
  taskRef?: ResourceRef<Task>
  state: PENDING | BLOCKED | RUNNING | TERMINAL | UNKNOWN      candidate
  dependencyDisposition: SATISFIED | WAITING | IMPOSSIBLE |
                         HUMAN_GATE_WAIT | UNKNOWN             candidate
  taskProjection?: TaskExecutionProjection
}

WorkflowOutcome {
  terminalDisposition: SUCCEEDED | FAILED | CANCELLED |
                       UNKNOWN                                candidate
  nodeSummary: AggregateNodeSummary
  reason: StableWorkflowReason
  message?: SafeMessage
  completedAt?: Instant
}
```

Bounded semantic rules:

- dependency blocking is not failure while required upstream outcomes remain
  non-terminal or unknown;
- a node becomes skipped/terminally non-executed when a required dependency
  can no longer satisfy execution, preserving current failure/timeout/skip
  propagation;
- independent siblings continue independently;
- partial completion is an aggregate observation, not necessarily a terminal
  Workflow Outcome;
- a Human Gate wait blocks only the governed continuation path and is distinct
  from dependency failure or execution success;
- retry belongs to the underlying Task unless Workflow-level orchestration
  explicitly creates/replaces a Task under later approved semantics;
- recovery of an Agent Instance does not automatically retry or succeed an
  affected Task/Workflow node;
- no new engine, queue, history store, or WorkflowExecution resource is
  implied.

Current Workflow phases and per-node states remain compatibility projections.
The current `Skipped` node state is retained, even though the logical model
explains why it was not executed.

## 53. Capability Outcome

Capability Outcome is owned by the Capability invocation domain and remains
separate from Task Outcome, Runtime interaction result, and transport error.

```text
CapabilityOutcome {
  disposition: AUTHORIZATION_DENIED | VALIDATION_FAILED |
               PROVIDER_UNAVAILABLE | PROTOCOL_FAILED |
               REMOTE_EXECUTION_FAILED | TIMED_OUT |
               SUCCEEDED | UNKNOWN                            candidate
  capabilityRef: ResourceRef<CapabilityDefinition>            R
  operation: LogicalOperationIdentity                          R
  output?: InlineValueOrOutputReference                        O
  reason: StableCapabilityReason                               R
  retrySafety?: CapabilityRetrySafety                          O
  message?: SafeMessage                                        O
  nativeReferences?: NativeReference[]                         O
  observedAt: Instant                                           R
}
```

The dispositions are semantic distinctions for draft review, not a frozen
universal error enum. Domain rules:

- `AUTHORIZATION_DENIED` may be final before Provider invocation and therefore
  legitimately have zero native references;
- validation precedes Provider handoff where Core/Capability owner can
  validate the semantic request;
- Provider unavailable and protocol failure describe different ownership and
  retry evidence;
- remote execution failure does not imply transport failure;
- HTTP/MCP/native success is Provider evidence; the Capability owner confirms
  semantic success/output conformance;
- `UNKNOWN` is used when completion or semantic validity cannot be established;
- retry safety depends on Capability side-effect/idempotency declarations and
  is not inferred from a generic retryable boolean.

## 54. Execution Identity Propagation

### 54.1 Propagation path

```text
Task or embedded Workflow execution owner creates PlatformExecutionIdentity
  -> Task/Workflow request and status carry the same logical identity
  -> routing decision records identity + selected Agent Instance
  -> Runtime Provider receives identity with effective Runtime Binding
  -> Runtime Provider propagates identity without replacement
  -> native Runtime may return 0:N opaque correlation IDs
  -> Capability authorization/resolution receives same root execution context
  -> Capability Provider propagates identity without replacement
  -> native Capability may return 0:N opaque invocation IDs
  -> outcomes/evidence correlate back to Platform identity
```

### 54.2 Rules

1. Platform execution correctness, authorization, outcome ownership, and
   recovery cannot require any native ID.
2. Provider transport may encode the Platform identity differently, but the
   semantic value must remain round-trippable and unchanged.
3. A Workflow execution has its own identity; each materialized Task has its
   own identity with optional root/parent correlation to the Workflow. This
   does not create a universal execution hierarchy resource.
4. Capability invocations attributable to a Task may correlate using that Task
   execution identity plus domain-specific subordinate context; whether a new
   child logical identity is required remains operation/retry-specific.
5. retries within current Task attempt semantics retain the Task execution
   identity unless an approved replay rule states otherwise.
6. duplicate, conflicting, or missing propagated identity is a Contract
   conformance failure, not permission to substitute a native run ID.
7. redaction and exposure policies apply to native evidence independently of
   Platform identity.

## 55. Native Reference and Ownership Semantics

```text
NativeReference {
  domain: RUNTIME | CAPABILITY | INFRASTRUCTURE               R
  providerRef?: ProviderRef                                   O
  nativeKind: OpaqueKindLabel                                 R
  opaqueId: OpaqueText                                        R
  observedAt: Instant                                         R
  freshness?: EvidenceFreshness                               O
  lifecycleOwnership: PLATFORM_OWNED | PROVIDER_OWNED |
                      EXTERNALLY_OWNED | SHARED | UNKNOWN     R
  executionRef?: PlatformExecutionIdentity                    O
  realizationRole?: OpaqueRoleLabel                           O
}
```

`lifecycleOwnership` is a cleanup safety hint backed by Binding/Provider policy,
not a transfer of authority. Rules:

- Platform cleanup may act only when the effective Binding and Provider
  Contract authorize cleanup for the declared ownership mode;
- `EXTERNALLY_OWNED`, `SHARED`, or `UNKNOWN` prohibits unconditional deletion;
- a native reference disappearing is evidence, not proof that the logical
  Instance/Task/Workflow has been deleted or recovered;
- native kind/role labels remain opaque diagnostics and cannot introduce
  Hermes/OpenClaw/Pod-specific Core branches;
- references are bounded in count/retention; large histories and raw native
  payloads belong in observability systems.

## 56. Recovery Assessment

Recovery Assessment remains an Agent Instance-owned embedded status value.

```text
RecoveryAssessment {
  truth: TRUE | FALSE | UNKNOWN | NOT_APPLICABLE               R
  reason: StableRecoveryReason                                 R
  desiredInstanceExists: FourWayTruth                          R
  stableIdentityRetained: FourWayTruth                         R
  effectiveBindingUsable: FourWayTruth                         R
  runtimeConditionAcceptable: FourWayTruth                     R
  routingEligibilityRestored: FourWayTruth                     R
  requiredRealizationAvailable: FourWayTruth                   R
  executionContinuity?: FourWayTruth                           O
  stateContinuity?: FourWayTruth                               O
  assessedDefinitionGeneration: DesiredGeneration              R
  assessedAt: Instant                                           R
  evidenceFreshness: EvidenceFreshness                          R
  evidenceRefs?: EvidenceReference[]                            O
  message?: SafeMessage                                         O
}
```

Assessment algorithm principles:

- applicable predicates are determined by declared Runtime ownership/profile,
  not by Provider family names;
- overall `TRUE` requires every required predicate to be true with sufficient
  fresh evidence;
- any required false predicate makes overall false;
- any unresolved required predicate makes overall unknown unless another
  required predicate is already false;
- not-applicable predicates are excluded from conjunction but remain visible;
- execution/state continuity is evaluated only when the relevant Contract and
  Provider profile explicitly support it;
- a restart, Pod replacement, new Gateway route, successful health endpoint,
  or new native session is evidence for some predicates at most; none alone is
  recovery;
- state portability is never assumed.

## 57. Human Gate Thin Interaction

Governance and execution owners communicate through references and state, not
through a new Human Gate Core resource.

```text
HumanGateRequestRef {
  decisionRequestRef: ResourceRef<GovernanceDecisionRequest>  T
  requiredAuthorityRef: ResourceRef<DecisionAuthority>        T
  requestedAt: Instant                                        T
}

HumanGateDecisionEvidenceRef {
  decisionRef: ResourceRef<GovernanceDecision>                 T
  disposition: APPROVED | REJECTED | EXPIRED | REVOKED |
               UNKNOWN                                        candidate
  decidedAt?: Instant
  evidenceRef?: EvidenceReference
}

HumanGateWaitState {
  gateRequestRef: HumanGateRequestRef                          T
  state: WAITING | RESUMABLE | REJECTED | EXPIRED | UNKNOWN   candidate
  decisionEvidenceRef?: HumanGateDecisionEvidenceRef           T
  continuationRef: WorkflowNodeOrTaskContinuationRef           T
}
```

- Governance owns request identity, authority evaluation, approval/rejection,
  expiry/revocation, and evidence.
- Task/Workflow owns waiting, resume eligibility, and continuation transition.
- approval makes a continuation eligible; it does not mean the continuation
  ran or succeeded.
- rejection/expiry is an execution-domain blocking disposition, not a Provider
  failure.
- stale, revoked, mismatched, or unknown evidence cannot be treated as approval.
- no Human Feedback, learning, preference, or approval workflow architecture
  is introduced.

## 58. Provider Extension Points

| Extension category | Logical location | Core visibility | Constraint |
| --- | --- | --- | --- |
| Provider configuration reference | desired/effective domain Binding | opaque ref only | target/version/credentials owned outside Core |
| Provider extension reference | Binding or Provider descriptor | opaque ref + declared compatibility | no stable Core parsing/branching |
| Runtime Package reference | Runtime Binding/internal registry metadata | package ID/version/compatibility facts | no public RuntimePackage resource |
| Provider descriptor | domain-specific internal registry | ID, compatibility version, supported profiles | Runtime and Capability registries remain distinct |
| native metadata | bounded NativeReference/evidence | safe kind/opaque ID/time/ownership hint | raw payload/topology excluded |
| safe diagnostic | domain Condition/Outcome | bounded redacted reason/message | no credentials, endpoints, or control via message text |

Provider-specific fields may be versioned behind the referenced extension
owner. Widespread Provider adoption does not promote a field into Core; only
cross-Provider semantic proof plus a Human architecture decision may do so.
Neither `hermes`, `openclaw`, `native`, MCP, REST, Pod, Gateway, nor a model
vendor becomes a stable Core field discriminator.

## 59. Expanded Connected-Schema Invariants

In addition to Section 35:

1. Agent Instance references exactly one Agent Definition at all times it is
   logically live.
2. Effective Definition revision/generation recorded by an Instance must resolve
   under its `definitionRef`.
3. A Task's selected Instance must reference the Task target Definition, or be
   the explicitly targeted authorized Instance.
4. A selected Instance must come from the Control Plane's eligible candidate
   set evaluated with sufficient freshness.
5. Task target intent is immutable for one accepted logical execution unless a
   separately defined rerouting rule preserves audit/provenance.
6. Runtime effective Binding must derive from authorized Definition desired
   intent and record source generation and compatibility decision.
7. Effective Binding cannot contain an independently editable desired field.
8. Capability invocation requires a resolvable Capability Binding and a current
   authorization decision independent of discovery/Provider feasibility.
9. Authorization denial must prevent Provider invocation and may have zero
   native references.
10. Platform Execution Identity remains stable from execution owner through
    routing and both Provider domains.
11. Native ID cannot replace or backfill missing Platform identity.
12. Provider result/transport status remains evidence; Task, Workflow, and
    Capability owners determine their own Outcomes.
13. Runtime Conditions and Agent Instance Conditions cannot share a condition
    concept merely because their structural fields match.
14. `UNKNOWN` cannot be treated as healthy, eligible, recovered, authorized, or
    successful.
15. `NOT_APPLICABLE` requires a declared profile rule, not missing evidence.
16. Recovery `TRUE` requires all applicable semantic predicates with fresh
    evidence; restart or replacement is insufficient.
17. A native realization with external/shared/unknown ownership cannot be
    unconditionally deleted by Platform cleanup.
18. Workflow node projection cannot become a second desired Task authority.
19. Human Gate approval affects resume eligibility only and cannot set Task or
    Workflow Outcome to succeeded.
20. No Core value may require Provider-family-specific interpretation for
    correctness.
21. Logical reference resolution failure preserves desired intent and produces
    domain-owned condition/outcome evidence rather than silently retargeting.
22. Old-generation observation cannot satisfy current-generation reconciliation
    without an explicit compatibility rule.
23. Native reference absence cannot prove logical deletion, failure, or
    recovery.
24. Current Task/Workflow phase projections remain coherent with richer states;
    conflicting representations are rejected, not silently prioritized.

## 60. Current API Compatibility Mapping — Checkpoint C

### 60.1 Current Task Agent reference

| Mechanism | Recommendation | Classification |
| --- | --- | --- |
| Preserve `spec.agentRef.name` read/write meaning | required throughout v0.2 compatibility window | KEEP |
| Interpret as Definition-facing legacy target under same namespace | deterministic compatibility layer | TRANSLATION |
| Add selected logical Instance to status/projection | new evidence, never request rewrite | ADDITIVE_FIELD |
| Add richer Definition/Instance target | only additive with mutual-exclusion validation or versioned API | ADDITIVE_FIELD / VERSIONED_MIGRATION |
| Reinterpret `agentRef.name` as Instance | prohibited | BREAKING_CANDIDATE |
| Put native Service/Pod/Gateway target in Task | prohibited | BREAKING_ARCHITECTURE |

### 60.2 Current Task status

| Current field | Compatibility mechanism | Connected-model mapping |
| --- | --- | --- |
| `phase` | stable compatibility projection | derives from submission/execution/Outcome without changing wire values |
| `result` | alias/derived field | Task Outcome inline output; output references require additive/versioned representation |
| `reason/message` | compatibility alias | Task-domain stable reason and safe message |
| `retryable` | derived compatibility field | Task assessment only; Capability side-effect retry safety remains distinct |
| `attempts` | keep | bounded Task AttemptSummary total |
| `startedAt/completedAt` | keep | Task execution/outcome timestamps |
| Execution Identity | additive | new embedded Core value; no native substitution |
| selected Instance | additive derived status | records Control Plane selection |

### 60.3 Current Workflow Task ownership/status

| Current behavior | Mechanism | Constraint |
| --- | --- | --- |
| Workflow embeds node requests | compatibility alias to embedded definition | no reusable Definition resource implied |
| controller creates owned Task CRs | keep | Task remains execution authority |
| `<workflow>-<node>` name and labels | keep current implementation | later change requires migration of Console/controller joins |
| node status map | derived field/projection | cannot become duplicate Task desired state |
| `Skipped` propagation | keep | maps to terminally non-executed dependency disposition |
| Workflow phase | stable compatibility projection | richer aggregate state must project deterministically |
| Human Gate waiting | additive future thin state | must not reuse Failed/Succeeded dishonestly |
| Workflow execution identity | additive | each Task may correlate by parent/root identity |

### 60.4 Current Runtime invocation path

| Current behavior | Compatibility mechanism | Target boundary |
| --- | --- | --- |
| same-name Agent Service | legacy routing translation | Control Plane selection precedes Provider/native route |
| `POST /v1/invoke` string input/output | keep Runtime-specific implementation | Provider evidence, not universal Execution schema |
| HTTP status classification | keep current Task compatibility | Runtime/Task/Capability domain ownership remains distinct |
| no Platform identity propagation | additive Contract candidate | required conformance before freeze |
| direct Operator Deployment/Service | migration required later | Runtime Binding/Provider boundary; no implementation here |

### 60.5 Current Console Agent/Workflow view

The current Console exposes Workflow and node Agent references, Task execution
state, results, attempts, reasons, and timestamps. Compatibility mechanisms:

- preserve current response fields and machine phase values;
- derive existing `agent.name` from the legacy Task target while optionally
  adding selected Instance information only through a compatible response
  extension/version;
- keep the Console read-only and Kubernetes-backed;
- do not make Console projection identity authoritative;
- do not treat `WorkflowExecutionDetail` naming as a Core resource;
- because Pydantic models forbid extras, any additive response field requires
  explicit schema/test work in a later authorized implementation.

## 61. Human Decisions Required — Checkpoint C

All decisions remain **PENDING** until the Human Checkpoint C Gate.

### C01 — Connected logical reference relationships

**Recommendation:** accept Section 44 cardinalities, resolver ownership, and
lifecycle consequences without selecting Kubernetes ObjectReference.
**Decision:** PENDING.

### C02 — Task Definition target and selected Instance

**Recommendation:** request carries Definition target or authorized explicit
Instance target; status records Control Plane-selected Instance; legacy Agent
name remains a compatibility target.
**Decision:** PENDING.

### C03 — Desired/effective/observed transitions

**Recommendation:** accept Section 46 selective placement and mandatory
generation/provenance/freshness rules.
**Decision:** PENDING.

### C04 — Agent Instance Status boundary

**Recommendation:** accept Definition provenance, effective Runtime summary,
routing eligibility, separate Runtime/Instance Conditions, recovery,
realization summary, and bounded native evidence; reject Pod-status mirroring.
**Decision:** PENDING.

### C05 — Condition structure and four-way truth

**Recommendation:** accept shared structure only, with domain concepts/reasons
and distinct TRUE/FALSE/UNKNOWN/NOT_APPLICABLE semantics; vocabulary remains
unfrozen.
**Decision:** PENDING.

### C06 — Runtime Condition placement

**Recommendation:** Runtime-domain Provider-normalized Conditions with
`RuntimeAvailable` as minimum candidate; conditional infrastructure/dependency
concepts and no TaskReady/native health names.
**Decision:** PENDING.

### C07 — Agent Instance Condition placement

**Recommendation:** Instance-domain conditions answer routing, Binding,
realization, reconciliation, degradation, and recovery questions without
equating them to Runtime/Pod health.
**Decision:** PENDING.

### C08 — Task execution separation

**Recommendation:** distinguish submission disposition, execution state, and
Task Outcome while preserving deterministic current phase/status projection.
**Decision:** PENDING.

### C09 — Workflow embedded execution

**Recommendation:** accept bounded node/dependency/partial/skip/Human Gate/
aggregate semantics inside Workflow; no WorkflowExecution resource or engine
redesign.
**Decision:** PENDING.

### C10 — Capability Outcome

**Recommendation:** accept Capability-owned distinctions for denial,
validation, Provider availability, protocol, remote execution, timeout,
success, and unknown; do not create a universal error schema.
**Decision:** PENDING.

### C11 — Execution Identity propagation

**Recommendation:** accept end-to-end unchanged Platform identity through
routing, Runtime, and Capability Providers with `0:N` optional native
correlations.
**Decision:** PENDING.

### C12 — NativeReference ownership shape

**Recommendation:** add lifecycle ownership hint to opaque bounded evidence;
external/shared/unknown ownership prohibits unconditional cleanup.
**Decision:** PENDING.

### C13 — Recovery Assessment

**Recommendation:** accept Instance-owned four-way predicate assessment with
generation/freshness provenance; restart/replacement and state portability are
insufficient.
**Decision:** PENDING.

### C14 — Human Gate thin interaction

**Recommendation:** Governance owns requests/authority/decisions/evidence;
Task/Workflow owns waiting/resume/continuation; approval is not success.
**Decision:** PENDING.

### C15 — Provider extension points

**Recommendation:** opaque config/extension refs, domain registry metadata,
bounded native evidence, and safe diagnostics only; no Provider-family fields
in stable Core.
**Decision:** PENDING.

### C16 — Compatibility aliases and translations

**Recommendation:** preserve current Agent ref, Task phases/status, Workflow
Task ownership, Runtime invocation, and Console fields through explicit alias,
translation, additive field, or versioned migration; prohibit in-place
reinterpretation.
**Decision:** PENDING.

### C17 — Eligibility and freshness safety

**Recommendation:** only sufficiently fresh eligible Instance evidence may
support routing; UNKNOWN/stale evidence cannot silently become eligible.
**Decision:** PENDING.

### C18 — Outcome ownership boundary

**Recommendation:** Provider/native results remain evidence; Task, Workflow,
and Capability owners derive distinct Outcomes, and Runtime interaction remains
Runtime-specific.
**Decision:** PENDING.

## 62. Contradictions and Stop-Condition Review — Checkpoint C

| Stop condition | Result |
| --- | --- |
| Another first-class resource required | Not found |
| WorkflowExecution required | Not found; bounded embedded structure remains sufficient |
| Universal Execution schema required | Not found; only identity/correlation and shared condition shape are common |
| Current Task compatibility requires immediate break | Not found; aliases/translations/additive status preserve current behavior |
| Condition sharing contradicts D32/D36 | Not found; structure is shared while concepts/reasons/ownership remain domain-specific |
| Provider-specific fields required in Core | Not found |
| Model routing detail required | Not found |
| S5-ARCH-004 boundary must change | Not found |

No blocking contradiction was found. Checkpoint D has not begun.

## 63. Evidence Debt — Checkpoint C

Carry forward Checkpoint A/B debt, plus:

- exact logical ID/name/scope mismatch and dangling-reference error taxonomy is
  unfrozen;
- Definition update adoption and target revision-selection rules remain open;
- explicit Instance targeting authorization and audit policy is unproven;
- routing eligibility input set, freshness thresholds, deterministic selection,
  rebinding, and in-flight rerouting remain Contract-freeze debt;
- current Agent compatibility interpreter/facade has no API representation or
  conformance evidence;
- submission/execution/outcome vocabulary and deterministic projection to/from
  current Task phases remain unfrozen;
- cancellation remains unsupported and Human Gate wait-state projection into
  the current Workflow API is unresolved;
- Capability denial/validation/Provider/protocol/remote/timeout taxonomies,
  retry safety, and deferred durability remain unfrozen;
- combined unchanged-consumer propagation of Platform Execution Identity
  through Runtime and Capability Providers remains unproven;
- native lifecycle ownership assertion source, authorization, revocation, and
  cleanup conformance remain open;
- Recovery predicate applicability, evidence thresholds, timeout/escalation,
  stateful/external profiles, and in-flight execution disposition remain open;
- Provider extension schema versioning, signing, redaction, and safe diagnostic
  limits remain unproven;
- existing Console compatibility requires future explicit API schema/tests for
  any additive selected-Instance/execution fields;
- ED-S5-001 continues to block Hermes certification/readiness only.

These debts block relevant Contract/schema freeze, API approval, migration,
Provider certification, or production claims. They do not require another
resource or a universal semantic object.

## 64. Checkpoint C State

LIFECYCLE: **REVIEW**
AUTHORIZATION: **AUTHORIZED**
STATUS: **PASS**
CHECKPOINT: **C — REFERENCES_STATUS_CONDITIONS_EXECUTION**
RESULT: **CONNECTED_SCHEMA_MODEL_RECOMMENDED**

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
NEXT_GATE: **Human Checkpoint C Gate**

Checkpoint D has not begun and is not authorized by this result.

# Checkpoint D — Compatibility and Migration Map

## 65. Human Checkpoint C Gate Record

HUMAN DECISION: **PASS WITH COMPATIBILITY AND FREEZE CONSTRAINTS**

| Accepted dimension | Checkpoint D authority |
| --- | --- |
| C01-C18 | `ACCEPTED_FOR_SCHEMA_DRAFT` |
| Agent migration direction | Option B; preserve current semantics and identity |
| Task targeting | Definition-facing request plus selected Instance projection |
| Workflow | one resource; definition/execution split remains debt |
| Condition/Capability Outcome | boundary accepted; vocabulary/taxonomy not frozen |
| Execution identity/native refs | embedded Platform identity; opaque optional correlations |
| Contract/schema/CRD | not frozen or approved |
| Checkpoint purpose | compatibility, migration, and evolution; no new schema breadth |

Sections 1-64 remain the distinct Checkpoint A-C records. Checkpoint D adds no
resource and does not reconstruct or rewrite prior evidence.

## 66. Migration Strategy Summary

**Recommendation:** a staged Option B transition using a compatibility
translation layer, additive logical/API projections where representable, and a
versioned representation only for semantics that cannot coexist safely in the
current API.

```text
Current v1alpha1 objects remain authoritative and valid
  -> compatibility reader interprets current Agent as Definition-facing intent
  -> Platform mints and durably records a distinct legacy-managed Instance ID
  -> current Task Agent reference remains unchanged
  -> Control Plane records selected Instance as additive derived evidence
  -> Runtime compatibility translator preserves current Service/invoke path
  -> users may explicitly adopt Definition/Instance-facing APIs when approved
  -> mixed mode remains observable and reversible within declared boundary
  -> legacy fields deprecate only after conformance, adoption, and Human Gate
```

This is a logical migration model, not authorization for a compatibility
controller, new CRD, webhook, database, API version, or status field.

### 66.1 Primary change classifications

Every difference below uses one primary classification:

| Classification | Meaning in this checkpoint |
| --- | --- |
| `KEEP` | preserve current representation and semantics |
| `ADDITIVE` | new optional representation/semantic with defined absence behavior |
| `COMPATIBILITY_ALIAS` | old representation continues to expose/project a target semantic |
| `DERIVED_PROJECTION` | computed read/status/view from authoritative source, never second desired authority |
| `TRANSLATION_LAYER` | bounded deterministic mapping across old/target boundaries |
| `DEPRECATE_LATER` | retain now; removal requires exit criteria and later approval |
| `MIGRATION_REQUIRED` | ownership/representation must move through explicit plan |
| `BREAKING_CANDIDATE` | cannot be done in place without compatibility break; not recommended now |
| `DEFERRED` | outside v0.2 migration evidence/scope |

`REMOVE_CANDIDATE` from the Gate's Runtime-specific evaluation is represented
here as `DEPRECATE_LATER` followed by a future removal decision; Checkpoint D
does not authorize removal.

## 67. Current Agent to Definition and Instance Migration

### 67.1 Persistence and authority by transition stage

| Stage | Persisted authority | Derived/effective state | User behavior | Primary classification |
| --- | --- | --- | --- | --- |
| D0 current-compatible | current Agent remains desired authority; existing Deployment/Service/status unchanged | Definition compatibility interpretation; distinct legacy-managed Instance mapping may be shadow/read-only until approved | all existing manifests and operations work unchanged | KEEP |
| D1 observable compatibility | current Agent still desired authority; durable compatibility metadata records schema interpretation and minted Instance identity | Definition projection, default managed Instance projection, selected Instance, Binding translation, execution identity | users can inspect but need not author new semantics | ADDITIVE + DERIVED_PROJECTION |
| D2 explicit adoption | approved Definition/Instance representations may be authored; current Agent remains accepted during window | compatibility adapter routes both forms through one semantic model | users opt in per Agent/workload | TRANSLATION_LAYER |
| D3 migration | adopted Agent desired authority moves to Definition representation; Instance lifecycle becomes explicit where required | legacy Agent facade projects compatible status/view | controlled conversion with rollback checkpoint | MIGRATION_REQUIRED |
| D4 future deprecation | legacy-only fields/paths emit actionable deprecation evidence | no silent translation for unsupported values | removal only after exit criteria/Human Gate | DEPRECATE_LATER |

The exact persistence representation for new logical Definition/Instance is
not selected. D1 requires any stable Instance mapping to be durable in an
approved source of truth; an ephemeral process-local map is prohibited.
Kubernetes remains the current Control Plane source of truth, but this does not
pre-approve a particular CRD/status/annotation encoding.

### 67.2 Compatibility interpretation

```text
Current Agent object A
  -> preserve A metadata identity as Definition-facing compatibility identity
  -> translate A.spec definition-owned values into Agent Definition intent
  -> translate Provider-owned values into opaque legacy Provider config/package refs
  -> preserve A.spec.replicas as legacy infrastructure replicas
  -> mint Instance identity I, where I != A identity
  -> record durable mapping I -> A Definition interpretation
  -> derive I effective Runtime Binding from A generation + legacy translator
  -> retain current Deployment/Service realization until migration stage permits change
```

The compatibility Instance is a logical projection only after it has a stable,
durably recorded Platform identity. It is not a Pod, replica, ordinal, Service,
or Agent UID alias. One legacy Agent initially maps to one legacy-managed
logical Instance whose Runtime may still have `replicas` native realizations.
Creating one Instance per replica is prohibited.

### 67.3 Current Agent field migration

| Current field/behavior | Target interpretation | Classification | Migration/exit rule |
| --- | --- | --- | --- |
| metadata name/namespace | Definition-facing compatibility address | KEEP | preserve throughout compatibility window |
| metadata UID | current API object evidence | KEEP | never reuse as Instance ID |
| role/displayName | Definition purpose/display | COMPATIBILITY_ALIAS | may become canonical on explicit Definition adoption |
| instructions.systemPrompt | Definition instruction intent | COMPATIBILITY_ALIAS | preserve inline behavior; future ref conversion explicit |
| capabilities strings | legacy Capability intent | TRANSLATION_LAYER | only named mapping may create Bindings; unknown remains visible |
| runtime.type | legacy Runtime class constraint | TRANSLATION_LAYER | resolve through legacy Runtime Provider descriptor |
| runtime.image | legacy Provider/package config | TRANSLATION_LAYER | opaque package/config ref; never stable Core field |
| model provider/name | legacy thin Model intent plus Provider detail | TRANSLATION_LAYER | keep until dedicated Model migration exists |
| model endpoint/baseUrl/secretRef | Provider config/credential reference | TRANSLATION_LAYER | no value copied into Core; later deprecate after equivalent refs work |
| resources cpu/memory | portable constraint candidate plus legacy raw values | TRANSLATION_LAYER | preserve current behavior; normalize only with proven semantics |
| replicas | legacy native realization count | KEEP | must not become Instance count |
| phase/readyReplicas | legacy infrastructure projection | COMPATIBILITY_ALIAS | derive compatible view from Instance/Runtime only after conformance |
| conditions | legacy Agent infrastructure conditions | TRANSLATION_LAYER | keep domain distinct; never merge vocabularies |
| same-name Deployment/Service | current native realization/route | KEEP in bounded mode | migration to Provider path requires conformance and rollback checkpoint |

### 67.4 Explicit Instance adoption

Users adopt explicit Instances only through a future approved representation.
For an Agent in compatibility mode:

1. the system exposes the minted legacy-managed Instance identity and source
   Agent generation;
2. user chooses to retain that Instance identity or creates additional new
   Instance identities under approved lifecycle rules;
3. Definition adoption preserves the Definition-facing identity mapping;
4. Tasks without explicit targeting continue Definition-based selection;
5. explicitly targeted Tasks require authorization and cannot target the
   compatibility Service directly;
6. the legacy path may be disabled per migrated Definition only after no active
   Task/Workflow depends on legacy interpretation and rollback criteria pass.

## 68. Identity Migration Map

| Identity/reference | Current | Target | Stability rule | Classification |
| --- | --- | --- | --- | --- |
| Agent metadata identity | namespaced Agent name/UID | Definition-facing compatibility identity | name/scope remain stable; UID remains representation evidence | KEEP |
| Agent Definition identity | no separate logical Contract ID | stable Definition identity mapped to current Agent during compatibility | mapping must be durable and one-to-one | ADDITIVE |
| Agent Instance identity | absent; Deployment/Service/replicas used operationally | new Platform-minted identity | never equal Definition ID, UID, Pod, Service, replica, Gateway, session | ADDITIVE |
| Task identity | Task metadata | Task logical resource identity | unchanged | KEEP |
| Task Agent reference | same-namespace Agent name | legacy Definition target alias | meaning remains unchanged; no Instance reinterpretation | COMPATIBILITY_ALIAS |
| Task selected Instance | absent | derived status/effective reference | new, stable for recorded routing decision | DERIVED_PROJECTION |
| Workflow identity | Workflow metadata | Workflow logical identity | unchanged | KEEP |
| Workflow node identity | local node string | embedded Definition node ID | unchanged within Workflow | KEEP |
| Workflow-owned Task identity | generated resource name/UID | Task identity correlated to node | current naming/labels remain compatibility contract | KEEP |
| Execution identity | absent | Platform-generated embedded identity | additive; native IDs cannot seed it | ADDITIVE |
| Console Agent name | node Agent reference/current Agent view | Definition-facing display with optional selected Instance detail | current visible name remains stable | COMPATIBILITY_ALIAS |
| observability labels | Agent/Workflow/task labels | compatibility labels plus logical IDs when approved | old labels retained during window; new IDs additive | ADDITIVE |

Identity drift is detected when one current Agent maps to multiple Definition
identities, one Instance ID maps across Definitions, legacy Agent name resolves
to an Instance directly, or rerouting changes selected Instance without an
auditable decision. Any such condition blocks migration.

Deletion/recreation of a same-named current Agent requires explicit identity
semantics because Kubernetes UID changes. This draft does not promise that a
recreated object retains the old logical Definition identity; the compatibility
mapping must use durable generation/revision and tombstone/adoption rules before
that guarantee can be made.

## 69. Task Migration Map

| Current field/behavior | v0.2 logical target | Classification | Compatibility mechanism |
| --- | --- | --- | --- |
| metadata identity | Task identity/revision | KEEP | current resource remains authoritative |
| creation timestamp | submitted/created evidence | KEEP | derive logical submission time without rewriting metadata |
| `spec.agentRef.name` | legacy Definition target | COMPATIBILITY_ALIAS | same namespace/name semantics preserved |
| `spec.input.prompt` | request input inline value | KEEP | remains valid input representation |
| timeout default/minimum | Task timeout intent | KEEP | preserve `300` default and existing validation |
| `status.phase` | projection of submission/execution/Outcome | COMPATIBILITY_ALIAS | deterministic mapping; current enum unchanged |
| `status.result` | Task Outcome inline output | COMPATIBILITY_ALIAS | preserve string; output ref is additive alternative later |
| `status.reason` | Task-domain Outcome reason | KEEP | existing machine values preserved |
| `status.message` | safe Task diagnostic | KEEP | retain behavior; future redaction limits additive policy |
| `status.retryable` | Task-owned retry assessment | KEEP | do not reuse for Capability side-effect safety |
| `status.attempts` | Task attempt summary total | KEEP | existing counting behavior unchanged |
| started/completed timestamps | execution/outcome times | KEEP | no reinterpretation |
| Platform Execution Identity | embedded execution identity | ADDITIVE | generated once and persisted before/with acceptance |
| submission disposition | distinct logical state | DERIVED_PROJECTION initially | derive from current phase/reason; explicit field only after API approval |
| execution state | distinct logical state | DERIVED_PROJECTION initially | derive deterministically from current phase |
| Task Outcome | domain semantic conclusion | DERIVED_PROJECTION initially | derive from current terminal status/result/reason |
| selected Instance | routing evidence | ADDITIVE | status-only/effective projection; not user-required |
| native refs | optional correlation evidence | ADDITIVE | absence cannot break execution |
| cancellation | unsupported future behavior | DEFERRED | no current field/enum expansion |

### 69.1 Exact Task breaking candidates

- changing `agentRef.name` to mean Agent Instance;
- requiring a new target field for existing Tasks;
- changing current phase/reason spellings or terminality;
- changing `result` from string to object without dual representation/version;
- resetting or redefining `attempts` around Provider attempts;
- requiring native references for completion;
- treating old Tasks without Platform Execution Identity as invalid;
- rerouting an accepted Task without auditable identity/provenance rules.

Old Tasks lacking Execution Identity receive a compatibility identity only by a
deterministic, collision-safe, durably recorded migration rule. Generating a
different identity on every read/restart is prohibited. Exact backfill mechanics
remain an API/migration design decision.

## 70. Workflow Migration Map

| Current semantic | v0.2 embedded model | Classification | Migration behavior |
| --- | --- | --- | --- |
| Workflow metadata identity | Workflow identity | KEEP | unchanged |
| `spec.tasks[]` | embedded definition nodes | COMPATIBILITY_ALIAS | logical grouping only; current wire stays |
| node name | local node identity | KEEP | unchanged |
| node Agent/input/timeout | embedded Task request | KEEP | current semantics retained |
| `dependsOn` | graph dependency refs | KEEP | graph validation retained |
| input result sources | node output refs | KEEP | order/result-passing retained |
| owned Task creation | materialized Task lifecycle | KEEP | Task remains execution authority |
| Task names/labels/owner refs | node/Task correlation | KEEP | changing requires later migration |
| failure/timeout skip propagation | dependency impossible/terminal projection | COMPATIBILITY_ALIAS | current behavior preserved |
| independent siblings/fan-in | runnable graph semantics | KEEP | no orchestration redesign |
| Workflow phase | aggregate execution/Outcome projection | COMPATIBILITY_ALIAS | current machine values remain |
| per-node status map | node execution projection | DERIVED_PROJECTION | cannot become desired Task authority |
| Workflow execution identity | embedded root identity | ADDITIVE | old Workflow compatibility backfill required |
| Task parent/root correlation | child correlation | ADDITIVE | does not create Execution resource |
| Human Gate waiting | thin embedded execution state | DEFERRED until representation approved | must not overload current success/failure dishonestly |
| reusable definition/multiple runs | future promotion | DEFERRED | requires independent lifecycle/identity evidence and Human Architecture Gate |

The existing Console and controller continue to see one Workflow plus owned
Tasks. No dual Workflow/WorkflowExecution writes occur. Future promotion trigger
remains multiple independently retained, referenced, authorized, and reconciled
runs of one reusable definition that cannot be represented compatibly inside
the current resource.

## 71. Capability Introduction Migration

Capability Definition and Binding can be introduced without invalidating
current workloads by making adoption explicit and operation-scoped.

| Current behavior | Introduction path | Classification |
| --- | --- | --- |
| Agent `capabilities[]` strings | optional legacy-name resolver to a declared Capability Definition/Binding | TRANSLATION_LAYER |
| unknown capability string | preserve as visible legacy value; no silent authority/provider mapping | KEEP |
| direct Runtime-internal tool behavior | continues for legacy workload profile, explicitly uncertified as platform Capability | KEEP during window |
| new Capability Definition | independently registered logical definition | ADDITIVE |
| new Capability Binding | optional Agent Definition governed intent | ADDITIVE |
| REST/MCP Provider descriptor | domain-specific internal registry metadata | ADDITIVE |
| authorization decision before invocation | required for adopted Binding path | ADDITIVE |
| native tool/endpoint identity | Provider extension/native evidence | TRANSLATION_LAYER |

Adoption sequence:

1. publish Capability Definition and Provider compatibility metadata;
2. map a legacy capability string only through explicit configured identity and
   version/operation rules;
3. add Capability Binding to adopted Definition intent;
4. validate authorization independently of discovery and Provider availability;
5. route new invocation through Capability Provider and correlate Platform
   Execution Identity;
6. compare outcomes with legacy behavior before deprecating direct integration.

Legacy direct behavior cannot be marketed as Contract-conforming Capability
use unless it passes the same authorization, identity, outcome, and Provider
isolation conformance. Deprecation begins only after all in-scope legacy strings
have explicit mappings or declared unsupported disposition, adopted workloads
pass conformance, and rollback exists. No marketplace or dynamic service is
introduced.

## 72. Runtime Migration Map

```text
current Agent runtime/model fields
  -> legacy Runtime compatibility translator
    -> DesiredRuntimeBinding interpretation
      -> domain Runtime Provider resolution metadata
        -> EffectiveRuntimeBinding on legacy-managed/new Instance
          -> current Native Service path OR adopted Provider path
            -> opaque native realization evidence
```

| Current Runtime input/behavior | Target treatment | Primary classification |
| --- | --- | --- |
| `runtime.type` | keep as compatibility input; translate to Runtime class/Provider constraints | TRANSLATION_LAYER |
| `runtime.image` | translate to opaque Runtime Package/Provider configuration ref | TRANSLATION_LAYER |
| model provider/name | keep legacy input; map only to thin Model Binding/reference where justified | TRANSLATION_LAYER |
| endpoint/base URL/Secret ref | Provider-owned opaque config/credential target | TRANSLATION_LAYER |
| simplified CPU/memory | legacy realization constraint with optional portable mapping | TRANSLATION_LAYER |
| replicas | current native realization count | KEEP |
| Operator constructs Deployment/Service | legacy Native Runtime Provider behavior | COMPATIBILITY_ALIAS initially; MIGRATION_REQUIRED later |
| same-name Service routing | compatibility Runtime path after logical selection | TRANSLATION_LAYER |
| `/v1/invoke` payload | current Runtime-native interaction | KEEP during compatibility; DEPRECATE_LATER only after conformance |
| Runtime environment variables | Provider implementation/config detail | DEPRECATE_LATER from direct Core coupling |
| Agent readiness phase/count | legacy infrastructure projection | DERIVED_PROJECTION |

No current Runtime-specific field is promoted to stable Core. Fields that
cannot be represented through opaque Provider configuration/package references
remain legacy-only and block that workload's Provider-path adoption rather than
expanding Core.

### 72.1 Runtime fallback boundary

Fallback to the current Runtime path is allowed only when all are true:

- the workload originated from or retains a valid legacy Agent representation;
- its current Runtime configuration is still understood by the legacy
  translator;
- the current Deployment/Service path remains present and compatible;
- no explicit adopted Provider-only semantic would be lost;
- routing/audit identifies fallback and preserves Platform execution identity;
- policy permits fallback.

There is no universal fallback from OpenClaw, Hermes, future third-party, or
explicit multi-Instance semantics to the current Native path. Claiming one
would hide behavior and ownership drift.

## 73. Console Compatibility Projection

The Console remains read-only and projects the current Kubernetes source of
truth. Its user-facing Agent concept may progressively disclose Definition and
Instance detail without changing business identity.

```text
Current Console Agent reference/name
  -> Definition-facing compatibility identity + display
  -> optional Instance summary (count/eligibility/selected Instance)
  -> optional Runtime Binding/Condition/Recovery technical detail

Current Workflow/Task execution view
  -> existing fields unchanged
  -> optional Platform Execution Identity and selected Instance
  -> native evidence only behind bounded operator detail
```

| Console concern | Compatibility rule | Classification |
| --- | --- | --- |
| existing routes and response fields | preserve | KEEP |
| machine phase values | preserve | KEEP |
| Agent name shown on node | Definition-facing alias | COMPATIBILITY_ALIAS |
| selected Instance detail | optional derived projection | ADDITIVE |
| Definition/Instance summary | derived from authoritative Control Plane objects/mapping | DERIVED_PROJECTION |
| Digital Employee/Agent business label | presentation projection only | KEEP |
| Provider/native IDs | optional restricted technical detail | ADDITIVE |
| Console database/source of truth | prohibited | BREAKING_CANDIDATE |

Because Console response models forbid extras, any new field requires an
explicit versioned or backward-compatible response model and tests in a later
authorized implementation. Old clients must continue to parse existing
responses unchanged. Console never owns Definition/Instance identity or
migration state.

## 74. Current Examples and Manifests

| Current artifact pattern | v0.2 interpretation | Classification |
| --- | --- | --- |
| Agent manifests with runtime/model fields | legacy Definition-facing intent plus Provider compatibility input | TRANSLATION_LAYER |
| Agent `replicas` | native realization count, not Instance count | KEEP |
| Task `agentRef.name` | legacy Definition target | COMPATIBILITY_ALIAS |
| Workflow embedded node Agent refs | embedded Task legacy targets | COMPATIBILITY_ALIAS |
| current timeout/result-passing/DAG examples | unchanged Task/Workflow behavior | KEEP |
| failure/skip Golden Demo | unchanged outcome/propagation compatibility fixture | KEEP |
| capability strings | legacy unmapped/mapped intent depending explicit registry config | TRANSLATION_LAYER |

All checked-in current manifests remain valid inputs during the compatibility
window. They should become mandatory conformance fixtures. New v0.2 examples
may demonstrate explicit Definitions/Instances/Bindings only after an API
representation is approved and must not replace legacy fixtures prematurely.

## 75. Versioned Transition Recommendation

Do not decide between same-version extension and a new Kubernetes API version
globally. Use a combined, evidence-triggered strategy:

### 75.1 Same current representation

Use only for behavior-preserving compatibility interpretation and additive
optional projections whose absence/unknown semantics are safe for old clients.
Do not add required fields, reinterpret current fields, or expand existing enums
without proving client/server compatibility.

### 75.2 New logical resources/representations

Agent Instance and Capability Definition require separately approved API and
persistence representations. Their logical novelty does not automatically
require changing Agent/Task/Workflow Kubernetes API version, and it does not
pre-approve them as CRDs.

### 75.3 New API version trigger

A new version/conversion layer is required if any approved representation must:

- change requiredness/defaulting or field type;
- reinterpret `agentRef`, Agent Runtime/Model fields, Task status, or Workflow
  structure;
- change enum terminality/meaning;
- split desired authority across incompatible objects;
- make round-trip conversion lossy;
- require old clients to understand a new state for correctness.

### 75.4 Dual-read and write policy

- dual-read may accept legacy and adopted representations through one semantic
  validator/resolver;
- dual-write is prohibited by default because it creates competing desired
  authorities and update loops;
- if conversion requires two persisted representations, one is explicitly
  authoritative and the other is a derived projection with generation and
  ownership markers;
- conflicts fail closed and become observable; last-writer-wins is prohibited;
- compatibility facade is read/project/translate behavior, not a second source
  of truth.

**Recommendation:** begin with current API preservation plus a logical
compatibility layer and additive observability, then select new API versions
per resource only after representation analysis proves necessity. This avoids
both assuming `v1alpha1` can absorb everything and creating versions without
evidence.

## 76. Mixed-Version Behavior

### 76.1 Supported bounded modes

| Mode | Desired authority | Routing/runtime | Status/view |
| --- | --- | --- | --- |
| legacy | current Agent/Task/Workflow | compatibility Instance + current Runtime path | current status authoritative; target semantics derived |
| compatibility-observed | current desired objects | same path plus minted identity/execution/routing evidence | current fields plus optional derived projections |
| adopted | approved Definition/Instance/Binding representation | Provider resolution path; legacy fallback only when eligible | target status plus current compatibility facade where lossless |
| mixed Workflow | current Workflow nodes may target legacy or adopted Definitions | each Task resolved independently under same execution correlation rules | aggregate uses current compatible phase projection |

### 76.2 Ambiguity prevention

- every object/workload carries an observable compatibility mode and semantic
  schema version once such representation is approved;
- one desired authority is declared per resource relationship;
- explicit Instance target cannot be interpreted by legacy Runtime routing;
- adopted-only fields cannot be silently dropped when projected to legacy;
- unsupported mixed dependency or Provider combinations fail validation before
  execution rather than degrade silently;
- selection, translation, fallback, and conversion decisions record generation,
  version, reason, and time;
- old consumers see only states that preserve current meaning; new distinctions
  unavailable to them remain additive detail, not altered phase semantics.

Fundamental ambiguity was not found at the logical layer. Representation-level
ambiguity remains a conformance/implementation gate.

## 77. Migration Safety and Risk Matrix

| Risk | Severity | Failure mode | Detection/observability | Mitigation/rollback boundary |
| --- | --- | --- | --- | --- |
| data loss | High | current Provider config/status cannot round-trip | field-level conversion diff; unmapped-field report | retain authoritative legacy object; block adoption on lossy mapping |
| Definition identity drift | Critical | current Agent maps to new Definition ID/name | durable mapping audit and uniqueness check | abort conversion; retain current Agent authority |
| Instance identity collision/drift | Critical | regenerated/shared ID after restart or across Definitions | mapping conformance and restart tests | require durable minted ID; never derive from replica/native ID |
| routing drift | Critical | Task selects Instance outside target/eligibility | decision provenance and invariant checks | fail closed; legacy path only under bounded criteria |
| behavior drift | High | Provider translation changes Runtime/model/capability behavior | unchanged-workload differential E2E | retain legacy Runtime path; block Provider adoption |
| status interpretation drift | High | current phase/result differs from richer model | bidirectional projection contract tests | current fields remain compatibility authority until proven |
| rollback difficulty | High | adopted-only semantics cannot map to legacy | pre-adoption reversibility assessment | mark non-rollbackable boundary; require explicit acceptance |
| mixed-version conflict | High | two desired authorities or incompatible refs | mode/source markers and generation conflict conditions | fail closed; prohibit implicit last-writer-wins/dual-write |
| Provider incompatibility | High | descriptor/package/profile mismatch | deterministic compatibility decision | no handoff; retain eligible legacy path only |
| Console break | Medium | old client rejects new fields or changed phase | API consumer/schema tests | version/add optional model; preserve existing response |
| migration invisibility | High | fallback/translation occurs silently | conditions/events/audit metrics by mode/reason | migration cannot progress without observable state |
| secret/config exposure | Critical | Provider config copied into Core/status/logs | redaction and schema-boundary tests | opaque refs only; block migration on exposure |
| cleanup ownership error | Critical | external/shared realization deleted | ownership-mode conformance and audit | fail safe; no unconditional deletion |
| execution identity split | High | old/new path produces conflicting IDs | end-to-end propagation/correlation test | persist once before handoff; block on mismatch |
| recovery fiction | High | restart projected as recovered | predicate/evidence conformance | keep UNKNOWN/FALSE; no automatic success/rerun |

Migration progression requires risk-specific evidence; a general passing test
suite cannot waive identity, cleanup, security, or rollback failures.

## 78. Rollback Model

### 78.1 Supported logical rollback

- existing Agent, Task, Workflow, manifests, current status, and current Console
  fields remain valid throughout D0-D2;
- additive Definition/Instance/execution/status projections may be ignored by
  old consumers because they do not change current wire semantics;
- compatibility observation can be disabled while current desired authority
  and Runtime path remain intact;
- Provider resolution may fall back to current Runtime only within Section
  72.1 criteria and with observable reason/provenance;
- migration may roll back before adopted-only desired semantics become
  authoritative or legacy configuration is removed;
- conversion writes require a recovery copy/authoritative source and verified
  reverse projection before cutover.

### 78.2 Not promised

- explicit multi-Instance lifecycle cannot generally collapse back to one
  current Agent/replica model without semantic/data loss;
- OpenClaw, Hermes, external/shared, Capability Provider, or adopted-only
  execution behavior cannot universally fall back to Native Runtime;
- in-flight execution cannot be silently moved or replayed during rollback;
- state/memory continuity across Providers is not assumed;
- native resources with external/shared/unknown ownership cannot be deleted to
  force rollback;
- new Capability authorization/outcome evidence cannot be reduced to legacy
  direct tool behavior without losing governance semantics;
- once deprecated fields are removed in a future approved version, rollback to
  clients requiring them needs an explicit conversion/support plan.

Every migration unit must declare its last reversible checkpoint and any
irreversible state before cutover. Where evidence is absent, rollback status is
`UNKNOWN`, and migration cannot claim reversible.

## 79. Schema Evolution Policy Candidate

| Evolution type | Candidate rule |
| --- | --- |
| additive optional field | allowed only with defined absence/default/unknown semantics and old-reader tolerance evidence |
| required field | new version or deterministic default/backfill with lossless conversion proof |
| semantic reinterpretation | prohibited in place; new field/version and migration required |
| enum expansion | allowed only if old consumers safely preserve/ignore unknown value; otherwise versioned change |
| terminality change | breaking candidate requiring version and migration |
| field deprecation | retain read/write or defined read alias during published compatibility window; emit actionable observability |
| field removal | later Human Gate only after usage zero/threshold, conformance, migration, rollback/support plan |
| reference evolution | add typed reference alongside legacy alias; conflicts fail; never change legacy target meaning |
| generation semantics | desired changes increment generation; derived/status writes do not; old generation cannot satisfy current reconciliation |
| Provider extension | versioned by Provider owner behind opaque ref; Core compatibility descriptor declares supported Contract profile |
| native evidence | additive and bounded; absence always valid unless a specific profile explicitly requires evidence, never execution identity |
| condition/outcome vocabulary | domain-owned versioning; shared structure does not imply synchronized enum releases |
| compatibility window | explicit start, supported modes, telemetry, deprecation criteria, and end Human Gate; not time-only |

The policy remains a Schema Draft recommendation, not frozen governance. Every
future change records source/target version, classification, compatibility
impact, conversion, mixed-mode behavior, deprecation window, and conformance.

## 80. Conformance Handoff

No tests are implemented here. Before the Schema Candidate can advance toward
API approval/freeze, the following evidence is required.

| Conformance area | Minimum evidence | Blocks |
| --- | --- | --- |
| existing Agent manifests | all checked-in manifests validate and retain current Deployment/Service/env/replica/status behavior in legacy mode | migration/adoption |
| Agent compatibility projection | field-by-field deterministic mapping including unmapped/Provider-owned data and round-trip report | schema/API approval |
| Definition/Instance derivation | stable distinct IDs across restart/update; generation provenance; no replica-to-Instance mapping | Agent migration |
| Agent identity deletion/recreation | explicit expected mapping/tombstone/adoption behavior | identity guarantee/freeze |
| existing Task behavior | current phases, results, retries, attempts, timestamps, timeout/error tests unchanged | Task migration |
| Task target selection | legacy Agent ref -> Definition target -> eligible selected Instance with auth/freshness and fail-closed cases | routing Contract |
| old Task identity backfill | deterministic persistent collision-free Platform Execution Identity or explicit legacy-unknown disposition | execution identity migration |
| existing Workflow behavior | DAG validation, owned Tasks, parallel/fan-in, result passing, failure/skip, aggregation unchanged | Workflow migration |
| Workflow identity propagation | root/parent Task execution correlation without new resource or behavior drift | execution Contract |
| Runtime Binding translation | current runtime/model/resource inputs map to opaque refs/effective Binding without Core leakage | Runtime migration |
| legacy Runtime fallback | bounded eligibility, behavior equivalence, audit, and explicit non-fallback cases | rollback claim |
| Capability introduction | legacy direct mode preserved; explicit Binding discovery/auth/deny-before-handoff/Provider isolation/outcome | Capability adoption |
| Provider extension isolation | unknown extensions round-trip opaquely; secrets/native config absent from Core/status/logs | security/API approval |
| Condition projection | four-way truth, generation, freshness, transition, and domain separation; current phases deterministic | condition schema/freeze |
| Recovery Assessment | negative restart-only case and positive applicable predicate case; unknown/stale/stateful/external cases | recovery vocabulary/freeze |
| Console compatibility | current REST responses/routes/phase values unchanged; additive version/model works with old clients | Console migration |
| mixed mode | legacy/adopted Tasks in one Workflow, one desired authority, conflict rejection, version/Provider mismatch | migration cutover |
| rollback | last reversible checkpoint, data/config retention, no in-flight replay, ownership-safe cleanup | operational approval |
| unchanged consumer | one generic consumer preserves Platform identity and domain semantics across Native/external Runtime and REST/MCP Capability Providers | Contract freeze/provider certification |

Conformance results must identify exact Contract/API/Provider/package versions,
mode, fixtures, and unsupported profiles. Passing legacy tests alone does not
certify the new semantic path.

## 81. Breaking Candidates and Deferred Changes

### 81.1 Breaking candidates

1. renaming current Agent to AgentDefinition in place;
2. making current Agent mean both Definition and Instance;
3. reusing Agent name/UID, Deployment, Service, Pod, replica ordinal, Gateway,
   or session as Instance identity;
4. changing `agentRef.name` to Instance or native target;
5. requiring explicit Instance or Execution Identity on existing Task specs;
6. changing Task phase/reason/result/attempt semantics or types in place;
7. splitting Workflow into Workflow and WorkflowExecution;
8. changing Workflow Task naming/labels/ownership or Console joins without
   migration;
9. treating capability strings as authorized Capability Bindings silently;
10. moving Runtime/model endpoints, credentials, images, or native configuration
    into stable Core;
11. using dual-write/last-writer-wins desired authority;
12. requiring native IDs for correctness or cleanup;
13. collapsing domain Conditions/Outcomes into universal enums;
14. projecting UNKNOWN as healthy/eligible/recovered/successful;
15. promising universal Provider fallback or state portability.

No breaking candidate is accepted or required by this migration recommendation.

### 81.2 Deferred

- Workflow Definition/Execution resource promotion;
- Model routing/fallback/ranking/quota/cost/context algorithms;
- cancellation and durable deferred execution;
- State/Memory portability;
- multi-tenant scope/identity/RBAC/policy lifecycle;
- Human Feedback learning architecture;
- dynamic Provider marketplace/registry service;
- automatic in-flight rerouting/replay;
- removal of any current Agent/Task/Workflow field or API version.

## 82. Human Decisions Required — Checkpoint D

All decisions remain **PENDING** until the Human Checkpoint D Gate.

### D01 — Staged Agent migration strategy

**Recommendation:** accept D0-D4 Option B stages with current Agent authoritative
through compatibility observation, explicit opt-in adoption, and later gated
deprecation.
**Decision:** PENDING.

### D02 — Definition identity preservation

**Recommendation:** preserve current Agent name/scope as Definition-facing
compatibility address through a durable one-to-one mapping; Kubernetes UID
remains representation evidence.
**Decision:** PENDING.

### D03 — New Agent Instance identity

**Recommendation:** Platform-mint and durably record a distinct legacy-managed
Instance identity; never derive it from Definition ID, replica, or native ID.
**Decision:** PENDING.

### D04 — Legacy Instance cardinality

**Recommendation:** one current Agent initially maps to one legacy-managed
logical Instance whose Runtime may own multiple native replicas; do not map
replicas to Instances.
**Decision:** PENDING.

### D05 — Task migration

**Recommendation:** preserve every current Task field/behavior; add Execution
Identity, selection, and richer states as additive/derived semantics; retain
legacy target alias.
**Decision:** PENDING.

### D06 — Workflow migration

**Recommendation:** preserve current DAG, Task ownership, behavior, status, and
Console joins; add embedded execution identity/projections only compatibly and
defer resource split.
**Decision:** PENDING.

### D07 — Capability introduction

**Recommendation:** optional explicit Definition/Binding adoption with named
legacy mapping, independent authorization, Provider isolation, and no silent
upgrade of capability strings.
**Decision:** PENDING.

### D08 — Runtime compatibility translation

**Recommendation:** translate current runtime/model/resource fields to desired
Binding and opaque Provider/package config while retaining the current Runtime
path for bounded legacy mode.
**Decision:** PENDING.

### D09 — Runtime fallback boundary

**Recommendation:** allow observable fallback only for legacy-compatible
workloads meeting Section 72.1; no universal external/adopted-to-Native
fallback.
**Decision:** PENDING.

### D10 — Console compatibility projection

**Recommendation:** preserve current routes/fields/phases and Agent name while
adding Definition/Instance/execution detail only through compatible derived
projections or API versions.
**Decision:** PENDING.

### D11 — Versioned transition strategy

**Recommendation:** preserve current APIs first, use additive safe projections,
and choose a new API version per resource only when requiredness/type/semantic/
round-trip evidence triggers it.
**Decision:** PENDING.

### D12 — Conversion and desired authority

**Recommendation:** permit dual-read through one semantic model; prohibit
dual-write by default; declare one authoritative desired representation and
fail closed on conflicts.
**Decision:** PENDING.

### D13 — Deprecated fields

**Recommendation:** deprecate current Provider-specific and legacy integration
fields only after equivalent opaque refs, adoption, conformance, observability,
rollback/support, and a later Human Gate; remove nothing in v0.2 draft.
**Decision:** PENDING.

### D14 — Breaking candidates

**Recommendation:** accept Section 81.1 as prohibited/unaccepted candidates;
none is required by the recommended migration.
**Decision:** PENDING.

### D15 — Rollback boundary

**Recommendation:** guarantee bounded rollback only while legacy authority/path
is retained and no adopted-only semantics would be lost; record explicit
non-rollbackable boundaries and treat absent evidence as UNKNOWN.
**Decision:** PENDING.

### D16 — Mixed-version behavior

**Recommendation:** support declared legacy, compatibility-observed, adopted,
and mixed Workflow modes with one desired authority, explicit versions/mode,
fail-closed conflicts, and observable selection/translation/fallback.
**Decision:** PENDING.

### D17 — Schema evolution policy

**Recommendation:** accept Section 79 candidate rules for optional/required
fields, reinterpretation, enums, deprecation/removal, references, generation,
extensions, evidence, and compatibility windows; policy remains unfrozen.
**Decision:** PENDING.

### D18 — Conformance handoff

**Recommendation:** require the Section 80 matrix before API approval,
migration, freeze, certification, or production claims as indicated.
**Decision:** PENDING.

### D19 — Current examples as fixtures

**Recommendation:** all checked-in current Agent/Task/Workflow examples remain
valid compatibility fixtures; new explicit v0.2 examples supplement rather
than replace them.
**Decision:** PENDING.

### D20 — Migration observability

**Recommendation:** require mode, source/target version, identity mapping,
generation, translation/selection/fallback reason, time, and failure conditions
before migration progresses.
**Decision:** PENDING.

## 83. Contradictions and Stop-Condition Review — Checkpoint D

| Stop condition | Result |
| --- | --- |
| Current Agent semantics must be silently reinterpreted | Not required; translation is explicit and old semantics remain |
| Existing identity cannot be preserved safely | Not found logically; durable mapping and deletion/recreation evidence remain pre-cutover requirements |
| Immediate breaking Task change unavoidable | Not found |
| Workflow must become two resources | Not found |
| Capability introduction breaks existing workloads | Not required; optional adopted path retains legacy mode |
| Runtime migration requires Provider-specific Core fields | Not found; opaque refs and legacy translator suffice |
| Rollback cannot be bounded | Bounded through D0-D2; adopted-only/non-legacy paths explicitly not promised universal rollback |
| Mixed-version semantics fundamentally ambiguous | Not found logically; one authority/mode/conflict rules bound them |
| S5-ARCH-004 boundary must change | Not found |

No blocking contradiction was found. Checkpoint E has not begun.

## 84. Evidence Debt — Checkpoint D

Carry forward Checkpoint A-C debt, plus:

- exact API/persistence representation for Definition, Instance, Capability,
  compatibility metadata, and additive status remains undecided;
- no durable Agent-to-Definition/Instance mapping implementation or restart,
  update, deletion/recreation, collision, adoption, or rollback evidence exists;
- compatibility Instance creation, ownership, lifecycle, and deletion semantics
  remain schema/API and conformance debt;
- field-level lossless translation for current Runtime/Model/resource values
  and secrets has not been proven;
- old Task/Workflow Platform Execution Identity backfill mechanics remain open;
- deterministic richer-state/current-phase projection needs contract tests and
  vocabulary review;
- explicit Definition/Instance reference coexistence and conflict validation
  lack API representation;
- Capability legacy-name mapping, authorization, Provider registration,
  outcome, and deprecation telemetry remain unimplemented/unproven;
- Runtime fallback equivalence is supported only conceptually for the legacy
  Native path and requires differential E2E evidence;
- mixed legacy/adopted Workflow behavior and rollback across in-flight work are
  unproven;
- Console API additive/version compatibility and old-client tolerance need
  explicit tests;
- compatibility/deprecation duration and adoption thresholds remain Human
  product/support decisions;
- schema evolution policy is a candidate, not frozen;
- combined unchanged-consumer Runtime/Capability conformance, Provider
  certification, recovery profiles, state continuity, and ED-S5-001 remain
  open under their existing classifications.

These debts block API/CRD approval, migration implementation, Contract/schema
freeze, Provider certification, production cutover, and applicable rollback
claims. They do not falsify the bounded logical migration path.

## 85. Checkpoint D State

LIFECYCLE: **REVIEW**
AUTHORIZATION: **AUTHORIZED**
STATUS: **PASS**
CHECKPOINT: **D — COMPATIBILITY_AND_MIGRATION_MAP**
RESULT: **COMPATIBILITY_MIGRATION_RECOMMENDED**

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
NEXT_GATE: **Human Checkpoint D Gate**

Checkpoint E has not begun and is not authorized by this result.

# Checkpoint E — Final Schema Candidate Convergence

## 86. Human Checkpoint D Gate Record

HUMAN DECISION: **PASS WITH CANDIDATE-CONVERGENCE CONSTRAINTS**

| Accepted dimension | Checkpoint E authority |
| --- | --- |
| D01-D20 | `ACCEPTED_FOR_SCHEMA_CANDIDATE` |
| Migration | staged Option B; no accepted breaking change |
| Identity | current Definition-facing address preserved; new distinct Instance ID |
| Task/Workflow | additive compatibility; current wire behavior remains binding input |
| Capability/Runtime | explicit translation/adoption; Provider specifics outside Core |
| Versioning/mixed mode | per-resource evidence; exactly one desired authority |
| Rollback | bounded only; no universal claim |
| Schema evolution | candidate policy, not frozen |
| Checkpoint purpose | final convergence; no exploratory expansion or implementation |

Sections 1-85 remain the distinct Checkpoint A-D record. No earlier Human
Decision, debt, or freeze constraint is rewritten by this convergence.

## 87. Executive Candidate Summary

**Candidate:** `v0.2 Core Schema Candidate v0`

The Candidate has five first-class logical resources: Agent Definition, Agent
Instance, Task, Workflow, and Capability Definition. Runtime Binding and
Capability Binding are domain-specific embedded Bindings; Model Binding is a
thin embedded foundation. Platform Execution Identity is a Platform-owned
embedded value, not a resource. Runtime and Capability Providers are distinct
interfaces whose registries and Runtime Package records remain internal
metadata. Domain Conditions, Outcomes, and Recovery Assessment remain embedded
under their semantic owners. Native identities remain opaque `0:N` evidence.

The Candidate preserves current Agent/Task/Workflow semantics through staged
Option B compatibility. It requires no accepted breaking change and no sixth
resource. It is implementation-neutral and representation-neutral: first-class
logical resource does not mean CRD. The Candidate is ready for schema
prototyping and bounded conformance work where classified below; it is not a
frozen Contract, approved API/CRD, implementation authorization, Provider
certification, or production-readiness claim.

## 88. Final Logical Schema Inventory

| Category | Candidate members | Final v0 disposition |
| --- | --- | --- |
| First-class logical resources | Agent Definition, Agent Instance, Task, Workflow, Capability Definition | candidate set fixed for final Human Gate |
| Embedded Bindings | Runtime Binding, Capability Binding | domain-specific desired/effective boundaries; no CRDs |
| Thin embedded Binding | Model Binding | references/ownership only; routing deferred |
| Core value object | Platform Execution Identity | embedded, Platform-created, stable, propagated |
| Relationship primitive | execution correlation | bounded parent/root/native relationships; no lifecycle resource |
| Domain Conditions | Runtime Conditions, Agent Instance Conditions | shared structure/four-way truth; domain vocabulary unfrozen |
| Domain Outcomes | Task Outcome, Workflow Outcome, Capability Outcome | separate ownership/taxonomy; Provider results are evidence |
| Embedded status | Agent Instance Status, Recovery Assessment | Instance-owned effective/observed state and semantic recovery |
| Provider interfaces | Runtime Provider, Capability Provider | replaceable translation boundaries, never Core resources |
| Internal metadata | Runtime Provider Registry, Capability Provider Registry, Runtime Package | deterministic version/compatibility facts; no public Registry service |
| Thin foundations | Model, Workspace, State/Memory, Knowledge, Policy, Permission, Human Gate | references/interaction boundary only |
| Rejected abstractions | universal Execution/Status/Result/Provider/Binding/Registry/RuntimeInstance; WorkflowExecution now | not part of Candidate |

## 89. Resource Candidate Cards

### 89.1 Agent Definition

| Dimension | Candidate card |
| --- | --- |
| Purpose | authoritative reusable logical definition of what an Agent is and what governed Bindings/references it requests |
| Authority/owner | Agent Definition/Core owns desired logical definition and generation |
| Identity | Platform resource identity; current Agent name/scope is the compatibility address; distinct from every Instance/native ID |
| Desired | role/purpose, display/instructions, desired Runtime Binding template, Capability Bindings, thin Model and other foundation refs |
| Effective | validation/default projection only; no running effective Runtime authority |
| Observed/status | observed generation and definition validation conditions only |
| References | Capability Definitions, thin Model/Workspace/State/Knowledge/Policy/Permission |
| Lifecycle | definition create/update/version/adoption/delete protection; live Instances prevent ungoverned deletion |
| Compatibility | current Agent evolves toward Definition through explicit translator; no rename or field reinterpretation |
| Provider boundary | Provider config/package/native mechanics only through opaque refs/legacy translator |
| Native evidence boundary | no Pod/container/Gateway/session/realization state |
| Evidence debt | revision/adoption/rollout, deletion/recreation identity, API representation, compatibility mapping conformance |
| Freeze status | `CANDIDATE_WITH_EVIDENCE_DEBT`; not frozen |

### 89.2 Agent Instance

| Dimension | Candidate card |
| --- | --- |
| Purpose | stable logical running identity that survives native realization replacement |
| Authority/owner | Agent Instance Control Plane owns desired lifecycle, effective resolution, routing eligibility, conditions, recovery |
| Identity | distinct Platform-minted identity; exactly one Definition ref; never replica/native identity |
| Desired | Definition ref and desired lifecycle intent |
| Effective | observed Definition revision/generation, effective Runtime Binding, optional thin Model projection, resolution provenance |
| Observed/status | routing eligibility, Runtime/Instance Conditions, Recovery Assessment, realization summary, native refs, freshness |
| References | exactly one Definition; effective Provider/package metadata; optional execution correlations |
| Lifecycle | Definition `1:N` Instances; identity stable across `1:N` temporal and `0:N` active realizations |
| Compatibility | one legacy Agent initially projects one legacy-managed Instance with durably recorded distinct identity; replicas remain native count |
| Provider boundary | Control Plane selects Instance; Runtime Provider translates its effective Binding and selects only within it |
| Native evidence boundary | opaque bounded refs; never routing/identity authority |
| Evidence debt | lifecycle vocabulary, targeting authorization, eligibility freshness, stable backfill/mapping, deletion/finalization, in-flight behavior |
| Freeze status | `CANDIDATE_WITH_EVIDENCE_DEBT`; not frozen |

### 89.3 Task

| Dimension | Candidate card |
| --- | --- |
| Purpose | durable requested-work lifecycle owning submission, execution observation, attempts, and Task terminal Outcome |
| Authority/owner | Task domain owns request and Task Outcome; Control Plane owns Instance routing |
| Identity | current Task identity plus embedded Platform Execution Identity for one logical execution |
| Desired/requested | Definition-facing target or authorized Instance target, input, timeout, routing/auth intent, retry policy where supported |
| Effective | target interpretation and selected Instance routing decision/provenance |
| Observed/status | submission disposition, execution state, attempts, Outcome, timestamps, optional native refs |
| References | Definition/Instance target family, authorization/policy refs, output ref, native evidence |
| Lifecycle | current Pending/Running/Succeeded/Failed/TimedOut behavior remains compatibility constraint; cancellation deferred |
| Compatibility | existing `agentRef`, input, timeout, phase, result, reasons, retryable, attempts, timestamps remain; richer model is additive/derived |
| Provider boundary | Provider/native result is evidence; Task owner determines Outcome |
| Native evidence boundary | optional `0:N`; absence cannot invalidate execution correctness |
| Evidence debt | identity backfill, exact state/outcome vocabulary, retry/replay/idempotency, target auth, output ref/retention, cancellation |
| Freeze status | `CANDIDATE_WITH_EVIDENCE_DEBT`; not frozen |

### 89.4 Workflow

| Dimension | Candidate card |
| --- | --- |
| Purpose | first-class DAG/orchestration lifecycle with embedded definition/request and aggregate execution/outcome |
| Authority/owner | Workflow owns graph, node orchestration, aggregate state/Outcome; Tasks own node execution |
| Identity | current Workflow identity; embedded root Platform Execution Identity; local node identities |
| Desired/requested | nodes, dependencies, Task requests, input-source references |
| Effective | runnable/blocked node interpretation; no separate desired Task authority |
| Observed/status | node Task projections, dependency/skip state, partial completion, Human Gate wait, aggregate Outcome |
| References | owned/referenced Tasks, node dependencies/output refs, thin Human Gate refs |
| Lifecycle | one v0.2 resource; current execution conflation retained as explicit debt |
| Compatibility | DAG, Task ownership/names/labels, result passing, parallel/fan-in, failure/skip, aggregation, status, Console joins preserved |
| Provider boundary | no direct Runtime/Capability Provider ownership; node Tasks follow their domain paths |
| Native evidence boundary | Workflow aggregates logical Task evidence; no native topology authority |
| Evidence debt | root/Task identity backfill, Human Gate representation, reusable multi-run promotion, mixed-mode/in-flight behavior |
| Freeze status | `CANDIDATE_WITH_EVIDENCE_DEBT`; not frozen |

### 89.5 Capability Definition

| Dimension | Candidate card |
| --- | --- |
| Purpose | provider/transport-independent enterprise identity and semantic operation Contract |
| Authority/owner | Capability domain owns identity/version/operation/input-output/risk/auth/execution characteristics |
| Identity | logical Capability/version/operation; never MCP tool, REST endpoint, SDK function, CLI command, or Provider ID |
| Desired/declarative | schemas, risk, authorization requirements, interaction characteristics/dispositions, compatibility policy |
| Effective | invocation-time Binding/Provider/version/auth resolution outside Definition |
| Observed/status | definition validation only; invocation produces separate Capability Outcome |
| References | input/output schemas, policy refs, Capability Bindings from Definitions |
| Lifecycle | definition/version publication and compatibility; no Provider-native deletion implied |
| Compatibility | optional adoption; legacy strings/direct tools require explicit mapping and remain ungoverned until conformance |
| Provider boundary | Capability Provider translates only after independent authorization; REST/MCP are realizations |
| Native evidence boundary | optional invocation refs under Capability Outcome; zero on pre-handoff denial is valid |
| Evidence debt | taxonomy, side effects/idempotency, deferred/cancel durability, third-party MCP, mapping/deprecation telemetry |
| Freeze status | `CANDIDATE_WITH_EVIDENCE_DEBT`; not frozen |

## 90. Authoritative Relationship Map

```text
Agent Definition
  1:N  -> Agent Instance
  1:1  -> desired Runtime Binding template (embedded)
  1:N  -> Capability Binding (embedded)
  0:1  -> thin Model Binding (embedded)
  0:N  -> thin Workspace/State/Knowledge/Policy/Permission refs

Agent Instance
  1:1  -> Agent Definition ref
  1:1  -> effective Runtime Binding (derived/embedded)
  1:N temporal / 0:N active -> opaque native Runtime realizations
  0:N  -> execution correlation refs (bounded observation)

Task
  1:1  -> logical target (Definition by default; authorized Instance optional)
  0:1  -> selected Agent Instance (effective routing evidence)
  1:1  -> Platform Execution Identity
  0:N  -> native Runtime/Capability/infrastructure refs

Workflow
  1:N  -> embedded node definitions
  0:N  -> owned/referenced Task resources over execution lifecycle
  1:1  -> root Platform Execution Identity per logical execution
  Task execution IDs -> optional parent/root correlation to Workflow

Capability Binding
  1:1  -> Capability Definition
  0:1  -> preferred/required Capability Provider metadata
  0:N  -> policy/authorization/config refs

Platform Execution Identity
  unchanged -> routing -> selected Instance -> Runtime Provider
            -> native Runtime -> Capability authorization/Provider
  0:N -> opaque native correlation references
```

Cardinality is semantic, not a persistence or CRD design. Bindings and
Execution Identity have no independently reconciled desired lifecycle.

## 91. Authority Map

| Question | Authoritative owner | Supporting actor/evidence | Explicit non-owner |
| --- | --- | --- | --- |
| Who owns Agent desired definition? | Agent Definition/Core | compatibility interpreter may translate legacy Agent | Agent Instance, Provider, native Runtime |
| Who owns Instance desired lifecycle? | Agent Instance Control Plane | API/user declares under policy | Runtime Provider/native realization |
| Who resolves effective Runtime Binding? | Agent Instance reconciler/domain Runtime resolver | Runtime registry/package compatibility metadata | Agent Definition status, native Runtime |
| Who observes native Runtime state? | Runtime Provider normalizes evidence | native Runtime/infrastructure supplies raw evidence | Task/Workflow owner |
| Who decides logical routing? | Control Plane | Instance eligibility and policy evidence | Runtime Provider/native Gateway |
| Who decides Capability authorization? | Governance/Capability authorization owner | Binding/policy/permission and request context | discovery, Provider, transport |
| Who determines terminal Task semantics? | Task domain | Runtime/Capability/Provider results are evidence | Provider/native system |
| Who determines Workflow Outcome? | Workflow domain | owned Task states/Outcomes | Task Provider/native system |
| Who determines Capability Outcome? | Capability domain | Provider/transport/remote evidence | Task/Runtime domain |
| Who determines recovery? | Agent Instance reconciler | Provider/native evidence and applicable predicates | Kubernetes restart/Provider alone |
| Who owns native realization mechanics? | Runtime Provider/native system under declared ownership mode | Kubernetes/infrastructure where applicable | Agent Definition/Task/Workflow |
| Who owns native cleanup authority? | declared Binding/Provider lifecycle owner under policy | NativeReference ownership hint/evidence | opaque ID holder by itself |
| Who creates Platform Execution Identity? | Task/Workflow execution owner in Platform | Providers propagate unchanged | native Provider/runtime/tool |
| Who owns Provider compatibility metadata? | domain registry/package publisher/governance | conformance/certification evidence | Core resource instance |

Core owns logical semantics and control; Provider owns translation/adaptation;
native Runtime/system owns native mechanics. None may silently assume another's
authority.

## 92. Canonical End-to-End Execution Trace

```text
1. Business/API request
   -> creates or invokes Task / embedded Workflow execution context

2. Task/Workflow owner
   -> creates Platform Execution Identity
   -> records Definition-facing logical target

3. Control Plane routing
   -> resolves Agent Definition/version/scope
   -> builds authorized eligible Agent Instance set
   -> evaluates eligibility freshness and policy
   -> selects Agent Instance and records selectedInstanceRef

4. Agent Instance effective state
   -> exposes effective Runtime Binding derived from Definition generation
   -> identifies Runtime Provider/package compatibility

5. Runtime Provider
   -> receives unchanged Platform Execution Identity
   -> translates effective Binding to native Runtime behavior
   -> may select a realization only inside selected Instance Binding

6. Native Runtime execution
   -> executes using OpenClaw, Hermes, Native, or future native mechanics
   -> emits optional native run/session/Pod/Gateway IDs as opaque evidence

7. Capability use, when requested
   -> resolves Capability Binding and Capability Definition/operation
   -> evaluates authorization independently of discovery/availability
   -> DENY may terminate before Provider handoff
   -> Capability Provider receives unchanged execution context
   -> invokes REST, MCP, or future transport/native operation
   -> emits optional native invocation IDs as opaque evidence

8. Normalization and semantic conclusion
   -> Runtime Provider produces Runtime-domain Conditions/evidence
   -> Capability domain produces Capability Outcome
   -> Agent Instance reconciler updates Instance Conditions/Recovery
   -> Task owner determines Task Outcome
   -> Workflow owner aggregates node state and Workflow Outcome
```

No native identifier is required for correctness, authorization, routing, or
Platform identity. Provider/native results remain evidence until the owning
domain derives its semantic conclusion.

## 93. Canonical Compatibility Trace

```text
Current Agent object/name/scope                         KEEP
  -> Definition-facing compatibility address           ALIAS
  -> current role/instructions/intent translation       TRANSLATED
  -> Provider-specific runtime/model config refs        TRANSLATED
  -> distinct durable legacy-managed Instance identity  ADDITIVE
  -> Instance effective Binding/status                  DERIVED

Current Task agentRef.name                              KEEP + ALIAS
  -> Definition logical target                          TRANSLATED
  -> eligible Instance resolution                       DERIVED
  -> selectedInstanceRef                                ADDITIVE + DERIVED

Current same-name Service / invoke path                 KEEP
  -> compatibility Runtime Provider behavior            TRANSLATED

Current Task/Workflow phases/results/status             KEEP
  -> richer submission/execution/outcome model          DERIVED

Current Console routes/fields/Agent name                KEEP
  -> Definition + Instance technical projections        ADDITIVE + DERIVED

Provider-specific legacy fields/path                    DEPRECATED_LATER
  only after equivalent refs, adoption, conformance,
  observable migration, bounded rollback, Human Gate
```

`ALIAS`, `DERIVED`, and `TRANSLATED` are presentation shorthand for the exact
Checkpoint D classifications `COMPATIBILITY_ALIAS`, `DERIVED_PROJECTION`, and
`TRANSLATION_LAYER`. No trace step changes current field meaning in place.

## 94. Candidate Stability Classification

Every major area has one primary classification.

| Semantic area | Classification | Basis / remaining boundary |
| --- | --- | --- |
| Agent Definition vs Agent Instance distinction | `CANDIDATE_STABLE` | accepted architecture/spike evidence and compatibility path |
| Definition `1:N` Instance | `CANDIDATE_STABLE` | required for multiple stable logical running identities |
| five-resource logical candidate set | `CANDIDATE_STABLE` | no sixth resource required across A-D |
| Task and Workflow separate first-class resources | `CANDIDATE_STABLE` | current source/tests plus accepted boundary |
| Workflow definition/execution embedded distinction | `CANDIDATE_WITH_EVIDENCE_DEBT` | one resource retained; future multi-run promotion unresolved |
| Capability Definition provider independence | `CANDIDATE_STABLE` | REST/MCP evidence and governance separation |
| Runtime vs Capability domain separation | `CANDIDATE_STABLE` | D32 Option C; distinct lifecycle/auth/outcome semantics |
| embedded Runtime/Capability Binding direction | `CANDIDATE_STABLE` | no independent lifecycle/resource need proven |
| thin Model Binding | `THIN_FOUNDATION` | routing/fallback evidence absent |
| Platform Execution Identity concept | `CANDIDATE_STABLE` | stable Platform-owned propagation boundary accepted |
| execution retry/replay/child identity rules | `CANDIDATE_WITH_EVIDENCE_DEBT` | side effects/in-flight/deferred behavior unresolved |
| bounded logical reference families | `CANDIDATE_STABLE` | typed domain/scope/provenance; representation deferred |
| current Agent compatibility Option B | `CANDIDATE_STABLE` | bounded staged path; no accepted break required |
| identity mapping/backfill mechanics | `CANDIDATE_WITH_EVIDENCE_DEBT` | persistence/restart/delete/recreate evidence absent |
| Core logical routing ownership | `CANDIDATE_STABLE` | Control Plane selects Instance; Provider translates Binding |
| routing eligibility vocabulary/thresholds | `CANDIDATE_WITH_EVIDENCE_DEBT` | freshness inputs/timeout/selection rules unfrozen |
| Provider isolation/extension boundary | `CANDIDATE_STABLE` | opaque refs/internal metadata; no Provider-specific Core |
| native identity opacity and `0:N` correlation | `CANDIDATE_STABLE` | repeated Runtime/Capability/Instance evidence |
| shared Condition structure/four-way truth | `CANDIDATE_STABLE` | boundary accepted; domain vocabularies separate |
| exact Condition names/serialization/reasons | `CANDIDATE_WITH_EVIDENCE_DEBT` | explicitly unfrozen |
| Task submission/execution/Outcome separation | `CANDIDATE_STABLE` | compatible deterministic projection exists logically |
| Task exact state/outcome taxonomy/backfill | `CANDIDATE_WITH_EVIDENCE_DEBT` | API/conformance evidence absent |
| Workflow Outcome ownership/current projection | `CANDIDATE_STABLE` | current behavior preserved; taxonomy unfrozen |
| Capability Outcome ownership boundary | `CANDIDATE_STABLE` | domain distinctions proven; taxonomy not frozen |
| Capability side-effect/deferred/cancel semantics | `CANDIDATE_WITH_EVIDENCE_DEBT` | evidence incomplete |
| restart/replacement is not recovery | `CANDIDATE_STABLE` | positive/negative spike evidence |
| Recovery Assessment placement/semantic predicate model | `CANDIDATE_STABLE` | Agent Instance-owned and four-way; threshold vocabulary debt remains |
| Recovery predicate applicability/thresholds | `CANDIDATE_WITH_EVIDENCE_DEBT` | ownership profiles, freshness, state/in-flight evidence incomplete |
| Provider registries and Runtime Package as internal metadata | `CANDIDATE_STABLE` | public resource/service not justified |
| Runtime/Capability Provider interfaces | `CANDIDATE_STABLE` | distinct replaceable translation boundaries |
| Runtime/Capability Contract conformance/freeze | `BLOCKED` | freeze gate and combined unchanged-consumer evidence incomplete |
| Workspace, State/Memory, Knowledge, Policy, Permission, Human Gate | `THIN_FOUNDATION` | references/interaction only |
| State portability | `DEFERRED` | unsupported and not assumed |
| multi-tenancy/governance lifecycle | `DEFERRED` | v0.4 direction/evidence absent |
| Model routing/fallback | `DEFERRED` | requires dedicated evidence |
| WorkflowExecution/universal Execution resources | `DEFERRED` | rejected for v0.2; promotion trigger not met |

## 95. Claim-Scoped Evidence Debt

| Debt | Classification | Scope blocked | Does not block |
| --- | --- | --- | --- |
| Runtime Contract unchanged-consumer conformance | `BLOCKED` for freeze | Runtime Contract freeze, broad Provider certification, stable implementation claim | Core Candidate convergence |
| `G-S5-RUNTIME-FREEZE-01` | `BLOCKED` / FAIL unchanged | Runtime Contract freeze | logical schema/prototype |
| ED-S5-001 Hermes | `BLOCKED` for Hermes certification | Hermes Provider/package certification and readiness | Core Candidate, Native/OpenClaw schema path |
| OpenClaw/Native Provider conformance | `CANDIDATE_WITH_EVIDENCE_DEBT` | certification/production claims for each combination | provider-neutral schema |
| Capability deferred execution | `CANDIDATE_WITH_EVIDENCE_DEBT` | deferred durability/observation profile | inline Capability boundary |
| side-effecting Capability | `CANDIDATE_WITH_EVIDENCE_DEBT` | retry/idempotency/safe replay claims | read-only/idempotent profile candidate |
| in-flight cancellation/retry/recovery | `CANDIDATE_WITH_EVIDENCE_DEBT` | cancellation/rebind/replay production behavior | identity/routing ownership |
| Recovery thresholds/applicability | `CANDIDATE_WITH_EVIDENCE_DEBT` | vocabulary freeze and production recovery claims | recovery placement/invariant |
| mixed-version implementation | `CANDIDATE_WITH_EVIDENCE_DEBT` | migration/cutover readiness | bounded logical compatibility path |
| identity mapping/backfill | `CANDIDATE_WITH_EVIDENCE_DEBT` | migration/API approval | Definition/Instance distinction |
| translation losslessness | `CANDIDATE_WITH_EVIDENCE_DEBT` | legacy workload adoption/fallback | target ownership boundary |
| Console old-client tolerance | `CANDIDATE_WITH_EVIDENCE_DEBT` | additive Console implementation | read-only projection strategy |
| third-party MCP | `CANDIDATE_WITH_EVIDENCE_DEBT` | that Provider certification/broad MCP claim | Capability Provider boundary |
| out-of-process Providers | `DEFERRED` unless claimed | mandatory isolation/deployment claim | serializable interface direction |
| State portability | `DEFERRED` | portability/continuity claims | thin State reference |
| multi-tenancy | `DEFERRED` | tenant isolation/enterprise production | tenant-ready separation principles |
| Model routing/fallback | `DEFERRED` | Model Contract/routing schema | thin Model Binding |
| S5-ARCH-001/002/003 main-tree gap | `CANDIDATE_WITH_EVIDENCE_DEBT` | durable provenance completeness | Candidate based on durable ARCH-004/spikes/current source |

No debt is silently converted into evidence. Debt classifications apply only
to the named Contract profile, Provider combination, migration, or product
claim.

## 96. Multi-Runtime Mapping

| Core semantic | OpenClaw Provider | Hermes Provider | Native Runtime Provider |
| --- | --- | --- | --- |
| Agent Definition | unchanged | unchanged | unchanged/current Agent compatibility input |
| Agent Instance | Platform identity independent of OpenClaw runs/Gateway | Platform identity independent of Hermes session/request | Platform identity independent of Deployment/Pod/Service |
| Runtime Binding | Provider/package/config refs in extension boundary | Provider/package/config refs in extension boundary | translated current type/image/env/package refs |
| logical routing | Control Plane selects Instance | Control Plane selects Instance | Control Plane selects Instance/legacy projection |
| native selection | Provider selects within Binding | Provider selects within Binding | Provider uses current/native realizations within Binding |
| Runtime Conditions | Provider-normalized domain semantics | Provider-normalized domain semantics | Provider-normalized readiness/invoke evidence |
| execution identity | propagated unchanged | propagated unchanged | propagated unchanged once conformance exists |
| native refs | OpenClaw run/Gateway/session IDs opaque | Hermes request/session/process IDs opaque | Pod/Service/process/request IDs opaque |
| recovery | Instance semantic predicates | Instance semantic predicates; ED-S5-001 applies to certification | Instance semantic predicates; restart alone insufficient |
| certification | combination-scoped evidence required | `EXPERIMENTAL / NOT CURRENTLY CERTIFIABLE` | conformance/certification evidence required |

Core resources and fields do not change by Runtime family. Provider/package
certification can advance independently without altering logical identity,
routing, Outcome, or recovery ownership.

### 96.1 Hermes disposition

HERMES: **EXPERIMENTAL / NOT CURRENTLY CERTIFIABLE**
ED-S5-001: **OPEN**

ED-S5-001 does not block Core Schema Candidate v0 convergence. It blocks only
applicable Hermes Provider/package certification, production readiness, and
Golden Demo claims that present Hermes as certified. No Hermes-specific Core
field, taxonomy, workaround, or relaxed invariant is introduced.

## 97. Golden Demo Traceability

```text
Digital Employee / business role (product projection)
  -> Agent Definition (role/purpose + governed desired intent)
    -> multiple Agent Instances (stable logical identities)
      -> Runtime Binding / Provider selection
         |- OpenClaw Provider [certification status displayed]
         |- Hermes Provider [EXPERIMENTAL / NOT CERTIFIABLE]
         `- Native Runtime Provider [certification status displayed]
      -> Task / Workflow with Platform Execution Identity
        -> logical selected Instance and Runtime evidence
        -> Capability Binding + authorization
           |- REST Capability Provider
           `- MCP Capability Provider
        -> Capability Outcome -> Task Outcome -> Workflow Outcome
  -> business result projection
```

The Demo can show one Definition with multiple Instances and different Runtime
Providers without changing Core semantics. Operator details progressively
disclose Binding, eligibility, Conditions, recovery, and native correlations.
Business users may continue seeing an Agent/Digital Employee projection.

Demo acceptance requirements include honest Provider/certification badges,
stable execution correlation, a denied Capability path before Provider
handoff, success/failure Outcomes, realization replacement with semantic
recovery assessment, and current compatibility behavior. Hermes may appear only
as experimental with ED-S5-001 disclosed; the Demo must not fake certification,
state portability, or universal rollback.

## 98. Implementation Readiness Map

This is a handoff classification, not authorization.

| Candidate area | Readiness | Rationale / next evidence |
| --- | --- | --- |
| five-resource logical model documentation | `READY_FOR_SCHEMA_PROTOTYPE` | Candidate cards/relationships/authority converged |
| embedded Runtime/Capability Bindings | `READY_FOR_SCHEMA_PROTOTYPE` | representation and compatibility algorithms remain prototype work |
| thin Model/Foundation refs | `DEFERRED` beyond thin prototype | do not elaborate without evidence |
| Platform Execution Identity value/propagation interface | `READY_FOR_SCHEMA_PROTOTYPE` | retry/backfill and combined path need conformance |
| typed logical/native reference structures | `READY_FOR_SCHEMA_PROTOTYPE` | API representation unresolved |
| current Agent compatibility interpreter | `READY_FOR_CONFORMANCE_TEST` after prototype plan | field mapping and identity safety matrix defined |
| Agent Definition/Instance identity mapping | `READY_FOR_CONFORMANCE_TEST` after durable prototype | restart/delete/recreate/adoption evidence required |
| Task/Workflow compatibility projections | `READY_FOR_CONFORMANCE_TEST` | current fixtures/tests provide baseline |
| Runtime Provider interface/Binding translation | `READY_FOR_CONFORMANCE_TEST` | Contract freeze still blocked |
| Capability Provider interface/Binding authorization | `READY_FOR_CONFORMANCE_TEST` | inline profiles first; side effects/deferred debt |
| shared Condition structure/four-way truth | `READY_FOR_SCHEMA_PROTOTYPE` | exact vocabulary/serialization unfrozen |
| domain Outcome structures | `READY_FOR_SCHEMA_PROTOTYPE` | taxonomies and projections require conformance |
| Recovery Assessment | `READY_FOR_CONFORMANCE_TEST` | negative/positive spike base exists; thresholds/profiles needed |
| mixed-version/rollback mechanics | `READY_FOR_CONFORMANCE_TEST` after representation prototype | no production claim until evidence |
| Console derived projection | `READY_FOR_CONFORMANCE_TEST` after API schema plan | old-client tolerance and no second source of truth |
| Native/OpenClaw Provider production use | `BLOCKED_FOR_PRODUCTION` | certification/readiness gates incomplete |
| Hermes Provider production use | `BLOCKED_FOR_PRODUCTION` | ED-S5-001 and Runtime freeze/conformance |
| Runtime/Capability stable Contract implementation | `BLOCKED_FOR_PRODUCTION` | freeze gates not passed |
| State portability, Model routing, multi-tenancy | `DEFERRED` | separate architecture/evidence required |

## 99. Bounded Conformance Matrix

Evidence types are independent:

- **CONTRACT CONFORMANCE** verifies unchanged semantic consumers and logical
  rules for a versioned Candidate/Contract.
- **PROVIDER CERTIFICATION** verifies one Contract + Provider + package + mode +
  platform combination, including declared optional profiles.
- **PRODUCT DEMO ACCEPTANCE** verifies honest end-to-end user/operator behavior
  and presentation; it cannot substitute for either technical gate.

| Area | Contract conformance evidence | Provider certification evidence | Product Demo acceptance |
| --- | --- | --- | --- |
| current Agent manifests | unchanged parse/validation/behavior; exact translation report | legacy Native translator/package combination | existing Agents run and display unchanged |
| Agent compatibility projection | deterministic field map, no secret/Core leakage, one authority | Provider config refs resolve equivalently | Definition/Instance detail projects under same business Agent |
| Definition/Instance identity | distinct durable IDs across restart/update/delete/recreate cases | realization changes preserve Instance | multiple Instances visible with stable identity |
| multiple Instances | `1:N`, target set, eligibility/selection invariants | Provider supports declared realization/profile behavior | route work to separate Instances without native IDs |
| Task targeting/selected Instance | legacy alias + Definition/explicit auth target + fail-closed mismatch | Runtime handoff uses already-selected Instance | selected Instance and reason visible |
| Workflow compatibility | current DAG/Task/result/skip/aggregate tests unchanged | each node Provider combination declared | current workflow and mixed Provider path render correctly |
| Execution Identity | stable creation/backfill/propagation and conflict/missing failures | unchanged round trip through Provider/native transport | one correlation shown across Task/Runtime/Capability |
| Runtime Binding translation | current inputs -> desired/effective/provenance, opaque extensions | package/config/mode compatibility and failure cases | switch eligible Providers without Core field changes |
| OpenClaw Provider | generic Runtime consumer unchanged | OpenClaw package/mode live certification suite | honest badge and success/failure/recovery path |
| Native Runtime Provider | generic Runtime consumer unchanged | current/native package and compatibility differential tests | legacy and adopted Native paths behave coherently |
| Hermes Provider | generic schema unchanged; no Hermes fields | blocked until ED-S5-001 and freeze prerequisites pass | experimental only; no certified claim |
| Capability Binding | identity/version/operation/auth decision invariants | Provider maps authorized Binding only | governed Capability shown separately from discovery |
| REST Capability | unchanged Capability consumer/output semantics | REST Provider live/profile tests | successful/failed REST operation correlated |
| MCP Capability | unchanged Capability consumer/output semantics | third-party MCP and declared profile tests | MCP operation honestly marked certification scope |
| authorization denial | deny before handoff, zero native ref valid, audit evidence | Provider must not be called | denied path visibly not transport failure |
| Conditions | four-way truth, generation/time/freshness/domain separation | native-to-domain normalization per Provider | stale/unknown not shown as healthy |
| Outcomes | domain ownership, evidence-to-semantic projection, current status map | native result interpretation per Provider | Task/Workflow/Capability results remain distinguishable |
| Recovery Assessment | applicable predicate/unknown/false/NA algorithm | ownership-mode realization/state evidence | restart-only negative and semantic recovery positive paths |
| mixed compatibility mode | one desired authority, conflict rejection, version/fallback audit | each mixed Provider combination certified independently | legacy/adopted nodes coexist without hidden behavior drift |
| rollback | reversible checkpoint, lossless reverse projection, in-flight exclusion | Provider cleanup/ownership/fallback safety | rollback scope and non-guarantees displayed |
| Console compatibility | current routes/fields/phases and old-client tests | not a Provider gate | current UX preserved; added detail is derived/read-only |

## 100. Freeze and Acceptance Readiness Gates

No gate passes merely because another gate passes.

| Gate | Required evidence/decision | Current state |
| --- | --- | --- |
| Core Schema Candidate Gate | Human acceptance of five resources, embedded/value boundaries, relationships, authority, compatibility, stability/readiness classifications | **PENDING — this Checkpoint E recommendation** |
| Core Schema Freeze Gate | normative field/serialization/version/compatibility policy, representation decision, conversion and conformance evidence, accepted governing decision | **NOT_READY / NOT_FROZEN** |
| Runtime Contract Freeze Gate | versioned Runtime Contract, unchanged-consumer conformance, Binding/Provider/package compatibility, Conditions/outcomes/recovery profiles, `G-S5-RUNTIME-FREEZE-01` pass | **BLOCKED / gate FAIL unchanged** |
| Capability Contract Freeze Gate | versioned Capability semantics, auth/outcome/input-output compatibility, required inline/deferred/side-effect profiles and conformance | **BLOCKED for broad freeze; evidence debt open** |
| Provider Certification Gate | frozen/applicable Contract profile plus combination-specific Provider/package/mode/platform live evidence | **NOT_READY; Hermes BLOCKED by ED-S5-001** |
| Production Readiness Gate | approved implementation/migration, security/operations/upgrade/rollback, certified combinations, compatibility and SLO evidence | **BLOCKED_FOR_PRODUCTION** |
| Golden Demo Acceptance Gate | honest end-to-end scenario, current compatibility, multiple Instances/Providers, execution/capability correlation, failure/recovery, accurate certification labels | **NOT_RUN / independent** |

The Human Final Schema Candidate Gate may accept Candidate v0 without freezing
schema or Contracts. Freeze requires separate normative artifacts, evidence,
and Human decisions.

## 101. ADR Impact Map

No ADR is edited here.

| ADR | Future impact | Candidate semantics to address | Timing |
| --- | --- | --- | --- |
| ADR-0003 Operator/reconciliation responsibilities | `CLARIFY_LATER` | separate Agent infrastructure, Agent Instance/effective Binding, Runtime Provider, and Task/Workflow reconciliation ownership; acknowledge existing controller drift | after Candidate acceptance, before implementation changes that depend on boundary |
| ADR-0004 pluggable Runtime architecture | `AMEND_LATER` | evolve `runtimeClass -> resolver -> adapter` prose toward Definition intent -> Instance effective Runtime Binding -> domain registry -> Runtime Provider -> opaque realization; preserve pluggability/ownership | before Runtime Provider production implementation/freeze |
| ADR-0005 Model abstractions | `CLARIFY_LATER` | distinguish thin Model Binding from current embedded Provider fields and runtime-local ModelProvider; keep routing/gateway/fallback deferred | after Model evidence, before Model schema implementation |

ADR-0001 Kubernetes source of truth, ADR-0002 declarative Agent principles, and
ADR-0006 read-only Console remain compatible. Any changed accepted decision
requires separately authorized ADR work and Human ownership.

## 102. Recommended Engineering Sequence

After—and only after—the Human Final Schema Candidate Gate:

1. **Candidate integration:** publish/locate the accepted Candidate and decision
   record; retain explicit non-freeze status and Contract index placeholders.
2. **Representation/prototype plan (G1/G2 as applicable):** choose bounded
   non-production representations for identity, references, Bindings,
   Conditions, Outcomes, compatibility mode, and provenance; decide which
   public API/CRD questions require architecture approval.
3. **Conformance harness:** implement implementation-neutral fixtures and
   unchanged-consumer tests before multiple Providers depend on implicit APIs.
4. **Compatibility interpreter/projection prototype:** prove lossless current
   Agent mapping, distinct durable Instance identity, current Task/Workflow
   projections, secret isolation, and restart/delete/recreate behavior.
5. **Agent Definition/Instance prototype:** exercise `1:N`, eligibility,
   selected Instance, generation provenance, and bounded native evidence behind
   non-production/approved interfaces.
6. **Runtime Provider conformance:** Native first as current differential
   baseline, OpenClaw as external validation, Hermes only within experimental
   scope until ED-S5-001 closes; keep certification combination-specific.
7. **Capability Provider conformance:** explicit Capability Definition/Binding,
   REST then MCP, deny-before-handoff, Outcome ownership, inline safe profiles
   before deferred/side-effect profiles.
8. **Recovery and mixed-mode evidence:** negative restart-only, positive
   semantic recovery, stale/unknown, ownership-safe cleanup, legacy/adopted
   Workflow, bounded rollback, and no in-flight replay claim.
9. **Console projection prototype:** preserve current API/UX and add read-only
   Definition/Instance/execution/certification details with old-client tests.
10. **Golden Demo integration:** execute honest multi-Instance/multi-Runtime/
    REST-MCP scenario with certification/debt labels and current compatibility.
11. **ADR work:** clarify/amend ADR-0003/0004 and later ADR-0005 only under
    separate authorization before affected production boundaries.
12. **Freeze/readiness review:** independently evaluate Core schema, Runtime,
    Capability, Provider certification, production, and Demo gates; do not merge
    them into one pass/fail decision.

No step in this sequence is authorized by Checkpoint E itself.

## 103. Human Decisions Required — Checkpoint E

All decisions remain **PENDING** until the Human Final Schema Candidate Gate.

### E01 — Final five-resource logical Candidate

**Recommendation:** accept Agent Definition, Agent Instance, Task, Workflow,
and Capability Definition as the complete v0.2 first-class logical Candidate;
no CRD count is implied.
**Decision:** PENDING.

### E02 — Embedded Binding disposition

**Recommendation:** accept Runtime and Capability Bindings as domain-specific
embedded structures and Model Binding as thin embedded foundation; no Binding
resource/CRD.
**Decision:** PENDING.

### E03 — Platform Execution Identity

**Recommendation:** accept embedded Platform-created stable identity propagated
unchanged end to end, with optional `0:N` native correlations and no universal
Execution resource.
**Decision:** PENDING.

### E04 — Relationship map

**Recommendation:** accept Section 90 cardinalities and typed relationships as
the authoritative Candidate map, independent of persistence representation.
**Decision:** PENDING.

### E05 — Authority map

**Recommendation:** accept Section 91 separation of Core semantic/control,
Provider translation, and native mechanics/ownership.
**Decision:** PENDING.

### E06 — Reference model

**Recommendation:** accept bounded typed logical families and structurally
separate opaque NativeReference evidence; serialization remains unfrozen.
**Decision:** PENDING.

### E07 — Condition boundary

**Recommendation:** accept shared structure and four-way truth with Runtime and
Instance domain ownership; names/reasons/serialization remain evidence debt.
**Decision:** PENDING.

### E08 — Outcome boundary

**Recommendation:** accept separate Task, Workflow, and Capability Outcomes;
Runtime interaction remains Runtime-specific and Provider results are evidence.
**Decision:** PENDING.

### E09 — Recovery Assessment

**Recommendation:** accept Instance-owned embedded semantic predicate model;
restart/replacement/state portability never imply recovery.
**Decision:** PENDING.

### E10 — Compatibility and migration strategy

**Recommendation:** accept staged Option B, current semantic preservation,
distinct durable Instance identity, additive/derived projections, and explicit
mapping/adoption/deprecation gates.
**Decision:** PENDING.

### E11 — Mixed-version authority and rollback

**Recommendation:** accept exactly one desired authority, fail-closed conflicts,
observable mode/translation/fallback, and bounded—not universal—rollback.
**Decision:** PENDING.

### E12 — Provider extension boundary

**Recommendation:** accept opaque configuration/extension refs, internal domain
metadata, bounded evidence, and safe diagnostics; no Provider-family Core
fields.
**Decision:** PENDING.

### E13 — Hermes debt scope

**Recommendation:** retain Hermes `EXPERIMENTAL / NOT CURRENTLY CERTIFIABLE` and
ED-S5-001 OPEN; debt blocks Hermes combination claims only, not Candidate v0.
**Decision:** PENDING.

### E14 — Candidate stability classification

**Recommendation:** accept Section 94 exact `CANDIDATE_STABLE`,
`CANDIDATE_WITH_EVIDENCE_DEBT`, `THIN_FOUNDATION`, `DEFERRED`, and `BLOCKED`
classifications.
**Decision:** PENDING.

### E15 — Implementation readiness map

**Recommendation:** accept Section 98 prototype/conformance/production/deferred
handoff classifications as non-authorization.
**Decision:** PENDING.

### E16 — Conformance matrix

**Recommendation:** accept Section 99 and keep Contract conformance, Provider
certification, and Product Demo acceptance independent.
**Decision:** PENDING.

### E17 — Freeze readiness gates

**Recommendation:** accept Section 100 independent gates; none is frozen or
production-ready by Candidate acceptance.
**Decision:** PENDING.

### E18 — Golden Demo traceability

**Recommendation:** accept Section 97 as the product trace; require honest
Provider/certification status and no fake Hermes/state/rollback claims.
**Decision:** PENDING.

### E19 — ADR impact

**Recommendation:** record ADR-0003 `CLARIFY_LATER`, ADR-0004 `AMEND_LATER`, and
ADR-0005 `CLARIFY_LATER`; perform no edits until separately authorized.
**Decision:** PENDING.

### E20 — Next engineering sequence

**Recommendation:** accept Section 102 sequencing after Final Gate, with
representation decisions and conformance before production Provider/API work.
**Decision:** PENDING.

## 104. Final Contradiction Review

| Authority/evidence | Review result |
| --- | --- |
| S5-ARCH-004 accepted boundary | aligned: five resources, embedded Bindings, embedded Execution Identity, domain ownership, internal metadata |
| S5-SPIKE-003 Capability evidence | aligned: provider-independent identity, REST/MCP separation, authorization before Provider, domain Outcome |
| S5-SPIKE-004 Agent Instance evidence | aligned: stable logical identity, platform routing, realization replacement, semantic recovery |
| Runtime Provider Architecture | aligned: Binding -> registry metadata -> Provider -> opaque native realization; Contract not frozen |
| current Agent API/controller | compatible through staged Option B; direct Runtime/Model/replica behavior preserved as legacy input/path |
| current Task behavior | preserved; richer identity/selection/state/outcome is additive/derived |
| current Workflow behavior | preserved; no split or engine redesign |
| current Console | preserved read-only projection and machine values; additive detail gated |
| D32 Option C | aligned: only identity/correlation/condition shape primitives shared; interactions/outcomes remain domain-specific |
| accepted compatibility constraints | aligned: no rename/reinterpretation, one authority, explicit mapping, bounded rollback, evidence-based versioning |

Final challenges:

- Candidate convergence does not require a sixth resource or universal
  Execution/Status/Outcome.
- Workflow can remain one resource with explicit evolution debt.
- Provider-specific behavior fits opaque extensions and certification profiles;
  no Core discriminator is required.
- Hermes debt stays combination-scoped and changes no Core field.
- current Task/Workflow compatibility is bounded without immediate breaking
  changes.
- unresolved evidence remains classified as debt, blocked, thin, or deferred;
  no unsupported claim is promoted to Candidate-stable.

**CONTRADICTION: NONE.** No accepted boundary change is proposed.

## 105. Optional Machine-Readable Companion

`S5-ARCH-005-SCHEMA-CANDIDATE-V0.yaml` was deliberately **NOT CREATED**.

At this stage a YAML structure would imply field names, nesting, serialization,
requiredness, and type precision beyond the accepted implementation-neutral
Candidate. The pseudo-schemas and cards in this artifact are sufficient for
prototype planning while clearly retaining non-normative status.

## 106. Checkpoint E State

LIFECYCLE: **REVIEW**
AUTHORIZATION: **AUTHORIZED**
STATUS: **PASS**
CHECKPOINT: **E — FINAL_SCHEMA_CANDIDATE_CONVERGENCE**
RESULT: **CORE_SCHEMA_CANDIDATE_V0_RECOMMENDED**

CANDIDATE: **v0.2 CORE SCHEMA CANDIDATE v0**
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
OPTIONAL_COMPANION: **NOT_CREATED / FALSE_PRECISION_AVOIDED**
NEXT_ACTION: **WAIT_FOR_HUMAN_DECISION**
NEXT_GATE: **Human Final Schema Candidate Gate**

S5-ARCH-005 remains open. This Checkpoint does not close the session or begin
implementation.

# Checkpoint F — Session Finalization

## 107. Human Final Schema Candidate Gate

HUMAN DECISION: **PASS WITH CONSTRAINTS**

| State | Finalization record |
| --- | --- |
| Human Final Schema Candidate Gate | `RECORDED / PASS_WITH_CONSTRAINTS` |
| v0.2 Core Schema Candidate v0 | `ACCEPTED` |
| Candidate character | implementation-neutral, representation-neutral, Provider-neutral, compatibility-aware |
| Five logical resource candidates | `ACCEPTED` |
| Five CRDs | `NOT_APPROVED / UNDECIDED` |
| Schema/Contract freeze | `NO` |
| API/CRD/implementation authorization | `NOT_GRANTED` |
| Provider certification | `NOT_GRANTED` |
| Production readiness | `NOT_GRANTED` |
| Golden Demo acceptance | `NOT_GRANTED` |

Candidate acceptance does not convert Candidate stability into frozen
stability. Serialization, API representation, persistence, conversion,
implementation, certification, readiness, and release decisions remain under
their independent Human Gates.

## 108. Accepted Candidate Boundary and Preserved Constraints

### 108.1 First-class logical resources

1. Agent Definition;
2. Agent Instance;
3. Task;
4. Workflow;
5. Capability Definition.

No sixth resource is added. `WorkflowExecution`, universal `Execution`,
universal `Status/Outcome/Recovery`, Binding resources, Provider resources, and
Registry resources remain outside the Candidate.

### 108.2 Embedded, value, interface, metadata, and thin boundaries

| Boundary | Accepted disposition |
| --- | --- |
| Runtime Binding | `DOMAIN_SPECIFIC_EMBEDDED_BINDING` |
| Capability Binding | `DOMAIN_SPECIFIC_EMBEDDED_BINDING` |
| Model Binding | `THIN_EMBEDDED_FOUNDATION` |
| Platform Execution Identity | `CORE_VALUE_OBJECT / EMBEDDED_VALUE` |
| Runtime Provider Registry | `INTERNAL_METADATA` |
| Capability Provider Registry | `INTERNAL_METADATA` |
| Runtime Package | `INTERNAL_METADATA` |
| Runtime Provider | `PROVIDER_INTERFACE` |
| Capability Provider | `PROVIDER_INTERFACE` |
| Workspace/State/Knowledge/Policy/Permission/Human Gate | `THIN_FOUNDATION` |

### 108.3 Identity and targeting constraints

- Agent Definition owns authoritative desired logical definition.
- Agent Instance owns a distinct stable Platform running identity and exactly
  one Definition reference.
- Definition-to-Instance is `1:N`; Instance-to-native realization is `1:N`
  temporal and `0:N` active where supported.
- current Agent name/scope remains the Definition-facing compatibility address;
  a compatibility Instance receives a separately minted durable identity.
- Task retains a Definition-facing logical target; selected Instance is
  Control Plane-resolved/effective routing evidence.
- Definition identity, Instance identity, Kubernetes UID, replica, Pod,
  container, Gateway, Hermes/OpenClaw session/run, and all native execution IDs
  remain distinct.

### 108.4 Domain ownership constraints

- Runtime and Agent Instance Conditions remain separately owned.
- Task, Workflow, and Capability Outcomes remain separately owned.
- Recovery Assessment remains Agent Instance-owned and embedded.
- four-way truth is accepted as semantic boundary; exact vocabulary and
  serialization are not frozen.
- Provider/native results and IDs are evidence, never automatic Platform
  semantic conclusions or identity.
- discovery is not authorization; denial may terminate before Provider handoff.
- restart, replacement, or process running does not establish semantic recovery.
- Provider-family/transport fields remain outside stable Core.

## 109. E01-E20 Human Decision Ledger

Each disposition preserves the exact subject in Section 103 and retains linked
debt. `ACCEPTED_AS_CANDIDATE` means logical Candidate acceptance only.

| ID | Subject | Human disposition | Preserved constraint/evidence debt |
| --- | --- | --- | --- |
| E01 | final five-resource logical Candidate | `ACCEPTED_AS_CANDIDATE` | representation and CRD count undecided |
| E02 | embedded Binding disposition | `ACCEPTED_AS_CANDIDATE` | Runtime/Capability embedded; Model remains thin; no Binding CRDs |
| E03 | Platform Execution Identity | `ACCEPTED_WITH_EVIDENCE_DEBT` | propagation concept accepted; retry/backfill/combined conformance unfrozen |
| E04 | relationship map | `ACCEPTED_AS_CANDIDATE` | logical cardinalities accepted; persistence/reference serialization undecided |
| E05 | authority map | `ACCEPTED_AS_CANDIDATE` | Core/Provider/native ownership fixed as Candidate boundary |
| E06 | reference model | `ACCEPTED_WITH_EVIDENCE_DEBT` | typed/opaque separation accepted; field names, resolution errors, serialization unfrozen |
| E07 | Condition boundary | `ACCEPTED_WITH_EVIDENCE_DEBT` | shared structure/four-way truth accepted; concepts/reasons/serialization not frozen |
| E08 | Outcome boundary | `ACCEPTED_WITH_EVIDENCE_DEBT` | domain ownership accepted; taxonomies, side effects, deferred behavior unfrozen |
| E09 | Recovery Assessment | `ACCEPTED_WITH_EVIDENCE_DEBT` | placement/predicate semantics accepted; applicability, thresholds, profiles unresolved |
| E10 | compatibility and migration strategy | `ACCEPTED_WITH_EVIDENCE_DEBT` | staged Option B accepted; mapping, backfill, translation and implementation unproven |
| E11 | mixed-version authority and rollback | `ACCEPTED_WITH_EVIDENCE_DEBT` | one desired authority/bounded rollback accepted; mixed-mode and in-flight evidence absent |
| E12 | Provider extension boundary | `ACCEPTED_AS_CANDIDATE` | opaque refs/internal metadata/bounded evidence only; no Provider-family Core fields |
| E13 | Hermes debt scope | `BLOCKED` | Hermes certification/readiness blocked by ED-S5-001; Core Candidate unaffected |
| E14 | Candidate stability classification | `ACCEPTED_AS_CANDIDATE` | exact stable/debt/thin/deferred/blocked classes retained; none means frozen |
| E15 | implementation readiness map | `ACCEPTED_WITH_EVIDENCE_DEBT` | prototype/conformance handoff accepted; no implementation or production authorization |
| E16 | conformance matrix | `ACCEPTED_WITH_EVIDENCE_DEBT` | evidence plan accepted; conformance/certification/demo tests not completed |
| E17 | freeze readiness gates | `BLOCKED` | Core/Runtime/Capability freeze and production gates not ready; Candidate Gate alone accepted |
| E18 | Golden Demo traceability | `ACCEPTED_WITH_EVIDENCE_DEBT` | product trace accepted; Demo not run/accepted and certification labels mandatory |
| E19 | ADR impact | `DEFERRED` | ADR-0003/0004/0005 work occurs only in separately authorized sessions |
| E20 | next engineering sequence | `ACCEPTED_AS_CANDIDATE` | sequencing recommendation accepted; no step authorized by this session |

No disposition is ambiguous. The ledger does not approve serialization,
implementation, certification, production, or merge.

## 110. Candidate Classification Verification

The exact Section 94 classifications remain authoritative:

- `CANDIDATE_STABLE` denotes an accepted Candidate semantic boundary only;
- `CANDIDATE_WITH_EVIDENCE_DEBT` retains named conformance, vocabulary,
  migration, or Provider debt;
- `THIN_FOUNDATION` prevents unauthorized lifecycle/schema expansion;
- `DEFERRED` remains outside v0.2 supported claims;
- `BLOCKED` cannot advance until its named gate/evidence changes.

No area is relabeled as frozen, implemented, certified, production-ready, or
Demo-accepted. Claim-scoped debt in Sections 64, 84, 95, and 99 remains open.

## 111. Independent Freeze, Certification, and Readiness State

| Gate/state | Finalization status |
| --- | --- |
| Core Schema Candidate | `ACCEPTED` |
| Core Schema Freeze | `NO` |
| Runtime Contract Freeze | `NO` |
| Capability Contract Freeze | `NO` |
| Runtime Freeze Gate `G-S5-RUNTIME-FREEZE-01` | `FAIL / UNCHANGED` |
| Provider Certification | `NOT_GRANTED` |
| Production Readiness | `NOT_GRANTED` |
| Golden Demo Acceptance | `NOT_GRANTED` |
| Hermes | `EXPERIMENTAL / NOT CURRENTLY CERTIFIABLE` |
| ED-S5-001 | `OPEN` |

ED-S5-001 blocks only applicable Hermes Provider/package certification and
readiness claims. It does not block the accepted Core Schema Candidate and does
not justify Hermes-specific Core fields.

## 112. ADR Impact Finalization

| ADR | Preserved impact | Change in this session |
| --- | --- | --- |
| ADR-0003 | `CLARIFY_LATER` | none |
| ADR-0004 | `AMEND_LATER` | none |
| ADR-0005 | `CLARIFY_LATER` | none |

ADR work remains Human-owned and separately authorized. `ADR_CHANGE: 0`.

## 113. Unresolved Evidence Debt at Finalization

All previously recorded debt remains. Principal open categories are:

- normative schema field names/types/requiredness/defaults/serialization and
  API/persistence/CRD representation;
- Runtime and Capability Contract conformance/freeze;
- durable Agent-to-Definition/Instance identity mapping, legacy Task/Workflow
  execution identity backfill, deletion/recreation/adoption, and lossless
  conversion;
- routing eligibility inputs/freshness, explicit targeting authorization,
  deterministic selection, rerouting, and in-flight behavior;
- exact Condition/Outcome/Recovery vocabularies, thresholds, transition rules,
  side-effect/idempotency, deferred/cancel behavior, and stateful/external
  profiles;
- mixed-version implementation, bounded fallback/rollback, cleanup ownership,
  secret isolation, and Console old-client tolerance;
- Native/OpenClaw/REST/MCP Provider conformance and combination-specific
  certification, third-party MCP, and out-of-process Provider evidence;
- Hermes ED-S5-001 and certification/readiness;
- State portability, Model routing/fallback, multi-tenancy, and broader
  governance remain deferred.

Evidence debt is claim-scoped and does not reopen the accepted Candidate
boundary. It blocks only the applicable freeze, migration, certification,
production, Provider, or product claim.

## 114. Final Consistency and Provenance Record

The finalized Candidate remains derived from:

1. validated `origin/main` baseline
   `c8e1768d8cbd014b7eb243531a40bbecb7895586`;
2. durable S5-ARCH-004 accepted Core Contract Boundary;
3. durable S5-SPIKE-003 Capability evidence;
4. durable S5-SPIKE-004 Agent Instance/routing evidence;
5. accepted ADRs interpreted with implementation-status separation;
6. current Agent/Task/Workflow CRDs, controllers, Runtime, Console, tests, and
   examples;
7. Human Checkpoint A-D Gates and Human Final Schema Candidate Gate.

The S5-ARCH-001/002/003 main-tree traceability gap remains recorded debt. No
historical artifact is reconstructed and no pending/non-durable decision is
promoted over S5-ARCH-004. Checkpoints A-E history remains in this artifact.

Consistency result:

- first-class Candidate count remains five;
- no Provider/native fields enter Core;
- no current API field is silently reinterpreted;
- no universal execution/status/outcome/recovery object is introduced;
- no schema/Contract is frozen;
- no representation, implementation, certification, readiness, or merge is
  authorized;
- no contradiction with the accepted A-E record was found.

## 115. Next Integration Recommendation

Recommended next session, not started here:

SESSION
ID: S5-REL-004
TITLE: S5-ARCH-005 Core Schema Candidate Integration

Purpose:

- pre-merge verification of PR #42;
- exact-head Human Merge Gate;
- merge into main;
- post-merge source-of-truth validation;
- durable Core Schema Candidate baseline verification.

PR #42 remains unmerged. No S5-REL-004 artifact or execution is created by
this finalization.

## 116. Session Finalization State

HUMAN_FINAL_SCHEMA_CANDIDATE_GATE: **RECORDED / PASS_WITH_CONSTRAINTS**
CORE_SCHEMA_CANDIDATE: **ACCEPTED**
E01_E20: **DISPOSITIONED_WITHOUT_OVERCLAIM**
CANDIDATE_SCOPE: **UNCHANGED**
EVIDENCE_DEBT: **PRESERVED**

LIFECYCLE: **CLOSING**
AUTHORIZATION: **AUTHORIZED**
STATUS: **PASS**
CHECKPOINT: **F — SESSION_FINALIZATION**
RESULT: **READY_TO_CLOSE**

CORE_SCHEMA_FREEZE: **NO**
RUNTIME_CONTRACT_FREEZE: **NO**
CAPABILITY_CONTRACT_FREEZE: **NO**
PROVIDER_CERTIFICATION: **NOT_GRANTED**
PRODUCTION_READINESS: **NOT_GRANTED**
GOLDEN_DEMO_ACCEPTANCE: **NOT_GRANTED**
`G-S5-RUNTIME-FREEZE-01`: **FAIL / UNCHANGED**
HERMES: **EXPERIMENTAL / NOT CURRENTLY CERTIFIABLE**
ED-S5-001: **OPEN**

PRODUCTION_CORE_CHANGE: **0**
EXISTING_SCHEMA_CHANGE: **0**
CRD_CHANGE: **0**
ADR_CHANGE: **0**
UNRELATED_CHANGE: **0**

NEXT_ACTION: **WAIT_FOR_HUMAN_CLOSE_CONFIRMATION**
NEXT_GATE: **Human S5-ARCH-005 Close Confirmation**

S5-ARCH-005 is not closed. `AUTHORIZATION` remains `AUTHORIZED`; the result is
not `SESSION_CLOSED`.
