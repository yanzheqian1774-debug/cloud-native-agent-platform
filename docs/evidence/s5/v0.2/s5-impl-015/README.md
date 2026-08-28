# S5-IMPL-015 — Bounded Intent and Canonical Planning Evidence

## Scope

Checkpoint A implements Package 1 from S5-PLAN-003 as an internal, in-memory,
non-executable planning boundary. It converts one bounded supplier-quality question
into inert generator output, deterministic validated planning contracts, an exact
planning approval, and an immutable canonical revision eligible only for future
Package 2 matching.

Architecture authority is S5-ARCH-006, S5-ARCH-010, S5-ARCH-011, and S5-ARCH-012.
The implementation starts from durable baseline
`05bac769b61f42aa5643a8496861e8e962c6bf5b` on branch
`codex/s5-impl-015-bounded-intent-canonical-planning`.

## Implemented boundary

- `BusinessQuestion`, `IntentCandidate`, `IntentRevision`, `TaskRequirement`,
  `WorkflowCandidate`, and deterministic `ValidationReport` internal contracts;
- NFC canonical JSON and SHA-256 digest versioning;
- deterministic Task identity, dependency normalization and topological ordering;
- duplicate, missing, self-dependency, cycle, unsupported and unresolved rejection;
- a maximum of 32 Tasks, 128 dependencies and 32,000 serialized candidate characters;
- separate exact-digest and exact-policy planning approval with idempotent replay;
- immutable corrected successor requiring a fresh digest, validation and approval;
- tenant and security-domain isolation;
- a pluggable generator port with an inert deterministic supplier-quality reference;
- matching eligibility only, explicitly excluding execution eligibility.

## Side-effect and authority exclusions

There is no public API, CRD, Workflow lifecycle, shared DTO, Canonical Graph,
persistence, dependency, CI workflow or frontend change. Package 1 performs no
matching, placement, Runtime, Provider, Capability, Knowledge, Kubernetes, network,
credential or external-persistence operation. It does not create Task CRDs or mint a
Platform Execution Identity.

`CANONICALIZED` means only that the exact approved internal revision is eligible for
a future Package 2 matcher. It does not mean published, executable, placed,
Runtime-bound or ready for execution.

## Focused validation

Commands required for Checkpoint A:

```text
uv run pytest console/backend/tests/test_planning.py console/backend/tests/test_planning_generator.py
uv run ruff check console/backend/src/agent_console/planning.py console/backend/src/agent_console/planning_generator.py console/backend/tests/test_planning.py console/backend/tests/test_planning_generator.py
uv run ruff format --check console/backend/src/agent_console/planning.py console/backend/src/agent_console/planning_generator.py console/backend/tests/test_planning.py console/backend/tests/test_planning_generator.py
```

The focused suite covers deterministic generation and canonicalization, exact digest
and policy approval, replay conflicts, rejection, the exact 128-dependency boundary,
cycle and malformed input rejection, immutable correction/successor behavior,
tenant/security-domain isolation, and absence of downstream authority.

Checkpoint A result at the uncommitted implementation head:

- focused pytest: `20 passed`;
- focused Ruff lint: passed;
- focused Ruff format check: passed with all four files already formatted.

Checkpoint A remains uncommitted. Exact-head CI, durable integration, Package 2–4,
Golden Demo, REL, Release, production readiness and certification are not claimed.

## Checkpoint B semantic audit and validation

Checkpoint B added focused evidence for the exact 32-Task and 32,000-character
ceilings, stored digest and policy substitution, malformed approval fields, non-UTC
timestamps, and immediate successor eligibility. The audit also normalized set-like
collections before canonicalization so incidental ordering cannot change canonical
bytes or digest. Approved successor linkage now makes the predecessor ineligible in
the engine's explicit eligibility relation while preserving its immutable record and
approval decision.

Exact Checkpoint B commands and results:

```text
uv run pytest console/backend/tests/test_planning.py console/backend/tests/test_planning_generator.py
# 27 passed

uv run ruff check console/backend/src/agent_console/planning.py console/backend/src/agent_console/planning_generator.py console/backend/tests/test_planning.py console/backend/tests/test_planning_generator.py
# passed

uv run ruff format --check console/backend/src/agent_console/planning.py console/backend/src/agent_console/planning_generator.py console/backend/tests/test_planning.py console/backend/tests/test_planning_generator.py
# four files already formatted

make check
# Ruff lint passed; format check passed with 125 files already formatted; 753 tests passed; one existing Starlette/httpx deprecation warning

uv run pre-commit run --all-files
# Ruff lint, Ruff format, and pytest hooks passed
```

The all-files hooks did not add or modify any unauthorized path. A final non-mutating
validation and seven-path diff audit follow the all-files hook run. Checkpoint B
remains uncommitted and makes no exact-head CI or durable integration claim.

## Checkpoint C terminal local validation

Before commit and handoff, Checkpoint C repeated the complete local gates on the
authorized branch and seven-path diff:

- focused pytest: `27 passed`;
- focused Ruff lint: passed;
- focused Ruff format verification: four files already formatted;
- `make check`: Ruff lint passed, 125 files already formatted, and `753 passed`;
- `uv run pre-commit run --all-files`: Ruff lint, Ruff format, and pytest passed;
- `git diff --check`: passed;
- manifest, lockfile, public API, CRD, Workflow lifecycle, shared DTO, Canonical
  Graph, persistence, CI workflow, frontend and downstream-authority audits: no
  impact.

One existing Starlette/httpx deprecation warning remains. Terminal commit, push, PR
and exact-head CI facts are recorded only after they exist. PR merge, Durable
Integration, exact-main CI, Human closure, REL and downstream work remain outside
S5-IMPL-015 authority.

## Checkpoint C Git and PR handoff

- Authorized baseline: `05bac769b61f42aa5643a8496861e8e962c6bf5b`.
- Implementation commit: `388c37b4ecdf22502f1578fb470d0b40ac048891`.
- Commit parent: `05bac769b61f42aa5643a8496861e8e962c6bf5b`.
- Branch: `codex/s5-impl-015-bounded-intent-canonical-planning`.
- Push: normal, non-force push to the authorized branch only.
- Pull request: Draft PR #75, head is the authorized branch and base is `main`.
- PR state at recording: open and unmerged.
- Final Evidence commit and exact-head CI: pending at this recording point.

The PR description records Package 1 scope, Portfolio and Architecture authority,
validation, known limitations, boundary exclusions, and the requirement for a
separately Human-authorized REL Session before Durable Integration. S5-IMPL-015 does
not authorize PR merge.

## Governance reconciliation

S5-PLAN-003 was Human-confirmed closed after PR #74 merged at durable main
`05bac769b61f42aa5643a8496861e8e962c6bf5b` and exact-main CI run `33145152123`
succeeded. This task forward-records that terminal fact without reopening the plan or
claiming that S5-IMPL-015 or any downstream Session is closed or integrated.
