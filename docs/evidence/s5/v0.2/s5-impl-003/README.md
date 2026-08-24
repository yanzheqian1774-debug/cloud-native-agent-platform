# S5-IMPL-003 — A3 Compatibility Interpreter Evidence

## Session and provenance

| Field | Value |
| --- | --- |
| Session | `S5-IMPL-003` |
| Track | `A3 — COMPATIBILITY_INTERPRETER` |
| Lifecycle | `REVIEW` |
| Checkpoint | `A — COMPATIBILITY_INTERPRETER_AND_SAFE_TASK_INTEGRATION_CANDIDATE` |
| Result | `A3_IMPLEMENTATION_CANDIDATE` |
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
  -> derive one typed compatibility Instance from Agent UID
  -> project agentRef.name as Definition identity
  -> derive/recover Platform Execution Identity from Task UID
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

The current Agent remains Definition-like and realization-oriented. A3 does
not call its name an Instance ID. It derives a distinct typed compatibility
Instance ID from the immutable Agent UID and validates that the observed Agent
matches the Task's namespace/name. Replacement produces a new internal
Instance ID. Terminating, missing, mismatched, malformed, or ambiguous evidence
fails closed before Runtime invocation.

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
| Retry | `PROVEN` | All HTTP attempts in one handler receive the same immutable envelope and Platform identity; existing attempt/status semantics remain unchanged. |
| Duplicate Runtime invocation | `BOUNDED_WITH_LIMITATION` | `Running` is durably written before invocation. A replay observing `Running` fails with `ExecutionStateUnknown` and performs zero invocation. This is not a distributed compare-and-set or Runtime idempotency protocol. |
| Restart | `BOUNDED_WITH_LIMITATION` | Restart before `Running` may safely reconstruct and execute. Restart after `Running` prevents re-invocation but cannot determine whether the previous Runtime request completed. |

Failure before invocation produces typed missing/invalid/conflicting evidence
or a retryable Agent lookup error and performs no Runtime call. Failure after
the invocation begins is conservatively treated as outcome-unknown on replay.
There is no silent remapping, new selection, or automatic fallback invocation.

## Test matrix

| Area | Covered evidence |
| --- | --- |
| Legacy/v0.1 compatibility | Current Agent and Task shapes, unchanged `agentRef.name`, unchanged Runtime request, unchanged Workflow-created Task wire |
| Projection | Same-namespace Definition projection and no input mutation |
| Missing/ambiguous/mixed evidence | Missing Agent, multiple candidates, namespace/name conflict, missing UID/runtime, terminating Agent |
| Instance safety | Typed ID distinct from Definition, replacement changes Instance ID, invalid evidence rejected |
| Execution identity | Typed Platform ID, deterministic replay recovery, new-Task uniqueness, native-ID substitution rejection |
| Retry/replay/restart | Same envelope across retry, terminal no-op, persisted-Running replay zero-invocation, unknown-outcome failure |
| Runtime Binding | Desired/effective typed separation, current runtime type/image projection, secret-shaped extra fields not imported |
| Workflow | Workflow-generated Task enters A3 without public-wire or controller changes |
| Rollback | Active-consumer path inventory is exact; no persisted A3 fields, migration, backfill, dependency, or lockfile change |

Baseline: `236` tests. A3 adds `31` tests. Full changed-head result:
`267 passed`, with one existing Starlette/httpx deprecation warning.

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
- The compatibility Instance is deterministic internal evidence, not a
  first-class Agent Instance resource or production routing policy.
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
A3_EXIT: A3_IMPLEMENTATION_CANDIDATE
SESSION_CLOSED: NO
NEXT_ACTION: WAIT_FOR_HUMAN_A3_IMPLEMENTATION_REVIEW_GATE
NEXT_GATE: Human S5-IMPL-003 A3 Implementation Review Gate
```
