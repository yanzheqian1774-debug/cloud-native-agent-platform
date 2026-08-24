# S5-IMPL-003 — A3 Compatibility Interpreter Evidence

## Session and provenance

| Field | Value |
| --- | --- |
| Session | `S5-IMPL-003` |
| Track | `A3 — COMPATIBILITY_INTERPRETER` |
| Lifecycle | `CLOSING` |
| Checkpoint | `B — A3_SAFETY_CONVERGENCE_AND_EXIT_CANDIDATE` |
| Result | `READY_TO_CLOSE` |
| Authorized baseline | `a630db68daf29778cedcb8e3826f73d1802c49f0` |
| Source Session | `S5-IMPL-002` |
| Source integration | `S5-REL-010` |
| Source PR | `#48` |
| S5-REL-010 provenance | `HUMAN_CONFIRMED_GIT_VERIFIED / FORWARD_IMPORTED_BY_S5_IMPL_003` |

The Human prerequisite gate classified the missing repository-native terminal
record as metadata lag only. It confirmed S5-REL-010 as `CLOSED / COMPLETED /
PASS / SESSION_CLOSED`, with reopening prohibited, source head
`e3e4d10711e6d89be2bfd9b9d383a89c19ff3c0d` and merge/durable-main commit
`a630db68daf29778cedcb8e3826f73d1802c49f0`. The minimal forward import is in
`PROJECT_STATE.md` and `docs/governance/REGISTRY.md`; no open PR or other active
writable Session owned either file when the collision audit ran.

## Current flow and integration state

Before A3, a Task create event read same-namespace `spec.agentRef.name`, wrote
`Running`, and synchronously invoked the same-named Agent Service. Retries were
HTTP attempts inside that handler. Workflow created ordinary owned Task
resources with the same public Task shape. A2 had no active controller
consumer.

The A3 flow is:

```text
current Task UID + namespaced agentRef.name
  -> read exactly one current Agent object
  -> validate Agent namespace/name/UID/runtime evidence
  -> derive one typed compatibility Instance from namespace/name/Agent UID
  -> project agentRef.name as Definition identity
  -> derive/recover Platform Execution Identity from namespace/name/Task UID
  -> build immutable A2 InternalExecutionEnvelope
  -> persist existing Running status as replay barrier
  -> invoke unchanged same-named v0.1 Agent Service
  -> retain the same envelope across in-handler retry attempts
```

Workflow behavior is unchanged: `build_workflow_task` still emits the exact
v0.1 Task wire, and the resulting Task enters this same interpreter without a
Workflow controller change.

```text
COMPATIBILITY_INTERPRETER: INTERNAL / REPLACEABLE / ACTIVE_TASK_CONSUMER
TASK_CONTROLLER_INTEGRATION: ENABLED
RESOURCES_INTEGRATION: EXISTING_WORKFLOW_TASK_BUILDER_PROVEN_COMPATIBLE / UNCHANGED
WORKFLOW_CONTROLLER_CHANGE: NONE
ACTIVE_A2_CONTROLLER_CONSUMERS: 1
```

## Identity and logical-execution boundary

The immutable Kubernetes Task UID is the new-logical-execution boundary.
Interpreting the same UID recovers the same Platform Execution Identity.
Deleting and recreating a Task produces a different Kubernetes UID and a new
Platform identity even if namespace/name are reused. No public status, spec,
annotation, CRD, or schema field is needed for retention.

The Task UID is only a seed. The root identity is a typed
`PlatformExecutionIdentity` containing UUIDv5 over the domain-separated input
`agentos.io/v0.2/task-execution/<namespace>/<task-name>/<task-uid>`. It is not
the raw Task UID. Namespace and resource name make the current Kubernetes
scope explicit. Cluster/tenant identity is not modeled, so the derivation is
scoped to one current Kubernetes control plane and is not a future global
identity Contract.

