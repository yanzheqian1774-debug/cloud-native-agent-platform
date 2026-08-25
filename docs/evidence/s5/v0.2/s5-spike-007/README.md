# S5-SPIKE-007 — Synthetic capability fixtures

## Session and Portfolio boundary

- Session ID: `S5-SPIKE-007`
- Conversation title: **Capability / REST Fixture Evidence**
- Canonical Portfolio title: **Synthetic capability fixtures**
- Authorized baseline: `4085aacd840face7bc16c93f75b3e10932c76c3b`
- Checkpoint A head: `120de72b525f7a0fb510ea96cf08aaf18e70a927`
- Branch: `codex/s5-spike-007-capability-rest-fixtures`
- Track/checkpoint: C / Checkpoint B — Capability Fixture Evidence Convergence
- Production change: **NO**
- Public Contract, API, CRD or schema freeze: **NO**
- Real Connector or credential use: **NO**

The exact accepted Portfolio row is:

> `S5-SPIKE-007 — Synthetic capability fixtures | SPIKE/C; REST/MCP/document/policy vectors | S5-PLAN-001; new isolated fixtures; excludes Contract/Core | Entry authorization→Fixture Gate; deterministic bundle; fixture PR | 1–2 sessions/high/Prep-1/C/E`

That row establishes the title **Synthetic capability fixtures**, objective
**REST/MCP/document/policy vectors**, predecessor **S5-PLAN-001**, output
**deterministic bundle and fixture PR**, writable scope **new isolated
fixtures**, and exclusions **Contract/Core**. Its acceptance path is Entry
authorization to the Human Fixture Gate. Its downstream consumers are Tracks C
and E. The preparatory-work table further assigns this Session only new
fixture/service paths plus tests/evidence outside production, with a local
Provider protocol/spy and mock identity/deny-before-handoff vectors.

The Portfolio explicitly makes S5-IMPL-007 depend on `A2,SPIKE-007` and gives
that later Session ownership of the Capability gateway/REST implementation and
the relevant TDA/MRA acceptance criteria. Therefore this spike is fixture
input, not an acceptance owner or production implementation.

Preflight found `origin/main` exactly at the authorized baseline, a clean new
isolated worktree, no pre-existing S5-SPIKE-007 branch/worktree, and no open PR
claiming these paths.

Checkpoint B reviewed and modifies exactly these existing paths:

1. `experiments/s5-spike-007-capability-rest-fixtures/capability_fixture.py`;
2. `experiments/s5-spike-007-capability-rest-fixtures/tests/test_capability_fixture.py`;
3. `docs/evidence/s5/v0.2/s5-spike-007/README.md`.

No additional path is introduced or modified at Checkpoint B.

## Fixture architecture

The disposable bundle contains:

- a synthetic Capability request and ALLOW/DENY authorization contexts;
- a deterministic scripted REST Provider double with an invocation counter
  and captured-request evidence;
- REST success, 4xx, 5xx and malformed-response fixtures;
- explicit timeout and post-invocation transport-ambiguity exceptions;
- a normalized Capability Outcome candidate with stable reason codes; and
- tests for authorization ordering, identity authority, immutability and
  redaction.

All data is synthetic. JSON is only a machine-readable test representation;
its names, shape, nesting and encoding are not a proposed public schema.

```text
synthetic request + authorization context
              |
              v
      request/target validation ----- invalid --------> outcome; calls = 0
              |
              v
      fail-closed decision check ---- DENY/invalid ---> outcome; calls = 0
              |
            ALLOW
              v
      scripted REST Provider double ---------------> outcome; calls = 1
```

## ALLOW, DENY and invocation evidence

An exact ALLOW with a well-formed context invokes the Provider once. A DENY is
resolved before the Provider handoff and leaves the counter at exactly zero.
Missing, ambiguous or malformed decisions also fail closed with zero calls.
The Provider returns transport/response evidence only and has no path to
override authorization.

