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

## Knowledge candidate implementation and UI continuation (2026-11-12)

The candidate now admits resourceKind=knowledge through the existing private
selected-upgrade route. Root and exact read authorization use KNOWLEDGE and the
existing definition management target. Bootstrap retains the existing
DefinitionManagement instance and passes it as an optional owner; absent policy
configuration does not grant access or fall back to Skill publication. Knowledge
rows are locked in their existing table, and its owner publishes inside the same
caller transaction. Receipts separately report knowledge publication, unchanged
active index identity, no indexing started, and no verified retrieval.

The isolated stale-preview case must use a valid Knowledge draft-to-validated
transition after preview; unlike Skill testing, Knowledge validation cannot be
repeated on an already validated revision. Do not loosen that lifecycle for tests.

Next UI work must reuse the authorized exact-version resource-directory
/{kind}/{identity}/{revision}/references projection already used by
DefinitionContentView. Check principal, scope, kind, identity, revision and digest;
an unavailable projection must disable batch preview rather than mean no incoming
references. Adapt the existing selected-upgrade component to a minimal typed
source view, preserve source-kind receipt recovery, lock conflicting single-owner
commands during unknown batch outcomes, and refresh the same definition after
receipt. Keep F3's existing resource detail and professional maintenance boundary.
Candidate backend checks do not establish installed, browser, or indexing success.

## Knowledge isolated delivery evidence (2026-11-12)

Candidate backend: 18 real PostgreSQL cases across Skill, MCP and Knowledge passed
(knowledge-extension-r2); 13 exact-selection/root-grant checks passed. Frontend:
32 selected-upgrade and definition-maintenance browser checks passed, plus lint
and full-feature build. Existing lint/build bundle-size warning remains.

Actual isolated UI submitted one batch ad9d03c720213edc211b4b238f60be666986a180430056543cd3b5dab364d8b4:
one selected employee and one selected capability advanced with the Knowledge
publication. One unselected employee and capability, old fixed revisions, index
and retrieval records stayed unchanged. Original COMMITTED receipt read back
equals the original receipt; no second submit. Protected run/model/budget records
and main process stayed unchanged. Read-only current-published detail return was
verified separately after its loading state settled. Evidence is under
work/evidence/f3-business-capability-design-20261111/knowledge-selected-upgrade
in the continuation workspace, not this repository. Main remains 99815cce48ea;
this candidate is not installed. Prototype review and guarded combined installation
remain gates; professional maintenance styling is not a full F3 visual pass.

## Knowledge reading presentation follow-up (2026-11-12)

A bounded frontend-only correction reuses one KnowledgeBody in both maintenance
and F3 read-only detail. Render stored paragraph chunks as one reading document
with blank-line separators, while the single document-level original disclosure
retains each saved chunk verbatim; do not claim original-file whitespace recovery.
Existing Markdown safety and document-review bundle parsing remain. Structured
JSON gets a generic field/row preview, preserving zero/false/null/missing distinction,
showing array preview limits explicitly, and retaining full saved original text.
Technical format/version metadata is collapsed; unknown field names and values
are not invented or interpreted as business conclusions. No mutation, indexing,
retrieval, backend contract or authorization change is included. Normal main
version remains 42291d82 until separately installed and verified.