The current Agent remains Definition-like and realization-oriented. A3 does
not call its name an Instance ID. It derives a distinct typed
`AgentInstanceId` containing UUIDv5 over the domain-separated input
`agentos.io/v0.2/legacy-agent-instance/<namespace>/<agent-name>/<agent-uid>`.
The result is neither the raw Agent UID nor Definition identity. Replacement
produces a new internal Instance ID. Terminating, missing, mismatched,
malformed, or ambiguous evidence fails closed before Runtime invocation.

```text
COMPATIBILITY_INSTANCE_MAPPING: ONE_TRANSITIONAL_COMPATIBILITY_INSTANCE_PER_CURRENT_AGENT_UID
COMPATIBILITY_INSTANCE_SCOPE: INTERNAL / TRANSITIONAL / REPLACEABLE / NOT_FROZEN
FINAL_DEFINITION_TO_INSTANCE_CARDINALITY: 1:N / UNCHANGED
```

The root Execution Identity is distinct from `status.attempts`. A3 implements
no typed attempt identity: `ATTEMPT_IDENTITY: DEFERRED`; the existing positive
attempt number remains Task status evidence only. The current Runtime returns
no native invocation identity. Any future native ID remains correlation-only
and cannot substitute for root Execution, attempt, Instance, or Definition
identity.

Desired and effective Runtime Binding values are distinct A1 owner types. Both
are derived only from the current Agent runtime intent for this compatibility
path. The effective Binding does not claim Provider lifecycle resolution.
Native identifiers are never accepted as Task UID, Instance ID, or Platform
Execution Identity and remain correlation-only; the current v0.1 Runtime wire
returns no native correlation ID to A3.

## Replay, retry, duplicate, and restart safety

| Behavior | Classification | Evidence and limitation |
| --- | --- | --- |
| Replay versus new execution | `PROVEN` | Same Task UID rebuilds an equal envelope; a new UID produces a unique Platform Execution Identity; terminal replay is a no-op. |
| Retry | `BOUNDED_WITH_LIMITATION` | All allowed HTTP attempts receive the same immutable root identity. Connect/pre-send and explicit retryable HTTP failures retain current retry behavior. Read/write/protocol failures are outcome-indeterminate and now fail closed without automatic retry. No attempt identity or Runtime idempotency key exists. |
| Duplicate Runtime invocation | `BOUNDED_WITH_LIMITATION` | `Running` is durably written before invocation. A replay observing `Running` fails with `ExecutionStateUnknown` and performs zero invocation. This is not a distributed compare-and-set or Runtime idempotency protocol. |
| Restart | `BOUNDED_WITH_LIMITATION` | Restart before `Running` may safely reconstruct and execute. Restart after `Running` prevents re-invocation but cannot determine whether the previous Runtime request completed. |

Failure before invocation produces typed missing/invalid/conflicting evidence
or a retryable Agent lookup error and performs no Runtime call. Failure after
the invocation begins is conservatively treated as outcome-unknown on replay.
There is no silent remapping, new selection, or automatic fallback invocation.

## Persisted replay barrier and crash-window matrix

The replay barrier is the existing public `Task.status.phase: Running` value;
there is no new field or schema. `patch_task_status` writes the complete
Running status synchronously before `invoke_compatible_agent`. If that write
fails, the exception aborts the handler and the Runtime is not invoked. An
existing terminal phase is a no-op. Existing Running is ambiguous and becomes
terminal `Failed / ExecutionStateUnknown` without another Runtime call. The
terminal patch is persisted by Kopf after the handler returns.