Missing Capability or Platform Execution Identity, an invalid Provider target,
a non-mapping request, non-string argument keys and an unsupported operation
are rejected before authorization handoff or Provider invocation. None can
fall back to ALLOW. A conflicting `ALLOW`/`DENY` value is classified as
ambiguous and fails closed.

The harness permits at most one invocation per `execute` call. The scripted
double fails on an unscripted extra invocation, making unintended retries
observable. Timeout and transport ambiguity normalize to `INDETERMINATE`, set
`transport_ambiguous=true`, and keep `retry_safe=false`; the fixtures make no
exactly-once or safe-retry claim.

## Failure and ambiguity matrix

| Vector | Calls | Candidate status / reason | Retry |
| --- | ---: | --- | --- |
| Explicit ALLOW + success | 1 | `SUCCEEDED / CAPABILITY_INVOCATION_SUCCEEDED` | no automatic retry |
| Explicit DENY | 0 | `DENIED / AUTHORIZATION_DENIED` | none |
| Missing decision | 0 | `DENIED / AUTHORIZATION_DECISION_MISSING` | none |
| Unknown or conflicting decision | 0 | `DENIED / AUTHORIZATION_DECISION_AMBIGUOUS` | none |
| Malformed authorization | 0 | `DENIED / AUTHORIZATION_CONTEXT_MALFORMED` | none |
| Missing identity / invalid target or request | 0 | `REJECTED` with stable bounded reason | none |
| REST 4xx | 1 | `FAILED / PROVIDER_CLIENT_ERROR` | false |
| REST 5xx | 1 | `FAILED / PROVIDER_SERVER_ERROR` | false |
| Malformed response | 1 | `FAILED / PROVIDER_RESPONSE_MALFORMED` | false |
| Timeout | 1 | `INDETERMINATE / PROVIDER_TIMEOUT_EFFECT_UNKNOWN` | false; effects unknown |
| Transport ambiguity | 1 | `INDETERMINATE / PROVIDER_TRANSPORT_EFFECT_UNKNOWN` | false; effects unknown |

## Outcome and diagnostic candidate

`CapabilityOutcome` is a private spike candidate, not a universal Core Outcome.
It records status, stable redacted reason, Platform Execution Identity,
Capability identity, Provider identity, optional native request correlation,
result, invocation evidence, retry safety and transport ambiguity.

Stable reasons include:

- `AUTHORIZATION_DENIED`;
- `AUTHORIZATION_DECISION_MISSING`;
- `AUTHORIZATION_DECISION_AMBIGUOUS`;
- `AUTHORIZATION_CONTEXT_MALFORMED`;
- `AUTHORIZATION_CONTEXT_IDENTITY_MISMATCH`;
- `CAPABILITY_IDENTITY_MISSING`;
- `PLATFORM_EXECUTION_IDENTITY_MISSING`;
- `PROVIDER_TARGET_INVALID`;
- `CAPABILITY_REQUEST_MALFORMED`;
- `CAPABILITY_OPERATION_UNSUPPORTED`;
- `CAPABILITY_INVOCATION_SUCCEEDED`;
- `PROVIDER_CLIENT_ERROR` and `PROVIDER_SERVER_ERROR`;
- `PROVIDER_RESPONSE_MALFORMED`; and
- `PROVIDER_TIMEOUT_EFFECT_UNKNOWN` and
  `PROVIDER_TRANSPORT_EFFECT_UNKNOWN`.

Exception messages and response bodies are never interpolated into diagnostic
reasons. The fixtures contain no credentials, tokens, secret values or real
enterprise identifiers.

## Identity and authority boundaries

The Platform Execution Identity is supplied by the caller and copied unchanged
through every outcome and Provider request capture. Capability identity,
Capability Provider identity and Provider-native request ID are separate
fields. Tests prove all four synthetic values are distinct and that a native
request ID cannot substitute for Platform authority.

Discovery is outside this harness. Authorization is a separate caller-supplied
decision that must be valid before invocation. This separation is intentional:
the Provider cannot discover itself into authorization or change ALLOW/DENY.

