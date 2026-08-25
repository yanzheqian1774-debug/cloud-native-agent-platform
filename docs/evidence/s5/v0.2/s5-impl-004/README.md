# S5-IMPL-004 Native Runtime Provider Implementation Evidence

## Result boundary

This artifact records the Checkpoint A implementation candidate for logical
Session `S5-IMPL-004`. The result is a bounded internal Native Runtime Provider
candidate: `COMPONENT_TESTED_CANDIDATE / PRIMARY_GOLDEN_PATH / NOT_CERTIFIED`.
It does not grant Provider certification, production readiness, Contract or
Schema freeze, or release acceptance.

The exact authorized baseline is
`6156aab9e70bc174c1493b13a407113eece95a77`. Source Sessions are
`S5-ARCH-006`, `S5-PLAN-001`, `S5-ARCH-007`, `S5-SPIKE-005`, and
`S5-REL-012`. PR #50 supplied the immediate Git provenance: evidence head
`9ffbc65cba7824414f618a2fd7218a847e83ae28` merged as the authorized baseline.

S5-REL-012 is Human-confirmed as
`CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS / SESSION_CLOSED`, with provenance
`HUMAN_CONFIRMED_GIT_VERIFIED`. `PROJECT_STATE.md` and
`docs/governance/REGISTRY.md` have `TERMINAL_METADATA_LAG`. That lag is
non-blocking for this bounded implementation and its forward import is
deferred to a separately authorized PLAN, REL, or GOV Session. This evidence
artifact is not a competing governance authority; S5-REL-012 was not reopened.

## Current Native inventory

Before implementation, the Native Runtime consisted of:

- `runtime/src/agent_runtime/main.py`: FastAPI application, environment-backed
  Runtime information, and the existing `/healthz`, `/readyz`, `/v1/info`, and
  `/v1/invoke` routes;
- `runtime/src/agent_runtime/providers/base.py`: Runtime-local model-generation
  interface, distinct from a Runtime Provider contract;
- `runtime/src/agent_runtime/providers/factory.py`, `mock.py`, and
  `openai_compatible.py`: current model provider selection and implementations;
- `runtime/tests/test_runtime.py` and `test_providers.py`: HTTP and model
  provider behavior;
- `runtime/Dockerfile`: Python 3.12 image, non-root `nobody` user, Runtime
  source import through `PYTHONPATH`, and the current Uvicorn entry point;
- `runtime/README.md`: empty placeholder;
- Kubernetes CRDs and workloads under `manifests/`; no Native Provider package
  or Provider-specific manifest existed there.

The HTTP app imports only the existing model provider factory. The new package
imports Python standard-library facilities and its own provider-local modules;
it does not import Stable Core, operator controllers, HTTP DTOs, OpenClaw, or
Hermes. Existing Runtime code does not import the candidate, so no circular
dependency or active integration consumer is introduced.

## Architecture and import direction

The internal direction is:

`internal Runtime Binding intent -> Native Provider -> deterministic Native mock`

The candidate remains provider-local under
`runtime/src/agent_runtime/providers/native/`. It neither implements the
conceptual Operator RuntimeClass/Resolver boundary from ADR-0004 nor modifies
the recorded architecture drift. It introduces no public API, CRD, frozen
schema, wire contract, operator integration, or Stable Core authority.

## Identity and exact target

The package identity is:

- distribution: `cloud-native-agent-platform`;
- version: `0.1.0`;
- module: `agent_runtime`;
- experimental manifest package ID:
  `cloud-native-agent-platform.native-runtime`.

The only accepted Runtime target is
`native:0.1.0+e6a162f:managed-kubernetes-deterministic-mock`. The provider
state is `SUPPORTED_CANDIDATE / PRIMARY_GOLDEN_PATH / NOT_CERTIFIED`.

The implementation consumes the integrated S5-SPIKE-005 Native manifest
candidate by pinning and testing its exact provider version, Runtime identity,
exact Runtime version, profile, compatibility, feature, limitation, degraded,
and certification facts. The manifest remains
`CANDIDATE / EXPERIMENTAL / NOT_FROZEN`; no public promotion occurs.

## Compatibility and diagnostics

Compatibility validation executes before binding translation or invocation.
It accepts only the exact Provider package, Native target/profile, and Core
`0.1.0`. Missing identity/version, package mismatch, Core mismatch, another
profile/version, OpenClaw, and Hermes fail closed with typed diagnostic
reasons. The Native Provider never dispatches to another Provider and exposes
no cross-Provider fallback.

Degraded operation is rejected when implicit. Explicit degraded operation
requires both manifest-backed evidence values, `deterministic mock label` and
`normalized outcome`, and records the limitation `deterministic mock execution
only`.

## Runtime Binding and Secret boundary

Desired Runtime Binding remains caller-owned platform intent. Translation
copies input, accepts a bounded allowlist of existing Native environment keys,
requires `MODEL_PROVIDER=mock`, applies deterministic defaults, sorts the
effective configuration, and emits a separate Effective Runtime Binding.
Caller input is not mutated.

