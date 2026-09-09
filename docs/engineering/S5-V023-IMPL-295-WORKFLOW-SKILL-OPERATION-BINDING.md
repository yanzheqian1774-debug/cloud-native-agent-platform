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

## Prior candidate validation and changed paths

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

At that earlier checkpoint, no backend, migration, CI, shared browser harness, App/Agent/MCP management page,
Evidence/focus path or delivery matrix was modified by 295. Backend, browser-regression
and CI changes visible in the branch are preserved second-parent content from formal
main `ae002a2...`, not 295 scope expansion. Full immutable Browser Acceptance and the
five new-source CI checks remain final-candidate gates before Human Pre-Merge review.

## Consolidated diagnostic authorization and harness correction

The Human `CONSOLIDATED_DIAGNOSTIC_AND_ACCEPTANCE` instruction extends this same
Session from source `33be91a6a117b780fc5f984d72856c07c37a102d`, tree
`0620e6b1af5e1e9bbaadc3509798e5a35dec9275`, to the existing formal harness and
its existing tests. There is no baseline refresh or Knowledge product change.
The additional paths are `scripts/acceptance/isolated_browser_harness.py`,
`tests/test_s5_impl_072_isolated_browser_harness.py`, and this scope/validation note.

The diagnosed harness defects were discarded backend stderr, a macOS cleanup
identity check that also required an already-listening service, and cleanup
exceptions replacing a primary startup exception. The harness now continuously
drains stderr with bounded line storage and bounded static classifications. Raw
stderr, exception messages, credentials and environment values are not evidence.
Oversized lines are discarded while draining continues; unknown classifications
remain `UNKNOWN`. `startup-diagnostics.json` records ready/failure and cleanup
phases separately, including whether the child was created, still running, or
actually exited. An exit observed after cleanup never replaces the original
failure-time process state.

Cleanup still checks the ownership token, exact child command, cwd, recorded
supervisor/start identity and OS parent relationship. A listener is not required
to establish ownership of an unready child. Unknown or mismatched ownership fails
closed. Primary exceptions remain primary even when cleanup or mandatory artifact
checks also fail; cleanup failures remain separately recorded and cannot turn a
failure into a pass. Browser selection, assertions, health/test deadlines, retries,
skip/flaky guards and release immutability checks are unchanged.

The concentrated diagnostic run `s5-295-consolidated-dTtocStS` first recorded a
provider preparation failure before any harness invocation. A later recorded
host PostgreSQL readiness check succeeded, allowing its never-invoked harness
phase to continue exactly once. The observed complete Knowledge scenario passed:
the second ingestion returned `COMPLETED` with a snapshot different from S0;
the original authoritative GETs subsequently returned that new snapshot and the
unchanged snapshot assertion passed. The observer exists only in its diagnostic
copy, not in the repository test or final acceptance candidate.

This does not establish the cause of historical product startup or Knowledge
failures. Historical full 36/37 failure, the previous Knowledge snapshot assertion
failure, pre-browser failures, and the identity-unconfirmed run retain their
original classifications. Final exact-candidate browser/quality and CI results
are recorded separately in the delivery evidence. PR #159 stays Draft and the
Session stays OPEN pending a Human acceptance decision.

## Bounded in-flight editor protection correction

Human authorization: `BOUNDED_IN_FLIGHT_EDITOR_PROTECTION_FIX`, starting at
source `9202b84c7dd20ae2a7ed91d8cbfaadb54d0b36ab`, tree
`b94824887c4088aac9204aaa21a3cb1dfeca62d2`, with unchanged base
`ae002a2e9a4b765fe311e1e74328a9b6111a4929`. This is a G0 bounded frontend fix;
operation identity, binding rules and backend lifecycle authority are unchanged.

The existing synchronous save latch captures the complete submitted content. While
it is held, a disabled fieldset freezes the Workflow name, ordinary inputs, task
structure, exact references and all Skill/revision/operation controls. Event capture,
content-update handlers and binding picker handlers also consult the synchronous
latch, including before React has rendered the disabled state. An accessible busy
status explains the freeze. The request and editor identities jointly guard save
success, errors and conflict readback. Closing or switching resources detaches the
editor; it does not cancel the backend write. An old response cannot clear a later
editor. Same-kind write serialization remains in place until the request finishes.
Failures restore editing with the submitted input retained. CAS continues to perform
an authoritative read and requires explicit restoration rather than automatic replay.

The existing real Workflow browser journey now holds actual production PUT responses
with `route.fetch()` and releases those unchanged responses. It covers exact description
and binding submission, disabled fields and structural/binding actions, keyboard and
click attempts during the hold, one write, complete authoritative content equality,
a later editor surviving the old response, and a genuine 409 CAS response followed
by enabled controls and retained input. Existing lifecycle and race assertions remain.
No retry, timeout, skip guard, backend, CI workflow or shared harness is changed.

