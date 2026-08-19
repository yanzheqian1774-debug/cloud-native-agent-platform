# Agent Engineering Guide

## Project

Product:
Enterprise Agent Platform

Mission:
Make AI agents production-grade enterprise workloads.

Product Core:
Enterprise Agent Lifecycle Platform

Technical Core:
Kubernetes-native Agent Control Plane.

## Source-of-Truth Hierarchy

Coding Agents must distinguish product direction from current
implementation.

Use this hierarchy:

1. Explicit Task / Acceptance Criteria
2. Current source code and tests
3. Approved ADRs
4. docs/engineering/CURRENT_IMPLEMENTATION.md
5. ARCHITECTURE.md
6. PRODUCT.md
7. ROADMAP.md

If these sources conflict, STOP when the conflict affects task scope,
public behavior, compatibility, or architecture.

Do not silently choose one interpretation.

## Read First

Before significant work, read:

- PRODUCT.md
- ARCHITECTURE.md
- ROADMAP.md
- docs/engineering/CURRENT_IMPLEMENTATION.md
- docs/engineering/REPOSITORY_MAP.md
- docs/engineering/CODEX_WORKFLOW.md
- docs/engineering/DEFINITION_OF_DONE.md
- docs/engineering/ARCHITECTURE_GATES.md

Then inspect task-specific source code, tests, and ADRs.

## Current vs Planned vs Conceptual

Every capability encountered in repository documentation should be
understood as one of:

### CURRENT

Implemented and supported by current source/tests.

### PLANNED

Approved roadmap direction but not necessarily implemented.

### CONCEPTUAL

Architecture exploration or long-term direction that may still change.

ROADMAP.md and ARCHITECTURE.md do not authorize implementation by
themselves.

Never implement a PLANNED or CONCEPTUAL capability unless the assigned
task explicitly includes it.

## Architecture Principles

- Platform != Control Plane.
- Agent Definition != Agent Instance.
- Agent != Runtime.
- Agent != Model.
- Runtime != State.
- Capability != Agent implementation.
- Contract before implementation.
- Reference implementations must be replaceable.
- Governance and Operations are cross-cutting.
- Solutions validate end-to-end platform behavior.

## Hard Rules

DO NOT change public CRD APIs without an approved architecture decision.

DO NOT change the Kubernetes API group without explicit approval.

DO NOT change a frozen Contract without approval.

DO NOT introduce a new persistent infrastructure dependency without
architecture review.

DO NOT introduce secrets into the repository.

DO NOT bypass, weaken, delete, or skip tests merely to make CI pass.

DO NOT silently change product or architecture boundaries.

DO NOT implement roadmap concepts merely because they appear in
PRODUCT.md, ARCHITECTURE.md, or ROADMAP.md.

DO NOT replace Kubernetes as the current Control Plane source of truth
without an approved architecture decision.

If completing a task requires violating a rule above:

STOP.

Report:

1. the conflict;
2. why it is required;
3. affected components;
4. compatibility impact;
5. possible alternatives;
6. recommended architecture decision.

## Scope Discipline

Implement only the assigned task.

Do not perform unrelated cleanup unless it is necessary for the task.

Do not opportunistically introduce future roadmap capabilities.

Prefer small, reviewable changes.

If an improvement is useful but outside scope, report it as follow-up
work instead of implementing it.

## Planning Rule

Use the Architecture Gates.

G0:
bounded autonomous implementation.

G1:
write an implementation plan before changing code.

G2:
STOP and request an architecture decision.

For complex tasks, prefer:

Inspect
→ Plan
→ Implement
→ Validate
→ Review.

## Validation

Run validation relevant to the change.

Repository baseline commands include:

    uv run ruff check .
    uv run pytest
    uv run pre-commit run --all-files
    make check

Frontend changes must additionally run the repository-defined frontend
lint and build commands.

Do not claim validation passed unless it was actually executed.

Do not report stale test counts as current results.

## Delivery

Where applicable, an implementation should include:

- code;
- tests;
- documentation;
- examples;
- migration notes.

Before reporting completion:

- inspect git diff;
- inspect git status;
- ensure no unrelated files changed;
- run required validation;
- disclose known limitations;
- identify follow-up work.

## Git

One engineering task should normally map to:

one Task
→ one Branch
→ one isolated Worktree
→ one PR.

Do not commit directly to main.

Parallel Coding Agents should not share a mutable worktree.

## Architecture Escalation

Follow:

docs/engineering/ARCHITECTURE_GATES.md

Architecture decisions remain human-owned.

## Completion

"Implemented" is not equivalent to "Done".

A task is Done only when applicable Acceptance Criteria and the
Definition of Done have passed.
