# S5-IMPL-001 — A1 Core Representation Prototype Evidence

## Session state

| Field | Value |
| --- | --- |
| Session | `S5-IMPL-001` |
| Lifecycle | `REVIEW` |
| Status | `PASS_WITH_CONSTRAINTS` |
| Result | `A1_IMPLEMENTATION_CANDIDATE` |
| Baseline | `d9452db86ed2dcfcd8d339a0b95898eb51041315` |
| Selected option | `R3 — INTERNAL_PROTOTYPE_REPRESENTATION_FIRST` |
| Implementation scope | `INTERNAL_CORE_ONLY` |

Source authority: [S5-ARCH-007 Core Representation & API Gate v1](../../../../../architecture/s5/v0.2/S5-ARCH-007-CORE-REPRESENTATION-API-GATE-V1.md).
The task supplied Human-confirmed closure evidence for S5-ARCH-007 and
S5-REL-008. Repository governance metadata was intentionally not changed by
this implementation session.

## Implementation inventory

The new dependency-free package contains:

- immutable `AgentDefinitionRef`, `AgentInstanceId`,
  `PlatformExecutionIdentity`, and `NativeCorrelationId` value types;
- distinct desired/effective Runtime Binding ownership wrappers;
- opaque temporal native realization evidence;
- internal selected-Instance evidence;
- an immutable `AgentInstance` aggregate with stable identity;
- injected production/test identity-minting seams;
- explicit internal errors;
- versioned JSON-compatible serialization at
  `core.agentos.io/prototype-v0.2`;
- a storage-independent `AgentInstanceRepository` protocol;
- an isolated deterministic in-memory prototype repository.

Root `pyproject.toml` was minimally updated only to add `core/src` to the
Python path and `core/tests` to test discovery. No dependency was added.

## Domain and authority map

| Value | Authority | Explicit non-authority |
| --- | --- | --- |
| Definition reference | Definition-facing current Agent projection | Instance, native Runtime |
| Instance ID | Platform-owned internal identity | Definition, Pod, container, process, native ID |
| desired Runtime Binding | Definition-owned intent | Instance observation |
| effective Runtime Binding | Instance-owned derived effective state | desired authority |
| selected Instance | internal router/selection evidence | current Task desired target |
| execution identity | Platform-owned immutable correlation | native IDs, credentials, authorization |
| native realization | opaque `0:N` temporal evidence | logical identity or desired state |

Provider/runtime family mechanics are absent from Stable Core fields.
Provider references and opaque scalar configuration remain behind the Runtime
Binding extension boundary. Secret-shaped configuration keys are rejected.

## Repository semantics

The repository protocol supplies `save`, `get`, `list_by_definition`, and
`delete`. The in-memory implementation enforces Instance ID uniqueness,
permits updates without Definition ownership change, returns canonical-copy
snapshots, orders lists by Instance ID, reports missing/duplicate/conflict
errors explicitly, and has no singleton or cross-repository state.

```text
PERSISTENCE: PROTOTYPE_ONLY
RESTART_STABILITY: NOT_YET_PROVEN
```

Persistent storage, concurrency/version control, delete/recreate tombstones,
restart-stable identity mapping, and backfill remain Evidence Debt.

## Identity and serialization invariants

- Definition and Instance identities are distinct runtime-checked types.
- Native correlation values cannot populate Instance identity.
- Native correlation values remain distinct from Platform Execution Identity.
- Instance identity and Definition ownership survive realization and effective
  Binding replacement.
- One Definition can own multiple Instances; one Instance has exactly one
  immutable Definition reference.
- deterministic minting is injectable; the default uses an internal UUID
  choice that is not frozen.
- desired and effective Bindings have separate serialized paths and types.
- unknown envelope/record fields, unsupported versions, wrong logical kinds,
  and empty required IDs fail safely.

```text
SERIALIZATION_STABILITY: NOT_FROZEN
```

## Tests and validation

Pre-change baseline: `166 passed`, with one existing Starlette/httpx
TestClient deprecation warning.

A1 adds 34 tests covering domain values, minting, identity substitution,
Bindings, native evidence, selected Instance evidence, repository contract,
isolation, serialization, Task targeting compatibility, and rollback
isolation.

Final local validation:

- targeted A1 tests: `34 passed`;
- full pytest: `200 passed`, one existing warning, zero new warnings;
- Ruff check: passed;
- Ruff format check: passed;
- `make check`: passed;
- `git diff --check`: passed;
- authorized-scope, public-wire, provider-field, native-authority,
  secret-pattern, and relative-link audits: passed.

Required GitHub CI: recorded on the Draft PR; CI must pass on the exact final
head before Human review completes.

## Compatibility and claim boundary

The baseline comparison shows no changes under CRDs, existing Agent/Task/
Workflow schemas, controllers, Runtime, Capability Provider, Gateway, Console,
or current manifests. `Task.spec.agentRef.name` remains Definition-facing and
Workflow DAG behavior remains untouched. The new package is not imported by
any production subsystem.

```text
PUBLIC_API_CHANGE: NO
SCHEMA_CHANGE: NO
CRD_CHANGE: NO
EXISTING_SCHEMA_CHANGE: NO
BREAKING_WIRE_CHANGE: NO
MIGRATION: NO
DUAL_WRITE: NO
PRODUCTION_CORE_INTEGRATION: NO
RUNTIME_PROVIDER_CHANGE: NO
CAPABILITY_PROVIDER_CHANGE: NO
CONSOLE_CHANGE: NO
DEPENDENCY_CHANGE: NO
```

## Rollback

Rollback removes `core/src/agent_core`, `core/tests`, this evidence directory,
and the two `pyproject.toml` discovery entries. No existing resource was read,
written, migrated, backfilled, or dual-written. There is no CRD/API-version
rollback, persisted-resource cleanup, or data reversal.

## Evidence Debt and exit assessment

`ED_S5_001` remains open and unchanged; it does not block this internal Core
prototype claim. Also open: production persistence, restart stability,
identity backfill, public representation, migration losslessness, deployed
mixed-version behavior, Runtime/Capability integration, routing, recovery
vocabulary, Console projection, certification, freeze, production readiness,
and release acceptance.

No A1 stop condition was triggered. Automated A1 exit criteria pass, subject
to exact-head GitHub CI and Human implementation review.

```text
A1_EXIT: PENDING_HUMAN_IMPLEMENTATION_REVIEW
A2_STATE: NOT_ACTIVE / NOT_AUTHORIZED
FREEZE_STATE: NOT_FROZEN
CERTIFICATION_STATE: NOT_GRANTED
PRODUCTION_READINESS: NOT_GRANTED
RELEASE_ACCEPTANCE: NOT_GRANTED
NEXT_ACTION: WAIT_FOR_HUMAN_A1_IMPLEMENTATION_REVIEW_GATE
```
