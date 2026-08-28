# S5-IMPL-031 Checkpoint C Terminal Implementation Evidence

## Scope

Checkpoint C validates Package 3 from S5-PLAN-003 as an internal, immutable,
in-memory Runtime Requirement and authorization-first Native placement boundary.
It changes no public API, CRD, shared DTO, Canonical Graph, persistence,
dependency, Workflow lifecycle, CI, frontend, Runtime lifecycle, or Package 4
path.

## Authority and baseline

- Baseline: `24525693464e3604d3d93619b606572317217cd9`.
- Branch: `codex/s5-impl-031-runtime-requirement-native-placement`.
- Portfolio authority: S5-PLAN-003, exact Package 3 section.
- Architecture: S5-ARCH-011; S5-ARCH-013 for advisory Package 2 matching;
  accepted Runtime Provider architecture; current Native compatibility and
  execution ownership boundaries.

## Implementation

`runtime_placement.py` derives a canonical `RuntimeRequirement` only from an
exactly approved `CanonicalWorkflowRevision` and complete advisory-only
`RoleMatchDecision` bindings. The record binds the Workflow identity/digest,
tenant, security domain, Task/Definition versions and digests, exact Native
identity/version/profile, Capability, Provider, and permission requirements.

`NativePlacementEvaluator` checks authorization and isolation before inspecting
the read-only declared-target tuple. It uses existing exact Native compatibility
semantics, sorts declarations deterministically, fails closed for missing,
malformed, stale, unknown, unavailable, incompatible, or ineligible inputs, and
emits an immutable digest-bound `NativePlacementDecision`. A successful decision
contains only an inert handoff value. Provider, Runtime, gateway, and execution
coordinator call counters are always zero.

## Safety ceilings

- 32 Tasks and 32 Runtime inputs per Task.
- 1,024 total derived bindings.
- 64 declared Native candidates and one supported Native family.
- 2,048 evaluations, 32 reason codes, and 32 KiB canonical request.
- 200-character identifiers and 500-character semantic fields.
- Overflow rejects without truncation or partial placement.

## Validation

- Focused Package 3 tests, including final hardening: 33 passed.
- Focused Ruff lint and format checks: passed.
- Planning, matching, Native compatibility, and execution coordinator regression
  slice: 153 passed before final hardening; the final complete repository gates
  include the hardened tests.
- Initial `make check`: 821 passed with one existing Starlette/httpx warning.
- `uv run pre-commit run --all-files`: all hooks passed and changed no
  unauthorized path.
- Post-hook `make check`: 821 passed with the same existing warning.
- Final hardened all-file pre-commit: all hooks passed.
- Final hardened `make check`: 823 passed with the same existing warning.
- Final diff, exact three-path, untracked-file, and impact audits passed.

## Terminal handoff

- Final commit: pending terminal commit.
- Push: pending terminal commit.
- Draft PR to `main`: pending terminal commit and normal push.
- Exact-head CI: pending Draft PR.
- Intended REL candidate `S5-REL-032`: collision audit found no repository
  content, local/remote ref, tag, worktree, commit, PR, issue, or current task
  owner; candidate only and not allocated.
- Fallback `S5-REL-034`: the same read-only collision audit found no collision;
  candidate only and not allocated.

The terminal source commit intentionally records push, Draft PR, and exact-head
CI as pending because those actions occur only after the immutable source commit.
Later CI truth may be recorded in the PR description without changing source.
This Evidence claims no execution, merge, integration, closure, Package 4,
Package 5, Demo, Release, REL allocation, or downstream authority.
`PROJECT_STATE.md` and `docs/governance/REGISTRY.md` retain the acknowledged
non-blocking forward-recording lag and remain unchanged.
