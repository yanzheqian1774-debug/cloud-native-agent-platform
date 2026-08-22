# S5-SPIKE-003 Checkpoint C Result

SESSION
ID: S5-SPIKE-003
TITLE: Capability Contract

PHASE: S5 / v0.2 CONNECT & MANAGE
TRACK: Capability
MODE: Spike / Experimental

LIFECYCLE: REVIEW
AUTHORIZATION: AUTHORIZED
STATUS: PASS
CHECKPOINT: C

RESULT:
CHECKPOINT_C_PASS

> **CAPABILITY CONTRACT CANDIDATE V0 · NOT FROZEN · REST/MCP DERIVED**

## H-CAP-01

**SUPPORTED**, within the bounded evidence of Checkpoints A–C.

Capability survived provider replacement, independent authorization, explicit
denial, platform-owned execution identity, materially different native failure
semantics, and inline/deferred outcome delivery. This supports Capability as a
first-class platform business abstraction. REST endpoints and MCP tools are
Provider-native realizations, not Capability identity.

The hypothesis remains falsifiable. It is not proven for side-effecting,
transactional, streaming, cancellable, retried, or long-running enterprise
operations, and Candidate v0 is neither a production schema nor a frozen
Contract.

## Capability Contract Candidate v0

Candidate v0 owns the smallest semantics required by accepted evidence:

1. provider-independent Capability semantic identity and versioned definition;
2. input and output contracts associated with that version;
3. an Agent-to-Capability Binding distinct from Provider realization and Policy;
4. platform execution/correlation identity created before Provider invocation;
5. authorization before submission, independent of discovery;
6. Provider-neutral request, acceptance, and normalized outcome;
7. inline outcome or deferred outcome through conditional observation;
8. normalized failure classes with bounded messages and optional opaque native
   diagnostic references;
9. a replaceable Capability Provider boundary that owns native translation and
   interpretation, not enterprise Capability semantics or permission.

Conceptually:

```text
Agent Definition
  -> Capability Binding
    -> Capability (semantic ID + versioned input/output contract)
      -> Policy authorization
        -> Provider resolution
          -> Capability Request (Platform Execution Identity)
            -> Capability Provider
              -> Accepted
                +-> Inline Normalized Outcome
                +-> Opaque Handle -> Observe -> Deferred Normalized Outcome
```

Candidate v0 intentionally excludes registry schema, fallback, retries,
idempotency, cancellation, streaming, complete schema evolution, and production
resource/API design.

## Capability Identity

### Stable semantic key

- `capability_id`: provider-independent enterprise/business meaning;
- `version`: version of that meaning and its input/output contract.

### Versioned definition, not identity key material

- description;
- input contract/schema reference;
- output contract/schema reference.

The definition is addressed by semantic ID and version. Changing the Provider
does not change that identity. An incompatible semantic or input/output change
requires a distinct version; exact compatibility rules remain evidence debt.

### Explicit exclusions from semantic identity

| Concern | Disposition | Evidence |
|---|---|---|
| Provider reference | **Not identity**; Provider selection/realization concern | REST and MCP realized the same `work-item.read@0.1` semantics and output |
| Risk classification | **Metadata/governance input**, possibly refined by operation/binding/context | no identity change was required to authorize or deny the same Capability |
| Permission | **Policy decision**, evaluated for Agent/execution identity and Binding | discoverable Binding was denied before Provider invocation |

The evidence rejects endpoint URL, HTTP method/status, MCP server/tool name,
transport, Runtime, native call ID, risk class, and permission as inherent
Capability identity.

## Capability Binding

Minimum logical relationship:

```text
Agent Definition reference
  + Capability identity/version
  + allowed/requested operation(s)
  + Provider selection intent or constraints (optional)
  + Policy reference/context (optional)
```

Ownership:

- **Capability** owns business meaning and versioned input/output contract.
- **Capability Binding** associates an Agent Definition with permitted/requested
  Capability use and optional Provider-selection constraints.
- **Provider resolution** selects a compatible Provider realization; the
  resolved Provider/native references are not Capability identity.
- **Policy** decides whether a concrete Agent/execution context may invoke the
  bound operation. Binding presence and discoverability are inputs, not proof
  of authorization.
- **Capability Provider** validates Provider-specific feasibility and translates
  the authorized request. It cannot grant authority the Platform denied.

Checkpoint A directly carried `provider_ref` in the experimental Binding. The
converged candidate treats that as selection/realization data inside or adjacent
to Binding, never as semantic Capability identity. Whether production design
uses a direct Provider reference, constraints, or a separate resolution record
is deliberately open.

## Provider Boundary

