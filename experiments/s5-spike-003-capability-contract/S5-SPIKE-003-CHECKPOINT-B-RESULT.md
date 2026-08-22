# S5-SPIKE-003 Checkpoint B Result

SESSION
ID: S5-SPIKE-003
TITLE: Capability Contract

PHASE: S5 / v0.2 CONNECT & MANAGE
TRACK: Capability
MODE: Spike / Experimental

LIFECYCLE: REVIEW
AUTHORIZATION: AUTHORIZED
STATUS: PASS
CHECKPOINT: B

RESULT:
CHECKPOINT_B_PASS

## H-CAP-01

**SUPPORTED**, within bounded Checkpoint A and B evidence.

The Capability abstraction survived platform-owned execution identity, opaque
Provider-native identities, materially different REST/MCP failures, and inline
versus deferred outcome delivery. The generic caller retained one semantic path
and no HTTP, MCP, JSON-RPC, endpoint, tool, or native exception knowledge.

## Execution Identity

**SUPPORTED.** Findings:

- the Platform creates `invocation_id` before authorization and Provider work;
- caller-supplied `correlation_id` relates the invocation to business context;
- both identities survive unchanged through REST and MCP outcomes;
- Provider handles and protocol/request IDs remain opaque and Provider-owned;
- normalized outcomes correlate to the original invocation without exposing
  REST/MCP details;
- diagnostic evidence is referenced opaquely and is not identity.

This does not define a production schema. It supports the shared baseline that
Execution Identity is platform-owned and distinct from Provider-native call
identity.

## Error Taxonomy

Candidate normalized classes supported by deterministic evidence:

- `AUTHORIZATION_DENIED`: policy denied before Provider submission;
- `INPUT_INVALID`: required capability input could not be translated;
- `PROVIDER_UNAVAILABLE`: REST remote unavailability/transport failure;
- `PROVIDER_PROTOCOL_ERROR`: MCP JSON-RPC error envelope;
- `REMOTE_EXECUTION_FAILURE`: REST remote rejection and MCP tool failure;
- `TIMEOUT`: REST transport timeout;
- `UNKNOWN`: malformed/unexpected successful native payload.

The distinctions survived without generic caller classification. More evidence
is needed before freezing names, retryability, hierarchy, or exhaustive mapping.

Provider-native evidence handling:

- Providers retain bounded native evidence under an opaque diagnostic key;
- normalized outcomes expose only `diagnostic_ref`;
- HTTP status values, JSON-RPC error objects, native MCP content, and exception
  class names do not enter Agent-facing messages, error classes, or identity;
- secret-bearing diagnostics are neither needed nor recorded.

## REST Failure Normalization

**PASS.** Deterministic evidence covered server unavailability, remote
rejection, timeout, missing input, and malformed result. Outcomes used stable
normalized classes and retained native details only behind an opaque diagnostic
reference.

## MCP Failure Normalization

**PASS.** A real local MCP stdio path returned a JSON-RPC error for one call and
an MCP tool `isError` result for another. They normalized respectively to
`PROVIDER_PROTOCOL_ERROR` and `REMOTE_EXECUTION_FAILURE`; native details did
not cross the Capability-facing boundary.

## Generic Caller Provider Independence

**PASS.** The same caller submitted both Provider types, consumed inline or
deferred outcomes, and returned normalized failures. Source tests prove it does
not contain HTTP, status-code, REST, MCP, or JSON-RPC classification terms.

## Invocation Lifecycle

**INLINE_AND_DEFERRED_REQUIRED.** Required means the candidate must leave room
for both shapes, not that every Provider must implement asynchronous execution.

Evidence showed:

- execution identity is required before Provider invocation;
- REST can return an immediate normalized outcome with acceptance;
- MCP can return acceptance plus an opaque handle, then produce outcome through
  observation;
- forcing inline-only would make the generic layer block on or absorb native
  interaction constraints;
- wait, streaming, cancellation, retry, and a full asynchronous engine remain
  out of scope and optional future capabilities.

The minimum candidate is therefore:

`Request -> Accepted(execution identity, handle, optional inline outcome) ->`
`Outcome (inline or observed)`.

Capability owns invocation/request/outcome meaning and correlation. A Runtime
may execute the call, but Runtime lifecycle does not own enterprise Capability
identity, permission, or normalized Capability outcome. These remain separate
execution layers.

### Comparison with Runtime Contract Candidate v1.1

Runtime Candidate v1.1 independently supports submit plus either terminal
inline outcome or durable correlation for later observation. Checkpoint B does
not copy Runtime lifecycle semantics wholesale. It finds the smaller analogous
shape justified by Capability evidence: pre-Provider platform identity,
acceptance, optional inline result, and observation for deferred outcomes.
Runtime health, availability, reconciliation, recovery, lifecycle operations,
and runtime observation vocabulary do not enter the Capability candidate.

## Contradictions

None. Execution Identity remained platform-owned. Capability Binding, Runtime
Binding, Policy, Agent Definition/Instance, Model Binding, Workspace Binding,
and Normalized Outcome were not silently redefined. No accepted ADR or
Production/Core source changed.

## Open Questions

- error-class naming, hierarchy, compatibility, retryability, and ownership;
- validation ownership once versioned input schemas exist;
- durable handle requirements and observation availability guarantees;
- how execution identity relates to tenant, actor, workload identity, audit,
  and credential references;
- timeout ownership across caller, Capability Provider, Runtime, and remote;
- sanitized diagnostic storage lifecycle and access policy;
- fallback/routing, schema negotiation, cancellation, streaming, idempotency,
  retries, risk taxonomy, and marketplace behavior remain deferred;
- live third-party MCP failure evidence remains evidence debt beyond the local
  deterministic protocol server.

## Production/Core source changes

**0.** All changes remain under
`experiments/s5-spike-003-capability-contract/`.

## Validation

- Targeted experimental tests: **PASS**, 12 passed (5 Checkpoint A regression,
  7 Checkpoint B).
- Repository tests / `make check`: **PASS**, 166 passed with one existing
  Starlette/httpx deprecation warning.
- Ruff: **PASS**.
- Format: **PASS**, 53 files already formatted.
- Pre-commit: **PASS** (Ruff lint, Ruff format, pytest).
- `git diff --check`: **PASS**.
- Secret hygiene: **PASS**, no credential-like assignment or bearer token
  found; no credentials required.
- Production/Core diff: **PASS**, zero changed paths outside the dedicated
  experiment directory.

## Recommendation

**PASS_TO_CHECKPOINT_C**

Checkpoint C requires Human review/authorization and was not started.
