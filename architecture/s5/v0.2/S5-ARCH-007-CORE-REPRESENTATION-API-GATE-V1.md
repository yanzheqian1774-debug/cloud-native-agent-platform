# S5-ARCH-007 — v0.2 Core Representation & API Gate v1

## 1. Session

| Field | Value |
| --- | --- |
| ID | `S5-ARCH-007` |
| Title | v0.2 Core Representation & API Gate |
| Session type | `ARCH` |
| Version | `v0.2 CONNECT — Digital Employee Technical Preview` |
| Lifecycle | `REVIEW` |
| Authorization | `AUTHORIZED` |
| Status | `PASS_WITH_CONSTRAINTS` |
| Checkpoint | `A — CURRENT_REPRESENTATION_DIFF_AND_G2_CANDIDATE` |
| Result | `CORE_REPRESENTATION_G2_CANDIDATE` |
| Authorized baseline | `040f324359c6db16ee52c55b8f367d1cc4157de9` |
| Branch | `codex/s5-arch-007-core-representation-api-gate` |
| G2-01–G2-12 | `PENDING_HUMAN_G2_GATE` |
| Prototype representation | `RECOMMENDED` |
| Schema freeze | `NO` |
| Contract freeze | `NO` |
| Production API commitment | `NO` |
| A1 state | `RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED` |
| Implementation started | `NO` |
| Next action | `WAIT_FOR_HUMAN_G2_REPRESENTATION_API_GATE` |
| Next gate | Human S5-ARCH-007 G2 Representation/API Gate |

This artifact makes one concrete prototype recommendation. It is an
architecture decision candidate, not implementation, a public schema, a
Contract, migration authorization, certification, or release acceptance.
Prototype field names below are intentionally precise enough to test but are
not permanently frozen.

## 2. Baseline, source sessions, and governance preflight

### 2.1 Baseline

- `origin/main` was exactly the authorized baseline at preflight.
- PR #45 was independently verified `MERGED`; its merge commit is the exact
  baseline.
- Work is isolated from the dirty unrelated primary checkout in the required
  branch/worktree.
- The Portfolio is present at
  [`docs/exec-plans/active/S5-PLAN-001-V0.2-IMPLEMENTATION-PORTFOLIO.md`](../../../docs/exec-plans/active/S5-PLAN-001-V0.2-IMPLEMENTATION-PORTFOLIO.md).

### 2.2 Source sessions and provenance

| Session | Verified disposition | Reopen | Provenance |
| --- | --- | --- | --- |
| S5-ARCH-005 | `CLOSED / COMPLETED / PASS / SESSION_CLOSED`; Core Candidate accepted | prohibited | repository-native Candidate and Registry |
| S5-ARCH-006 | `CLOSED / COMPLETED / PASS / SESSION_CLOSED`; G01–G08 retained | prohibited | repository/PR-native and Human-confirmed |
| S5-PLAN-001 | Human-confirmed `CLOSED / COMPLETED / PASS / SESSION_CLOSED`; PR #45 merged | prohibited | `HUMAN_CONFIRMED_GIT_VERIFIED` |
| S5-REL-007 | Human-confirmed `CLOSED / COMPLETED / PASS / SESSION_CLOSED`; durable main is the authorized baseline | prohibited | `HUMAN_CONFIRMED_GIT_VERIFIED / FORWARD_IMPORTED_BY_S5_ARCH_007` |

Repository metadata at the baseline predates the last two closure facts. This
Session forward-imports those facts into the Registry rather than creating a
recursive S5-REL-007 closeout PR.

### 2.3 Entry-state verification

- Implementation Entry: `CONDITIONALLY_GRANTED`.
- Implementation Started: `NO`.
- S5-ARCH-007 is the first recommended narrow Gate after integration.
- Tracks A–E: `ACCEPTED_FOR_PORTFOLIO_PLANNING / NOT_ACTIVE /
  NOT_AUTHORIZED`.
- S5-ARCH-005 Core Candidate and G01–G08 remain accepted.
- Core Schema, Runtime Contract, and Capability Contract freeze: `NO`.
- Provider certification, production readiness, and release acceptance:
  `NOT_GRANTED`.

No material baseline or governance contradiction was found.

## 3. Evidence method and authority

Source and tests define current behavior. The accepted Candidate defines the
logical boundary. Relevant implementation evidence is:

- CRDs: `manifests/crd/*.agentos.io.yaml`;
- controllers and builders: `operator/src/agent_operator/`;
- Native Runtime and its request/response types: `runtime/src/agent_runtime/`;
- Console backend DTO/projection/repository: `console/backend/src/agent_console/`;
- Console frontend types/API assumptions: `console/frontend/src/`;
- wire and behavior assertions: `tests/`, `operator/tests/`, `runtime/tests/`,
  and `console/backend/tests/`;
- compatibility fixtures: `manifests/` and `examples/golden-engineering-demo/`.

Accepted ADR-0003/0004/0005 drift remains recorded. This Gate neither resolves
the Operator ownership drift nor implements RuntimeClass, Runtime Adapter,
ModelPolicy, or ModelGateway.

## 4. Current representation inventory

### 4.1 Current CRDs and API versions

| Kind | Group/version | Scope | Storage/served | Controller owner |
| --- | --- | --- | --- | --- |
| Agent | `agentos.io/v1alpha1` | namespaced | `v1alpha1` / `v1alpha1` | Agent handlers in `operator/src/agent_operator/main.py` |
| Task | `agentos.io/v1alpha1` | namespaced | `v1alpha1` / `v1alpha1` | `operator/src/agent_operator/task_controller.py` |
| Workflow | `agentos.io/v1alpha1` | namespaced | `v1alpha1` / `v1alpha1` | `operator/src/agent_operator/workflow_controller.py` |

There is no current AgentInstance, Capability, RuntimeClass,
WorkflowExecution, Provider, Binding, ModelPolicy, or Registry CRD. Kubernetes
metadata supplies names, namespaces, UIDs, generations, and owner references;
none currently serves as Platform Agent Instance or Platform Execution
Identity.

### 4.2 Agent wire inventory

Authoritative schema: `manifests/crd/agents.agentos.io.yaml`. Desired-state
producer is the manifest/API caller; consumers are the Agent controller and
resource builders. Status producer is the Agent controller.

