# S5-SPIKE-003 Checkpoint A Result

SESSION
ID: S5-SPIKE-003
TITLE: Capability Contract
PHASE: S5 / v0.2 CONNECT & MANAGE
TRACK: Capability
MODE: Spike / Experimental
STATUS: PASS
CHECKPOINT: A

## H-CAP-01

**SUPPORTED**, within Checkpoint A's bounded evidence.

A generic Agent-side caller used one stable business capability identity and
one normalized request/result vocabulary with two materially different
providers. REST and MCP translation remained behind the provider boundary. An
explicit policy DENY prevented provider invocation even though the capability
and binding were discoverable.

This supports a first-class Capability abstraction and challenges models that
make an MCP tool name, REST endpoint, provider, risk class, or permission part
of Capability identity. It does not freeze a Contract or prove long-running,
streaming, transactional, or side-effecting capabilities.

## Capability Identity Candidate

Minimum stable identity:

- `capability_id`: provider-independent business meaning;
- `version`: version of that meaning and its compatible contract.

Contract metadata associated with, but not constituting, identity:

- description;
- input schema reference;
- output schema reference;
- risk-classification reference.

`provider_ref` does not belong to identity; it belongs to the binding. Risk is
governance classification metadata associated with the capability (and may be
further constrained at binding or policy time), not identity. Permission is a
policy decision over Agent/execution identity, capability binding, and
operation; it belongs to neither identity nor discovery.

## Capability Binding Candidate

An Agent Definition-like declaration binds:

`CapabilityIdentity + operation -> provider_ref`

The experimental Agent-facing path requested `work-item.read@0.1/read` for
both providers. REST mapped it to `GET /todos/{id}`; MCP mapped it to
`tools/call(work_item_read)`. Provider-native endpoint/tool identities did not
enter Agent-side semantics.

This is a candidate only. Provider selection cardinality, fallback, binding
credentials, and compatibility constraints remain open.

## Provider Boundary

**PASS.** The generic caller has no `if provider == "rest"`, `if provider ==
"mcp"`, endpoint, HTTP, JSON-RPC, tool-name, or MCP protocol knowledge. Each
provider implements `start(request)` and `result(handle)` as an experimental
shape while owning native translation. Both returned the same normalized
business output:

```json
{"item_id": 1, "summary": "delectus aut autem", "completed": false}
```

The split method is deliberately not a claim that every capability is
synchronous. It demonstrates that provider-native interaction can be hidden
without forcing a universal synchronous `invoke()`.

## Discovery vs Permission

**PASS.** `agent/untrusted` received a discoverable `work-item.read@0.1`
binding, but policy returned `capability_not_authorized`. The REST provider's
start count remained unchanged, proving denial occurred before provider-native
invocation. The provider could not bypass the Agent-side binding/policy gate in
the tested call path.

## Invocation / Result

Minimum request candidate:

- capability identity;
- operation;
- schema-conforming input;
- correlation ID.

Provider boundary candidate:

- start native work and return an opaque provider-scoped handle;
- resolve/observe a normalized result separately.

Minimum normalized result candidate:

- terminal status (`succeeded`, `denied`, `failed` in this experiment);
- correlation ID;
- schema-conforming output on success;
- stable error code and sanitized message on non-success.

Queued/running states, polling/streaming, cancellation, deadlines,
idempotency, partial results, retries, approval, and audit metadata are not yet
proven and must not be silently inferred.

## Evidence

REST Evidence: **PASS** — a real read-only HTTPS request to JSONPlaceholder
`/todos/1` was translated to normalized `work-item.read` output.

MCP Evidence: **PASS** — a real local MCP stdio JSON-RPC sequence executed
`initialize`, `tools/list`, and `tools/call` against a deterministic MCP server,
then translated the native content to the same normalized output.

DENY Evidence: **PASS** — explicit denial produced a normalized result and the
provider invocation count did not change.

Machine-readable evidence:
`evidence/S5-SPIKE-003-CHECKPOINT-A-EVIDENCE.json`.

## Production/Core source changes

**0.** All changes are contained under
`experiments/s5-spike-003-capability-contract/`.

## Contradictions

None observed. The evidence is consistent with the shared semantic baseline:
Capability Binding remains distinct from Runtime, Model, Workspace, Policy,
and execution identity. No production implementation or accepted ADR was
changed.

## Open Questions

- What version-compatibility rules apply to input/output schema evolution?
- Is `operation` part of a capability version's contract or a separately
  versioned sub-resource?
- Can one binding select multiple providers, and who owns selection/fallback?
- What lifecycle vocabulary is minimal for asynchronous, streaming, approval,
  and long-running capabilities?
- Where do deadlines, idempotency keys, cancellation, retry safety, and partial
  results belong?
- How are execution identity, credential references, tenant, and audit context
  conveyed without entering capability identity?
- Can risk vary by operation, data classification, binding, or runtime context?
- How are native provider errors mapped to stable cross-provider error codes?
- Does real ecosystem MCP implementation evidence expose protocol/version or
  content-shape constraints missed by the deterministic server?

## Validation

- Targeted experiment tests: **PASS**, 5 passed.
- Existing repository tests / `make check`: **PASS**, 166 passed with one
  existing Starlette/httpx deprecation warning.
- Ruff lint: **PASS**.
- Ruff format check: **PASS**, 51 files already formatted.
- `git diff --check`: **PASS**.
- Pre-commit: **PASS** (Ruff lint, Ruff format, pytest).
- Credential/secret hygiene: **PASS**, no credential-like assignment or token
  found under the experiment path; no credentials required.
- Production/Core diff: **PASS**, zero paths outside the dedicated experiment
  directory.

## Recommendation

**PASS_TO_CHECKPOINT_B**

Human review is required before Checkpoint B. Do not freeze this candidate or
start Checkpoint B automatically.
