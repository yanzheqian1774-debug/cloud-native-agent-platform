# S5-IMPL-041 Checkpoint A Report

## State

`ACTIVE / FINAL_CHECKPOINT_A_CORRECTIONS_COMPLETE / AWAITING_HUMAN_REVIEW`

## Final journey, catalog, and intervention correction

Root cause: the earlier correction still made Knowledge A/B the entry point,
exposed Human control mainly at final approval, projected relationships as an
untyped node inventory, and used vertically stacked resource cards. It also
mixed discovery, matching, permission, and execution status into one label.

Correction:

- Restored the eleven-stage Problem-to-Approved-Plan journey as the primary
  experience, with a sticky stage navigator and visible partial/formal progress.
- Added governed clarification, interpretation, Knowledge selection, Blueprint
  selection, Task correction with DAG validation, authorized resource-match
  selection, capability-gap disposition, immutable successor revisions, typed
  ordered events, Human Evidence, before/after values, reasons, exact revision
  IDs, and canonical digests.
- Moved real two-run Knowledge A/B under secondary Evidence, with Run A/Run B,
  difference, adoption, and return actions.
- Added durable process-epoch Problem/Plan recovery and Plan inventory entries.
- Replaced the node grid with one-hop typed directional relationships, arrow and
  relationship labels, direction/object/relation filters, expansion/collapse,
  fit/reset, list fallback, exact details, and return context.
- Added bounded searchable master-detail catalogs, category tabs, MCP
  Server→Tool→Operation metadata, display codes, object icons, readable Human
  review time, and separated catalog/plan/permission/execution semantics.

The uninterrupted Browser review created one real controlled-model/Qdrant
Problem, recorded six governed Human interventions and seven Plan Revisions,
approved the exact current revision, recovered it after reload, found it in the
Plan inventory, traversed catalog and relationship views, and ended at
`计划已批准（当前版本暂不执行）`.

## Real AI analysis streaming addendum

Root cause: the prior primary page projected stage changes from client elapsed
time around one blocking request. Although the underlying Model and retrieval
were real, that presentation was not verifiable incremental analysis.

Correction:

- Added a real `text/event-stream` Problem-analysis transport with server-minted
  event IDs, monotonic sequence, previous-event digest chaining, event digests,
  correlation/causation, partial/formal classification, actor, typed stage,
  terminal state, authorized replay, and restart-loss errors.
- The server now emits structured interpretation, entities, scope, constraints,
  missing information, and an explicit clarification request before planning.
- Planning pauses for Human clarification, records the response, and resumes the
  same stream. During the actual controlled Model call the server emits truthful
  operation heartbeats with elapsed time, never a fabricated percentage.
- After the real Model/Qdrant result exists, the stream emits authorized source
  titles/excerpts, source-backed findings, incremental Tasks and dependency
  edges, per-Task Agent/Skill/MCP/Knowledge/Runtime matches, the capability gap,
  schema/rule/authorization validation, and the immutable Plan Revision/digest.
- Browser reconnect replays the authorized process-local stream and suppresses
  duplicate event IDs in the Product projection.
- The UI labels partial items as generating/AI suggestions and formal or
  system-validated records distinctly. It explicitly states that hidden
  chain-of-thought is not exposed.

The final Browser run observed six events before the Human pause, live events
advancing during the actual Model call, and 61 ordered events at terminal Human
review readiness. It then approved the exact streamed Plan Revision and retained
the truthful non-execution boundary.

## Entry gate

- Remote-advertised `main`: `d45e95913d4fa783bfff19836be43a9e0530ac5d`.
- Exact-main CI: `33311032723 / main / exact SHA / SUCCESS`.
- S5-ARCH-016: Human-confirmed `ARCHITECTURE_ACCEPTED / PASS_WITH_CONSTRAINTS / CLOSED`.
- S5-IMPL-040 and S5-REL-043: closed; PR #90 durably integrated.
- No competing v0.2.1 branch, PR, owner, or path writer was found.
- Worktree began clean and detached at the exact authorized baseline.
- Single implementation branch: `codex/s5-impl-041-dynamic-problem-approved-plan`.
- Qdrant and controlled Model evidence is recorded in `README.md`.
- No new dependency or lockfile change was required; Qdrant uses existing `httpx`.

## Functional result