Unknown configuration and secret-like keys fail closed. Secret, token,
password, credential, and API-key values are never accepted into normalized
evidence or diagnostic text. The implementation adds no credentials, Secret
material, or new configuration transport.

## Execution identity and normalized evidence

Platform Execution Identity is mandatory and must be identical in the outer
execution envelope and compatibility request. It is propagated unchanged into
compatibility decisions, correlation, success, failure, timeout ambiguity,
observation, lifecycle, and cleanup evidence. Identity fallback is prohibited.

Native invocation IDs are optional, opaque correlation evidence. Caller-supplied
native IDs, native-ID substitution for Platform identity, and duplicate native
IDs are rejected. Native IDs never become lookup or Platform authority.

Successful deterministic execution returns normalized output and correlation.
Known invocation failure becomes `FAILED`; timeout or transport ambiguity
becomes `UNKNOWN` rather than an unsafe retry/success claim. Diagnostics use
stable provider-local reason values.

## Health and lifecycle support matrix

| Seam | Candidate state | Evidence boundary |
| --- | --- | --- |
| Compatibility preflight | Supported | Exact match or typed fail-closed decision |
| Health | Supported | Normalized provider-local healthy state |
| Readiness | Supported | Exact selected target ready |
| Runtime information | Supported | Package, target, features, limitations, certification state |
| Invoke | Supported | Deterministic mock Golden Path |
| Observe result | Supported | In-process Platform-identity lookup for completed success |
| Start | Not yet proven | No durable provisioning claim; explicit unsupported result |
| Stop | Not yet proven | No distributed lifecycle claim; explicit unsupported result |
| Cleanup | Bounded support | Removes only provider-local correlation/result evidence |
| Crash/restart recovery | Not yet proven | No success claim |
| Exactly-once execution | Not supported | No success claim |

Kubernetes continues to own the existing Deployment/Pod lifecycle. This
candidate does not provision, delete, replace, recover, or claim ownership of
Kubernetes resources.

## Files created and modified

Created implementation files:

- `runtime/src/agent_runtime/providers/native/__init__.py`;
- `runtime/src/agent_runtime/providers/native/models.py`;
- `runtime/src/agent_runtime/providers/native/compatibility.py`;
- `runtime/src/agent_runtime/providers/native/binding.py`;
- `runtime/src/agent_runtime/providers/native/provider.py`.

Created test files:

- `runtime/tests/test_native_runtime_provider.py`;
- `runtime/tests/test_native_provider_compatibility.py`.

This README is the only documentation/evidence change. No existing source,
HTTP route, Dockerfile, Kubernetes manifest, CRD, schema, dependency, lockfile,
governance index, task controller, or workflow controller is modified.

## Validation and audits

Validation on the implementation candidate produced:

- targeted Native Provider tests: `29 passed`;
- all Runtime tests: `41 passed`, with one existing Starlette/httpx
  deprecation warning;
- integrated S5-SPIKE-005 compatibility tests: `17 passed`;
- full pytest: `329 passed`, with the same one warning;
- Ruff lint: passed;
- Ruff format check: passed for 74 files;
- `make check`: passed, including `329 passed`;
- `git diff --check`: passed.

Changed-path ownership, imports and cycles, public wire/API/CRD/schema,
dependencies and lockfile, Platform/native identity authority, Runtime Binding
authority, fallback/degraded behavior, secret patterns and redaction, relative
links, and rollback were audited explicitly. Changes are limited to the Native
provider package, its two Runtime test files, and this evidence directory.
Imports compile and load from `runtime/src` without Core, operator, HTTP,
OpenClaw, or Hermes consumers. No relative Markdown links were added. Secret
pattern scanning found no credential-shaped values; named fake negative-test
values are asserted absent from diagnostics.

## Limitations and Evidence Debt

- The candidate has component evidence only; it is not wired into an Operator
  or public execution path.
- Deterministic mock is the only supported profile.
- Provider-local observation and cleanup are in-memory and not durable.
- Provisioning, distributed leases, restart/crash recovery, semantic recovery,
  exactly-once execution, fleet management, multi-tenancy, and certified
  cleanup are not proven.
- Provider certification, Runtime Contract freeze, production readiness, and
  release acceptance remain not granted.
- OpenClaw and Hermes implementation remain not started and unauthorized.
- S5-REL-012 repository terminal metadata remains deferred governance work.

## Public wire, rollback, and downstream boundary

Public Runtime HTTP behavior is unchanged, including all route paths, methods,
request bodies, response bodies, and status handling. Public Kubernetes APIs,
CRDs, schemas, and manifests are unchanged. There is no migration, dual write,
or persistent state change.

Rollback is deletion of the new provider package, its two test files, and this
evidence directory. No data rollback, compatibility migration, manifest
rollback, or controller reconciliation is required.

Downstream integration remains separately owned. `task_controller.py` and
`workflow_controller.py` are untouched, and this Session does not authorize an
active consumer, router, Capability Gateway, Console surface, OpenClaw adapter,
or Hermes adapter.
