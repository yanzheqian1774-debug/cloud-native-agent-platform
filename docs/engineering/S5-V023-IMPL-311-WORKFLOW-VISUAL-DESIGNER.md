# S5-V023-IMPL-311 — Workflow visual designer

## Session and baseline

- Session: `S5-V023-IMPL-311`
- Type: `IMPL / FRONTEND`
- Source and durable main at session start:
  `f189212232fc194859a695f0307e83b0c7b73c0f`
- Source tree: `a8a9251d5d2e47605d18bb63e362164ec4c920d2`
- Branch: `codex/s5-v023-impl-311-workflow-visual-designer`
- Architecture gate: `G1` — a bounded Console capability over the existing
  private Workflow Definition API and DTO.

The session does not change a public CRD, API group, frozen Contract, backend
lifecycle, authorization boundary, persistence mechanism, or execution
semantics.

## Implementation plan

1. Preserve the existing `WorkflowContent` object as the single editable
   business fact. Derive canvas nodes, edges, validation messages, selected-node
   forms, and resource inspection from that object. Keep manual coordinates in
   component view state only.
2. Add an accessible, dependency-derived canvas without a third-party graph
   dependency. Provide automatic layered layout, selection, keyboard access,
   zoom, fit/reset, and display-only node dragging. Keep a complete list view
   and a narrow-screen view switcher.
3. Edit only fields present in the formal frontend DTO. Update nodes by
   `taskId`, preserve untouched task/reference/binding fields, and require an
   explicit impact confirmation before deleting a step and its incoming
   dependency references.
4. Reuse the formal published Skill operation directory for precise Skill
   revision, digest, operation, schemas, and constraints. For resource details
   not supplied by an existing authorized GET, show the exact identity already
   returned by Workflow GET and mark richer detail unavailable.
5. Keep the existing save snapshot, editor ownership, duplicate-submit guard,
   CAS recovery, and late-response isolation in `WorkflowWorkbenchPage`.
   Surface non-sensitive schema paths and local graph issues in a global,
   keyboard-accessible error summary, with node/field navigation where a task
   can be identified.
6. Verify focused source tests and Playwright coverage, frontend lint/build,
   relevant repository quality gates, git diff/status, and desktop/390px real
   browser screenshots. Record TEST_ADAPTER and formally connected service
   evidence separately.

## Compatibility and risk controls

- The saved body remains the complete existing `WorkflowContent`; no canvas
  state is serialized and no unknown layout field is added.
- Dragging never changes `taskId` or `dependsOn`.
- Adding or removing a dependency edits only `dependsOn`. Deleting a task is a
  two-step operation that lists affected dependents before removing the task ID
  from those dependents; references and bindings on all surviving tasks remain
  unchanged.
- Existing lifecycle controls remain authoritative. Published revisions are
  read-only and require the existing successor action before editing.
- Client graph checks are guidance only. Backend validation remains
  authoritative.
- No execution success, progress, Workflow Run, Task Run, Attempt, Placement,
  or authorization is inferred from definition validity.

## Layout persistence boundary

There is no layout or coordinate field in the formal `WorkflowContent`,
`WorkflowTask`, or backend Workflow Definition schema at this baseline.
Automatic layout is therefore the default. Manual positions are local view
state for the current mounted designer only and are not saved across reloads or
devices.

## Checkpoints

- Checkpoint A: load existing Workflow -> render dependency canvas -> select a
  node -> edit the formal node form -> save -> read back exact content.
- Checkpoint B: dependency editing, deletion impact, exact resource/binding
  detail, error navigation, list equivalence, keyboard/focus behavior, and
  responsive layout.
- Checkpoint C: focused and full validation, browser evidence, commit, non-force
  push, and one Draft PR. Human acceptance, Ready state, merge, and deployment
  remain outside this session.

## Implemented result

- Desktop keeps the formal Workflow catalog beside the selected Workflow
  revision, visual canvas, and selected-node details. The catalog uses the
  already-loaded formal list response for search, lifecycle filtering, bounded
  client pagination, exact applicable revision labels, and a collapsible rail.
- Draft authoring provides the same canvas/list/config views over one
  `WorkflowContent` object. Published revisions remain read-only and expose the
  existing successor action.
- Canvas controls provide zoom in/out, restore 100%, fit, blank-area pan,
  automatic layout, expand/exit, current-Workflow node search, selected-node
  location, and first-issue location. Node cards use text plus a compact icon
  derived from actual reference kinds; multi-resource tasks remain explicitly
  composite and unknown types remain general steps.
- Dependency edits and task deletion require explicit impact confirmation.
  Removing a task removes only that task and its ID from surviving
  `dependsOn` arrays; no surviving references, operation bindings, or other
  fields are rewritten.
- Resource details use Workflow GET identity and the formal eligible published
  Skill operation directory. Unavailable richer detail is labelled as not
  connected rather than inferred. Technical schemas and policy constraints are
  disclosed on demand.
- Read-only list/detail fetches use both AbortController cancellation and the
  pre-existing request-owner sequence check. Writes retain the pre-existing
  editor-owner snapshot, in-flight lock, duplicate-submit guard, CAS recovery,
  and no-replay behavior. Switching definitions with an open editor requires
  an explicit keep-or-discard choice.
- The Human reference image `7workflow.png` informed the compact catalog,
  broad canvas, top control strip, and selected-node hierarchy only. Its sample
  metrics, running states, execution buttons, Webhook, Human approval, and
  output nodes were not copied.

## Validation record

- `make check`: PASS — Ruff, Ruff format check, and repository pytest;
  `1584 passed, 133 skipped` (environment-dependent integration tests skipped
  by their existing gates).
- `npm run build`: PASS.
- `npm run lint`: PASS.
- `uv run pytest tests/test_s5_v023_impl_311_workflow_visual_designer.py -q`:
  PASS, `3 passed`.
- `npx playwright test tests/e2e/workflow-visual-designer.spec.ts`: PASS,
  `4 passed`; this is deterministic `TEST_ADAPTER` interaction evidence.
- Existing mocked Workflow regression selection: PASS, `7 passed`, covering
  denied disclosure, exact binding round-trip, CAS input retention/no replay,
  late-response isolation, ineligible Skill exclusion, digest mismatch, and
  FastAPI detail arrays.
- Full existing `workflow-runtime-workbench.spec.ts`: `7 passed, 3 failed` when
  attempted without the trusted backend. The three failures require the real
  service at `127.0.0.1:8000`, which was not running; they are not reported as
  product journey success.

## Service and evidence boundary

The code continues to call the existing formal Workflow and Skill APIs. No
test identity, fallback success, or bypass was added. Trusted real-service
browser completion remains conditional on the 305 service/identity environment.
The screenshots under `docs/evidence/s5/v0.2/s5-v023-impl-311/` show actual
branch UI rendered with the deterministic TEST_ADAPTER and are labelled as
presentation/interaction evidence only.
