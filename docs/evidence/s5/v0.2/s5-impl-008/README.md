# S5-IMPL-008 — MVS execution integration candidate evidence

## State

- Session: `S5-IMPL-008`
- Checkpoint: `A — MVS_TASK_RUNTIME_CAPABILITY_OUTCOME_INTEGRATION_CANDIDATE`
- Result candidate: `MVS_EXECUTION_INTEGRATION_CANDIDATE`
- Lifecycle target: `REVIEW`
- Session closed: `NO`
- Authorized resume baseline: `73de37f328f9303c43a7de0a92da334639bad660`
- Document/File: `NOT_STARTED / POST_MVS / NOT_AUTHORIZED`

This evidence supports a bounded v0.2 Technical Preview candidate. It does not
grant release acceptance, Provider certification, production readiness,
exactly-once execution, permanent Operator ownership, or Contract/schema
freeze.

## Architecture provenance and O1 constraints

The implementation follows S5-ARCH-008's Human-selected `O1 —
BOUNDED_OPERATOR_HOSTED_MVS_INTEGRATION`. The Task controller remains a thin
Kubernetes adapter and replay-barrier coordinator. Use-case sequencing lives in
`agent_operator.execution_coordinator`, which imports no Kopf or Kubernetes
controller behavior and receives Native and Capability collaborators
explicitly.

ADR-0003 remains `Accepted / Partial / unchanged / not superseded`. Physical
Operator hosting is temporary for this MVS. The coordinator is an extraction
seam, not a claim that the Operator permanently owns execution or business
orchestration.

## Baseline recovery

- Existing worktree: `/private/tmp/s5-impl-008-workflow-outcome-document-extension`
- Existing branch: `codex/s5-impl-008-workflow-outcome-document-extension`
- Previous HEAD: `f6309c163194ebc7f64a21661770a5a43252e3fc`
- `origin/main`: `73de37f328f9303c43a7de0a92da334639bad660`
- Update: `git merge --ff-only origin/main`
- Intervening history: S5-ARCH-008 candidate plus PR #54 integration only.
- Rebase/reset/cherry-pick/force update: not used.

Resumed-baseline validation before source mutation:

- full pytest: `446 passed`, one known Starlette/httpx deprecation warning;
- Ruff lint: pass;
- Ruff formatting: `83 files already formatted`;
- `make check`: pass, `446 passed`;
- frontend lint: pass;
- frontend build: pass.

## Previous execution sequence

1. Observe a current Task and preserve `Task.spec.agentRef.name` as the
   Definition-facing reference.
2. Use the A3 compatibility interpreter to select current Agent evidence and
   derive the stable Platform Execution Identity from the Task UID.
3. Persist `Running` as the replay barrier.
4. Invoke the same-name Agent Service directly over the legacy HTTP path.
5. Apply current retry classification and project the result into current Task
   status.
6. Workflow continues to create and observe current Task resources, propagate
   results, skip blocked nodes, and aggregate terminal phases.

## Candidate execution sequence

1. The Task controller observes the current Task, loads the current Agent
   evidence once, and invokes the existing A3 compatibility interpreter.
2. A3 preserves the Definition reference, selected Agent Instance evidence,
   desired/effective Binding, and Task-UID-derived root Platform Execution
   Identity.
3. The controller builds an immutable internal execution context and persists
   the existing `Running` replay barrier before any possible effect.
4. The controller calls the Kubernetes-independent coordinator.
5. The coordinator validates and invokes the exact deterministic Native mock
   profile through `NativeRuntimeProvider`; mismatch rejects before its
   invoker. Native IDs remain correlation-only.
6. If the current Agent declares a capability, one bounded internal request is
   built for the first declared capability. No Task or Workflow wire field is
   added.
7. The coordinator consumes `CapabilityGateway`; authorization occurs before
   the injected synthetic REST Provider. DENY performs zero Provider calls and
   ALLOW performs exactly one.
8. Runtime and optional Capability evidence are normalized into an internal,
   domain-specific, version-unfrozen Outcome carrying the unchanged root
   Platform identity.
9. The controller maps that Outcome to the existing Task status shape. Unknown
   or ambiguous effects fail closed and are never projected as success.
10. Existing Workflow Task creation, observation, DAG, result propagation,
    skip, and aggregation behavior remains unchanged.

## Changed-path ownership map

| Path | Owner / purpose |
| --- | --- |
| `operator/src/agent_operator/execution_coordinator.py` | S5-IMPL-008; controller-independent coordinator, explicit ports/context, internal Outcome, deterministic synthetic wiring |
| `operator/src/agent_operator/task_controller.py` | S5-IMPL-008 after A3 handoff; thin adapter and existing replay/status projection |
| `operator/tests/test_execution_coordinator.py` | S5-IMPL-008; deterministic component and cross-boundary contract tests |
| `operator/tests/test_task_controller.py` | S5-IMPL-008; active consumer, replay, retry, identity and status compatibility |
| `core/tests/test_compatibility.py` | Explicitly authorized compatibility allowlist extension only; no Core implementation change |
| `docs/evidence/s5/v0.2/s5-impl-008/README.md` | Required S5-IMPL-008 evidence |

No Runtime Provider, Capability Gateway, Core representation, Workflow
controller, resource builder, public API, HTTP wire, CRD, schema, dependency,
lockfile, governance, ADR, Console, experiment, Document/File, OpenClaw, or
Hermes path changes.

## Controller-to-coordinator boundary

The controller owns Kubernetes evidence loading, terminal/replay checks,
persisting the `Running` barrier, collaborator construction, and projection to
the existing Task status. The coordinator owns only bounded sequencing of the
existing Native and Capability boundaries and internal Outcome normalization.

The explicit execution context carries:

- Definition reference;
- selected Agent Instance evidence;
- Platform Execution Identity;
- desired/effective Runtime Binding;
- exact deterministic Native configuration; and
- optional requested Capability and authorization evidence.

The coordinator is testable without Kubernetes event handling, network, a
global repository, global selector, global minter, or clock.

## Active-consumer inventory

| Boundary | Before | Candidate |
| --- | ---: | ---: |
| Native Provider default Task-path consumers | 0 | 1 |
| Capability Gateway default Task-path consumers | 0 | 1 when a capability is requested |

The legacy `invoke_agent` function remains as a rollback-compatible v0.1 seam
but is no longer the default Task execution path in this candidate. Real model
and real external network behavior are not activated.

## Identity and invocation ordering

- The Kubernetes Task UID remains the logical execution boundary.
- Reinterpreting the same UID recovers the same Platform Execution Identity.
- The same identity is used by the Native request, Native evidence, Capability
  request, authorization context, Provider request, Capability Outcome, and
  internal Task Outcome.
- Native and Capability native IDs remain optional correlation evidence and
  cannot substitute for Platform identity.
- Capability authorization is resolved before Provider invocation.
- Invalid, absent, malformed, ambiguous, or denied authorization fails closed.

## Internal Outcome examples

Successful Runtime-only execution is classified `SUCCEEDED` with requested
and effective Runtime evidence, Runtime result, no Capability evidence, and
`retry_safe=false`.

Successful combined execution is classified `SUCCEEDED` with the same root
Platform identity in Runtime and Capability evidence. The existing Task result
remains the Runtime output; internal Capability evidence is not serialized into
an unapproved public field.

Denied capability execution is classified `DENIED`, contains the authorization
decision and zero-call evidence, and maps to existing Task failure fields.
Timeout/transport ambiguity is classified `UNKNOWN`, has no result, is not
retry-safe, and cannot become Task or Workflow success.

## Replay and crash-window matrix

| Window | Candidate behavior |
| --- | --- |
| Before `Running` is persisted | No Provider/Gateway effect has begun; handler may be retried normally |
| `Running` persisted, before Native invocation | Replay sees `Running`, fails closed as `ExecutionStateUnknown`, and does not invoke |
| Native invocation may have begun, no evidence returned | Outcome is `UNKNOWN`; no automatic retry and no Capability invocation |
| Native succeeded, Capability not begun | A controller crash leaves `Running`; replay does not repeat either possible effect |
| Capability invocation may have begun | Gateway returns indeterminate/ambiguous evidence; Task fails closed and replay does not invoke again |
| Task terminal status observed again | Terminal replay is a no-op |
| Two stale handlers race before either observes `Running` | Existing distributed-CAS limitation remains; duplicate prevention is not proven |

The current barrier is not a distributed CAS, Provider idempotency key, or
exactly-once guarantee. No attempt identity is minted and no automatic
reinvocation occurs after ambiguous possible effects.

## Compatibility and public-wire audit

- Public API change: no.
- Existing Runtime HTTP wire change: no.
- CRD/Kubernetes API group/schema change: no.
- Task/Workflow spec or status shape change: no.
- lifecycle semantic change: no; current phases, replay barrier and Workflow
  aggregation remain.
- migration/backfill/dual write: no.
- dependency/lockfile change: no.
- Kubernetes remains the Control Plane source of truth.

## Security and redaction

The integration consumes the Native Provider's bounded configuration and
secret-shape rejection. It introduces no credential transport. Capability
requests use the existing bounded, secret-rejecting models and an injected
network-free synthetic transport. Diagnostics are stable codes and do not
include caller data or secrets.

## Validation and audits

Candidate-worktree results before commit:

- targeted A1/A2/A3, Task/Workflow, Native, Capability, and coordinator suite:
  `224 passed`;
- Core, Operator, Runtime, and Gateway regression suite: `368 passed`;
- full pytest: `456 passed`, one existing Starlette/httpx warning;
- Ruff lint: pass;
- Ruff format check: `85 files already formatted`;
- `make check`: pass, `456 passed`;
- frontend lint: pass;
- frontend build: pass;
- `git diff --check`: pass;
- exact changed-path/ownership and dependency/lockfile audits: pass;
- import direction, invocation ordering, identity authority, replay/crash,
  secret/redaction, public-wire/schema, production-import, and rollback audits:
  pass.

CI quality gates must be verified again against the exact pushed final head.

## Rollback

Revert the S5-IMPL-008 commit. This removes the controller-to-coordinator
integration, the internal coordinator/Outcome, tests, and evidence, restoring
the pre-candidate direct Agent Service path. No data migration, schema
rollback, dual-write reconciliation, external cleanup, or durable Provider
cleanup is required.

## Evidence Debt

- Operator-hosted execution remains temporary and blocks production readiness
  until a later Human architecture decision and extraction.
- The `Running` replay barrier is not exactly-once or distributed-CAS proof.
- Native and Capability packages and internal Outcome vocabulary remain
  unfrozen and uncertified.
- Only the deterministic Native mock profile and injected synthetic Capability
  transport are active.
- Durable concurrency, multi-process recovery, Provider idempotency, real
  network/runtime behavior, tenancy, and operational ownership remain open.

## Deferred scope

Document/File remains `POST_MVS / RECOMMENDED_ONLY / NOT_ACTIVE /
NOT_AUTHORIZED` and requires a separate Human slice gate. Product View,
Technical Operations View, AI-assisted authoring, Dynamic Digital Workforce,
Runtime scale-to-zero, Skill/MCP, enterprise Job/Memory/State, and v0.3-v1.0
roadmap work remain inactive future handoffs.
