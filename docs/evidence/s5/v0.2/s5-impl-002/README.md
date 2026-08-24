# S5-IMPL-002 — A2 Identity Spine Evidence

## Session and provenance

| Field | Value |
| --- | --- |
| Session | `S5-IMPL-002` |
| Checkpoint | `A — IDENTITY_SPINE_AND_EXECUTION_ENVELOPE_CANDIDATE` |
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
ROUTING_POLICY: PROTOTYPE / NOT_FROZEN
POLICY_IMPLEMENTATION: PROTOTYPE_LEXICAL_INSTANCE_ID_NOT_FROZEN
EXECUTION_IDENTITY_PERSISTENCE: NOT_YET_INTEGRATED
RETRY_PROPAGATION: NOT_YET_PROVEN
RECONCILIATION_REPLAY_STABILITY: NOT_YET_PROVEN
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
an active production-path consumer.

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

Consequently Checkpoint A keeps the adapter component-only. Repeated component
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

## Tests and validation

The baseline has 209 tests. A2 adds 22 component tests for projection,
selection, ambiguity, duplicate and invalid identities, Binding ownership,
one-time minting, unchanged handoff, native-ID separation, immutable envelope,
realization replacement, repeated-build semantics, and Operator mapping.

Final validation results:

- exact clean baseline: `209 passed`, one existing warning;
- targeted A2 component tests: `22 passed`;
- full changed head: `231 passed`, one existing warning;
- Ruff check and format check: passed;
- `make check`: passed (`231 passed`);
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

## Evidence Debt, limitations, and Stop Conditions

Retained A1 debt remains authoritative. A2 additionally retains execution
identity persistence, reconciliation replay stability, retry propagation,
child execution semantics, durable Instance selection, production routing
policy, active controller integration, controller restart, duplicate execution
prevention, persistent repository, mixed-version deployment, public selected
Instance projection, Console projection, and Runtime Provider integration.

`ED-S5-001` remains `OPEN`. No Schema/Contract Freeze, Certification,
Production Readiness, or Release Acceptance is granted.

The active-controller integration Stop Condition was encountered during
analysis and respected: without persistence/idempotency evidence, consuming A2
from the default Task path could duplicate identity and Runtime execution. This
does not block the authorized component-level A2 candidate.

```text
A2_EXIT_STATUS: PENDING_HUMAN_IMPLEMENTATION_REVIEW
A3_STATE: NOT_ACTIVE / NOT_AUTHORIZED
```