The outcome is `INTERNAL_FIXTURE_CANDIDATE`. It is not a universal Core
Outcome, public API, CRD, frozen schema, certification claim or production
Connector evidence. S5-IMPL-007 may reuse its behavioral semantics but must
define its own bounded internal interface and must never import `experiments/`
as a production dependency.

## Validation results

Checkpoint A CI on commit `120de72b525f7a0fb510ea96cf08aaf18e70a927`
passed both **Quality Gates** and **Frontend Quality Gates**. Checkpoint B
results recorded on `2026-08-25` from the converged candidate:

- targeted S5-SPIKE-007 tests: **26 passed**;
- existing production Capability tests: **none present at this baseline**;
- full pytest: **389 passed**, with one existing Starlette/httpx deprecation
  warning;
- Ruff lint: **passed**;
- Ruff format check: **76 files already formatted**;
- `make check`: **passed** with the same 389-test result and warning;
- `git diff --check`: **passed**;
- path/ownership audit: **passed**; only the two authorized new roots and
  `pyproject.toml` test discovery changed, and GitHub reported no open PRs;
- production import audit: **passed**; no production module imports spike code;
- public API/CRD/schema audit: **passed**; no such file changed;
- dependency/lockfile audit: **passed**; no dependency entry or lockfile
  changed;
- authorization/zero-call/identity audit: **passed by targeted tests**;
- missing/ambiguous/request/target/operation audit: **passed by targeted
  tests**;
- timeout/retry audit: **passed by targeted tests**; one call, explicit
  ambiguity and no automatic retry;
- state-isolation audit: **passed**; counters and request captures are
  instance-local;
- Capability Outcome non-promotion audit: **passed**; references occur only in
  the isolated experiment and its evidence;
- Secret/redaction audit: **passed**; no credential pattern or real material
  occurs in fixtures, and raw synthetic failure detail is not exposed;
- relative-link audit: **passed**; this evidence adds no relative link;
- rollback audit: **passed**; every changed path is covered below.

## Limitations and Evidence Debt

- This is a synchronous in-memory harness, not a network client or production
  Gateway/Provider.
- It proves deterministic normalization, not HTTP stack behavior, distributed
  delivery, cancellation, rate limiting, retries or idempotency.
- It does not implement discovery, policy evaluation, MCP, Document/File,
  sandboxing, credential binding, registry behavior or a real Connector.
- The candidate operation and outcome shapes may be discarded or adapted when
  the Track A identity/interface handoff is available.
- S5-IMPL-007 must define its bounded internal interface under separate
  authorization and retain deny-before-invocation, unchanged Platform identity
  and explicit ambiguity semantics.

## Rollback and S5-IMPL-007 handoff

Rollback is deletion of
`experiments/s5-spike-007-capability-rest-fixtures/`, this evidence directory,
and, for complete discovery cleanup, the two inert S5-SPIKE-007
`pyproject.toml` test-discovery entries added at Checkpoint A. There is no data,
state or schema migration. Deleting the isolated Fixture/test/evidence files
alone removes all executable and documentary spike behavior. No production
behavior, dependency, lockfile, public API, CRD or schema is affected.

After this spike closes and integrates, separately authorized S5-IMPL-007 may
consume the behavioral vectors and tests as design evidence. It must not treat
the Python dataclasses or JSON serialization as a frozen Capability Contract.

```text
NEXT_RECOMMENDED_SESSION: S5-IMPL-007
NEXT_RECOMMENDED_TITLE: Capability gateway and REST
NEXT_SESSION_TYPE: IMPL
NEXT_SESSION_STATE: RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED
S5_IMPL_007_ENTRY: READY_ONLY_AFTER_S5_SPIKE_007_CLOSE_AND_DURABLE_INTEGRATION
S5_IMPL_008_STATE: NEW / NOT_ACTIVE / NOT_AUTHORIZED
```
