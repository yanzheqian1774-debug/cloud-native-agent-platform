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
