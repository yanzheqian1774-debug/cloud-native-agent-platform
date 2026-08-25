# S5-IMPL-007 — Capability gateway and REST

## Session and Portfolio boundary

- Session: `S5-IMPL-007`
- Track: C — Capability Workflow Authorization
- Authorized baseline: `ed0628b7d220f92f566f54978bc31bbbd672da61`
- Source Sessions: `S5-SPIKE-007`, `S5-REL-014`
- Checkpoint: A — Capability Gateway REST Implementation Candidate
- Branch: `codex/s5-impl-007-capability-gateway-rest`

The exact accepted Portfolio row is:

> `S5-IMPL-007 — Capability gateway and REST | IMPL/C; ALLOW/DENY + synthetic REST | A2,SPIKE-007; new gateway/provider/tests; excludes broad MCP/real connector | A2→Capability Gate; gateway evidence; PR | 2–4 sessions/medium/Post-A/MVS`

The Portfolio assigns this Session `TDA-07`, `TDA-08`, `MRA-11`, `MRA-14`,
`MRA-15`, and `MRA-17`. It owns the bounded internal Capability Contract
candidate. It does not own Task or Workflow controllers, public API/CRDs,
Capability discovery, a Policy Engine, MCP, Document/File, or real enterprise
connectors. `S5-IMPL-008` remains inactive and owns later integration.

Preflight verified `origin/main` and PR #52's merge commit both equal the
authorized baseline. PR #52 is merged. No open PR existed, and no other active
worktree or branch owned the new S5-IMPL-007 implementation paths. The source
fixture records S5-SPIKE-007's Human-gated closure and durable integration
handoff; the routing authorization records S5-REL-014 closed.

## Implementation architecture

The implementation is an internal package under the repository's existing
reserved `gateway/` boundary:

```text
CapabilityRequest
  -> CapabilityGateway
    -> injected AuthorizationDecisionPort
      -> explicit ALLOW / DENY / fail-closed validation
    -> injected CapabilityProvider only after ALLOW
      -> RestProvider Candidate
        -> immutable ProviderRequest
        -> injected RestTransport (one attempt)
    -> internal normalized CapabilityOutcome
```

The Gateway boundary is Provider-neutral. The REST Provider owns only REST
translation and response normalization. Transport is injected and deterministic
in component tests; there is no production network client, endpoint, dependency,
fallback, retry, discovery, or credential injection.

## Authorization-before-invocation evidence

Authorization context is validated before calling the decision port. Missing,
unknown, non-enum, empty, conflicting, or exceptional decisions fail closed.
Only one typed `ALLOW` decision reaches the Provider. `DENY` returns a normalized
denial with zero attempts, no REST request, and no Provider-native request ID.
The denial diagnostic contains only a validated stable reason code, never raw
authorization input.

Component tests use a transport spy to prove:

- ALLOW: exactly one transport call and one bounded invocation attempt;
- DENY: zero transport calls and zero invocation attempts;
- ambiguity/timeout: exactly one call, no retry, `retry_safe=False`;
- Provider response fields and Provider-produced outcomes cannot override the
  Gateway's authorization result.

Decision evidence (`authorization`, stable decision diagnostic) remains distinct
from Provider evidence (`invocation`, HTTP status, bounded result, native ID,
ambiguity).

## Identity and authority boundaries

`PlatformExecutionIdentity` is imported from the existing internal v0.2 Core
representation. Requests, authorization context, Provider requests, and Outcomes
retain that typed value unchanged. Capability and Provider identities are
separate internal types. A Provider-native request ID is opaque evidence only;
equality with the Platform identity is rejected and it can never substitute for
Platform authority.

The candidate does not create a new Core resource or persistence authority.
Kubernetes, Task, Workflow, Runtime, and current public contracts are unchanged.

## REST behavior matrix

