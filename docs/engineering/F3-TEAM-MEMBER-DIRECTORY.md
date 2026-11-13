# F3 team and member directory delivery boundary

Base: 6352c59. Isolated branch: codex/f3-team-member-directory-20261113.

## Verified reference

The frozen prototype was executed through #design-picker and the actual team tab
buttons at 1440x900, including final worker-multi695 and late resource composition
injections. Evidence: work/evidence/f3-team-member-directory-prototype/complete.json
(outside this checkout). Final team navigation is 团队 / 全部成员 / 本次工作团队.
Reference pages: team, team-detail66, work-team66, worker-detail63, worker-multi695,
team-routines. Samples, fixed-work scheduling, team relationships and resource counts
are not implementation facts.

## Scope and mapping

- /teams remains the real team collection and exact team detail. It must not alias the
  employee-maintenance collection. Reuse listTeams/readTeam and existing save receipts.
- /employees and /digital-employees provide the real 全部成员 collection with the same
  team navigation. Preserve exact definitions, authoring reads, creation, editing,
  historical selection, and resource-return verification. Make compact responsive
  cards: name, verified responsibility, actual classified resource counts, publication
  and draft facts, primary 查看数字人. Draft secondary; history in details.
- Current-work team navigation uses existing authorized current-work reads and exact
  links to the existing work page. A work record is not proof of team membership;
  no fabricated team or handoff. No modifications to task directory source files.
- Fixed work is an explicit unavailable capability because current team UI has no
  scheduler backend. Retain navigation/explanation, no mock recurring jobs or writes.
- Preserve shared search across team/member tabs. Add identity-scoped collection view
  restoration for page cursor/index and scroll where currently lost on remount;
  restore only view coordinates, never cached authority or resource content.

## Files and compatibility

Primary files: digital-employees/DigitalEmployeesPage.tsx, EmployeeCollectionCard.tsx,
EmployeeCollectionCard.css; teams/TeamsPage.tsx and shared navigation/read-only work
component; related scope-bound navigation/position helper as necessary. Existing
resource return must retain exact identity/revision/digest and finite validated route
context. Preserve typed read checks, write guards, UNKNOWN recovery and authoring
contract. No API/schema/model/config/database changes.

## Validation and delivery

Isolated Playwright tests for team/member tab search, known versus unknown publication
and counts, draft/history selection, exact resource round trip, scope/identity change,
page and scroll restoration, creation/edit regression, desktop/mobile layout. Run lint
and build plus required normal commit checks. Compare final local screenshot against
executed reference; disclose unavailable scheduler/global-work-team features and
prototype sample differences. Installed-account acceptance belongs to coordinator.

## Isolated verification (2026-11-13)

- Employee/resource closure: final r6 complete run passed (64 tests; last-run status
  passed with no failed tests). Includes exact member/resource return, query/status,
  page-two cursor and scroll restoration, identity isolation, authoring and work rows.
- Team management: final r7 17 passed, including existing creation/history/UNKNOWN
  recovery and new shared-tab/search plus 1440/390 compact grid checks. Build passed
  through the configured preview web server; frontend lint passed.
- Visually inspected final r7 members-grid-1440.png and members-grid-390.png against
  the executed frozen members page. Corrected bot icon and mobile toolbar wrapping.
  Evidence folders are outside checkout under work/evidence/ in the coordinator root.
- Earlier full team configuration r5: 17 team-management tests passed and six
  untouched conversation-team-return tests failed while expecting the old
  .conversation-journey at /work, before reaching the team page. This separate
  conversation fixture path is not claimed passed or silently weakened.

Installed-account verification and final prototype acceptance remain coordinator
gates. Fixed-work scheduling is unavailable; work records do not establish team
affiliation. Resource summaries count only verified direct bindings, not inferred
ontology/tool resources. Shared shell/navigation cleanup remains parent-owned; only
the disclosed /digital-employees team highlight alias changes here.
