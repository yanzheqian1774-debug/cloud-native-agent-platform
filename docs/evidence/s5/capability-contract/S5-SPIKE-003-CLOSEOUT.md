# S5-SPIKE-003 Closeout

SESSION
ID: S5-SPIKE-003
TITLE: Capability Contract

PHASE: S5 / v0.2 CONNECT & MANAGE
TRACK: Capability
MODE: Spike / Experimental

LIFECYCLE: CLOSED
AUTHORIZATION: COMPLETED
STATUS: PASS
CHECKPOINT: CLOSEOUT

RESULT:
SESSION_CLOSED

DISPOSITION:

- CAPABILITY_CONTRACT_DISCOVERY_COMPLETE
- READY_FOR_ARCHITECTURE_CONVERGENCE
- CONTRACT_NOT_FROZEN

## Human Final Spike Gate

**PASS** — `HUMAN_FINAL_SPIKE_GATE_PASS`.

The Human Final Spike Review accepted the bounded evidence and convergence
inputs from Checkpoints A–C. H-CAP-01 is **SUPPORTED**. This closeout records
the review result; it does not extend the experiment, decide architecture,
freeze a Contract, or authorize production implementation.

## Human Close Confirmation

**PASS** — `SESSION_CLOSED`.

The Human Close Confirmation accepted the final bounded evidence, carried the
listed evidence debt forward without blocking closure, and transitioned the
session from `CLOSING` to `CLOSED`. Authorization is completed. Reopening this
session is prohibited.

## Checkpoints

| Checkpoint | Lifecycle | Status | Accepted result |
|---|---|---|---|
| A | CLOSED | PASS | Same Agent-side Capability semantics survived REST and MCP; discovery remained distinct from authorization; explicit DENY prevented Provider invocation |
| B | CLOSED | PASS | Platform Execution Identity survived Provider boundaries; native identifiers remained opaque; REST/MCP failures normalized; generic caller remained independent; inline and deferred outcomes are required shapes |
| C | CLOSED | PASS | Capability Contract Candidate v0 converged as supported and ready for architecture convergence; no Contract was frozen |

No Checkpoint D exists or is authorized.

## H-CAP-01 Final Spike Disposition

**SUPPORTED / BOUNDED EVIDENCE.**

Capability is supported as a first-class platform business abstraction.
Provider mechanisms realize Capability semantics without owning them. Accepted
separations are:

```text
Discovery != Authorization != Invocation
Capability != Provider
Capability != REST
Capability != MCP
Capability != Runtime
```

Provider-native endpoints, tools, protocol details, exceptions, and invocation
identifiers remain subordinate/opaque. The evidence does not prove every
Capability form and does not freeze Candidate v0.

## Convergence Inputs

### CAND-S5-003-01 — Capability Contract Candidate v0

**SUPPORTED / READY_FOR_ARCHITECTURE_CONVERGENCE / NOT FROZEN.**

Accepted evidence-backed semantic inputs include:

- provider-independent Capability ID and version;
- versioned description and input/output contract association;
- Capability Binding distinct from Provider realization and Policy;
- authorization before Provider submission;
- Provider-neutral request, acceptance, inline/deferred outcome, and normalized
  failure semantics;
- required Provider translation/error normalization with conditional native
  observation and opaque diagnostic evidence;
- Provider reference, risk classification, and permission excluded from
  inherent Capability semantic identity.

This is an architecture convergence input, not a production schema, CRD, API,
SDK, implementation authorization, or frozen Contract.

### AP-S5-011 — Platform Execution Identity

**SUPPORTED / CROSS-TRACK EVIDENCE / NOT FROZEN.**

Platform Execution Identity remains stable across logical routing and Provider
translation. Provider-native execution identifiers remain subordinate, opaque
correlation evidence. A combined Runtime-Provider-plus-Capability-Provider
end-to-end path remains evidence debt.

### CAND-S5-003-02 — Shared Execution Envelope

**ARCHITECTURE_CONVERGENCE_CANDIDATE / NOT FROZEN.**

Capability and Runtime candidates overlap in a small vocabulary involving
Execution Identity, submission/acceptance, inline/deferred outcome, optional
observation handle, normalized status/error, and diagnostic references.