| Condition | Normalized status | Stable diagnostic | Attempts | Ambiguity |
| --- | --- | --- | ---: | --- |
| 2xx JSON mapping | `SUCCEEDED` | `CAPABILITY_INVOCATION_SUCCEEDED` | 1 | `NONE` |
| 4xx | `FAILED` | `PROVIDER_CLIENT_ERROR` | 1 | `NONE` |
| 5xx | `FAILED` | `PROVIDER_SERVER_ERROR` | 1 | `NONE` |
| other status / malformed body | `FAILED` | `PROVIDER_RESPONSE_MALFORMED` | 1 | `NONE` |
| unsupported content type | `FAILED` | `PROVIDER_CONTENT_UNSUPPORTED` | 1 | `NONE` |
| timeout | `INDETERMINATE` | `PROVIDER_TIMEOUT_EFFECT_UNKNOWN` | 1 | `TIMEOUT_EFFECT_UNKNOWN` |
| ambiguous transport | `INDETERMINATE` | `PROVIDER_TRANSPORT_EFFECT_UNKNOWN` | 1 | `TRANSPORT_EFFECT_UNKNOWN` |
| other transport exception | `FAILED` | `PROVIDER_TRANSPORT_FAILED_REDACTED` | 1 | `NONE` |

Only uppercase bounded HTTP methods are accepted. Targets must be authorized
HTTPS URLs without embedded credentials, query strings, or fragments. Headers,
request bodies, content type, response evidence, and serialized sizes are
bounded. No automatic retry or silent fallback exists.

## Secret and redaction boundary

Serializable headers, request arguments, authorization attributes, Provider
request bodies, and result evidence are copied, bounded JSON only, and scanned
recursively for secret-like keys and high-confidence secret values. Credential-
bearing configuration fails closed. Caller mappings are not mutated. Exception
messages and `repr` output never enter diagnostics or evidence. Stable diagnostics
contain no raw authorization, transport, or Provider exception input.

This candidate does not implement Secrets Manager, credential injection,
credential lifecycle, or a real connector. Secrets remain outside the candidate
request and Outcome models.

## Capability Outcome Candidate

The internal Outcome contains Platform Execution Identity, Capability identity,
Provider identity, authorization result, normalized status, stable diagnostic,
zero-or-one bounded invocation evidence, ambiguity, optional opaque native
request ID, and conservative retry safety. It is unfrozen and must not be
treated as a universal Core Outcome, CRD, public schema, or competing Task or
Workflow authority.

## Active integration classification

```text
DEFAULT_TASK_PATH_CONSUMES_CAPABILITY_GATEWAY: NO
ACTIVE_CONSUMER_COUNT: 0
TASK_CONTROLLER_CHANGE: NO
WORKFLOW_CONTROLLER_CHANGE: NO
ACTIVE_RUNTIME_BEHAVIOR_CHANGE: NO
```

## Exact changed paths

- `gateway/src/agent_gateway/`
- `gateway/tests/test_capability_gateway.py`
- `core/tests/test_compatibility.py` (narrow Human-authorized exact-path identity
  consumer allowlist amendment)
- `docs/evidence/s5/v0.2/s5-impl-007/README.md`
- `pyproject.toml` (only `gateway/src` test import discovery)

No dependency or lockfile is changed.

## Validation

Validation results recorded on 2026-08-25:

- targeted S5-IMPL-007 component tests: **36 passed**;
- Gateway/Core/A1/A2/A3/Native/fixture adjacent validation: **222 passed**;
- full pytest: **425 passed**, with one existing Starlette/httpx deprecation
  warning;
- Ruff lint: **passed**;
- Ruff format: **83 files already formatted**;
- `make check`: **passed** with the same 425-test result and warning.

Exact-head CI results are recorded after the Draft PR is created.

## Limitations and Evidence Debt

- This is a synchronous, transport-injected component Candidate with zero active
  consumers, not a production REST connector or unrestricted network client.
- It does not prove live endpoint behavior, authentication, rate limiting,
  cancellation, durable audit, distributed delivery, idempotency, sandboxing,
  long-running operations, or exactly-once execution.
- Timeout and ambiguous transport explicitly retain unknown-effect evidence;
  side effects cannot be excluded and retry safety is not inferred.
- Capability discovery, a production Policy Engine, MCP, Document/File, secret
  lifecycle, third-party Provider conformance, certification, and production
  readiness remain debt or later scope.
- The internal models remain candidates and may change before any Contract or
  schema freeze.

## Rollback and S5-IMPL-008 handoff

Rollback deletes the new `gateway/src/agent_gateway/` package, its component
test, this evidence directory, and the inert `gateway/src` pytest import path.
There is no data, state, schema, wire, API, CRD, dependency, or migration to
reverse.

S5-IMPL-008 may later consume this boundary only after separate authorization
and Human acceptance. It owns Task/Workflow integration and must preserve the
Gateway's authorization-before-invocation, unchanged Platform identity,
zero-call denial, and explicit ambiguity semantics. This Session does not
activate or modify S5-IMPL-008.