| Field | Wire/cardinality/optionality/default | Validation and consumers | v0.2 relevance / sensitivity |
| --- | --- | --- | --- |
| `metadata.name`, `metadata.namespace` | Kubernetes identity; `1:1`, required by API conventions | controller names Deployment/Service and DNS route from it | Definition-facing compatibility address; highly sensitive |
| `metadata.uid` | Kubernetes assigned; `1:1` | copied through `kopf.adopt` owner references | native ownership evidence, never Instance ID |
| `spec.runtime.type` | string; required | enum `native|hermes|external`; controller injects `AGENT_RUNTIME` | legacy Provider-specific intent; translate, do not reinterpret |
| `spec.runtime.image` | string; optional; controller default image | resource builder consumes | legacy managed realization input; opaque compatibility data |
| `spec.model.provider` | string; required | runtime factory accepts implemented values | legacy model/provider config; thin Model Binding input only |
| `spec.model.name` | string; required | passed to runtime/model provider | compatibility field; no platform routing semantics |
| `spec.model.endpoint` | string; optional | no current source consumer found | retained legacy field; evidence debt |
| `spec.model.baseUrl` | string; optional | injected as `MODEL_BASE_URL` | Provider-specific legacy field; retain |
| `spec.model.secretRef.{name,key}` | object; optional; both children required if present | becomes Secret key env source | secret reference only; never serialize secret value |
| `spec.capabilities[]` | strings; `0:N`, optional | no current production consumer found | legacy declarations; explicit mapping required before governed Binding claim |
| `spec.replicas` | integer; optional; default `1`, minimum `0` | Deployment replicas/status comparison | native realization count, not Instance cardinality |
| `spec.resources.{cpu,memory}` | strings; optional | no current builder consumer found | retained legacy desired hints; not Stable Core fields |
| `spec.identity.{role,displayName}` | strings; optional | injected into runtime env | Definition content |
| `spec.instructions.systemPrompt` | string; optional | injected into runtime env and model messages | Definition content |
| `status.phase` | optional enum | controller writes Pending/Provisioning/Running | current infrastructure summary; not Instance Condition |
| `status.observedGeneration` | optional int64 | schema exists; no current writer found | Definition validation provenance candidate; currently absent |
| `status.readyReplicas` | optional int32 | timer derives from Deployment | native readiness evidence; not routing sufficiency alone |
| `status.conditions[]` | optional objects | fields have no required list, enum, default, or current writer | structural precedent only; four-way truth not implemented |

The controller creates a same-name Deployment and Service, adopts both to the
Agent, labels them `agentos.io/agent=<Agent name>`, and invokes through the
same-name Service. This physically combines Definition intent, desired native
realization count, and a runtime address; it does not create a distinct
Platform Instance.

### 4.3 Task wire inventory

Authoritative schema: `manifests/crd/tasks.agentos.io.yaml`. The Task
controller owns execution and status.

| Field | Wire/cardinality/optionality/default | Producer/consumer and validation | v0.2 relevance / sensitivity |
| --- | --- | --- | --- |
| `metadata.name/namespace/uid` | Kubernetes resource identity | caller/API; controller | durable Task identity, not execution identity |
| `spec.agentRef.name` | string; `1:1`, required, min length 1 | caller; controller constructs same-name Service URL | keep Definition-facing target; highly sensitive |
| `spec.input.prompt` | string; required, min length 1 | caller; controller/runtime | keep unchanged |
| `spec.timeoutSeconds` | integer; optional; API default 300; min 1 | controller default also 300 | keep unchanged |
| `status.phase` | enum; optional | controller writes Pending/Running/Succeeded/Failed/TimedOut | current lifecycle compatibility |
| `status.result` | string; optional | controller writes runtime output | legacy Task Outcome projection, not universal result |
| `status.reason` | optional closed error enum | error classifier/controller | preserve; richer taxonomy unfrozen |
| `status.message` | string; optional | controller | preserve |
| `status.retryable` | boolean; optional | controller | current retry evidence |
| `status.attempts` | integer; optional; min 0 | retry executor/controller | current attempt count; attempts do not mint new Task identity today |
| `status.startedAt/completedAt` | date-time; optional | controller | Task lifecycle evidence |

The controller synchronously calls
`http://<agent>.<namespace>.svc.cluster.local:8080/v1/invoke` with JSON
`{"input": <prompt>}` and expects `{"output": ...}`. It performs bounded
retries inside one Task reconciliation. There is no router, selected Instance,
effective Runtime Binding, execution identity, native correlation, or
capability authorization context.

### 4.4 Workflow wire inventory

Authoritative schema: `manifests/crd/workflows.agentos.io.yaml`. Workflow owns
the DAG and aggregate status; generated Tasks own node execution.

| Field | Wire/cardinality/optionality/default | Producer/consumer and validation | v0.2 relevance / sensitivity |
| --- | --- | --- | --- |
| `spec.tasks[]` | array; `1:N`, required, min 1 | caller; graph/controller | preserve embedded DAG semantics |
| `spec.tasks[].name` | required string, min 1 | graph/controller; generated Task name suffix | local node identity |
| `spec.tasks[].agentRef.name` | required string, min 1 | builder copies to Task | Definition-facing target; preserve |
| `spec.tasks[].input.prompt` | required string, min 1 | builder/prompt resolver | preserve |
| `spec.tasks[].input.from[]` | optional; default `[]`; each `.task` required | graph validation/result projection | data dependency |
| `spec.tasks[].dependsOn[]` | optional; default `[]` | graph validation/scheduling | control dependency |
| `spec.tasks[].timeoutSeconds` | optional; default 300; min 1 | copied to Task | preserve |
| `status.phase` | Pending/Running/Succeeded/Failed | Workflow controller | aggregate compatibility field |
| `status.startedAt/completedAt` | optional date-time | schema exists; no current controller writer found | retained wire field |
| `status.taskCount` | optional integer, min 0 | controller | projection |
| `status.tasks.<node>.phase` | node phase incl. TimedOut/Skipped | controller | node projection |
| `status.tasks.<node>.taskRef.name` | optional string | controller derives `<workflow>-<node>` | owned Task reference |
| `status.tasks.<node>.reason/message` | optional strings | skip/aggregation logic | node evidence |

Generated Tasks use labels `agentos.io/workflow` and
`agentos.io/workflow-task` and a Kubernetes owner reference adopted from the
Workflow. Existing DAG validation rejects cycles, unknown/self/duplicate
dependencies and invalid result-source relationships. No new
WorkflowExecution resource is needed or authorized.

### 4.5 Runtime, capability, and serialization inventory

| Area | Current physical representation | Ownership / sensitivity | v0.2 interpretation |
| --- | --- | --- | --- |
| Native Runtime request | Pydantic `InvokeRequest(input: str)` at `POST /v1/invoke` | runtime public HTTP wire; tests assert shape | unchanged compatibility request |
| Native Runtime response | `InvokeResponse(output, agent, model)` | runtime wire; tests assert exact JSON | native evidence; does not define Outcome or IDs |
| Runtime info | env-derived agent/namespace/runtime/role/display/model values | runtime-local | native/config observation only |
| Runtime adapter | none | ADR-0004 partial/drift | effective Binding must stay prototype-only in A1 |
| Model provider | runtime-local ABC plus mock/OpenAI-compatible factory | runtime-local Provider implementation | not platform Model Contract |
| Capability structures | Agent `spec.capabilities[]` strings only | no governed consumer/authorization/outcome | semantic mismatch; map only when explicit |
| YAML | Kubernetes manifests parsed by API; PyYAML in schema tests | CRD schemas/defaulting authoritative | do not add YAML public schema in A1 |
| JSON | FastAPI/Pydantic at runtime and Console; Kubernetes Python client dicts | current wire contracts | A1 fixtures use JSON-compatible internal records |
| Conversion/defaulting | no conversion webhook; CRD OpenAPI defaults plus Python fallback defaults | API server/controllers | no cross-version conversion exists |
| Validation | CRD OpenAPI plus Python graph/error validation | API server/controllers | preserve current errors and defaults |

