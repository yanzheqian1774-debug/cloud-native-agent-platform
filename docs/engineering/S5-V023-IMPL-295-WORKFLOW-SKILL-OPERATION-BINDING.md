# S5-V023-IMPL-295 Workflow Skill operation-binding UI

## Authority, baseline and gate

- Session: `S5-V023-IMPL-295`; type: bounded frontend implementation.
- Source: `6035917d7a6f31ee12cf121ff9958d2326f9879d`; tree:
  `eb88a36cfd15d93280aa51a656690e9e6c732ccf`.
- Controlled refresh source: `ae002a2e9a4b765fe311e1e74328a9b6111a4929`;
  tree: `d007b63a4ab4a6bd38849d3c03df5ff6927d07a7`. The ordinary
  `--no-ff` merge has parents `9157bf3e2c94f3772084fb8e837182784ad1a7cb`
  and `ae002a2e9a4b765fe311e1e74328a9b6111a4929`.
- Branch: `codex/s5-v023-impl-295-workflow-skill-operation-binding` in the
  isolated `a8e2` worktree.
- Architecture gate: G1. This task adds a Console capability behind the existing
  private Workflow API. It does not change a public API, CRD, Workflow lifecycle,
  persistence, resolver, execution authority or Skill domain authority.

The accepted identity and execution boundaries are
`S5-V023-IMPL-288-GOVERNED-EXECUTION-AUTHORITY-ADDENDUM-V1` and
`S5-V023-ARCH-263-SKILL-ATTEMPT-EXECUTOR-SIDE-EFFECT-CONTRACT-V1`. Current wire
authority is `workflow_definition_schemas.py` plus its service and API tests.

## Current contract used by the frontend

Each Workflow task may omit `skillOperationBindings` for historical compatibility.
When present, the non-empty collection contains only:

```text
skillId + skillRevisionId + skillDigest + operation
```

The same task must contain a matching `SKILL` exact reference. Existing non-empty
bindings cannot be deleted by omission, `null` or an empty collection. A retained
binding is sent back explicitly during unrelated edits. Historical unbound content
is not backfilled, and published content or digests are never rewritten.

A successor copies the immutable published content into a new Draft. It does not
validate, review, publish, approve a Plan or grant execution. Binding and publication
do not create a Run, Task Run, Attempt, executor selection, credential authority or
dispatch authority.

## 293 dependency and controlled-refresh checkpoint

At implementation start, the local 293 branch
`codex/s5-v023-impl-293-workflow-skill-authoring` still pointed to
`adcd648a0fc8ca60066f52665ce0e83d7332b7dd`. There was no 293-specific reviewable
commit, operation-directory DTO or endpoint contract.

During implementation, the remote 293 branch published reviewable candidate
`932afaeb06b8388926c5cf63eeddbebec1b3393e`, tree
`045616e621d12c7664e091d52e2c944cd8bdbbdb`. It is based on `adcd648...`, while
295 is based on main merge `6035917...`; it was inspected directly and was not
merged, cherry-picked or copied from a mutable worktree.

That candidate confirms the existing `GET /api/internal/v0.2.2/resources/skill`
projection as the operation directory. An eligible item comes only from the exact
current published revision of an enabled, non-archived, non-deprecated Skill. Its
strict operation record contains `name`, input/output schemas, `READ_ONLY`
side-effect class, exact executor identity/configuration digest, side-effect policy
identity/digest and versioned I/O limits. Invalid, absent, null, empty or duplicate
operations fail closed. The Workflow resolver independently validates the same exact
Skill ID, revision, digest and operation during validate and publication.

The frontend uses a dedicated strict read adapter over that confirmed GET projection.
It does not change the shared Skill adapter and does not treat `capabilities`, Skill
names or revision-level schemas as operation identities.

The 293 implementation subsequently entered formal main through REL-296. This branch
was refreshed only to the fixed commit and tree above, without rebase, squash, amend,
force-push or use of the 293 worktree/runtime. Migrations `0001` through `0017` match
that main tree exactly. The refreshed candidate therefore exercises the same strict
GET projection and Workflow resolver used by the production backend rather than a
copied or test-only resolver.

