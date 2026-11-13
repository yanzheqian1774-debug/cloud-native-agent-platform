# F3 team return context — G1

Base: 6afdad. Within the existing six-package management delivery.

Observed: team directory detail links, save readback, history links and member return discard the directory search. Preserve q as navigation only and carry it to member detail as teamDirectoryQuery; exact team/revision/digest checks remain unchanged. No permission, publication, execution, storage schema or owner changes.

Validation: controlled browser directory → pinned team → member → team → directory, edited draft return, save and history retain the search. Existing invalid team context must still suppress return. This is not real maintenance/publication acceptance or full F3 visual acceptance.

Remaining findings: create/edit team controls lack a current permission capability projection (owner still rejects unauthorized commands); fixed routines explicitly remain unconnected. Keep these distinct from already proven employee publication and read-only team history.

The same package extends the finite employee-resource return allowlist with teamRef/teamRevision/teamDigest/teamDirectoryQuery (bounded identities, SHA256, bounded search, duplicate rejection). These are navigation hints only; resource→employee still rechecks exact resource membership/current session, and employee→team still re-reads the exact team and verifies employee triple under current scope. No arbitrary return URL.

## Review evidence and next bounded work

Frozen reference: V6.9-F3 frozen package, `交互原型.html`; delivery checklist `management-delivery-checklist-880-r1/CHECKLIST.txt`, priorities 3–5. This patch preserves F3's existing page composition; it does not claim screenshot-level final acceptance.

1. Team directory → exact detail → member → resource → member → team: confirmed lost navigation context in TeamsPage/EmployeeTeamContext and resourceJourneyLinks; corrected in this package. Exact resource and team authorization are reread on return, stale/wrong team membership gives no team return link.
2. Team current/history/maintenance: existing immutable successor and UNKNOWN original-save readback remain. Readonly maintain controls are not correctly projected: TeamsPage only checks feature/current head, but workbench_team.save_grants requires exact CREATE or REVISE. Next G1 should project current per-action authorization without granting it, bind to identity/scope/exact target and withdraw on session/permission changes. POST owner stays authoritative.
3. Employee detail/maintenance: DigitalEmployeesPage uses authoring.head AVAILABLE to offer maintenance; workbench_employee_relations READ_EMPLOYEE_AUTHORING marks AVAILABLE on exact EMPLOYEE READ, not mutation permission. Same projection gap exists here; do not interpret readable head as authority to revise/approve/publish. Existing real employee publication evidence remains valid for its authorized subject, not for every reader.
4. Member resources: genuine binding counts only after exact employee read, unavailable resources do not become zero counts. AGENT/runtime cards explicitly say detail entry not connected where unsupported. These are partial coverage, not forged resource success.
5. Work linkage remains explicit and does not start execution or grant permissions. Fixed routines explicitly say scheduling is not connected; this package does not introduce scheduler semantics.

Verification: 2 navigation/edit/save/history browser cases PASS; 4 resource-return cases PASS (matched, revoked-team, wrong-member, duplicate query), single worker and controlled API fixtures. Both browser invocations ran production TypeScript/Vite build successfully. No actual API, credentials, DB, model, publish or task calls. Real member-maintenance and prototype same-state visual acceptance remain parent follow-up, not satisfied by these controlled tests.