| Window | Persisted evidence | Replay and side-effect behavior | Classification |
| --- | --- | --- | --- |
| C0 — before Running write | No A3 execution evidence | Runtime has not been called; reconstruction with the same Task UID may invoke | `PROVEN` |
| C1 — after Running, before invocation | `Running`, attempts `0` | Runtime has no side effect; replay refuses invocation and reports unknown because it cannot prove the exact crash point | `BOUNDED_WITH_LIMITATION` |
| C2 — during invocation | `Running` | Runtime may have produced side effects; replay never invokes; outcome cannot be recovered | `OUTCOME_INDETERMINATE / REQUIRES_RUNTIME_IDEMPOTENCY` |
| C3 — after Runtime success, before terminal write | `Running` | Runtime result/side effects may exist; replay never invokes; success cannot be reconstructed | `OUTCOME_INDETERMINATE` |
| C4 — after Runtime failure, before terminal write | `Running` | Runtime may have produced partial side effects; replay never invokes; failure detail may be lost | `OUTCOME_INDETERMINATE` |
| C5 — after terminal write | Terminal phase and outcome | Replay is a no-op and performs zero invocation | `PROVEN` |

This is not exactly-once execution. It prefers possible false-negative/unknown
outcome over automatic duplicate invocation after a persisted Running state.

## Concurrent reconciliation and retry analysis

Kopf normally serializes handlers for one object in one process, but A3 adds no
global lock. A test with two handlers holding the same stale non-Running status
proves both can write Running and invoke. Kubernetes resource-version CAS,
multi-process synchronization, distributed locking, and a Runtime idempotency
key are not provided. Duplicate prevention is therefore bounded to observed
persisted status and normal framework serialization.

Within one handler, every retry uses the same immutable envelope and root
Execution Identity; `status.attempts` counts calls. Connect failures and
explicit retryable HTTP responses use the existing retry loop. Read, write,
and remote-protocol failures may occur after delivery, so A3 maps them to
non-retryable `ExecutionOutcomeUnknown`. They are not automatically treated as
proof of non-execution. No native invocation correlation is available.

```text
DUPLICATE_EXECUTION_PREVENTION: BOUNDED_WITH_LIMITATION
DISTRIBUTED_CAS: NOT_PROVIDED
RUNTIME_IDEMPOTENCY_KEY: NOT_PROVIDED
```

## Fallback and active-path classification

There is no conditional identity-bypass fallback. The compatibility path is
always interpreted first, then calls the unchanged v0.1 same-named Service
target from the validated Definition in the envelope. Invalid evidence cannot
activate the Service path, substitute Definition for Instance, or discard the
root Platform identity. The compatibility invocation is deterministic and
test-observable; it is not a competing source of truth. Source rollback
restores the prior direct call without data migration.

```text
FALLBACK_AUTHORITY: COMPATIBILITY_ONLY / NOT_A_COMPETING_SOURCE_OF_TRUTH
ACTIVE_TASK_PATH_CHANGE: YES — INTERNAL_PRE_INVOCATION_IDENTITY_AND_REPLAY_PATH
ACTIVE_RUNTIME_TARGET_CHANGE: NO
PRODUCTION_CORE_CHANGE: YES — INTERNAL_COMPATIBILITY_INTERPRETER
OPERATOR_PRODUCTION_PATH_CHANGE: YES — BOUNDED_TASK_CONTROLLER_INTEGRATION
EXTERNAL_SIDE_EFFECT_ORDER_CHANGE: YES — Agent read/interpretation now precedes Running; Runtime remains after Running
```

## Test matrix

| Area | Covered evidence |
| --- | --- |
| Legacy/v0.1 compatibility | Current Agent and Task shapes, unchanged `agentRef.name`, unchanged Runtime request, unchanged Workflow-created Task wire |
| Projection | Same-namespace Definition projection and no input mutation |
| Missing/ambiguous/mixed evidence | Missing Agent, multiple candidates, namespace/name conflict, missing UID/runtime, terminating Agent |
| Instance safety | Typed ID distinct from Definition, replacement changes Instance ID, invalid evidence rejected |
| Execution identity | Typed Platform ID, deterministic replay recovery, new-Task uniqueness, native-ID substitution rejection |
| Retry/replay/restart | Same root envelope across retry, terminal no-op, persisted-Running replay zero-invocation, status-write fault injection, unknown-outcome suppression |
| Concurrency | Two stale handlers demonstrate the absence of distributed CAS and the retained duplicate limitation |
| Runtime Binding | Desired/effective typed separation, current runtime type/image projection, secret-shaped extra fields not imported |
| Workflow | Workflow-generated Task enters A3 without public-wire or controller changes |
| Rollback | Active-consumer path inventory is exact; no persisted A3 fields, migration, backfill, dependency, or lockfile change |

