# S5-IMPL-002 — A2 Identity Spine Evidence

## Session and provenance

| Field | Value |
| --- | --- |
| Session | `S5-IMPL-002` |
| Lifecycle | `CLOSING` |
| Checkpoint | `B — A2_CONVERGENCE_AND_COMPONENT_SPINE_EXIT` |
| Result | `READY_TO_CLOSE` |
| Authorized Checkpoint A head | `872ca1a4e6b5fd16646f3b93380331782cd5844b` |
| Authorized baseline | `27a4392e94646a3efcdada2818f7124193a13e39` |
| Source Sessions | `S5-IMPL-001`, `S5-REL-009` |
| Source architecture | [S5-ARCH-007](../../../../../architecture/s5/v0.2/S5-ARCH-007-CORE-REPRESENTATION-API-GATE-V1.md) |
| A1 evidence | [S5-IMPL-001](../s5-impl-001/README.md) |

The implementation started from an isolated worktree and the exact
`origin/main` baseline. That commit is the repository-native merge of PR #47
and contains the importable A1 package. The task supplied Human-confirmed
closure and S5-REL-009 recovery provenance; this IMPL Session does not rewrite
Governance metadata merely to forward-import that closure.

## Resolved writable scope and ownership

The durable Portfolio A2 row authorizes the approved A package, narrowly
bounded Operator adapters, and owned tests. The resolved paths are:

- `core/src/agent_core/interface_spine/`;
- `core/tests/test_interface_spine.py`;
- `operator/src/agent_operator/identity_adapter.py`;
- `operator/tests/test_identity_adapter.py`;
- this evidence directory.

The Portfolio single-writer map assigns Task controller integration to
S5-IMPL-003 and Workflow controller integration to S5-IMPL-008. Therefore
`task_controller.py` and `workflow_controller.py` are unchanged. Public CRDs,
schemas, Runtime/Capability Providers, Gateway, Console, dependencies,
migrations, and release/governance material are unchanged.

## Implementation structure and propagation path

The dependency direction is:

```text
component-only Operator adapter
  -> A2 internal interface spine
  -> A1 representation values and repository port
```

The Core package has no Operator or Kubernetes import. A Definition-facing
request preserves the current namespaced `Task.spec.agentRef.name` address.
The builder projects it to `AgentDefinitionRef`, invokes the injected selector,
validates selected Instance ownership and effective Binding, invokes the
injected execution-identity minter exactly once, and builds one immutable
internal envelope.

The envelope contains typed Definition, Instance, Platform Execution Identity,
desired/effective Binding, selection evidence, optional opaque native
correlations, and an optional internal source Task reference. Adding native
evidence returns a new envelope while retaining the exact Platform identity,
selected Instance, and effective Binding.

```text
ROUTING_POLICY: PROTOTYPE_ONLY / REPLACEABLE / NOT_FROZEN
POLICY_IMPLEMENTATION: PROTOTYPE_LEXICAL_INSTANCE_ID_NOT_FROZEN
ROUTING_SEMANTICS: NOT_PRODUCTION_READY
EXECUTION_IDENTITY_PERSISTENCE: NOT_INTEGRATED
RETRY_PROPAGATION: NOT_YET_PROVEN
RECONCILIATION_REPLAY_STABILITY: NOT_YET_PROVEN
RESTART_BEHAVIOR: NOT_YET_PROVEN
EXECUTION_ENVELOPE_CONTRACT: INTERNAL / VERSION_UNFROZEN
```

The lexical policy is deterministic under input reordering and exists only for
component evidence. An alternative injected policy proves ambiguous selection
can fail closed. Neither vocabulary nor policy is a public Contract.

## Operator adapter and active-consumer state

```text
OPERATOR_ADAPTER_IMPLEMENTED: YES — COMPONENT_ONLY
DEFAULT_TASK_PATH_CONSUMES_A2: NO
ACTIVE_RUNTIME_BEHAVIOR_CHANGE: NO
EXISTING_PRODUCTION_PATH_INTEGRATION: NO
TASK_CONTROLLER_CHANGE: NO
WORKFLOW_CONTROLLER_CHANGE: NO
```

