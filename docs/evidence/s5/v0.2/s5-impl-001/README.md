# S5-IMPL-001 — A1 Core Representation Prototype Evidence

## Session state

| Field | Value |
| --- | --- |
| Session | `S5-IMPL-001` |
| Lifecycle | `CLOSING` |
| Status | `PASS` |
| Result | `READY_TO_CLOSE` |
| Baseline | `d9452db86ed2dcfcd8d339a0b95898eb51041315` |
| Authorized Checkpoint A head | `b6a2939e8e55da95a171455a42e273235c9b6790` |
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

## Implementation classification

```text
INTERNAL_CORE_IMPLEMENTATION_CHANGE: YES — BOUNDED_INTERNAL_PROTOTYPE
PRODUCTION_CORE_CHANGE: YES — NEW_UNCONSUMED_INTERNAL_CORE_PACKAGE
ACTIVE_RUNTIME_BEHAVIOR_CHANGE: NO
EXISTING_PRODUCTION_PATH_INTEGRATION: NO
CONTROLLER_CHANGE: NO
```

Repository Core implementation changed because A1 added code under
`core/src/agent_core/`. The package is unconsumed by existing production
paths, so active Runtime behavior and public contracts did not change.

## Checkpoint B code-structure review

- Domain modules import only the Python standard library and A1-local errors.
- Repository ports depend on domain values; the domain does not depend on the
  repository or its in-memory implementation. No circular dependency exists.
- Kubernetes, Provider implementations, Gateway, Console, environment reads,
  and active controllers are absent.
- Aggregate/value records are frozen and slotted. Runtime Binding
  configuration is defensively copied into a read-only mapping; realization
  collections and native correlations are tuples.
- All timestamps are explicit inputs. The aggregate has no hidden system-clock
  or environment dependency.
- Package exports are intentional internal prototype surfaces. The internal
  serialization marker is not re-exported from the package root.
- Error types are internal and contain no configuration values or credentials.

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
CONCURRENCY_SAFETY: NOT_YET_PROVEN
MULTI_PROCESS_CONSISTENCY: NOT_PROVIDED
CRASH_RECOVERY: NOT_PROVIDED
DURABLE_TOMBSTONES: NOT_PROVIDED
MULTI_TENANT_ISOLATION: NOT_PROVEN
```

Persistent storage, concurrency/version control, delete/recreate tombstones,
restart-stable identity mapping, and backfill remain Evidence Debt.

Insert/replacement behavior is explicit: a new ID inserts; an existing ID with
the same Definition and creation identity replaces the stored snapshot; an
identical duplicate is rejected; changed Definition ownership raises a typed
ownership conflict; and changed creation identity for an existing ID raises a
typed duplicate/conflict error. Lookup/list results cross the canonical copy
boundary. Missing get/delete operations raise `InstanceNotFoundError`.

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
- root/parent/attempt values are optional internal execution-tree metadata:
  roots equal their stable execution identity and have no parent; children
  retain a distinct root and require a parent; attempts are positive integers.

```text
EXECUTION_TREE_SEMANTICS: NOT_FROZEN
RETRY_PROPAGATION: NOT_YET_INTEGRATED
TASK_WORKFLOW_INTEGRATION: DEFERRED_TO_A2_OR_LATER

