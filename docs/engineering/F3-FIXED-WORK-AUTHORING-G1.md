# F3 fixed-work authoring G1

Base b92d797. This package implements only team-scoped configuration drafts,
exact revision reads and durable idempotent save receipts. No enable, timer,
event delivery, model invocation, START, execution authority or TeamRevision
change. Frozen F3 natural-language description is retained as user-authored
configuration, never represented as parsed/validated executable instructions.

TEAM REVISE on the aggregate is necessary but insufficient: an explicit,
default-disabled authoring policy must additionally bind current subject,
namespace/domain, exact team revision/digest, allowed READ/SAVE and expiry.
Exact TEAM READ is also required. No arbitrary subject parameter or prefix
matching. All normal trusted session/generation/revocation checks remain in
WorkbenchOwnerAuthorization; no special empty-grant exception.

New fixed_work_authoring PostgreSQL schema (0067), reused owner connection and
transaction, exact checksum/shape compatibility at opt-in startup only. No
startup migration. Append-only draft revisions/receipts; CAS head plus stable
subject/command and work locks. Same command/body reads the original receipt;
changed content or wrong predecessor conflicts. Read endpoints never write.
Policy is reloaded at each request, so disabling/removing/expiring it fails
closed; no policy digest is treated as an execution approval.

Config: FIXED_WORK_AUTHORING_ENABLED=true and absolute private
FIXED_WORK_AUTHORING_POLICY_PATH, with TEAM_DEFINITIONS_ENABLED=true.
Default registers no routes and initializes no schema. Config drafts explicitly
return executionEnabled=false, authorityGranted=false, state=DRAFT_ONLY.
No capability/resource reference in free text is treated as a verified binding.

Tests: pure policy/schema boundaries; ordinary authenticated maintainer real
isolated PG/BFF save/replay/revise/read, no TEAM REVISE, no policy match, expired
policy, read revocation, wrong subject/team/version, changed payload, stale CAS,
transaction rollback and schema compatibility. No devadmin shortcut. Root owns
real migration/activation and decides exact production authoring policy.

## First-package scope and delivery boundary

No frontend or natural-language model parsing is added here. `instruction` is
literal user-authored text and `trigger` is only structural configuration. The
response says `DRAFT_ONLY`, `CONFIGURATION_STRUCTURE_ONLY`,
`executionEnabled=false`, `triggerCreated=false`, `authorityGranted=false`.
Resource names in text are not verified resource bindings. There is no enable,
pause execution, simulation, timer or event submission endpoint.

Routes (private Workbench APIs):
- POST `/teams/{team_id}/revisions/{team_revision_id}/fixed-work-drafts`
- GET same prefix `/{work_id}/revisions/{revision_id}`

A work remains pinned to its original exact team revision; changing a team's head
never silently moves the draft. Revision read requires the currently applicable
READ policy and exact TEAM READ. Save/replay requires both READ and REVISE plus
SAVE policy. A 404 is not proof of no previous write. Original POST may only be
retried with identical command/body; its receipt is content-bound and immutable.
No new-key recovery is introduced. Schema migration 0067 is applied explicitly by
the deployment owner; startup only checks checksum and shape. The domain has its
own migration ledger and does not add version 67 to the authority migration
ledger. Do not migrate from the legacy authority bootstrap migration directory.

The authoring policy grants no execution and is a private local configuration
reloaded for each request. Policy edits during a request are not claimed as a
transactional revocation protocol; exact TEAM permission revocation remains the
existing authorization owner's responsibility. Production policy changes must use
the platform's controlled configuration activation procedure. Per-request expiry
and enabled/scope checks remain mandatory even for replay.

## G1 increment: persisted draft discovery

The global frozen `team-routines` entry has no selected team. Use the existing
bounded team directory, explicitly select a readable exact team revision, then
GET `/teams/{team_id}/revisions/{team_revision_id}/fixed-work-drafts`.
Without team LIST, retain entry from an already-readable team detail; do not
invent a team picker or call an authorization failure an empty directory.
The nested directory requires exact TEAM READ and authoring-policy READ. Its
1..50 keyset page is bound to the authenticated scope/subject, exact team and
policy digest by the existing signed cursor codec. It lists persisted draft
heads only, enabling refresh/reentry without preknown work IDs or browser-only
storage. `configurationCanSave` is the intersection of policy SAVE and current
TEAM REVISE, never execution authority. All writes recheck the original owner.
No new schema, trigger or enable action is added. UI remains a follow-up; its
plain-language description is not claimed to have been parsed by a model.