S5-SPIKE-003 does **not** decide whether this becomes shared Control Plane
semantics, remains duplicated across Runtime and Capability, or requires
another decomposition. It does not create or freeze a Shared Execution
Contract. That question belongs to a separately authorized S5-ARCH-003.

### Capability Provider Isolation

**SUPPORTED / EVIDENCE-BACKED.**

Generic callers consume only Contract vocabulary and declared behavior. REST,
MCP, Provider identity, endpoint/tool identity, transport, protocol errors, and
native exception classes remain behind Provider boundaries. Provider
discoverability or Binding presence never grants invocation authority.

## Preserved Open Questions

1. Capability version and input/output contract compatibility rules.
2. Whether operation belongs inside one Capability version or is separately
   versioned.
3. Minimum Provider descriptor, compatibility declaration, and resolution
   record.
4. Whether Provider selection lives in Capability Binding or an adjacent
   resolution object.
5. Durability and availability guarantees for Accepted, opaque handles, and
   deferred observation.
6. Stable normalized error names, hierarchy, compatibility, and retryability.
7. Relationship between Platform Execution Identity, actor/workload/tenant
   identity, credentials, audit, and approval.
8. Storage, authorization, expiry, and redaction ownership for native diagnostic
   evidence.
9. Risk classification granularity across Capability, operation, Binding, data,
   and invocation context.
10. Whether shared execution semantics belong in a higher shared envelope while
    preserving Capability- and Runtime-specific ownership.

## Evidence Debt

- one end-to-end execution carrying the same Platform Execution Identity through
  Runtime Provider and Capability Provider layers;
- live third-party MCP success and failure evidence beyond the deterministic
  local MCP protocol server;
- side-effecting and long-running Capability evidence;
- deferred outcome durability and process-restart evidence;
- Provider/Capability version compatibility negotiation;
- multiple Capabilities with materially different input/output contracts;
- multi-tenant policy, credential-reference, audit, and diagnostic-access
  evidence;
- provider fallback/routing, complete schema evolution, idempotency, retries,
  cancellation, streaming, broad risk taxonomy, and dynamic marketplace;
- Model Binding, Workspace Contract, and State Contract remain outside this
  Spike.

## Architecture and Production Boundary

- Production/Core source changes: **0**.
- ADR changes: **0**.
- CRD/API/Operator/Runtime/Console changes: **0**.
- Capability Contract frozen: **NO**.
- Shared Execution Contract created or frozen: **NO**.
- S5-ARCH-003 started: **NO**.
- S5-DEV started: **NO**.
- S5-SPIKE-005 started: **NO**.

All S5-SPIKE-003 artifacts remain under
`experiments/s5-spike-003-capability-contract/`.

## Artifacts

- `S5-SPIKE-003-PLAN.md` — G1 experiment plan;
- `S5-SPIKE-003-CHECKPOINT-A-RESULT.md` — identity, binding, Provider, REST/MCP,
  discovery/permission, and DENY evidence;
- `evidence/S5-SPIKE-003-CHECKPOINT-A-EVIDENCE.json` — Checkpoint A evidence;
- `S5-SPIKE-003-CHECKPOINT-B-RESULT.md` — Execution Identity, errors, failure
  normalization, and invocation lifecycle;
- `evidence/S5-SPIKE-003-CHECKPOINT-B-EVIDENCE.json` — Checkpoint B evidence;
- `S5-SPIKE-003-CHECKPOINT-C-RESULT.md` — Candidate v0 convergence;
- `S5-SPIKE-003-CLOSEOUT.md` — Human Final Spike Gate and closeout record.

## Git State

- Branch: `codex/s5-spike-003-capability-contract`.
- Pull request: draft PR #36.
- Pre-closeout convergence commit:
  `b739193ec7c673cec6d8f87027b6a908e51b9a57`.
- Final closeout commit: the commit containing this artifact; exact immutable
  identity is reported in the final session response and PR history.
- Intended post-commit working tree: clean.

## Validation

- Existing targeted spike tests: **PASS**, 12 passed; no new experiment was
  added or executed.
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
- ADR diff: **PASS**, zero.

## Next Action

**NONE**

The session is `LIFECYCLE: CLOSED`, `AUTHORIZATION: COMPLETED`, and must not be
reopened.
