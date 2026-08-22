# S5-SPIKE-004 — CHECKPOINT B RESULT

SESSION

ID: S5-SPIKE-004

TITLE: Agent Instance & Routing

PHASE: S5 / v0.2 CONNECT & MANAGE

TRACK: Agent Instance

MODE: Spike / Experimental

LIFECYCLE: REVIEW

AUTHORIZATION: AUTHORIZED

STATUS: PASS

CHECKPOINT: B

## Results

| Item | Result |
| --- | --- |
| H-INS-01 | **SUPPORTED** |
| H-INS-02 | **SUPPORTED** |
| H-INS-03 | **SUPPORTED** |
| H-INS-04 | **NOT_YET_TESTED** |
| H-INS-05 | **SUPPORTED** |
| Logical endpoint | **PASS** |
| Multi-instance routing | **PASS** |
| Provider-independent caller | **PASS** |
| Realization replacement | **PASS** |
| Shared gateway case | **PASS** |

## Logical Endpoint

The experimental caller expresses only:

- platform execution identity;
- logical Agent Definition identity;
- optional logical Agent Instance identity;
- logical payload.

Its source contains no Pod, container, Hermes, OpenClaw, gateway,
runtime-native endpoint/target, realization, or Provider vocabulary. A source
boundary test enforces that constraint.

## Multi-Instance Routing

One logical Definition, `researcher:v7`, has two eligible Instances:
`researcher-a` and `researcher-b`. Four Definition-addressed requests route in
the deterministic sequence A, B, A, B. The strategy is an in-memory test-only
round robin and makes no production scheduling claim.

An explicit logical `instance_id` can constrain the eligible set. It remains a
platform selector; the caller never supplies a native target.

## Routing Ownership

Observed flow:

```text
Generic Caller
  -> LogicalAgentRequest(definition_id, optional instance_id, execution_id)
  -> ExperimentalPlatformRouter selects eligible AgentInstance
  -> RuntimeBinding lookup
  -> selected Binding's ExperimentalRuntimeProvider
  -> Provider translates Binding to active RuntimeRealization
  -> native target
```

The Router owns Definition/Instance eligibility and deterministic selection.
The Provider receives a Binding that already names the selected Instance. It
can select among that Binding's native realizations, but has no collection of
eligible platform Instances and performs no platform-level Instance selection.
This supports H-INS-05.

## Realization Replacement

Two calls explicitly addressed `researcher-a` with the same logical request.
Between calls, the Provider replaced native target
`shared-gateway/session-a-v1` with `shared-gateway/session-a-v2`.

Both caller-visible outcomes retained the same Instance and execution identity.
Only Provider-side dispatch evidence changed native identity. The Router neither
stored nor inspected the realization and did not need notification of the
replacement.

This validates routing continuity only. It is not runtime or semantic recovery
evidence, and H-INS-04 remains untested.

## Shared Gateway Case

`researcher-a` and `researcher-b` route through distinct Bindings and sessions
under the same `shared-gateway` infrastructure identity. The Router still
selects distinct logical Instances, and the Provider translates them to
distinct session targets.

This falsifies universal equivalence between Instance and endpoint/Gateway.

## Execution Identity

The caller creates `execution_id`. Its exact value is preserved through the
logical request, platform routing, selected Instance, Runtime Binding, Provider
translation, native dispatch evidence, and logical outcome. It is not derived
from or rewritten as a Pod, Gateway, session, realization, or Provider ID.

The spike does not define production uniqueness, retry, idempotency, trace, or
persistence semantics for execution identity.

## Contradictions

None found against the accepted Checkpoint A evidence or shared semantic
baseline. No routing evidence required changing Definition, Instance, Binding,
Provider, execution identity, or normalized-outcome meanings.

## Open Questions

- What eligibility inputs may a production Router use without absorbing
  Provider-native health or placement responsibilities?
- Is explicit Instance targeting public caller intent, a privileged internal
  operation, or both?
- How should the Provider select among multiple active realizations belonging
  to one already-selected Instance?
- Which failures permit retranslation within an Instance versus require a new
  platform Instance selection?
- How should concurrent Router replicas preserve deterministic policy without
  introducing a new source of truth?
- Which execution-identity semantics apply to retries, replay, fan-out, and
  asynchronous observation?

## Production/Core Source Changes

**0.** All changes remain under
`experiments/s5-spike-004-agent-instance-routing/`. No CRD, API, Operator,
Runtime, Console, ADR, frozen Contract, persistent state, or production
scheduler changed.

## Validation

- targeted experimental tests: **9 passed**;
- repository regression / `make check`: **passed**, 166 tests passed with one
  existing Starlette/httpx deprecation warning;
- Ruff lint: **passed**;
- Ruff format check: **passed**;
- pre-commit: **passed** (Ruff lint, Ruff format, pytest);
- `git diff --check`: **passed**;
- secret hygiene: **passed** by inspection and targeted credential-pattern
  scan; native identifiers are synthetic and no credentials are present;
- Production/Core diff: **0 files** by current path inspection.

## Recommendation

**PASS_TO_CHECKPOINT_C**

Checkpoint B supports logical routing and the proposed routing ownership split.
Checkpoint C recovery was not executed and requires Human review/authorization.
