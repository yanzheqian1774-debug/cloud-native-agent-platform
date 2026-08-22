# S5-SPIKE-004 — CHECKPOINT A RESULT

SESSION

ID: S5-SPIKE-004

TITLE: Agent Instance & Routing

PHASE: S5 / v0.2 CONNECT & MANAGE

TRACK: Agent Instance

MODE: Spike / Experimental

STATUS: PASS

CHECKPOINT: A

## Hypotheses

| Hypothesis | Result | Evidence |
| --- | --- | --- |
| H-INS-01 | **SUPPORTED** | A Definition and two Instances retain one Definition identity/version and distinct Instance identities. Instance records do not contain Pod, process, profile, gateway, endpoint, or native IDs. |
| H-INS-02 | **SUPPORTED** | The experimental caller-facing objects select Definition/Instance semantics. Native identity occurs only after Runtime Binding at the Provider boundary. Routing behavior itself was not tested. |
| H-INS-03 | **SUPPORTED** | `researcher:v7` is referenced by `researcher-a` and `researcher-b`; the test requires two unique Instance IDs. |
| H-INS-04 | **NOT YET TESTED** | Replacement preserved logical identity, but no task/session/state/policy continuity probe verified restored platform semantics. Restart or replacement alone is insufficient evidence of recovery. |

## Definition / Instance Boundary

The minimum useful experimental fields were:

- Definition: stable `definition_id` plus immutable/revision-selecting `version`;
- Instance: stable `instance_id`, Definition identity/version reference, desired
  lifecycle, and Runtime Binding reference.

The Definition describes reusable logical intent. The Instance supplies a
separate platform-managed running identity and lifecycle intent. Multiple
Instances can reference the same exact Definition version. These fields are a
spike result, not a proposed production schema; ownership, tenancy, generation,
conditions, execution identity, policies, workspaces, and deletion semantics
remain open.

## Instance / Realization Boundary

The experiment maps:

```text
AgentInstance(instance_id=researcher-a)
  -> RuntimeBinding(binding-a, provider=kubernetes)
  -> RuntimeRealization(realization-1, Pod, pod-uid-1)
  -> replacement RuntimeRealization(realization-2, Pod, pod-uid-2)
```

The Instance ID and Binding ID remain stable while both realization and native
IDs change. This supports a logical Instance/native realization boundary. It
does not establish that every replacement preserves semantic recovery.

## Cardinality Findings

| Relationship | Experimental finding | Constraint status |
| --- | --- | --- |
| Definition -> Instance | 1:N demonstrated | Supported |
| Instance -> Binding | 1:1 used by this minimal model | Provisional, not universal |
| Binding -> active realization | 1:1 replacement and 1:N replicas demonstrated | Provider/runtime dependent |
| Instance -> realization over time | 1:N demonstrated | Supported |
| multiple Instances -> shared Gateway | N:1 demonstrated with distinct gateway sessions | Supported |
| Instance -> Pod | Not invariant | Rejected as a universal equivalence |

The shared-Gateway case agrees with the closed S5-SPIKE-002 OpenClaw evidence:
one Gateway can host multiple logical sessions/runs and its process can be
replaced. The closed S5-SPIKE-001 Hermes evidence left profile/container/gateway
cardinality unresolved. Those sessions were used only as existing evidence and
were not reopened or modified.

## Ownership Findings

The ownership split survived all modeled cases:

- platform owns Definition identity, Instance identity, desired lifecycle, and
  the reference to a Binding;
- Provider validates ownership of the Binding and maps it to zero, one, or
  multiple runtime-native realizations;
- runtime/substrate owns native kinds and IDs such as Pod UID, process ID,
  gateway, or session.

A Provider was explicitly prevented from realizing a Binding assigned to a
different Provider. Sharing a gateway did not transfer native gateway ownership
to either Instance.

## Contradictions

None found against the shared semantic baseline or Accepted ADR ownership
direction. No production implementation was compared or changed to conform to
this experimental model.

## Open Questions

- Must an Instance have exactly one current Runtime Binding, or can rebinding,
  migration, or staged rollout require multiple current/historical Bindings?
- Which semantic probes prove recovery: execution identity, workspace/state,
  policy, capability/model bindings, accepted work, or all of them?
- Is Instance desired lifecycle independent of replica count and execution
  concurrency?
- Which conditions distinguish bound, realizable, runtime-ready,
  dependency-ready, and semantically recovered states?
- What is the portable identity boundary for runtimes whose native Agent,
  profile, session, and gateway lifetimes differ?

## Production/Core Source Changes

**0.** All additions are below
`experiments/s5-spike-004-agent-instance-routing/`. No CRD, API group, frozen
Contract, controller, runtime, Console, or production lifecycle code changed.

## Validation

- targeted experimental tests: **5 passed**;
- repository regression / `make check`: **passed**, 166 tests passed with one
  existing Starlette/httpx deprecation warning;
- Ruff lint: **passed**;
- Ruff format check: **passed**;
- `git diff --check`: **passed**;
- pre-commit: **passed** (Ruff lint, Ruff format, pytest);
- secret hygiene: **passed** by inspection and targeted credential-pattern
  scan; test-only native IDs are synthetic and no credentials are present;
- Production/Core diff: **0 files**.

## Recommendation

**PASS_TO_CHECKPOINT_B**

Checkpoint A supports the separations and cardinality flexibility needed to
evaluate routing. Human review/authorization is required before Checkpoint B.
Do not freeze this spike model as a production Agent Instance schema.