The adapter maps the existing Task target into the internal request and does
not invoke a Runtime or write status. It is intentionally not imported by the
Task controller. It is the only non-test Operator import of A2, but it is not
an active production-path consumer. Invalid Task targets and incomplete source
references raise the typed A2 `InvalidDefinitionProjectionError`; no fallback
derives an Instance or Execution identity from Definition or native identity.

```text
ACTIVE_CONSUMER_COUNT: 0
A2_ACTIVE_CONTROLLER_INTEGRATION: DEFERRED_TO_A3_WITH_EVIDENCE_REQUIREMENTS
A2_RUNTIME_INTEGRATION: NOT_STARTED
```

## Reconciliation and idempotency analysis

The current Task handler uses a Kubernetes Task create event as a new logical
execution. `create_task` immediately writes Running status and synchronously
invokes the Runtime through retry handling. A retry is an HTTP invocation
attempt within the same handler call. No current internal execution envelope or
Platform Execution Identity is retained.

Blindly activating A2 there would mint on every handler invocation. A replay
or controller restart could therefore mint another identity, and the current
handler has no durable idempotency key that proves duplicate Runtime invocation
cannot occur. Selection could also change if eligible realizations changed.
No-Instance would fail before invocation, but mapping that internal failure to
existing Task status is A3 integration behavior and is not introduced here.

Consequently A2 keeps the adapter component-only. Repeated component
builder calls are explicitly separate envelopes with separately minted IDs;
they do not claim replay equivalence. Retry propagation, child execution
semantics, restart behavior, durable selection, and duplicate-execution
prevention remain unresolved rather than being silently frozen.

## Compatibility and rollback

```text
V0_1_COMPATIBILITY: PASS
CURRENT_MANIFEST_CHANGE_REQUIRED: NO
PUBLIC_WIRE_CHANGE: NO
PUBLIC_API_CHANGE: NO
SCHEMA_CHANGE: NO
CRD_CHANGE: NO
BREAKING_WIRE_CHANGE: NO
MIGRATION: NO
DUAL_WRITE: NO
DEPENDENCY_CHANGE: NO
```

Existing Agent, Task and Workflow objects are not mutated. The default Task,
Workflow, Native Runtime, Gateway, and Console paths are unchanged. Rollback is
file removal of the A2 Core modules, component adapter, tests, and this evidence
only; it requires no persisted-resource update, CRD rollback, data rewrite,
Runtime cleanup, or dual-write cleanup.

## Checkpoint B code and test-quality review

The Checkpoint B audit confirms that Core imports only A1 domain/repository
ports and the standard library; Operator depends on Core, never the reverse;
no import cycle or global selector, repository, minter, or clock exists; and
the selector and minter are explicit injected dependencies. Records are frozen
and native correlation inputs are defensively copied. Definition, Instance,
Execution, and native identity types remain runtime-distinct. Desired and
effective Bindings retain distinct owner types. Package exports are intentional
internal surfaces and expose no serialization or compatibility promise.

The tests map to Definition projection and non-mutation; typed invalid-input
failure; one-to-many and deterministic prototype selection; replaceable
ambiguity policy; no eligible, duplicate, mismatched, and missing-Binding
failures; one-time execution minting and unchanged propagation; native,
Definition, and Instance substitution rejection; envelope mismatch,
immutability, and defensive-copy invariants; Binding propagation; realization
replacement; component adapter behavior; v0.1 wire compatibility; exact
inactive-consumer scope; and migration-free rollback.

## Tests and validation

The baseline has 209 tests. A2 adds 27 component tests for projection,
selection, ambiguity, duplicate and invalid identities, Binding ownership,
one-time minting, unchanged handoff, native-ID separation, immutable envelope,
realization replacement, repeated-build semantics, and Operator mapping.

Final validation results:

- exact clean baseline: `209 passed`, one existing warning;
- targeted A2 component tests: `27 passed`;
- full changed head: `236 passed`, one existing warning;
- Ruff check and format check: passed;
- `make check`: passed (`236 passed`);
- `git diff --check`: passed;
- changed-path and shared-owner audit: passed;
- Core import-direction, import smoke test, and bytecode compilation: passed;
- public-wire and CRD/schema diff: empty/passed;
- dependency and lockfile diff: empty/passed;
- targeted secret-pattern scan: passed;
- evidence relative-link target validation: passed;
- active-consumer and rollback-boundary audit: passed.

The warning is the existing FastAPI TestClient import warning that Starlette's
`httpx` integration is deprecated; A2 introduced no new warning. GitHub CI
must pass on the exact pushed head before Human review completes.

## A3 durable Portfolio handoff

```text
A3_SESSION_RESOLUTION: PASS / UNIQUE
A3_SESSION_ID: S5-IMPL-003
A3_TITLE: A3 Compatibility Interpreter
A3_SESSION_TYPE: IMPL
A3_PREDECESSOR: S5-IMPL-002
A3_EFFORT_RANGE: 1–3 sessions / medium
A3_EXIT_GATE: Compatibility Gate
A3_STATE: RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED
```

A3's objective is to translate current Agent/Task/Workflow references into the
internal spine for the bounded slice, or prove that a later public migration
Gate is necessary. Its likely writable scope is a bounded compatibility
interpreter and matching tests adjacent to
`operator/src/agent_operator/task_controller.py` and `resources.py`;
`workflow_controller.py` is only optional and serialized with its S5-IMPL-008
owner. The Task schema/controller has the single-writer sequence S5-IMPL-003,
then S5-IMPL-008 after handoff.

A3 must preserve existing CRDs absent a separate G2 Gate and must not perform
durable bulk backfill, destructive conversion, or cutover. Required evidence
includes legacy manifests, mixed presence/absence, ambiguous mapping,
migration-free rollback, no silent identity remap, v0.1 fallback, logical-new
execution versus replay, identity retention/reuse, duplicate invocation
prevention, failure/retry, restart, selected Instance validation, and current
`make check`. Exit requires one current Task to enter A2 without behavior
regression or an explicit architecture escalation. Its direct downstream
consumer is the Minimum Vertical Slice/current Task bridge; S5-IMPL-005 and
S5-IMPL-008 depend on A3, while S5-IMPL-004, S5-IMPL-007, and S5-IMPL-009 may
proceed from their separately stated A2 prerequisites.

## Evidence Debt, limitations, and Stop Conditions

Retained A1 debt remains authoritative. A2 additionally retains execution
identity persistence, reconciliation replay stability, retry propagation,
child execution semantics, durable Instance selection, production routing
policy, active controller integration, controller restart, duplicate execution
prevention, persistent repository, mixed-version deployment, public selected
Instance projection, Console projection, and Runtime Provider integration.

`ED-S5-001` remains `OPEN`. No Schema/Contract Freeze, Certification,
Production Readiness, or Release Acceptance is granted.

No Stop Condition was triggered. A constraint was identified and the Stop
Condition was avoided: active controller integration was deferred before the
boundary because reconciliation replay, restart, identity persistence, and
duplicate-execution safety are not proven. Activating the default Task path
without that evidence would trigger a Stop Condition.

```text
STOP_CONDITIONS_TRIGGERED: NO
CONSTRAINT_IDENTIFIED: ACTIVE_CONTROLLER_INTEGRATION_DEFERRED
DEFER_REASON: RECONCILIATION_REPLAY_RESTART_AND_DUPLICATE_EXECUTION_SAFETY_NOT_PROVEN
STOP_CONDITION_AVOIDED: YES
A2_IMPLEMENTATION: COMPLETE_FOR_COMPONENT_TESTED_IDENTITY_SPINE
A2_EXIT: READY_FOR_HUMAN_CLOSE_CONFIRMATION
HUMAN_CLOSE_CONFIRMATION: PENDING
SESSION_CLOSED: NO
```
