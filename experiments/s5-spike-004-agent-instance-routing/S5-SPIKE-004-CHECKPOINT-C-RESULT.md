# S5-SPIKE-004 — CHECKPOINT C RESULT

SESSION

ID: S5-SPIKE-004

TITLE: Agent Instance & Routing

PHASE: S5 / v0.2 CONNECT & MANAGE

TRACK: Agent Instance

MODE: Spike / Experimental

LIFECYCLE: REVIEW

AUTHORIZATION: AUTHORIZED

STATUS: PASS

CHECKPOINT: C

## Results

| Item | Result |
| --- | --- |
| H-INS-01 | **SUPPORTED** |
| H-INS-02 | **SUPPORTED** |
| H-INS-03 | **SUPPORTED** |
| H-INS-04 | **SUPPORTED** |
| H-INS-05 | **SUPPORTED** |
| Failure observation | **PASS** |
| Realization replacement | **PASS** |
| Semantic verification | **PASS** |
| Negative restart != recovery | **PASS** |
| Execution identity | **SUPPORTED** |
| AP-S5-001 | **SUPPORTED** |
| AP-S5-010 | **SUPPORTED** |
| AP-S5-011 | **SUPPORTED** |

## Failure Observation

The experiment begins with logical Instance `researcher-a`, Binding
`binding-a`, and native realization `session-a-v1` in normalized state:

```text
RuntimeAvailable = TRUE
InfrastructureAvailable = TRUE
```

A deterministic Provider-side failure marks the native session unavailable.
The platform-facing observation preserves Instance and realization identity,
keeps synthetic native evidence separate, and transitions:

```text
RuntimeAvailable: TRUE -> FALSE
InfrastructureAvailable: TRUE
```

Infrastructure remains available in this managed experimental case while the
runtime semantic surface is unavailable. For an external target where
infrastructure is outside the observation/ownership boundary, the experiment
reports `InfrastructureAvailable = NOT_APPLICABLE`. When the Provider cannot
establish runtime truth after recreation, it reports
`RuntimeAvailable = UNKNOWN` rather than manufacturing readiness.

No `TaskReady` Runtime condition was introduced.

## Reconciliation Ownership

The evidence keeps three layers distinct:

| Layer | Experimental responsibility |
| --- | --- |
| Process supervision | Native substrate may recreate a process/session and report native action evidence. |
| Runtime reconciliation | Provider translates the selected Binding, performs an owned runtime-specific recreation, and observes runtime semantics. |
| Agent Instance reconciliation | Platform detects divergence in normalized observations and verifies that the same logical Instance is semantically reachable again. |

The platform reconciler does not create native targets. The Provider does not
select a platform Instance. A substrate/native restart is only an input to
semantic verification, never the recovery verdict.

## Realization Replacement

Both positive and negative cases replace `session-a-v1` with `session-a-v2`
while retaining:

- Instance identity `researcher-a`;
- Binding identity `binding-a`;
- logical Definition identity `researcher:v7`;
- platform execution identity for the verification route.

The required old/new realization inequality passed. It was not used alone to
claim recovery.

## Semantic Verification

The positive case requires all of the following before returning the candidate
outcome `RECOVERED`:

1. selected Binding has a replacement realization;
2. Provider resolves that Binding and observes `RuntimeAvailable = TRUE`;
3. logical routing reaches the same `researcher-a` Instance again;
4. caller and dispatch evidence preserve the platform execution ID;
5. old and new realization identities differ.

All five checks passed. The Router did not inspect or learn that realization
identity changed.

## Negative Restart != Recovery

The negative case successfully performs Provider/native recreation and obtains
a different realization ID. Its semantic readiness probe remains false and the
logical route raises an unavailable error. The result is:

```text
RESTART_SUCCEEDED = TRUE
RECOVERY_SUCCEEDED = FALSE
candidate outcome = NOT_RECOVERED
```

This is direct falsification evidence against equating native restart with
Agent Instance recovery and supports H-INS-04 and AP-S5-001.

## Recovery Outcome

The bounded evidence found three normalized result categories useful:

- `RECOVERED`: applicable runtime condition is true and logical routing to the
  same Instance is verified;
- `NOT_RECOVERED`: native action completed but applicable semantic verification
  is false;
- `RECOVERY_UNKNOWN`: native action completed but semantic truth cannot be
  established.

These names are spike-local candidates. They are not a frozen Contract, schema,
condition set, or production state machine. Provider-native evidence remains a
separate opaque string in the experiment.

## Execution Identity

The positive case uses `execution-stable` before failure and after verified
recovery. The same value is preserved across caller, Router, Instance selection,
Binding, Provider translation, native dispatch evidence, and logical outcome.
It is independent from `session-a-v1` and `session-a-v2`.

This adds recovery-path support for AP-S5-011. It does not freeze uniqueness,
retry, idempotency, parent/child, persistence, or Provider-native correlation
semantics.

## Architecture Principle Evidence

- **AP-S5-001 — SUPPORTED:** native restart/recreation is neither necessary
  evidence nor sufficient proof of semantic recovery; explicit semantic
  verification determines the outcome.
- **AP-S5-010 — SUPPORTED:** recovery routing still leaves logical Instance
  selection with the platform and selected-Binding translation with the
  Provider.
- **AP-S5-011 — SUPPORTED:** platform execution identity survives routing,
  Provider translation, failure, realization replacement, and post-recovery
  verification without becoming a native realization ID.

All three remain candidates/evidence. This spike does not freeze them or modify
architecture baselines or ADRs.

## Contradictions

None found against the accepted Checkpoint A/B evidence or shared semantic
baseline. No production architecture change was needed.

## Open Questions

- Which required conditions and Binding/model/capability/workspace/policy probes
  form the production semantic recovery predicate for each Instance class?
- Who times out `RECOVERY_UNKNOWN`, and when may it become `NOT_RECOVERED`?
- How are in-flight executions classified when realization replacement occurs?
- Which Provider ownership modes permit active recovery versus observation only?
- How should stateful Runtime semantics be verified without conflating state
  portability with Runtime availability?
- What compatibility rules govern recovery outcomes and condition vocabulary if
  they become a formal Contract?

## Production/Core Source Changes

**0.** All changes remain under
`experiments/s5-spike-004-agent-instance-routing/`. No CRD, API, Operator,
Runtime, Console, ADR, frozen Contract, persistent state, production controller,
or production Provider changed.

## Validation

- targeted experimental tests: **13 passed**;
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

**PASS_TO_ARCHITECTURE_CONVERGENCE**

Checkpoint C is the final planned checkpoint. No Checkpoint D was created. The
session transitions to Human Final Spike Review, not closing.