### 4.6 Console inventory

The backend is a read-only Kubernetes projection. It exposes
`GET /api/v1/workflows` and
`GET /api/v1/workflows/{namespace}/{name}`. Pydantic DTOs set
`extra="forbid"`; the TypeScript interfaces mirror the DTO field names and
closed phase unions. The repository reads Kubernetes Workflows and label-joined
Tasks. The frontend assumes `agent.name` is the current Agent reference and
has no Definition/Instance split, execution ID, selected Instance, Runtime
Binding, Capability Outcome, or Recovery projection.

This strict DTO behavior makes uncoordinated additive Console response fields
compatibility-sensitive even when Kubernetes objects tolerate them. A1 must
not modify Console APIs; later projections require their own versioned DTO or
explicit tolerant-consumer evidence.

### 4.7 Tests asserting current behavior

| Behavior | Primary evidence |
| --- | --- |
| Task schema required fields/status enum/retry fields | `tests/test_task_crd.py` |
| Workflow DAG schema/defaults/status/taskRef | `tests/test_workflow_crd.py` |
| Agent builders, labels, env, default runtime image | `operator/tests/test_resources.py` |
| owner adoption and Agent reconciliation/status | `operator/tests/test_operator.py` |
| exact Task invoke JSON, status, retry and timeout | `operator/tests/test_task_controller.py`, `operator/tests/test_retry.py` |
| Workflow-owned Task naming/labels, DAG, fan-in, skip/result passing | `operator/tests/test_workflow_controller.py`, `operator/tests/test_workflow_graph.py` |
| exact Native Runtime request/response and info | `runtime/tests/test_runtime.py`, `runtime/tests/test_providers.py` |
| Console DTO exactness/projection/routes | `console/backend/tests/test_schemas.py`, `test_projection.py`, `test_app.py` |

## 5. Logical-to-physical diff

Classification is against the accepted Candidate, not target architecture in
general.

### 5.1 Agent Definition and Instance

| Logical element | Current physical evidence | Classification | v0.2 consequence |
| --- | --- | --- | --- |
| Definition compatibility address | Agent name + namespace | `DIRECTLY_REPRESENTED` | retain unchanged |
| desired role/display/instructions | Agent embedded spec | `DIRECTLY_REPRESENTED` | Definition-owned |
| desired Runtime Binding | `spec.runtime` plus model/config fields | `REPRESENTED_WITH_SEMANTIC_MISMATCH` | compatibility translator input, not new semantics |
| Capability Bindings | `spec.capabilities[]` strings | `REPRESENTED_WITH_SEMANTIC_MISMATCH` | explicit governed mapping required |
| thin Model Binding | embedded `spec.model` Provider fields | `REPRESENTED_WITH_SEMANTIC_MISMATCH` | thin compatibility projection only |
| distinct Instance ID | none | `MISSING` | internal Platform-minted ID required |
| Definition reference from Instance | none | `MISSING` | required internal ref |
| effective Runtime Binding | derivable from Agent spec/current path but unrecorded | `DERIVABLE` | record in prototype snapshot |
| placement-independent Instance | none | `MISSING` | prohibit Pod/Service/UID substitution |
| native realizations/history | Deployment/Service/Pod evidence only, not normalized | `INTERNAL_ONLY` | opaque evidence, optional `0:N` |
| eligibility/routability | same-name Service and ready replicas imply reachability only | `REPRESENTED_WITH_SEMANTIC_MISMATCH` | explicit prototype state needed |
| Instance Conditions | none | `MISSING` | minimal structure in prototype |
| Recovery Assessment | none | `MISSING` | optional/unknown prototype boundary |

### 5.2 Task and Workflow

| Logical element | Current physical evidence | Classification | v0.2 consequence |
| --- | --- | --- | --- |
| Task Definition target | `spec.agentRef.name` | `DIRECTLY_REPRESENTED` | keep wire meaning |
| selected Instance evidence | none | `MISSING` | internal resolution record |
| Platform Execution Identity | none | `MISSING` | internal minted value |
| native correlation evidence | none | `MISSING` | optional list; never authority |
| Task Outcome | phase/result/reason/message/retryable/times | `REPRESENTED_WITH_SEMANTIC_MISMATCH` | lossless derived domain Outcome |
| retry/recovery fields | attempts/retryable; retry executor | `DIRECTLY_REPRESENTED` for Task retry | not Instance Recovery |
| Workflow DAG | embedded tasks/dependencies/input sources | `DIRECTLY_REPRESENTED` | preserve |
| Workflow-owned Tasks | owner refs, labels, deterministic names | `DIRECTLY_REPRESENTED` | preserve |
| Workflow Outcome | aggregate phase/node evidence | `REPRESENTED_WITH_SEMANTIC_MISMATCH` | derive; vocabulary unfrozen |
| root/child execution identity | none | `MISSING` | root plus child correlation internally |
| WorkflowExecution resource | none | `DEFERRED` | explicitly not introduced |

### 5.3 Capability, Conditions, Outcomes, and recovery

| Logical element | Current physical evidence | Classification | v0.2 consequence |
| --- | --- | --- | --- |
| Capability Definition | capability strings only | `MISSING` | internal fixture/reference candidate only in A1 |
| governed Capability Binding | strings with no auth/provider/version semantics | `REPRESENTED_WITH_SEMANTIC_MISMATCH` | embedded internal record; no CRD |
| authorization evidence | none | `MISSING` | future C-track producer; shape may be fixture-only |
| Capability Outcome | none | `MISSING` | domain-owned and deferred from A1 execution |
| Runtime Condition | health/readiness/native failures fragmented | `DERIVABLE` | shared structure, Runtime-owned |
| Agent Instance Condition | none | `MISSING` | Instance-owned structure |
| Task Outcome | Task status | `DERIVABLE` | exact lossless mapping required |
| Workflow Outcome | Workflow/task status | `DERIVABLE` | aggregate mapping required |
| Recovery Assessment | none | `MISSING` | Instance-owned; no restart-equals-recovery rule |
| four-way truth | Kubernetes condition strings not constrained; no N/A | `MISSING` | internal enum semantic boundary only |

## 6. Bounded representation options

### 6.1 R1 — Compatibility-first additive public representation

Physical form: retain Agent/Task/Workflow and add optional fields to their
existing `v1alpha1` schemas, plus a new AgentInstance representation.