## Frontend behavior

The Workflow Builder shows a binding section for every canonical task. Selectors
start empty and require the user to choose Skill resource, exact published revision
and exact operation in sequence. The selected operation preview shows the formal
schemas, side-effect/executor/policy identities and I/O constraints before the
binding is written into the Draft. Existing bindings show the exact Skill resource
ID, revision ID, digest and operation, and verify that the task still carries its
matching `SKILL` reference. The paired reference is protected from binding-only
removal. Generic references remain available to existing Workflow consumers and
never create operation bindings implicitly.

The Workflow detail surface repeats the actual bindings before lifecycle controls so
the exact saved state is visible before validate, review or publish. Revision history
also reports the number of bound operations. Missing values and unavailable
operation-directory metadata remain visible as missing.

Request generations protect selection, refresh, save and lifecycle reads from stale
responses. Duplicate synchronous writes are suppressed. On edit or lifecycle CAS
conflict, the page performs one authoritative GET, retains the user's complete Draft
input, and never automatically replays the write.

Final frontend audit findings were resolved in the candidate: a successor Draft does
not hide the still-current `publishedRevisionId`; Workflow writes remain disabled
while another resource is loading; and a Skill reference must match the binding's
resource ID, revision and digest before the UI reports it as verified or enables
validation. Both reason-code objects and FastAPI validation-detail arrays remain
controlled error responses.

## Validation boundary

Frontend lint, production build and focused Workflow/Runtime regression are required
for this checkpoint. Mocked error/latency tests prove deterministic local state
handling but do not replace the production API lifecycle. The real combined browser
case provisions Runtime and Skill dependencies through formal HTTP, creates a
historical unbound Workflow revision, explicitly selects and saves the published
Skill revision and operation through the Workflow UI, then confirms the authoritative
GET, unrelated-edit retention, exact pre-review identity, validate/review/publish and
successor behavior. The same real case exercises invalid operation and unavailable
Skill rejection, CAS recovery without replay, duplicate-write suppression, a delayed
real detail response, keyboard focus order and 390 px overflow.

## Candidate validation and changed paths

Focused validation on the refreshed candidate passed:

- `npm run lint`;
- `npm run build` with 106 transformed modules;
- six focused Playwright tests for explicit three-stage selection/save/edit/readback,
  exact operation metadata, invalid-resource exclusion, 390 px overflow, edit CAS
  retention/no replay, successor-Draft eligibility, exact reference-digest matching,
  FastAPI validation-detail handling and late detail response suppression.
- one real combined frontend/backend Playwright case using dedicated PostgreSQL and
  Qdrant containers, formal Skill/Runtime/Workflow HTTP, and the real Workflow UI;
- the refreshed 293 Skill-operation schema and resolver tests (`4 passed`).

The current-main Workflow contract tests passed `14` cases. Repository-wide
`make check` passed Ruff, formatting and `1544 passed / 103 environment-dependent
skipped`; those skips are not integration evidence.

Changed paths are limited to:

- `console/frontend/src/api/workflowDefinitions.ts`;
- `console/frontend/src/api/workflowSkillOperations.ts`;
- `console/frontend/src/workflows/WorkflowBuilderPage.tsx`;
- `console/frontend/src/workflows/WorkflowSkillOperationBindingEditor.tsx`;
- `console/frontend/src/workflows/WorkflowWorkbenchPage.tsx`;
- `console/frontend/src/styles/resource-management.css`;
- `console/frontend/tests/e2e/workflow-runtime-workbench.spec.ts`;
- this implementation note.

No backend, migration, CI, shared browser harness, App/Agent/MCP management page,
Evidence/focus path or delivery matrix was modified by 295. Backend, browser-regression
and CI changes visible in the branch are preserved second-parent content from formal
main `ae002a2...`, not 295 scope expansion. Full immutable Browser Acceptance and the
five new-source CI checks remain final-candidate gates before Human Pre-Merge review.
