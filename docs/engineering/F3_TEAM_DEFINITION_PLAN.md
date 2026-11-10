# F3 team definition implementation plan (G1)

## Authority and scope

User authorizes completing F3 task/resource/digital-worker management. Frozen F3
team-detail66 includes team goal, accountable owner, shared employee members,
team-local duties and handoff text. Existing EmployeeRevision represents one
employee composition, not this team. Reuse accepted S5-ARCH-018 domain-owned typed
ports and existing PostgreSQL deployment; no new database, State Plane, Tenant
model, Control Plane authority, public CRD or frozen Contract change.

## Vertical slice

1. Typed team revision: scoped identity, immutable revision and predecessor,
   title, goal, owner reference, and ordered team-local member responsibilities.
   Each member pins existing employee definition/revision/digest. Team edits never
   mutate those employees or their duties elsewhere.
2. A domain-owned PostgreSQL repository on the existing pool: explicit migration
   and schema compatibility, immutable revision bytes/digest, expected head CAS,
   append-only command receipt/audit and bounded exact replay. Deployment remains
   off until migration and restore validation. No in-memory production fallback.
3. Private Workbench read/create/successor operations through the existing trusted
   session, CSRF and exact-grant transaction. Authorize TEAM definition operations
   and each exact Employee READ before mutation; membership conveys no grants.
   Policy service failure and stale/inaccessible member references fail closed.
4. F3 team page integration after the existing visual confirmation hold: list,
   exact detail, create/edit and saved readback. Preserve original task and employee
   navigation. No fixed-job scheduling or implicit execution from team save.
5. Real isolated PostgreSQL, service restart, browser save/read/edit/history and
   referenced employee unchanged checks. Existing task/runtime/result regressions,
   prototype comparison and reviewer acceptance precede completion claims.

## Compatibility and acceptance

New private team schema/operations are additive. Current employee and execution
identities, versions, grants and audit remain authoritative. No team-to-work
success is inferred from membership. Validate empty/duplicate/foreign references,
wrong digest, cross-scope reads, denied access, concurrent edit, same-key replay,
changed-key conflict, restart and unavailable storage. Never rename publication,
execution or business outcome semantics to represent team membership.

This plan is not implementation or acceptance evidence. Domain types alone do not
complete the slice; persistence, authorized endpoints and real browser operations
remain required. If implementation requires cross-plane ownership, frozen
contract/lifecycle changes, another persistent dependency or tenant/IAM changes,
stop that change for architectural decision rather than silently expanding scope.

## Implementation checkpoint (2026-11-10)

Storage and private Workbench operations now exist in the candidate. TEAM uses
CREATE/LIST on its collection, REVISE on one aggregate and READ on one revision;
registration does not grant these operations to any existing user. Save additionally
requires current READ on each exact Employee revision on the same transaction and
checks its digest. Even command replay rechecks these grants. There is no automatic
Employee publication, instance creation, task execution or privilege inheritance.

TEAM_DEFINITIONS_ENABLED is off by default. Opt-in startup checks migration 0051
compatibility using the existing owner pool; it does not apply that migration.
The installed platform and its database have not been changed. Isolated integration
checks use real PostgreSQL, session login, CSRF and current grant reads, with test
policy grants seeded only into the disposable database. This is not browser page
or production authorization acceptance.

Remaining: page authoring and history navigation, migration/deployment rehearsal,
real browser create/edit/readback, owner selection semantics and visual comparison.
Reviewer correction: a skill-only new frame is an isolated sample, not complete UI;
verify shared frame continuity across skills, employees, tasks and conversation,
including navigation, editing, loading/error states and retained context.

## F3 frontend continuation (2026-11-11)

Reuse the existing private team API for directory, exact detail and successor
save. The frozen team-detail66 frame supplies team goal and member-local duties;
show employee detail navigation with exact references, never infer shared task
ownership from membership. The existing team owner is an accountable reference,
not permission inheritance or an employee maintainer. New teams default to the
current authenticated principal; editing preserves the recorded owner until a
proper responsible-person selector exists.

UI uses trusted session/CSRF and the existing command transport. Before confirm,
read every chosen employee revision and verify its digest. Preserve one immutable
save intent with the expected team head/version and digest in session-scoped
storage, keyed by principal and team. Unknown writes can only read back the same
revision, not silently create another. Refresh restores the frozen intent. Exact
readback checks scope, content digest and revision identity; current-head changes
block an edit instead of forking from stale state. Role/session changes withdraw
content and invalidate pending UI state. Feature stays off until migration,
authorization and paired installation have been independently verified.

No scheduling, execution, publication, membership-derived grant, organizational
hierarchy or SSO is introduced. Empty/inaccessible team data must not be presented
as a successful empty global directory. Existing employee definitions are never
changed by editing team-local responsibilities.

## Team presentation and resource summary continuation (2026-11-11)

Align the installed team workspace with the frozen frame: compact title and
right-side actions, labeled member-duty-handoff columns, and no recovery action
after a confirmed save. Reuse already authorized exact employee reads to present
per-member resource counts and duties navigation. Counts describe the team's
pinned employee revision, not the latest publication or executable tool access.
No inferred team work or outcomes: the current backend has no team-work binding.
Any later association requires explicit authoritative linkage, not a join on
shared employee membership. Preserve team context on the duties return path.
Validate save/read/history, unknown recovery, member return and mobile layout;
compare actual page with the frozen prototype before visual acceptance.
