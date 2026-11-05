# S1 conversation projection and switch continuity (G1)

2026-11-05. Frozen experience: R2-conversation-switch-1, AC01–05.

Current authority: business_problem_authority owns Problem/revisions/criteria;
draft_assistance owns contexts/turns/invocations; workflow_planning owns proposal
history and confirmed Plan; execution_authority owns Run/task/artifact/outcome.
No independent durable conversation collection or arbitrary conversation-to-work
association was found. Do not introduce a parallel owner or database. Minimal
compatible slice projects currently readable Problems as conversation entries,
labels the source limitation, and keeps unsent text/navigation state as browser
view state scoped to trusted principal, tenant and security domain. It never
turns local view state into permission, Plan, Run or business success.

Components: BusinessNavigation gets an inline expandable list; existing
ProblemWorkspacePage retains draft and reading context on route switches;
ConversationFrame restores reading position; current existing right panel remains
backed by the selected Problem/Run. Browser back/forward use the same route path.
New conversation is an empty view until an explicit existing submit action.

Preserve old views on A-B-A, including unsent draft and existing URL-selected
execution/resource context. Re-read canonical objects after switching; isolate
stale asynchronous responses and identity changes. Do not hydrate cached authority
or execute on selection. Refresh restores browser draft/view state only; canonical
records still require current GET permission. Multi-work graph/node controls
without an existing owner remain unavailable, not simulated.

Validation: frontend lint/build; browser A-B-A drafts/scroll, new empty view,
refresh and back/forward with request-method capture; exact 1280x900 frozen/actual
screenshots and explicit differences. Read-only ledger/Run audit before/after.
AC03/full multi-work coverage remains open wherever live sources are absent.
No cross-device persistence or S2/S3 implementation is claimed.

## Verification recorded in this slice

Actual backend, candidate static frontend browser checks: four readable Problem
entries; A-B-A draft isolation and 150px reading restore; browser back/forward;
reload retains inactive draft; new view is empty; collapse/expand accessible.
All observed application requests during switching were GET. Nine historical
execution projections retained exact progress/artifact/outcome/resource-use fields.

Frontend lint/build passed. Existing dead session-read counter removed from the
identity test (no assertion or behavior removed); that test passed. Backend suite
2259 passed/514 skipped, two Git provenance checks initially failed because the
system Git invokes Xcode; both passed with the required fallback Git. Ruff and
format checks passed. No PostgreSQL fixture was pointed at the real database.

1280x900 evidence remains an explicit comparison, not pixel equality. Independent
conversation history, unread service, multi-work/graph/node state and cross-device
persistence are not supplied by this slice. UI-only local drafts are not records.