| Dimension | Assessment |
| --- | --- |
| API/CRD/schema | additive public fields and likely a new CRD; Human G2 required |
| controllers/runtime | routing, reconciliation, propagation, status writers change |
| Task/Workflow | wire retained but schemas and generated Tasks change |
| Console | additive projection/DTO tolerance work |
| migration | lazy identity backfill plus mixed old/new reconciliation |
| rollback | bounded only while new writers/readers are gated; stored fields persist |
| test burden/risk | high; schema, envtest/live API, old-client and mixed-version tests |
| MVS/OpenClaw | supports both, but commits public shape before prototype evidence |
| Option B alignment | strong semantically, premature physically |
| Evidence Debt | serialization/backfill/routing debt remains and becomes public |

Disposition: reject for A1; retain as a later G2 candidate only after internal
fixtures prove the shape.

### 6.2 R2 — New versioned public API representation

Physical form: introduce a new API version and/or public resources with
conversion between current and new representations.

| Dimension | Assessment |
| --- | --- |
| API/CRD/schema | new API version and possibly new CRD; conversion/storage decision required |
| controllers/runtime | dual-version reads and explicit desired authority required |
| Task/Workflow | conversion must preserve all current wire behavior and DAG semantics |
| Console | version negotiation/projection changes |
| migration/rollback | largest burden; conversion webhook and storage rollback risk |
| mixed version | complex; cannot dual-write desired authority |
| test burden/risk | highest; round-trip losslessness and skew matrix |
| MVS/OpenClaw | extensible but unnecessary to prove MVS |
| Option B alignment | compatible in principle, expensive before evidence |
| Evidence Debt | conversion, storage, defaulting, old-client behavior all open |

Disposition: reject for A1 and defer until a public-version trigger is proven.

### 6.3 R3 — Internal prototype representation first

Physical form: a versioned internal, JSON-compatible representation package
and fixtures with pure translators from current objects. No Kubernetes writer,
CRD, endpoint, controller, runtime, or Console integration.

| Dimension | Assessment |
| --- | --- |
| API/CRD/schema | none |
| exact ownership | internal Core prototype owns normalized Definition, Instance, execution, Binding, Condition/Outcome records |
| controllers/runtime | consumers absent in A1; A2 consumes records behind internal interfaces |
| Task/Workflow | current wire is read losslessly; no writes or reinterpretation |
| Console | no change; fixtures can later drive projection design |
| migration | deterministic lazy mapping function and mapping fixture; no object mutation |
| mixed version | old objects map to `LEGACY_COMPAT`; prototype-native fixtures map to `PROTOTYPE`; conflicts fail closed |
| rollback | disable/remove internal consumer; current objects remain sole desired authority |
| test burden/risk | bounded; serialization, invariants, round trips, negative mappings |
| MVS/OpenClaw | supports Native MVS identity spine and opaque future Provider evidence |
| Option B alignment | strongest reversible first step |
| Evidence Debt | exposes rather than prematurely freezes API/migration decisions |

Disposition: **recommended for A1**.

### 6.4 R4 — Hybrid staged embedded-status projection

Physical form: use R3 models but persist Instance/execution material under
existing Agent/Task/Workflow status before creating public desired resources.

| Dimension | Assessment |
| --- | --- |
| API/CRD/schema | existing-schema additive changes required |
| ownership | risks confusing observed projection with Instance desired lifecycle |
| migration/mixed version | status backfill and multiple controller writers |
| rollback | stored status is removable but skew and pruning behavior remain |
| test burden/risk | medium-high; API-server pruning and status ownership tests |
| MVS/OpenClaw | can expose evidence quickly but cannot cleanly represent `1:N` Instances |
| Option B alignment | partial; tempts embedded Agent identity reuse |
| Evidence Debt | Instance persistence/authority remains unresolved |

Disposition: reject for A1. It is materially distinct but violates the clean
desired/effective ownership needed for a first-class logical Instance.

## 7. Recommended prototype representation — R3

### 7.1 Ownership and serialization envelope

A1 should create a dependency-free internal package under
`core/src/agent_core/representation/v0_2/` and tests under `core/tests/`.
Records serialize to canonical JSON-compatible Python dictionaries with
`schemaVersion: "core.agentos.io/prototype-v0.2"`. The representation is not
served by an endpoint and not persisted into Kubernetes.

All references use an internal object with:

- `kind`: bounded logical kind;
- `name`: non-empty DNS-compatible compatibility name where applicable;
- `namespace`: non-empty Kubernetes namespace for current objects;
- optional `uid`: source Kubernetes UID as provenance only.

Native evidence uses a structurally separate object:

- `system`: opaque Provider/runtime family label;
- `kind`: opaque native ID kind;
- `id`: non-empty opaque identifier;
- optional `observedAt`;
- optional `attributes`: redacted scalar metadata only.

No native reference may populate a logical reference or Platform ID.

### 7.2 Agent Definition

Prototype type `AgentDefinitionRecord`:

| Path | Cardinality / optionality | Owner / derivation |
| --- | --- | --- |
| `definitionRef` | exactly 1 | from current Agent name/namespace; Core owns logical meaning |
| `source.generation` | `0:1` | Kubernetes metadata provenance |
| `source.uid` | `0:1` | provenance only; not logical identity |
| `role`, `displayName`, `instructions.systemPrompt` | optional | lossless current Agent fields |
| `desiredRuntimeBinding` | exactly 1 for current valid Agents | translator-owned compatibility Binding |
| `capabilityBindings[]` | `0:N` | explicit legacy-unmapped or governed fixtures |
| `modelBinding` | `0:1` | thin embedded foundation |
| `compatibility.mode` | exactly 1 | `LEGACY_AGENT_V1ALPHA1` in current translation |
| `compatibility.unconsumedFields[]` | `0:N` | prevents silent loss |

Current `Agent` remains the v0.2 prototype Definition-facing public address.
No rename, API version, or conversion is used. Provider-specific current
fields are retained in the compatibility payload and translated into opaque
Binding config; they are not declared Stable Core. With no explicit persisted
Instance, the interpreter produces one deterministic legacy-managed Instance
record for routing simulation only.

### 7.3 Agent Instance

Prototype type `AgentInstanceRecord`:

| Path | Cardinality / optionality | Ownership / rule |
| --- | --- | --- |
| `instanceId` | exactly 1 | Platform-minted, immutable, never Definition/native ID |
| `definitionRef` | exactly 1 | logical Definition reference |
| `scope.namespace` | exactly 1 for current compatibility | logical scope |
| `desired.lifecycle` | exactly 1 | internal prototype intent, initially `Active` |
| `effective.definitionGeneration` | `0:1` | resolution provenance |
| `effective.runtimeBinding` | exactly 1 when resolved | Instance resolver-owned snapshot |
| `effective.resolvedAt` | exactly 1 when resolved | RFC 3339 timestamp |
| `placementRef` | `0:1` | opaque logical placement hint, not identity |
| `status.eligibility` | exactly 1 | `ELIGIBLE|INELIGIBLE|UNKNOWN` prototype vocabulary |
| `status.conditions[]` | `0:N` | Instance-owned conditions |
| `status.recoveryAssessment` | `0:1` | Instance-owned semantic assessment |
| `status.realizations[]` | `0:N` | opaque native evidence; temporal history |
| `status.activeRealizationIds[]` | `0:N` | references entries in realizations only |
| `compatibility.sourceAgentRef` | exactly 1 for legacy mode | mapping provenance |