| Responsibility | Candidate requirement | Evidence/disposition |
|---|---|---|
| Provider identity and Candidate compatibility declaration | **REQUIRED** for replaceable resolution; schema unproven | two Providers realized one semantic contract, but compatibility negotiation was not exercised |
| Binding/Provider-specific validation | **REQUIRED when selected** | REST/MCP required different native inputs and mechanisms |
| Request translation | **REQUIRED** | common `work-item.read` became HTTP request or MCP tool call |
| Native invocation | **REQUIRED when interaction is declared** | both Providers invoked real native paths |
| Native observation | **CONDITIONAL** | required for deferred MCP outcome; not required for inline REST outcome |
| Native error interpretation | **REQUIRED when interaction is declared** | HTTP response/transport and MCP protocol/tool failures differed materially |
| Normalized outcome translation | **REQUIRED when interaction is declared** | both success and failure reached common Agent-side semantics |
| Native diagnostic evidence preservation | **CONDITIONAL** | useful for failures; only bounded opaque references cross the boundary |
| Cancellation, streaming, retry adaptation | **OPTIONAL / FUTURE** | not evidenced and not part of Candidate v0 |

No universal transport method is proposed. The experimental `submit` and
`observe` names demonstrate semantics, not a production language-level API.
Providers may be in-process or out-of-process, but native objects, endpoints,
tool schemas, protocol errors, and exceptions must not cross the boundary as
generic business semantics.

## Invocation Lifecycle

**INLINE_AND_DEFERRED_REQUIRED** remains the converged finding.

Platform-owned:

- Capability request meaning, operation, and contract-conforming input;
- Execution Identity and correlation;
- pre-submission authorization result;
- Accepted and normalized Outcome semantics;
- normalized success/failure status and error class.

Provider-owned:

- native request/call identity;
- transport, endpoint/tool, and invocation mechanics;
- opaque Provider handle realization;
- native observation and native error interpretation;
- bounded diagnostic evidence behind an opaque reference.

`Accepted` is first-class because it marks that an authorized request with a
Platform identity crossed into Provider responsibility. It may carry an inline
terminal Outcome. If it does not, it carries correlation/handle information
that permits later Outcome observation.

`Observe` is **CONDITIONAL**: required only when a Provider accepts deferred
work. It is not required for an inline-only Provider. Cancellation, streaming,
wait APIs, retries, progress states, and a full asynchronous engine remain
optional future capabilities and are not implied by Candidate v0.

## Capability vs Runtime

| Contract | Question answered | Owns | Does not own |
|---|---|---|---|
| Capability | “What enterprise/business capability is being invoked?” | semantic Capability identity/version, input/output meaning, Capability Binding, authorization boundary, normalized Capability outcome | Runtime lifecycle, Runtime Package/Provider, health, reconciliation, native carrier topology |
| Runtime Candidate v1.1 | “How is execution carried by a Runtime?” | Runtime Binding, Provider/Package compatibility, realization, availability/observation, optional interaction transport | enterprise Capability identity, permission, business input/output meaning |

Both candidates independently require submit/acceptance, correlation, optional
deferred observation, and normalized outcome concepts. The overlap does not
justify merging Capability and Runtime:

- a Capability can be realized by REST or MCP without changing its meaning;
- a Runtime can execute many Capabilities without owning their identity;
- Runtime health/availability is not Capability invocation success;
- Capability authorization is not Runtime interaction eligibility;
- one Platform Execution Identity can correlate logical Capability invocation,
  Runtime-carried execution, and Provider-native evidence while each Binding
  and Provider identity remains distinct.

The experiment did not execute an end-to-end Runtime Provider plus Capability
Provider chain with one ID. Cross-track evidence nevertheless supports keeping
the ID platform-owned and passing it through both translation layers. That
remaining combined path is evidence debt, not a reason to collapse the
Contracts.

## Error Model

Minimum supported semantic groups:

| Group | Candidate class/evidence |
|---|---|
| Platform/policy denial | `AUTHORIZATION_DENIED`; denial occurred before Provider submission |
| Input/contract failure | `INPUT_INVALID`; required input could not be translated |
| Provider availability failure | `PROVIDER_UNAVAILABLE`; REST remote/transport unavailability |
| Provider protocol failure | `PROVIDER_PROTOCOL_ERROR`; MCP JSON-RPC error |
| Remote execution failure | `REMOTE_EXECUTION_FAILURE`; REST rejection and MCP tool failure converged |
| Timeout | `TIMEOUT`; deterministic REST transport timeout |
| Unknown/unclassified | `UNKNOWN`; malformed/unexpected native success payload |

Candidate v0 requires a normalized category, bounded message, original Platform
Execution Identity, and optional opaque diagnostic reference for non-success.
Exact names, hierarchy, retryability, compatibility, and exhaustive mappings
are not frozen. HTTP status, MCP JSON-RPC codes, native content, and Provider
exception classes remain diagnostic evidence.

## Discovery / Authorization / Invocation

```text
Discovery != Authorization != Invocation
```

- **Discovery** is a Capability-plane catalog/metadata concern: it answers what
  semantics and compatible Provider realizations are known. Discovery creates
  no authority.
- **Authorization** is a Platform Governance/Policy concern: it evaluates
  Agent/execution identity, Capability Binding, operation, and context before
  Provider submission.
