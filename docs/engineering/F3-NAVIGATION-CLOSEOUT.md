# F3 navigation closeout

Base 2624d0c; isolated worktree f3-navigation-closeout. Shared navigation/Shell,
ConversationList and related tests only. No Journey, execution API, model or DB changes.

The legacy entry is not duplicate chat data: ProblemWorkspacePage reads the separate
business-problem collection and revisions; private conversations have independent
messages and explicit links. Preserve /work?legacy=1&panel=existing as a secondary
historical-business-problem entry without copying, deleting or auto-linking records.
No live database inventory is claimed; verify an unlinked legacy problem fixture.

Plan: remove inner conversation fold; keep one scope-bound outer fold with stable
expanded state across routes. Preserve history scroll independently of outer-nav
scroll. Use native scrollbars and stable gutter with quiet default/hover/focus/scroll
visibility; do not hide OS-mandated scrollbars. Remove sticky group-title occlusion,
reserve safe padding, and prevent automatic heading focus from scrolling ancestors.
Unify selected icon/color behavior across tasks, resources and member aliases.

Validation: ordinary-account fixtures, 1440 and narrow viewport; one fold, legacy-only
problem access, cross-route folds/history scroll, refresh and return input+selection,
no model/execution POST; computed icon and clipping geometry checks; screenshots.
Run frontend lint/build and normal commit hooks. Actual installed acceptance remains
coordinator-owned. OS always-show behavior is preserved by native scrollbars but
must not claim physical OS settings were toggled unless actually tested.

## Verification

Final isolated run f3-navigation-closeout-r4: 26/26 passed. Covers the four new
navigation cases plus existing history/menu/security-isolation regressions. Frontend
lint and build passed. Final screenshots navigation-1440.png/navigation-390.png
were visually inspected; the executed frozen F3 reference in
f3-team-member-directory-prototype/prototype-team-members-1440.png was also reviewed.
These are fixture screenshots, not actual installed-account acceptance.

A meaningful old-test fixture defect was corrected: the internal workflow-definition
collection returns a raw array, not a workbench result envelope; the original
navigation assertions remain intact. Selected resource icon colors were overriding
shared active colors; the selected-state shell rule now explicitly inherits text
color. No resource content or authority behavior changed.

Known boundaries: legacy inventory was verified by source and an independently
unlinked historical problem fixture, not a new live DB scan. No OS preferences were
changed; native scrollbars are retained and never display:none/width:0. Hover has a
stronger thumb, stable gutter geometry is verified, forced-colors uses native auto.
Actual resource/employee detail roundtrip is covered elsewhere; this package re-ran
historical-work return and navigation/menu restoration, not every detail editor.

## Follow-up: explicit historical problem reader

Installed ordinary-account evidence navigation-team-installed-actual-r2 showed an
empty historical selection incorrectly presented as 新建对话 with a new-question
composer. The follow-up only changes legacy=1&panel=existing with no selected problem:
a historical heading, existing-problem selector, truthful empty/read-failure states,
and no composer/new-question guidance. Selecting a problem keeps the original deep
link/details/authority behavior. Normal new conversation and legacy draft routes are
unchanged. No ConversationJourney modifications or actual service calls.

Follow-up verification: f3-legacy-reader-r2 passed 21/21 isolated tests, including
cross-selection of two independent historical problems, return/reload, retained
formal-edit affordance, and unaffected ordinary/legacy-new composers. Zero POSTs in
the new scenario. Final 1440 screenshot was inspected, including historical breadcrumb.
Frontend build passed through test preview; this is not installed-account acceptance.