For A1 fixtures, IDs are UUID strings minted by an injected Platform ID
factory. Production format is not committed. The same source object plus a
durable mapping fixture must recover the same ID across translator restarts;
hashing Definition identity into Instance identity is prohibited. A missing
mapping is a typed `BACKFILL_REQUIRED` result, not permission to mint on every
read.

Deletion/cleanup and replacement are represented, not executed. Definition
deletion with a live Instance is a stop/error fixture. Realization replacement
appends evidence without changing `instanceId`. Cleanup authority comes from
Binding ownership policy, never possession of a native ID.

### 7.4 Embedded Bindings

- `RuntimeBindingRecord` lives at
  `AgentDefinitionRecord.desiredRuntimeBinding` and
  `AgentInstanceRecord.effective.runtimeBinding`. It contains a stable
  prototype `bindingId`, `providerRef`, `mode`, optional `packageRef`, opaque
  redacted `configuration`, and resolution provenance. Desired and effective
  records are separate snapshots.
- `CapabilityBindingRecord` lives at
  `AgentDefinitionRecord.capabilityBindings[]`. It references one Capability
  Definition, optional Provider metadata, authorization/policy refs, and opaque
  redacted config. Legacy strings remain `LEGACY_UNGOVERNED` until mapped.
- `ModelBindingRecord` lives at `AgentDefinitionRecord.modelBinding` and may be
  projected into Instance effective state. It contains only logical/model
  references plus legacy provenance; routing/fallback is deferred.

All three are embedded. None has an independent lifecycle, API, CRD, registry,
or Provider-specific Stable Core discriminator.

### 7.5 Platform Execution Identity

Prototype type `ExecutionIdentityRecord`:

| Path | Rule |
| --- | --- |
| `executionId` | exactly one Platform-minted immutable UUID string in prototype fixtures |
| `rootExecutionId` | equals self for root Task/Workflow execution; inherited unchanged by child Tasks |
| `parentExecutionId` | absent for root; Workflow root ID for node Task |
| `attempt` | positive integer observation; retry retains `executionId` |
| `nativeCorrelations[]` | optional `0:N` opaque evidence |
| `createdAt` | Platform owner timestamp |

Minting authority is the Platform Task owner for a standalone Task and the
Workflow owner for a Workflow root. Each Workflow-created Task receives its
own execution ID with root/parent links; a controller retry of the same logical
Task retains that ID and increments attempt. Explicit user re-execution creates
a new Task/execution ID unless a future idempotency Contract says otherwise.

Propagation contract for A2 and later:

```text
Business/API request
  -> Task/Workflow owner (mint/persist internal record)
  -> router (unchanged ID + Definition target)
  -> selected Instance (record selectedInstanceRef)
  -> effective Runtime Binding
  -> Runtime Provider
  -> native Runtime
  -> Capability authorization
  -> Capability Provider
  -> normalized observations
  -> Task/Workflow Outcome
```

Every hop accepts and returns the same `executionId`; native IDs only append to
`nativeCorrelations`. Logs/traces may include the Platform ID but must redact
Binding configuration, prompts/results where policy requires, credentials, and
native metadata marked sensitive. The ID is correlation, not authentication
or authorization.

Old Tasks without the field translate to `executionIdentity.state =
BACKFILL_REQUIRED` and may continue on the current path. A1 does not mutate
them. Tests must prove retry stability, child/root relationships, `0:N` native
correlations, invalid native-ID substitution rejection, and redaction.

### 7.6 Task selection and Outcomes

Prototype type `TaskExecutionRecord` keeps:

- `taskRef` and current Definition-facing `target.definitionRef`;
- optional explicitly authorized `target.instanceRef` for future use;
- `executionIdentity`;
- `routing.selectedInstanceRef` as exactly `0:1` effective evidence;
- `routing.effectiveRuntimeBindingRef` as `0:1`;
- `routing.decision` and provenance;
- lossless current request fields;
- `outcome` as a Task-owned derived record;
- `nativeCorrelations[]` as evidence.

`selectedInstanceRef` is internal in A1. It is never written into
`spec.agentRef`; it cannot change the target's meaning. When no prototype
Instance is available, legacy execution continues unchanged and selection is
`UNRESOLVED_LEGACY`, not fabricated.

### 7.7 Conditions, Outcomes, and recovery

The minimum shared structural record is:

```json
{
  "type": "Ready",
  "truth": "UNKNOWN",
  "reason": "ObservationUnavailable",
  "message": "No normalized observation is available.",
  "observedAt": "2026-08-24T00:00:00Z",
  "observedGeneration": 7
}
```

`truth` permits `TRUE`, `FALSE`, `UNKNOWN`, and `NOT_APPLICABLE`. Type/reason
vocabularies, wire casing, and serialization remain unfrozen. Runtime and
Instance own separate condition lists.

Outcomes share only identity/time/evidence/reference primitives. Task,
Workflow, and Capability keep distinct types and constructors. A1 implements
lossless Task/Workflow compatibility outcome derivation and shape-only
Capability fixtures; it does not create a universal Outcome.

`RecoveryAssessmentRecord` is Instance-owned and contains `truth`, `reason`,
`assessedAt`, predicate evidence refs, and optional prior/current realization
refs. `TRUE` requires an explicit semantic predicate fixture. A restart,
replacement, health response, or running Pod alone cannot produce `TRUE`.

### 7.8 Serialization examples

Legacy Agent translation:

```json
{
  "schemaVersion": "core.agentos.io/prototype-v0.2",
  "definition": {
    "definitionRef": {"kind": "AgentDefinition", "namespace": "default", "name": "researcher"},
    "desiredRuntimeBinding": {
      "bindingId": "runtime-binding/researcher",
      "providerRef": "native-compat",
      "mode": "MANAGED",
      "configuration": {"legacyRuntimeType": "native", "image": "enterprise-agent-runtime:v0.1-dev"}
    },
    "capabilityBindings": [],
    "modelBinding": {"legacyProvider": "mock", "legacyModel": "mock-model"},
    "compatibility": {"mode": "LEGACY_AGENT_V1ALPHA1", "unconsumedFields": []}
  }
}
```

Instance and Task execution fixture:

```json
{
  "instance": {
    "instanceId": "0198e5a0-1c2d-7a10-9b21-112233445566",
    "definitionRef": {"kind": "AgentDefinition", "namespace": "default", "name": "researcher"},
    "effective": {"runtimeBindingRef": "runtime-binding/researcher", "definitionGeneration": 7},
    "status": {"eligibility": "ELIGIBLE", "conditions": [], "realizations": []}
  },
  "taskExecution": {
    "taskRef": {"kind": "Task", "namespace": "default", "name": "research"},
    "target": {"definitionRef": {"kind": "AgentDefinition", "namespace": "default", "name": "researcher"}},
    "executionIdentity": {
      "executionId": "0198e5a1-77ca-7d0b-a812-223344556677",
      "rootExecutionId": "0198e5a1-77ca-7d0b-a812-223344556677",
      "attempt": 1,
      "nativeCorrelations": []
    },
    "routing": {
      "selectedInstanceRef": "0198e5a0-1c2d-7a10-9b21-112233445566",
      "effectiveRuntimeBindingRef": "runtime-binding/researcher",
      "decision": "SELECTED"
    }
  }
}
```

### 7.9 Defaulting, validation, exposure, and rollback

- Defaults are applied only by explicit translator functions and are visible
  in fixtures. Current API-server defaults remain authoritative for current
  objects.
- Validation rejects missing references, identity aliasing, native IDs in
  logical fields, unknown extra fields, secret-shaped configuration values,
  selected Instances from another Definition/scope, multiple desired
  authorities, and contradictory mixed modes.
- Internal records are immutable value snapshots. Derived fields identify
  their source and cannot become desired authority.
- No public API, CRD, status write, annotation, label, or Console field exposes
  A1 records.
- Rollback is removal/disablement of the internal consumer and mapping store;
  current Kubernetes objects remain unchanged and authoritative.

## 8. Task and Workflow compatibility

- `Task.spec.agentRef.name` and Workflow node `agentRef.name` continue to mean
  the current namespaced Agent/Definition-facing address.
- The internal alias is `target.definitionRef`; it does not replace or mutate
  the wire field.
- Router resolution is future A2 work: current target -> compatible Definition
  -> eligible Instance set -> one selected Instance -> effective Binding.
- `selectedInstanceRef`, execution identity, effective Runtime evidence, and
  native correlations are internal in A1/A2 unless a later Human G2 explicitly
  authorizes public representation.
- Existing controller Service routing, retry, status, result, reason, Workflow
  Task naming/labels/owner references, DAG scheduling, result passing,
  parallel/fan-in, failure, timeout, and skip semantics remain unchanged.
- Workflow-created Tasks inherit the Definition target and root correlation in
  the internal prototype; they remain ordinary current Task resources on wire.
- Old/new mixed execution is fail-open only to the unchanged legacy path when
  no new desired authority exists. Conflicting authority or invalid mapping
  fails closed in the prototype.
- No `WorkflowExecution` resource is introduced.

## 9. Compatibility, migration, mixed version, and rollback map

| Consumer/object | Read compatibility | Write compatibility | Migration/backfill | Rollback |
| --- | --- | --- | --- | --- |
| existing Agent manifests/clients | unchanged | unchanged Agent writes | lazy internal translation; explicit durable mapping needed for Instance ID | ignore prototype records |
| existing Task callers | unchanged `agentRef/input/timeout` | unchanged | missing execution ID marked `BACKFILL_REQUIRED`; no mutation in A1 | current controller path |
| Workflow DAGs | unchanged | unchanged | root/child IDs only in internal fixtures initially | current Workflow/Task ownership |
| Native Runtime | unchanged invoke JSON | unchanged response | A2 envelope adapter needed before propagation | omit envelope; current call |
| Gateway/API | no current production Gateway | no change | future owner must expose IDs only after G2 | no endpoint to revert |
| Console | current strict DTOs unchanged | read-only | future additive/versioned projection with tolerance tests | current DTOs |
| old objects without Instance ID | translated only with mapping or `BACKFILL_REQUIRED` | never rewritten by A1 | prefer lazy mapping creation in separately authorized store; no hash alias | current object remains authority |
| old Tasks without execution ID | readable and executable | current writes only | lazy correlation for new executions; historical IDs remain unknown unless evidence exists | no fabricated history |
| mixed-version controllers | only one current writer | no dual desired write | prototype reader must be side-effect free | disable reader |

Migration recommendation: **lazy, explicit, mapping-backed adoption**. Eager
cluster-wide mutation is rejected. Identity mapping must bind source
`group/version/kind/namespace/name/uid` to a separately minted Instance ID,
survive restart, distinguish delete/recreate by UID, and retain tombstone/audit
evidence. A1 uses fixtures/in-memory test stores only; persistence choice is
deferred.

Dual-write of desired state is prohibited. There is always one desired
authority: current Kubernetes objects during this prototype. Read projection
may be additive. Deprecation begins only after equivalent public replacement,
adoption telemetry, conversion evidence, rollback rehearsal, and a later Human
Gate. No Provider-specific current field is removed.

## 10. G2 change classification

### 10.1 Proposed-change ledger and totals

| Proposed item | Classification | Affected future path | A1? |
| --- | --- | --- | --- |
| versioned internal records and validators | `INTERNAL_REPRESENTATION_ONLY` | `core/src/agent_core/representation/v0_2/` | yes |
| pure current-Agent/Task/Workflow translators | `INTERNAL_REPRESENTATION_ONLY` | same package | yes |
| internal JSON fixtures/mapping store abstraction | `INTERNAL_REPRESENTATION_ONLY` | `core/tests/`, optional owned fixture path | yes |
| internal execution envelope and propagation contract | `INTERNAL_REPRESENTATION_ONLY` | A1/A2 package | yes, shape only |
| additive future Gateway request/response identity | `API_ADDITIVE_NON_BREAKING` | future Gateway/API | no; separate G2 |
| additive future Task/Workflow public identity/selection status | `EXISTING_SCHEMA_ADDITIVE` | current CRDs/controllers | no; separate G2 |
| public AgentInstance API without current CRD | `NEW_API_VERSION` | future public API | no; separate G2 |
| public AgentInstance CRD | `NEW_CRD` | `manifests/crd`, controller | no; separate G2 |
| reinterpret `Agent` or `agentRef` as Instance | `EXISTING_CRD_SEMANTIC_CHANGE` | Agent/Task/Workflow | blocked |
| require new identity fields from old clients | `BREAKING_WIRE_CHANGE` | APIs/CRDs/runtime | blocked |
| public Condition/Outcome vocabulary | `DEFERRED` | API/schema | no |
| WorkflowExecution resource | `DEFERRED` | none authorized | no |
| native ID as Platform identity | `BLOCKED` | all | no |

Totals: `INTERNAL_REPRESENTATION_ONLY=4`,
`API_ADDITIVE_NON_BREAKING=1`, `EXISTING_SCHEMA_ADDITIVE=1`,
`NEW_API_VERSION=1`, `NEW_CRD=1`, `EXISTING_CRD_SEMANTIC_CHANGE=1`,
`BREAKING_WIRE_CHANGE=1`, `DEFERRED=2`, `BLOCKED=1`.

### 10.2 Gate answers

- A1 public API change: `NO`.
- A1 CRD change: `NO`.
- A1 existing-schema change: `NO`.
- A1 breaking wire change: `NO`.
- A2 can proceed internally without those changes if it remains an envelope,
  router interface, and compatibility adapter not exposed or persisted in
  current CRDs/APIs. Any controller behavior or Runtime invoke-wire change
  still needs its separately authorized Session and applicable G1/G2 review.