- **Invocation** is a Capability execution concern: after authorization, the
  Provider translates and performs native work, then normalizes its outcome.

A Provider may validate feasibility but must not reinterpret discoverability or
Binding presence as permission. The explicit Checkpoint A DENY proved Provider
invocation can remain zero for a discoverable bound Capability.

## Execution Identity

**SUPPORTED** as AP-S5-011 — Platform Execution Identity, a cross-track
evidence-backed candidate that remains **NOT FROZEN**.

Candidate principle:

> Execution Identity is platform-owned and remains stable across logical
> routing, Runtime Provider translation, and Capability Provider invocation.
> Provider-native execution identifiers remain subordinate, opaque correlation
> evidence.

Direct Checkpoint B evidence showed stable identity across REST and MCP success,
failure, inline, deferred, and denial paths. Runtime Candidate v1.1 independently
requires platform correlation across inline/deferred interaction. The exact
same identity traversing a combined Runtime-plus-Capability execution path was
not executed; therefore the principle is supported as a convergence candidate,
not frozen or fully certified.

## Architecture Convergence Candidates

### AC-S5-CAP-01 — Capability Contract Candidate v0

Adopt the semantic candidate in this result as input to human-owned architecture
convergence. Do not freeze or implement it directly from this Spike.

### AP-S5-011 — Platform Execution Identity

Retain as **SUPPORTED / CROSS-TRACK / NOT FROZEN**. Platform identity is distinct
from Agent identity, Capability identity, Runtime Binding, Provider realization,
and Provider-native call ID.

### AC-S5-EXEC-01 — Shared Execution Envelope

**ARCHITECTURE_CONVERGENCE_CANDIDATE / NOT FROZEN.** Capability and Runtime
candidates duplicate a small cross-cutting vocabulary:

- Platform Execution Identity and correlation;
- submission/acceptance;
- inline or deferred terminal outcome;
- optional opaque observation handle;
- normalized status/error envelope and diagnostic reference.

Architecture convergence should decide whether this belongs to a higher shared
Execution Contract/envelope reused by Capability and Runtime. This Spike does
not define, name authoritatively, or freeze such a Contract. Capability-specific
business contracts/authorization and Runtime-specific lifecycle/availability
must remain outside any shared envelope.

### AC-S5-CAP-02 — Provider Isolation

Core/Agent-facing consumers branch only on Contract vocabulary and declared
capabilities, never on REST, MCP, Provider ID, endpoint, tool, protocol, or
native exception. Provider-specific translation and diagnostic evidence remain
behind a replaceable boundary.

## Contradictions

None found.

- Capability remained distinct from Runtime, Provider, Tool, MCP, Model, State,
  Workspace, and Agent identity.
- Execution Identity remained platform-owned.
- Discovery did not imply authorization.
- Provider did not bypass Policy/Binding.
- no accepted ADR, frozen Contract, CRD/API, Operator, Runtime, Console, or
  Production/Core source changed.

## Open Questions

1. What compatibility rules govern Capability version and input/output contract
   evolution?
2. Is operation part of one versioned Capability definition or separately
   versioned?
3. What is the minimum Provider descriptor/compatibility declaration and
   resolution record?
4. Does Provider selection intent live directly in Binding or in an adjacent
   resolution object?
5. What durable guarantees apply to Accepted, opaque handles, and deferred
   observation?
6. Which error names/hierarchy and retryability semantics are stable enough for
   a future Contract?
7. How are actor/workload/tenant identity, credentials, audit, approval, and
   execution identity related without collapsing them?
8. Who stores, authorizes access to, expires, and redacts native diagnostic
   evidence?
9. How does risk vary by Capability, operation, data, Binding, and invocation
   context?
10. Should shared execution semantics become a higher Execution Contract, and
    how can it avoid absorbing Capability- or Runtime-specific ownership?

## Evidence Debt

- one end-to-end execution carrying the same Platform Execution Identity through
  Runtime Provider and Capability Provider layers;
- live third-party MCP server success and failure evidence beyond the local
  deterministic MCP protocol server;
- side-effecting and long-running Capability evidence;
- deferred outcome durability/process-restart evidence;
- compatibility negotiation across Provider and Capability versions;
- validation against multiple Capabilities with materially different input and
  output contracts;
- multi-tenant policy, credential-reference, audit, and diagnostic-access
  evidence;
- fallback/routing, schema evolution, idempotency, retries, cancellation,
  streaming, risk taxonomy, marketplace, Model, Workspace, and State questions
  remain explicitly deferred.

## Production/Core source changes

**0.** Checkpoint C adds only this convergence artifact below
`experiments/s5-spike-003-capability-contract/`.

## Validation

- Targeted tests: **PASS**, 12 passed (Checkpoint A/B prototype regression;
  Checkpoint C adds no executable behavior).
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

**PASS_TO_ARCHITECTURE_CONVERGENCE**

This is the final planned checkpoint. Do not create Checkpoint D. Do not
transition to Closing. Wait for Human Final Spike Review.
