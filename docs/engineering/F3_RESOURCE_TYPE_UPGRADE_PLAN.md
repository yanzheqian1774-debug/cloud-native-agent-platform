# F3 existing resource type upgrade continuation (G1, 2026-11-12)

## Scope and current evidence

MCP and Knowledge already have separate authoritative create/edit/validate/review/
publish lifecycles. Employee members and capability bindings already admit both.
The selected-upgrade transaction currently only publishes Skill. Do not recreate
lifecycles, add a scheduler, or equate publication with runtime invocation.

First adapt MCP through the existing resource management owner, in the same
transaction as selected employee/capability successors. Knowledge follows after
its repository/owner transaction boundary has been verified separately. This plan
covers the full resource goal; MCP is an implementation step, not all-type closure.

## Compatibility and interfaces

Add optional resourceKind=skill|mcp to the private upgrade request, default skill.
Retain existing oldSkill/newSkill wire keys for compatibility; the UI names the
actual resource type. Preserve the exact original skill canonical request and
preview representation so old command receipts still recover. MCP canonical
requests include kind to prevent cross-kind command reuse. No public contract,
schema migration, new owner, grant bypass or lifecycle transition is introduced.

## Behavior and risks

Use exact kind-specific manage/read grants, current head and draft checks, same
row locks and same owner publication. Skill still requires current operation test
coverage. MCP uses its existing validated/reviewed publication policy; never claim
Skill executor test coverage for MCP or imply publication proves network health.
Selected replacements update only the exact old reference and its responsibility
bindings; preserve unselected members, historical revisions and original runs.
Never resubmit after an unknown result. Keep original receipt recovery and actor,
scope, budget and audit rules. A failure in any selected owner rolls back all.

## Validation and delivery

Test both kinds, old Skill canonical digest compatibility, denied grants, stale
heads, exact reference mismatch, conflicting drafts, receipt replay, rollback and
scope mismatch. Browser checks must identify MCP throughout preview/receipt and
retain pending command recovery. Then use the isolated real database and actual
page for MCP publication plus selected employee/capability references; no model
execution or main data seeding. Compare F3 existing version/impact layout and send
the page to prototype review before guarded combined installation. Until those
checks pass, classify the new route as candidate, not delivered or callable.

## Knowledge owner boundary verified; follow-up plan (2026-11-12)

DefinitionManagement already rebinds KnowledgeLifecycleService's PostgreSQL pool
to the authorized caller connection and delegates policy publication to
PreparedResourceOwner. Reuse that manager; add its dependency to the existing
selected-upgrade bootstrap, not a second Knowledge lifecycle. Knowledge uses
KNOWLEDGE grants and knowledge_operation.knowledge row locking. Publication does
not rebuild indexes or perform retrieval; preserve activeIndexSnapshotId and old
retrieval/citation facts. Keep Skill/MCP canonical request and receipt recovery
unchanged. Add knowledge as a distinct source kind with its existing management
targets. Validate late-owner rollback of the knowledge resource alongside selected
employee/capability changes in real isolated PostgreSQL before browser publication.

Current presentation drift: ResourceVersionImpact showed Skill operation-test
coverage for MCP. Correct this bounded view first: health records must match both
current revision and digest; distinguish initialization from invocation and make
no new network calls. This correction does not establish knowledge batch support.

## Functional drift review gate (2026-11-12)

For each delivered page, compare the frozen F3 user intent, displayed capability,
actual authorized backend command, and persisted result. Review functionality
alongside visual matching. Distinguish draft/save, publication, connection check,
tool invocation, and business acceptance; do not collapse these into success.
Check exact revision binding, original-conversation return, pending clarification
continuation, receipt recovery without duplicate submission, and unchanged old
references where applicable. Record mismatches with the page, expected behavior,
observed evidence, bounded correction, verification, and installation status.
Ordinary corrections are authorized; missing backend capabilities remain visible
gaps. Reviewer handoff must name both visual and functional acceptance scope.