- Public AgentInstance, Task/Workflow fields, Gateway DTOs, a new API version,
  any CRD, or semantic reinterpretation require separate Human G2
  authorization. The last two breaking/semantic options are not recommended.

## 11. A1 implementation handoff

| Field | Handoff |
| --- | --- |
| Recommended Session | `S5-IMPL-001` |
| Title | A1 Core Representation Prototype |
| Type | `IMPL` |
| Objective | implement R3 as a versioned dependency-free internal model, pure compatibility translators, canonical fixtures, validation, and negative tests; prove identity separation and lossless current-object reads without production integration |
| Writable paths | `core/src/agent_core/representation/v0_2/`, `core/tests/`, `docs/evidence/s5/v0.2/s5-impl-001/`; root `pyproject.toml` only if needed to add `core/src` to test discovery and with no dependency change |
| Prohibited paths | `manifests/crd/`, `operator/src/`, `runtime/src/`, `gateway/`, `console/`, current production tests outside the owned Core test path, ADR bodies, dependencies, release tags |
| Deliverables | typed immutable records, canonical serializer/parser, validators, mapping-store protocol plus in-memory fixture, pure Agent/Task/Workflow translators, two positive serialization fixtures, compatibility report |
| Positive tests | exact serialization, round trip, current manifest translation, stable injected IDs, Definition `1:N` Instances, retry ID stability, Workflow root/child correlation, selected Instance/effective Binding linkage, `0:N` native evidence, four-way truth |
| Negative tests | Definition/Instance ID equality, native ID substitution, missing mapping, cross-Definition selection, duplicate active native refs, secret material, unknown fields, dual authority, invalid four-way truth, restart-equals-recovery |
| Rollback | remove/disable unconsumed internal package; no current object or API was mutated |
| Entry conditions | Human accepts G2-01–G2-12; separately authorizes S5-IMPL-001; isolated worktree; exact accepted baseline/handoff; no public schema owner active |
| Stop conditions | public field/CRD/endpoint needed; persistence dependency needed; lossless translation impossible; accepted semantic boundary contradicted; current production path must change |
| Exit Gate | A1 Representation Prototype Exit: tests and fixtures prove shape/invariants; all public/API/CRD/schema changes remain zero; debt ledger updated |
| PR boundary | one internal representation/interface PR; no A2 routing/controller integration |

Acceptance ownership: S5-IMPL-001 owns A1 code/test evidence and the A1 Exit;
Humans own architecture acceptance. Debt addressed: serialization candidate,
identity separation, reference shape, translation-loss detection, execution
correlation invariants. Debt retained: persistent mapping, cluster backfill,
public API/CRD, routing eligibility, Provider conformance, Console tolerance,
vocabulary freeze, recovery thresholds, mixed live controller versions.

`A1_STATE: RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED`.

## 12. G2 Human decision candidates

Every decision below remains `PENDING_HUMAN_G2_GATE`.

### G2-01 — Definition representation

- Recommendation: current namespaced `Agent` remains the v0.2 prototype
  Definition-facing public compatibility address; R3 translates it internally.
- Alternatives: new API version; new Definition CRD; embedded-only model.
- Evidence: current manifests/controllers/Tasks/Console all address Agent by
  name; Candidate requires address preservation.
- Compatibility/rollback: zero wire change; disable translator.
- Evidence Debt: Definition versioning, deletion protection, public future
  representation.
- Required disposition: accept/reject/modify R3 Definition interpretation.

### G2-02 — Instance representation

- Recommendation: distinct internal `AgentInstanceRecord` in A1; no CRD/API.
- Alternatives: additive public CRD (R1), new versioned API (R2), Agent status
  projection (R4).
- Evidence: no current Instance exists; current replicas/native resources
  cannot satisfy stable identity or `1:N` semantics.
- Compatibility/rollback: no current writes; package removal.
- Evidence Debt: durable store, backfill, deletion/finalization, public model.
- Required disposition: accept/reject/modify internal-first Instance.

### G2-03 — Execution Identity representation

- Recommendation: internal embedded record with Platform-minted immutable ID,
  root/parent relationships, retry stability, and `0:N` native evidence.
- Alternatives: public Task fields now; native correlation; universal Execution
  resource. The latter two are rejected.
- Evidence: no current field propagates across controller/runtime/capability
  boundaries; Candidate E03 accepts the concept with debt.
- Compatibility/rollback: old objects remain valid; disable envelope.
- Evidence Debt: persistence, public request/response placement, tracing policy.
- Required disposition: accept/reject/modify lifecycle rules.

### G2-04 — Task targeting compatibility

- Recommendation: preserve `spec.agentRef.name` exactly as Definition-facing;
  internal typed alias only.
- Alternatives: new additive target union later; reinterpret as Instance
  (blocked).
- Evidence: CRD, controller URL construction, Workflow builder, fixtures, and
  Console all depend on current meaning.
- Compatibility/rollback: unchanged; alias removable.
- Evidence Debt: explicit Instance target authorization and public target union.
- Required disposition: accept/reject/modify preservation rule.

### G2-05 — selectedInstanceRef representation

- Recommendation: optional internal effective routing evidence owned by the
  Control Plane; absent on unresolved legacy execution.
- Alternatives: Task status additive field later; spec field (rejected as
  conflating desired target and effective selection).
- Evidence: no current router; Candidate requires selected Instance evidence.
- Compatibility/rollback: no wire change; remove internal projection.
- Evidence Debt: public status placement, rerouting/in-flight semantics.
- Required disposition: accept/reject/modify internal status location.

### G2-06 — Runtime Binding prototype location

- Recommendation: desired Binding embedded in Definition record; effective
  snapshot embedded in Instance record; Task holds only a reference/evidence.
- Alternatives: Binding CRD or Provider fields in Core (rejected).
- Evidence: accepted embedded boundary; current runtime/model fields need
  explicit compatibility translation.
- Compatibility/rollback: current fields retained; internal translation only.
- Evidence Debt: resolver/provider/package conformance and exact vocabulary.
- Required disposition: accept/reject/modify embedded locations.

### G2-07 — Capability Binding continuity

- Recommendation: embedded Definition bindings; legacy strings explicitly
  `LEGACY_UNGOVERNED` until mapped; authorization stays separate.
- Alternatives: Capability Binding resource; silently treat strings as
  governed (rejected).
- Evidence: current strings have no consumer/auth/version/Outcome; accepted
  Candidate keeps Binding embedded.
- Compatibility/rollback: preserve strings; remove projection.
- Evidence Debt: Capability Definition representation, mapping, Provider and
  authorization conformance.
- Required disposition: accept/reject/modify continuity rule.

### G2-08 — Condition/Outcome/Recovery minimum representation

- Recommendation: shared structural fields/four-way truth only; Runtime and
  Instance Conditions separate; Task/Workflow/Capability Outcomes separate;
  Recovery Instance-owned.
