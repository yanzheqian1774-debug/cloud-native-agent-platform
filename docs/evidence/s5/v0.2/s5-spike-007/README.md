# S5-SPIKE-007 — Synthetic capability fixtures

## Session and Portfolio boundary

- Authorized baseline: `4085aacd840face7bc16c93f75b3e10932c76c3b`
- Branch: `codex/s5-spike-007-capability-rest-fixtures`
- Track/checkpoint: C / Capability REST Fixture Evidence Candidate
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

The harness permits at most one invocation per `execute` call. The scripted
double fails on an unscripted extra invocation, making unintended retries
observable. Timeout and transport ambiguity normalize to `INDETERMINATE`, set
`transport_ambiguous=true`, and keep `retry_safe=false`; the fixtures make no
exactly-once or safe-retry claim.

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

## Validation results

Results recorded on `2026-08-25` from the final candidate:

- targeted S5-SPIKE-007 tests: **16 passed**;
- existing production Capability tests: **none present at this baseline**;
- full pytest: **379 passed**, with one existing Starlette/httpx deprecation
  warning;
- Ruff lint: **passed**;
- Ruff format check: **76 files already formatted**;
- `make check`: **passed** with the same 379-test result and warning;
- `git diff --check`: **passed**;
- path/ownership audit: **passed**; only the two authorized new roots and
  `pyproject.toml` test discovery changed, and GitHub reported no open PRs;
- production import audit: **passed**; no production module imports spike code;
- public API/CRD/schema audit: **passed**; no such file changed;
- dependency/lockfile audit: **passed**; no dependency entry or lockfile
  changed;
- authorization/zero-call/identity audit: **passed by targeted tests**;
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
and the two S5-SPIKE-007 `pyproject.toml` test-discovery entries. No production
behavior, dependency, lockfile, public API, CRD or schema is affected.

After this spike closes and integrates, separately authorized S5-IMPL-007 may
consume the behavioral vectors and tests as design evidence. It must not treat
the Python dataclasses or JSON serialization as a frozen Capability Contract.
