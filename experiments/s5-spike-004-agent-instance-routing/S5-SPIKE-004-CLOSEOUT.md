# S5-SPIKE-004 — CLOSEOUT

SESSION

ID: S5-SPIKE-004

TITLE: Agent Instance & Routing

PHASE: S5 / v0.2 CONNECT & MANAGE

TRACK: Agent Instance

MODE: Spike / Experimental

LIFECYCLE: CLOSING

AUTHORIZATION: AUTHORIZED

STATUS: PASS

CHECKPOINT: CLOSEOUT

RESULT: **READY_TO_CLOSE**

DISPOSITION:

- **AGENT_INSTANCE_ROUTING_RECOVERY_DISCOVERY_COMPLETE**
- **READY_FOR_ARCHITECTURE_CONVERGENCE**

This artifact records the Human Final Spike Gate. It does not transition the
session to `CLOSED`; Human close confirmation remains required.

## Checkpoint Final State

| Checkpoint | Lifecycle | Status | Result artifact |
| --- | --- | --- | --- |
| A — Object model | CLOSED | PASS | `S5-SPIKE-004-CHECKPOINT-A-RESULT.md` |
| B — Logical routing | CLOSED | PASS | `S5-SPIKE-004-CHECKPOINT-B-RESULT.md` |
| C — Semantic recovery | CLOSED | PASS | `S5-SPIKE-004-CHECKPOINT-C-RESULT.md` |

No Checkpoint D was created or authorized.

## Final Hypothesis Disposition

| Hypothesis | Final result | Accepted evidence |
| --- | --- | --- |
| H-INS-01 | **SUPPORTED** | Agent Instance is a platform-managed logical running identity distinct from Pod, container, gateway, profile, endpoint, process, and native realization. |
| H-INS-02 | **SUPPORTED** | Caller addresses logical Agent/Instance semantics without knowing runtime-native identity. |
| H-INS-03 | **SUPPORTED** | One Agent Definition can own multiple independently addressable Agent Instances. |
| H-INS-04 | **SUPPORTED** | Recovery requires restoration and verification of platform semantics; native restart/recreation alone is insufficient. |
| H-INS-05 | **SUPPORTED** | Platform selects the logical Instance; Runtime Provider translates only the selected Runtime Binding to native target semantics. |

## Accepted Convergence Inputs

### Agent Instance Boundary

Agent Instance is supported as a platform-managed logical running identity.
Realization identity may change while Instance identity remains stable.

```text
Agent Instance != Pod
Agent Instance != Container
Agent Instance != Gateway
Agent Instance != Profile
Agent Instance != Runtime-native realization
```

This is evidence for architecture convergence, not a frozen production schema
or authorization for an AgentInstance CRD.

### AP-S5-001 — Restart is not Recovery

**STRONGLY SUPPORTED / CROSS-RUNTIME + INSTANCE EVIDENCE / NOT ADR-FROZEN**

Process supervision, Runtime reconciliation, and Agent Instance reconciliation
remain separate layers. `RESTART_SUCCEEDED` does not imply
`RECOVERY_SUCCEEDED`; recovery requires semantic verification.

### AP-S5-010 — Logical Routing Ownership

**SUPPORTED / EVIDENCE-BACKED / READY_FOR_ARCHITECTURE_CONVERGENCE**

Platform owns logical Agent Instance selection. Runtime Provider translates the
selected Runtime Binding into runtime-native realization semantics.

### AP-S5-011 — Platform Execution Identity

**STRONGLY SUPPORTED / CROSS-TRACK / NOT FROZEN**

Execution Identity remains platform-owned across logical routing, Runtime
Binding, Provider translation, failure, and realization replacement.
Provider-native identifiers remain subordinate correlation evidence.

## Unfrozen Recovery Candidates

The spike-local outcomes `RECOVERED`, `NOT_RECOVERED`, and
`RECOVERY_UNKNOWN` remain **NOT FROZEN**. S5-ARCH-003 may determine their final
semantic placement; this closeout does not start that architecture task.

## Evidence Debt and Open Questions

- Define the minimum production Agent Instance identity/lifecycle schema,
  including tenancy, ownership, generation, conditions, and deletion semantics.
- Decide Binding cardinality during rebinding, migration, rollout, and history.
- Define production eligibility and selection inputs without leaking
  Provider-native scheduling concerns into platform routing.
- Decide whether explicit Instance targeting is public, privileged/internal, or
  both.
- Define how a Provider selects among multiple realizations for one already
  selected Instance.
- Define semantic recovery predicates across Runtime, Model, Capability,
  Workspace, Policy, and state concerns without collapsing their ownership.
- Define timeout/escalation semantics for `RECOVERY_UNKNOWN` and treatment of
  in-flight executions during replacement.
- Define Execution Identity uniqueness, retry, replay, idempotency, hierarchy,
  persistence, and opaque native-correlation rules.
- Validate stateful and external/observe-only recovery modes with real runtime
  integrations; the Checkpoint C recovery harness is deterministic and
  in-memory.
- Resolve final condition and recovery-outcome vocabulary through architecture
  convergence before freezing any Contract.

## Artifact Index

- `S5-SPIKE-004-CHECKPOINT-A-RESULT.md` — object-model evidence;
- `S5-SPIKE-004-CHECKPOINT-B-RESULT.md` — logical-routing evidence;
- `S5-SPIKE-004-CHECKPOINT-C-RESULT.md` — semantic-recovery evidence;
- `object_model.py` and `tests/test_object_model.py` — identity, ownership, and
  cardinality harness;
- `generic_caller.py`, `routing.py`, and `tests/test_routing.py` — logical
  routing harness;
- `recovery.py` and `tests/test_recovery.py` — normalized recovery harness.

## Architecture and Production Impact

- Production/Core source changes: **0**;
- ADR changes: **0**;
- public CRD/API changes: **0**;
- frozen Contract changes: **0**;
- new persistent dependencies: **0**.

## Git State

- Branch: `codex/s5-spike-004-agent-instance-routing`;
- Checkpoint C commit: `eba8711`;
- closeout commit: the commit containing this artifact;
- PR: `#35`, draft, targeting `main`;
- working tree before closeout artifact creation: clean and synchronized with
  `origin/codex/s5-spike-004-agent-instance-routing`.

## Final Validation

- targeted experimental tests: **13 passed**;
- repository regression / `make check`: **passed**, 166 tests passed with one
  existing Starlette/httpx deprecation warning;
- Ruff lint: **passed**;
- Ruff format: **passed**;
- pre-commit: **passed** (Ruff lint, Ruff format, pytest);
- `git diff --check`: **passed**;
- secret hygiene: **passed** by inspection and targeted credential-pattern
  scan; native identifiers are synthetic and no credentials are present;
- Production/Core diff: **0 files**.

## Next Action

**WAIT_FOR_HUMAN_CLOSE_CONFIRMATION**