- Alternatives: current phase-only projection; universal types (rejected).
- Evidence: current phase/status fragmentation plus accepted E07–E09.
- Compatibility/rollback: derive current fields losslessly; internal removal.
- Evidence Debt: exact vocabularies, transitions, thresholds, side effects.
- Required disposition: accept/reject/modify minimum structures.

### G2-09 — Migration and backfill approach

- Recommendation: lazy explicit mapping keyed by full source identity/UID;
  never hash/reuse Definition identity; A1 fixtures only.
- Alternatives: eager mutation; ephemeral mint on read; deterministic hash.
  All alternatives are rejected for current scope.
- Evidence: current objects lack Instance/execution IDs; Candidate requires
  durable distinction and bounded rollback.
- Compatibility/rollback: no current mutation; discard fixture mapping.
- Evidence Debt: production persistence, tombstones, adoption, observability.
- Required disposition: accept/reject/modify lazy mapping policy.

### G2-10 — Mixed-version behavior

- Recommendation: current Kubernetes objects remain sole desired authority;
  side-effect-free prototype reads; fallback to unchanged legacy path only
  when no conflict; fail closed on dual authority.
- Alternatives: dual write or opportunistic adoption (rejected).
- Evidence: current single-version CRDs/controllers and accepted E11.
- Compatibility/rollback: disable prototype reader.
- Evidence Debt: live skew, in-flight Tasks, controller rollout, cleanup.
- Required disposition: accept/reject/modify authority/fallback rules.

### G2-11 — Public API / CRD / Schema authorization

- Recommendation: authorize **zero** public API, CRD, or existing-schema change
  for A1; require a later evidence-backed G2 for any such change.
- Alternatives: R1/R2/R4 public or stored projection now.
- Evidence: A1 can prove the Minimum Vertical Slice representation internally;
  current strict wire tests and absent conversion machinery raise commitment
  cost.
- Compatibility/rollback: strongest possible—no wire/store mutation.
- Evidence Debt: public shape remains open by design.
- Required disposition: explicitly accept zero-change boundary.

### G2-12 — A1 scope and exit criteria

- Recommendation: accept the Section 11 handoff and exact path/stop/exit Gate.
- Alternatives: combine A1/A2 or include controller/schema work (rejected as an
  oversized PR and premature coupling).
- Evidence: Portfolio assigns S5-IMPL-001 one internal interface PR before A2.
- Compatibility/rollback: isolated, dependency-free, unconsumed package.
- Evidence Debt: all integration and production behavior remains for A2+.
- Required disposition: accept/reject/modify, then separately authorize A1.

## 13. Evidence Debt and open decisions

### 13.1 Debt partially addressed by this Gate

- concrete prototype field paths, ownership, cardinality, and serialization;
- exact current wire inventory and logical/physical classification;
- bounded option comparison and reversible choice;
- Definition/Instance separation and native-reference prohibition;
- execution identity minting/propagation/retry/child rules;
- Task/Workflow alias and selected Instance boundary;
- no-change A1 classification and handoff.

### 13.2 Retained debt

- Human G2 disposition and A1 implementation evidence;
- persistent identity mapping/backfill and delete/recreate behavior;
- public API/CRD/version/conversion/defaulting decisions;
- live routing eligibility, freshness, deterministic selection, and rerouting;
- Runtime/Capability Provider interfaces and conformance;
- Capability Definition public representation and authorization evidence;
- exact Condition/Outcome/Recovery vocabulary and transition rules;
- stateful recovery, side effects, replay/idempotency, cancellation;
- Console additive-field tolerance and product/technical projections;
- live mixed-controller versions and rollback rehearsal;
- OpenClaw exact targets; Hermes ED-S5-001; Provider certification;
- State portability, Model routing, multi-tenancy, broader governance.

Open decisions are exactly G2-01–G2-12 plus later independently gated public
representation, Contract freeze, certification, production, and release
decisions. Nothing in this Gate closes ED-S5-001.

## 14. Constraints, contradiction review, and final state

| State | Result |
| --- | --- |
| Five logical resources | preserved; no five-CRD assumption |
| Definition/Instance identity | distinct |
| Native ID authority | prohibited |
| Provider-specific Stable Core fields | none proposed |
| Runtime/Capability Binding | embedded |
| Model Binding | thin embedded foundation |
| Universal Status/Outcome | not introduced |
| Console source of truth | Kubernetes remains authoritative |
| Production/Core change | `0 / NO` |
| Runtime Provider change | `0 / NO` |
| Capability Provider change | `0 / NO` |
| Console change | `0 / NO` |
| Test source change | `0 / NO` |
| Dependency change | `0 / NO` |
| CRD/schema/API change | `0 / NO` |
| Freeze/certification/readiness/release promotion | none |
| Contradictions | `NONE` |

The known ADR drift is not a contradiction introduced by this recommendation:
R3 deliberately avoids changing affected production boundaries. A later A2
Session must stop if it would silently resolve ADR-0003/0004/0005 drift.

## 15. Validation record

| Validation | Result |
| --- | --- |
| baseline and ancestry | pass: `HEAD == origin/main == 040f324359c6db16ee52c55b8f367d1cc4157de9` before edits; PR #45 merge matches |
| source closure/provenance | pass; permitted S5-REL-007 forward import recorded |
| authorized paths | pass: only this artifact, directory README, Project State, and Registry changed |
| inventory/mapping/options/recommendation | pass: three CRDs and all requested implementation surfaces covered; R1–R4 evaluated; R3 selected |
| identity/propagation/domain boundaries | pass by document review: Definition/Instance distinct; end-to-end identity trace complete; native authority and universal Outcome prohibited |
| G2 and A1 handoff completeness | pass: G2-01–G2-12 and all handoff fields present |
| relative links | pass: referenced repository targets exist |
| targeted secret scan | pass: no credential/private-key patterns found in changed artifacts |
| `git diff --check` | pass |
| `make check` | pass: Ruff check, Ruff format check, and 166 pytest tests passed |
| existing warnings | one Starlette/httpx TestClient deprecation warning; unrelated to this documentation Gate |
| required GitHub CI | pass on draft PR #46: Quality Gates and Frontend Quality Gates |

Current artifact state before Human Gate:

```text
SESSION: S5-ARCH-007
LIFECYCLE: REVIEW
AUTHORIZATION: AUTHORIZED
STATUS: PASS_WITH_CONSTRAINTS
RESULT: CORE_REPRESENTATION_G2_CANDIDATE
G2_01_G2_12: PENDING_HUMAN_G2_GATE
PROTOTYPE_REPRESENTATION: RECOMMENDED
SCHEMA_FREEZE: NO
CONTRACT_FREEZE: NO
PRODUCTION_API_COMMITMENT: NO
A1_STATE: RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED
IMPLEMENTATION_STARTED: NO
NEXT_ACTION: WAIT_FOR_HUMAN_G2_REPRESENTATION_API_GATE
```