SERIALIZATION_MARKER: INTERNAL_FIXTURE_FORMAT_MARKER
PUBLIC_API_GROUP: NO
KUBERNETES_API_VERSION: NO
PUBLIC_COMPATIBILITY_PROMISE: NO
SERIALIZATION_FREEZE: NO
```

`core.agentos.io/prototype-v0.2` is an internal fixture discriminator only. It
is not a media type, Kubernetes API group/version, external Contract, or
long-term compatibility promise.

## Binding and native-evidence review

Desired and effective Runtime Bindings are separate wrapper types and separate
fixture paths. Both contain the same Provider-neutral embedded Binding value;
neither is a CRD or public Contract. Configuration accepts only defensively
copied, redacted JSON scalars and has no Runtime-family-specific field.

Native evidence is optional, opaque, immutable, and `0:N`. It has a distinct
correlation-ID type, owns no desired state, round-trips deterministically, and
can be appended/replaced without changing Instance identity. Typed native
values are rejected by Instance and Platform Execution Identity constructors.

## Tests and validation

Pre-change baseline: `166 passed`, with one existing Starlette/httpx
TestClient deprecation warning.

A1 adds 43 tests covering domain values, minting, identity substitution,
Bindings, native evidence, selected Instance evidence, repository contract,
isolation, serialization, Task targeting compatibility, and rollback
isolation.

Test-quality mapping:

| Category | Collected tests | Primary coverage |
| --- | ---: | --- |
| Domain/identity/minting/Binding/native evidence | 20 | typed substitution, empty values, opaque minting, redaction, ownership, defensive copying |
| Repository contract | 9 | insert/replace/duplicate/conflict, get/list/delete, ordering and isolation |
| Serialization/execution scope | 12 | round trips, shape/type confusion, root/parent/attempt constraints |
| Compatibility/rollback | 2 | Definition-facing Task target and absence of active consumers |

Final local validation:

- targeted A1 tests: `43 passed`;
- full pytest: `209 passed`, one existing warning, zero new warnings;
- Ruff check: passed;
- Ruff format check: passed;
- `make check`: passed;
- `git diff --check`: passed;
- authorized-scope, public-wire, provider-field, native-authority,
  secret-pattern, and relative-link audits: passed.

Required GitHub CI: recorded on the Draft PR; CI must pass on the exact final
head before Human review completes.

## Public-wire and pyproject review

```text
PUBLIC_WIRE_NON_CHANGE: PASS
ACTIVE_RUNTIME_BEHAVIOR_CHANGE: NO
DEPENDENCY_CHANGE: NO
BUILD_BACKEND_CHANGE: NO
UNRELATED_TOOLING_CHANGE: NO
```

The only root `pyproject.toml` changes remain the `core/src` Python import path
and `core/tests` pytest discovery entry required to collect the A1 package and
tests. Project dependencies, development dependencies, build configuration,
Ruff policy, and all unrelated tooling are unchanged.

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
INTERNAL_CORE_IMPLEMENTATION_CHANGE: YES — BOUNDED_INTERNAL_PROTOTYPE
PRODUCTION_CORE_CHANGE: YES — NEW_UNCONSUMED_INTERNAL_CORE_PACKAGE
ACTIVE_RUNTIME_BEHAVIOR_CHANGE: NO
EXISTING_PRODUCTION_PATH_INTEGRATION: NO
RUNTIME_PROVIDER_CHANGE: NO
CAPABILITY_PROVIDER_CHANGE: NO
CONSOLE_CHANGE: NO
DEPENDENCY_CHANGE: NO
```

## Rollback

Rollback removes the new representation/repository directories, `core/tests`,
this evidence directory, and the two `pyproject.toml` discovery entries. No
existing resource was read, written, migrated, backfilled, or dual-written.
There is no controller, CRD/API-version, persisted-resource, or dual-write
cleanup.

```text
ROLLBACK: PASS / REVERSIBLE_WITHOUT_RESOURCE_MIGRATION
```

## Evidence Debt and exit assessment

`ED_S5_001` remains open and unchanged; it does not block this internal Core
prototype claim. Open debt is: durable persistence; restart stability;
concurrency safety; multi-process consistency; crash recovery; durable
tombstones; identity backfill; public representation; public selected-Instance
and Execution Identity exposure; serialization stability; execution-tree
semantics; retry propagation; deployed mixed-version behavior; migration
losslessness; live routing; Runtime Provider integration; OpenClaw evidence;
Hermes ED-S5-001; Console projection; recovery vocabulary; State portability;
and multi-tenancy.

No A1 stop condition was triggered. Automated A1 exit criteria and the Human
A1 Implementation Review Gate pass with constraints, subject to exact-final-
head GitHub CI and Human Close Confirmation.

```text
A1_IMPLEMENTATION: COMPLETE_FOR_BOUNDED_INTERNAL_PROTOTYPE
A1_RUNTIME_INTEGRATION: NOT_STARTED
A1_EXIT: READY_FOR_HUMAN_CLOSE_CONFIRMATION
A2_STATE: RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED
FREEZE_STATE: NOT_FROZEN
CERTIFICATION_STATE: NOT_GRANTED
PRODUCTION_READINESS: NOT_GRANTED
RELEASE_ACCEPTANCE: NOT_GRANTED
HUMAN_CLOSE_CONFIRMATION: PENDING
SESSION_CLOSED: NO
NEXT_ACTION: WAIT_FOR_HUMAN_CLOSE_CONFIRMATION
```