Baseline: `236` tests. A3 adds `47` tests. Full changed-head result:
`283 passed`, with one existing Starlette/httpx deprecation warning.

## Compatibility and changed paths

```text
PUBLIC_API_CHANGE: NO
SCHEMA_CHANGE: NO
CRD_CHANGE: NO
EXISTING_SCHEMA_CHANGE: NO
BREAKING_WIRE_CHANGE: NO
MIGRATION: NO
BACKFILL: NO
DUAL_WRITE: NO
DEPENDENCY_CHANGE: NO
V0_1_COMPATIBILITY: PASS
KUBERNETES_SOURCE_OF_TRUTH: PRESERVED
```

Implementation paths:

- `operator/src/agent_operator/compatibility_interpreter/`;
- `operator/src/agent_operator/task_controller.py`;
- matching Operator tests;
- one narrow Core active-consumer/rollback test;
- this evidence directory;
- minimal S5-REL-010 provenance rows in the two authorized governance files.

`operator/src/agent_operator/resources.py` and
`operator/src/agent_operator/workflow_controller.py` are unchanged. Public
CRDs/schemas, Runtime and Capability Providers, Gateway, Console, ADR bodies,
dependencies, lockfiles, release files, OpenClaw, and Hermes are unchanged.

## Rollback and fallback

Rollback is a source-only revert of the interpreter, Task-controller bridge,
tests, evidence, and minimal forward-import rows. No resource rewrite, data
migration, backfill, dual-write cleanup, Runtime cleanup, or schema rollback is
required. The v0.1 Service URL and `{input}`/`{output}` wire remain the actual
invocation path. Invalid A3 evidence fails closed; it never silently bypasses
the interpreter. A source rollback restores the prior direct path.

## Evidence Debt and limitations

- Exact Runtime outcome recovery after a controller crash is not available.
- The `Running` barrier bounds duplicates but is not a cross-controller CAS or
  downstream Runtime idempotency key.
- Two concurrent handlers with stale status can both invoke; normal Kopf
  per-object serialization is a framework bound, not distributed proof.
- The compatibility Instance is deterministic internal evidence, not a
  first-class Agent Instance resource or production routing policy.
- Cluster/tenant identity is not part of the deterministic seed; identities
  are scoped to the current Kubernetes control plane.
- Effective Binding is compatibility evidence, not Provider certification.
- Platform identity is not propagated through the unchanged v0.1 Runtime wire;
  downstream propagation belongs to later authorized Runtime integration.
- No native correlation is available from the current Runtime response.
- A2/A3 internal envelopes and vocabulary remain unfrozen.
- ED-S5-001 remains `OPEN`.

## Stop Conditions and handoff

No public field, Workflow change, migration, dependency, native authority, or
v0.1 break was required. Replay is distinguishable by Task UID, identity is
recoverable without public persistence, and duplicate invocation is bounded by
the existing durable Running transition. The restart limitation is reported
honestly and is not promoted to exactly-once execution.

```text
FREEZE_STATE: UNCHANGED / NO CONTRACT OR SCHEMA FREEZE
CERTIFICATION_STATE: NOT_GRANTED
PRODUCTION_READINESS: NOT_GRANTED
RELEASE_ACCEPTANCE: NOT_GRANTED
IMPLEMENTATION_STARTED: YES
A3_IMPLEMENTATION: COMPLETE_FOR_BOUNDED_COMPATIBILITY_INTERPRETER
A3_EXIT: READY_TO_CLOSE
SESSION_CLOSED: NO
NEXT_ACTION: WAIT_FOR_HUMAN_CLOSE_CONFIRMATION
NEXT_GATE: Human S5-IMPL-003 Close Confirmation
```