The Chinese-first Browser journey submits a formal Problem, calls the controlled
planning Model, validates its structured output, applies deterministic rules,
performs authorization-first dense Qdrant and sparse retrieval, exposes exact
citations and Blueprint/gap states, produces a dynamic Task DAG with exact
resource bindings, creates an immutable Human-corrected successor, approves its
exact digest, and ends at an explicitly inert dispatch boundary.

Run A and Run B are separate actual planning records. Run A has one authorized
document revision, one citation and three Tasks. Run B uses the successor index
snapshot, has two document revisions/citations and five Tasks, adding explicit
containment and three-batch effectiveness/escalation work. The two runs differ
materially in task decomposition, acceptance criteria, approval requirements,
expected Evidence, citations, and resource bindings.

Measured backend stage totals in the final controlled comparison were 15.771 s
for Run A and 24.617 s for Run B (40.388 s combined). The earlier uninstrumented
Browser smoke took approximately 210 s wall-clock, so the bounded model/context
changes reduced observed comparison time by approximately 80.8%; the earlier
measurement cannot truthfully provide per-stage attribution.

## Browser evidence

- Desktop: `browser/desktop-1280x720.png`.
- Mobile entry: `browser/mobile-390x844.png`.
- Mobile overflow audit: document/body `scrollWidth=390`, `clientWidth=390`.
- Browser console: zero errors in the final production-bundle checks.
- Correction: Plan 1 → Plan 2; before/after retained.
- Approval: exact Plan 2 revision/digest; terminal state `INERT`.

### Deduplicated contextual relationship addendum

- The complete cross-object graph now has one dedicated `/relationships` view.
- Employee Overview contains only compact counts; Tasks, Capabilities,
  Skills/Tools, Knowledge, Runtime, and Execution Records present only their
  subject-specific inventories and bindings.
- Resource and Runtime details link to the dedicated graph instead of embedding
  another global graph.
- The graph is derived from the exact canonical Problem/Plan/Task bindings;
  selection, object type, stable ID, revision, and return context remain visible
  without repeating the graph across functional pages.
- Desktop 1280 px: `clientWidth=1280`, `scrollWidth=1280`.
- Mobile 390 px: `clientWidth=390`, `scrollWidth=390`; all four filtered nodes
  occupied `left=33` through `right=357`, with no inaccessible off-screen node.
- Relationship screenshots: `browser/relationships-desktop-1280x720.png` and
  `browser/relationships-mobile-390x844.png`.
- Final journey/catalog Evidence:
  `browser/final-primary-journey-zh-1280x720.png`,
  `browser/final-primary-journey-en-1280x720.png`,
  `browser/final-plan-inventory-zh-1280x720.png`,
  `browser/final-resource-catalog-zh-1280x720.png`,
  `browser/final-typed-relationships-zh-1280x720.png`,
  `browser/final-typed-relationships-zh-390x844.png`, and
  `browser/final-typed-relationships-en-390x844.png`.
- Final streaming Evidence: `browser/final-ai-streaming-zh-1280x720.png`,
  `browser/final-ai-streaming-zh-390x844.png`, and
  `browser/final-ai-streaming-en-390x844.png`.

## Validation

- Focused v0.2.1 backend/frontend correction and streaming tests: `17 passed`.
- Ruff lint: passed.
- Ruff format check: passed.
- Frontend ESLint: passed.
- TypeScript and production build: passed.
- Pre-hook `make check`: `985 passed`, one existing warning.
- `pre-commit run --all-files`: passed; no hook mutation.
- Post-hook `make check`: `985 passed`, one existing warning.
- `git diff --check`: passed.

## Mutation audit and terminal-delivery proposal

Only the paths reported by `git status --short` belong to S5-IMPL-041. No
dependency, lockfile, CRD, API-group, Docker Compose, Kubernetes, CI,
deployment, public Demo, credential, commit, push, PR, REL, or downstream-task
mutation occurred.

The proposed terminal delivery is the complete current worktree diff only. It
must not be committed, pushed, or opened as a PR without the separate Human
Terminal Delivery Gate.

## Collision audit

The preserved S5-IMPL-040 environment was not stopped or changed. Final Browser
QA used isolated backend `127.0.0.1:8011` and frontend `127.0.0.1:4181` with a
temporary `/tmp` production proxy. No REL candidate is allocated;
the next candidate must recheck main, open PRs, exact paths, Qdrant cleanup,
and owner state.
