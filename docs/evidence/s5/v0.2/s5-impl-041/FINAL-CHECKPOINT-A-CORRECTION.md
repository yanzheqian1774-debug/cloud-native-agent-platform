# S5-IMPL-041 Final Checkpoint A Correction Evidence

State: `ACTIVE / FINAL_CHECKPOINT_A_RELEASE_BLOCKERS_CORRECTED / AWAITING_HUMAN_REVIEW`

This correction remains a process-local, non-production planning preview. It
does not authorize or claim execution, persistent authority, HA, SLA, Runtime
Instance, Agent Instance, or OpenClaw support. Qdrant remains a replaceable
derived retrieval index.

## Root causes

- Duplicate Plan Revisions: the mutation boundary validated only the current
  predecessor digest and appended a successor for every accepted request. It
  did not recognize an identical retry before the stale-predecessor check, so
  double-clicks or resubmission could append substantially identical revisions.
- Repeated usage relationships: catalog projections flattened Tasks from every
  immutable Plan Revision and rendered consumer names directly. The projection
  did not select the current revision or deduplicate by stable Task ID.

## Corrections

- The service now serializes intervention and summary-correction mutations and
  records a deterministic request digest. An identical replay returns the
  existing authoritative Problem without adding a revision, event, or Human
  decision.
- Resource catalogs project current-revision Tasks and deduplicate consumers by
  stable Task ID. Each consumer is a compact `Task code · name` link to the
  exact Task detail.
- The primary stream is a compact semantic timeline. Repeated model heartbeats
  update one `正在形成初步判断` record. Raw events and JSON exist only in the
  collapsed `技术事件详情` disclosure.
- Planning, approval, and execution availability are separate. After approval,
  the only current lifecycle statement is `计划已批准，当前版本不执行`; invalid
  intervention and execution actions are absent.
- The five-Task dependency projection uses a bounded three-column desktop grid
  and a vertical mobile sequence with code, name, owner, dependency summary,
  state, and exact resource-match disclosure.

## Browser evidence

- Clean real SSE journey paused for Human clarification after six server
  events, then continued on the same stream.
- Final projection contained 29 unique semantic records, two authorized
  Knowledge sources, exactly five Tasks, five resource-match results, one
  capability gap, and two validation results.
- A double-click on one Knowledge confirmation created exactly one successor:
  revision history changed from one to two and remained two after reload/replay.
- Exact-revision approval removed the clarification action and all current
  `待人工审核计划` text, while retaining the no-execution boundary.
- Resource catalog showed five unique Task consumers with exact Task links.
- At 1280×720: document width 1280, navigation client/scroll width 1082/1082.
- At 390×844: document width 390, navigation client/scroll width 356/356,
  zero off-screen Task/timeline/navigation nodes.
- English projection retained 29 timeline items, five Task nodes, the approved
  state, and document width 390 at the mobile viewport.
- No warning or error was emitted by the corrected production asset during the
  final Browser run.

Screenshots:

- `browser-final-correction-desktop-1280x720.png`
- `browser-final-correction-mobile-390x844.png`

## Focused validation

- Backend streaming/idempotency plus frontend projection/deduplication guards:
  `19 passed`.
- Frontend ESLint: passed.
- Frontend TypeScript and live-mode production build: passed.

## Remaining truthful limitations

- Problem, stream, mutation-idempotency, revision, and approval authority is
  process-local and is lost on backend restart.
- Qdrant contains only replaceable derived vectors; platform-owned records keep
  document revisions, Chunk digests, authorization scope, snapshot manifests,
  citations, decisions, and Evidence relationships.
- Approval is planning approval only. This version has no dispatch or execution
  authority.