The validation record for this correction is external to the repository at
`/Users/tristan/.codex/validation/s5-295-inflight-20260908/`. It retains new sanitized
source manifests, selected test titles/results, immutable-release acceptance summaries
and final source/CI correspondence. These are newly produced correction evidence,
not recovered copies of the deleted earlier release or raw acceptance artifacts.
The previous eight-file correspondence report remains historical; it never proves
that all tracked files of the earlier local release were checked. The final correction
record identifies the candidate tested after this document was finalized. Earlier
validation counts in this note refer to the prior candidate, not to this correction.

Published-revision selection and the unchanged binding contract retain their prior
review conclusions. Draft task deletion is distinct from implicit binding omission
on a retained task; retained-task identity semantics and broader multi-binding test
coverage remain explicit limitations rather than newly imposed architecture rules.
Human acceptance, Ready transition, merge and Session closure remain ungranted.

## Fresh-provider bootstrap critical-path correction

Human authorization `启动关键路径有界修复授权` continues this same Session from
source `d0221768efa85bc1d0d92b6e5ede21b439ccddb1`, tree
`a207050a2726c6e39399d8e425a24857686a91c2`. It permits only the Console
composition root, existing domain initialization wiring, regression tests and this
note. The health contract and 20-second deadline, migrations `0001` through `0017`,
public contracts, execution ownership, browser assertions and retry/skip guards are
unchanged.

The pre-fix startup trace showed sequential import-time initialization crossing the
health deadline before Agent Definition initialization began. Knowledge owns the
ordered `0003` then `0005` chain; Skill/MCP owns `0002` then `0004`; Runtime Profile
and Workflow Definition use the same `0007` SQL but retain distinct domain ledgers
and therefore remain one ordered chain. Agent Definition `0001` then `0006` follows
Knowledge and Skill. Execution `0008` is independent until Workflow Control `0009`
then `0010`, which also requires Workflow Definition; Digital Employee `0014` is
last. Governed execution's optional `0015`, `0016`, `0011`, `0017` path is unchanged.

The correction removes module-import side effects from the four domain API modules.
The production composition root first opens independent persistence pools in
parallel without running migrations. It then executes only proven-independent
migration chains in two dependency waves: Knowledge, Skill/MCP, the internally
serial Runtime-to-Workflow chain, and Execution `0008`; followed by Agent Definition
and the internally serial Workflow Control chain. Digital Employee `0014` remains a
final serial step before the FastAPI import can finish and the server can report
healthy. Each chain keeps its own connection and a single migration writer. Required
preparation or activation errors propagate before health; legacy direct configure
helpers retain their previous unavailable-state behavior.

An initial pool-preparation-only attempt still missed the 20-second deadline and was
not promoted to browser acceptance. After the dependency waves were implemented, a
fresh PostgreSQL/Qdrant run with no pre-applied schema reached health in `2.978`
seconds, restarted in `1.608` seconds, and rejected an unavailable Qdrant without
ever reporting health. The worktree was then removed externally before the changes
were committed. The same existing branch and fixed source were remounted at its
original path and the patch was reconstructed. The rebuilt tracked content was
therefore tested again: fresh health in `4.327` seconds, initialized restart in
`4.420` seconds, and unavailable-Qdrant exit code `1` after `5.180` seconds with no
health response. All 12 expected domain migration ledger rows were present exactly
once and no migration was pre-applied. Both runs removed their owned containers.

The additional implementation paths are:

- `console/backend/src/agent_console/app.py`;
- `console/backend/src/agent_console/persistence_bootstrap.py`;
- `console/backend/src/agent_console/digital_employee_bootstrap.py`;
- `console/backend/src/agent_console/knowledge_api.py`;
- `console/backend/src/agent_console/runtime_profile_api.py`;
- `console/backend/src/agent_console/skill_mcp_api.py`;
- `console/backend/src/agent_console/workflow_definition_api.py`;
- `console/backend/tests/test_persistence_bootstrap.py`;
- this implementation note.

The reconstructed pre-freeze backend suite passed `569` tests with `100`
environment-dependent skips. After restoring the locked frontend dependencies, the
shared isolated-browser harness tests passed all `156` cases; frontend lint and the
production build also passed with 106 transformed modules. Repository-wide
`make check` then passed Ruff, formatting and `1558 passed / 104`
environment-dependent skips. Exact frozen-candidate Browser Acceptance, source
identity and combination CI remain subsequent evidence and do not rewrite the
historical Knowledge or pre-browser failures.
