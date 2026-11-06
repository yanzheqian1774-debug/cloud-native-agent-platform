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

## S1 continuation: actual work context (G1, 2026-11-05)

Verified authority mapping:
- The four left entries are four readable BusinessProblem revisions, not four
  independently stored conversations. Their created_at is record time, not a
  fabricated latest-message/unread timestamp.
- draft_assistance.contexts/turns/invocations owns pre-Problem assistance and
  parent-turn lineage. It is not a general message history or multi-work owner.
- workflow_planning history exposes requests/questions only within an existing
  suggestion_context_id/proposal lineage. It validates exact historical targets.
- PreparedExecution GET validates its digest and target Problem. Its semantics,
  participants, progress, artifacts and source supply existing work node facts.
  These references can support a read-only process/detail view with no new owner.

Minimal compatible mapping: one current problem projection -> exact visited
execution preparation digest -> real task_id and artifact_id. Persist only view
selection/scroll/return focus per authenticated principal/tenant/domain/login
expiry + problem + preparation digest + artifact digest. Never persist an
ExecutionView as authorization. On every mount, current authorized GET precedes
rendering any task/selection/artifact. Invalid or foreign local refs cannot render
another work's data. Browser back/forward/refresh only restore this view state.

Changes: reusable browser-only view state; existing execution panel gets a
read-only process tab over real tasks/dependencies and exact participant
properties; existing artifact dialog and supplier/sales selection preserve their
own identities and scroll; left list remembers visited exact work URL. No new
run, no new multirun membership, no S2/S3 or dual-employee exploration.

Login isolation: use session.absolute expiry returned as expiresAt (server-owned,
fixed for each authenticated login), alongside principal/tenant/domain; idle
expiry is rolling and must not key views. No CSRF or credentials in view storage.
Add actual separate-login checks, not only principal-string fixtures.

If durable cross-problem conversation is required, a concrete G2 candidate is a
separate conversation/message/link domain in existing approved PostgreSQL with
immutable message references and exact owner-authorized links, no execution
lifecycle or permission authority. Requires decision on ownership, membership,
retention and message-write policy; this slice does not implement or approve it.

Acceptance: actual historical supplier/sales runs, distinct task/artifact
identities; A-B-A nonzero reading/working scroll + unsent text; task property and
artifact return focus; browser history/refresh; separate login/identity isolation;
0 business POST/model calls after explicit login. Preserve 38/14/USD11.126748.

## Concrete missing contract candidate — NOT implemented / NOT approved

Current compatible identity is (login scope, Problem ID, exact preparation digest,
task ID, artifact ID/digest). Problem revision/Plan version/Run state and artifact
access are always read from their owners. A selected task never creates a Run.

To meet durable conversation/multiple-work semantics, the proposed minimal domain
would need conversation_id, tenant/domain, owner principal, membership revision,
created_at and title; ordered immutable message_id/conversation_id/sequence,
author principal, created_at and content reference; and typed link_id/message_id
or conversation_id + target owner/type/ID/revision/digest. A link is navigation,
not authority, and cannot write Problem, Plan, Run, approvals or resource grants.
Read of each linked object must pass its existing exact permission; revoked or
missing links show unavailable without falling back to other conversation data.
Writes require explicit membership policy, idempotency and expected conversation
revision; retention/deletion and ordering must be decided before implementation.

Current APIs have no general conversation membership/message writer or durable
multi-work link owner. Repurposing draft_assistance or deriving membership from
accessible Problems would change semantics. Recommended decision: one narrowly
scoped conversation domain within approved platform storage, referencing existing
owners, no execution service. Alternative until approved: retain this explicitly
labelled Problem projection. This is a state/ownership G2 decision under
ARCHITECTURE_GATES.md, not a request to approve a parallel execution system.

## Second-batch evidence (2026-11-06)

Eight candidate-browser checks passed against actual authenticated backend:
A-B-A exact work/task/properties/draft; nonzero work scroll 120/95px and reading
20/20px; back/forward; exact artifact refresh (170px) and supplier selection;
return focus; sales dimension/group restoration; wrong Problem/digest denied;
new-login and cross-account isolation. No business POST or model invocation.
Frontend lint and trusted-profile build passed. These are implementation evidence,
not independent monitor acceptance. The initial test's hidden-dialog count
expectation was corrected; its failure evidence is retained outside the repo.

AC01 PARTIAL: readable Problem list/title/record time and selected identity;
no general persistent conversation, latest-message or unread owner.
AC02 PARTIAL: draft, actual task, right-rail owner and nonzero scroll restoration;
no continuous message-history anchors or a conversation with three linked works.
AC03 PARTIAL: actual execution task/properties/artifact/scroll/focus restoration;
no multi-work membership, graphical relationship selection or business process.
AC04 PARTIAL: first-batch empty new view/inactive drafts/collapse retained;
second-batch refresh restores real artifact context. Long-list nonzero scroll
is not established from only four real entries; no fabricated rows added.
AC05 compatible projection PASS: actual exact-URL work/node/draft restore on
back/forward with zero duplicate writes. Durable conversation scope remains open.
Overall S1 remains PARTIAL. S2/S3 and two-employee work are not included.

## Approved persistent slice (2026-11-06)

User approval relayed by monitor chat 01a1aa5c-194c-7530-b4f7-f20450693703
accepts contract v0.1 D1-D3: existing PostgreSQL private conversation/message/link
records, preserving original execution and permission authorities. D4 is an
estimate. This is the human G2 decision for this narrow state owner, not a change
to Problem/Plan/Run lifecycle or a second executor. Single writer verified at
1607f85; no tracked changes, queue0,38 calls/14 unsettled/USD11.126748 unchanged.

Implementation: additive schema and private owner checks; trusted BFF session and
CSRF; version CAS, idempotent create/append/link, immutable messages, exact
existing-owner read authorization for work refs; feature flag default off.
Console conversation list/history with existing work drilldown and browser-only
drafts/positions; clear supported followup routes and ambiguity; no automatic
Problem/model/Run creation from append. Old projection remains available with
flag off. Migration rollback disables feature and retains records.

Validation: isolated PostgreSQL64335 integration for concurrency/idempotency/
private scope/foreign refs, BFF auth/CSRF/flag; frontend checks; controlled actual
conversation records with old work READ only, reload/new login/A-B-A/drilldown,
0 new model calls/business owner writes and unchanged old authority table audit.
No historical replay. Deliver exact commit/install/checkpoint and frozen diff.

### First implementation boundary and rollback

PRIVATE_CONVERSATIONS_ENABLED=true enables BFF routes; otherwise writes fail
closed and UI retains legacy work entry. Apply migration0046 explicitly with
scripts/acceptance/private_conversation_migrate.py --apply, using existing DB
via CONVERSATION_DATABASE_URL. The checksum ledger rejects changed migration.
Rollback disables the flag and restores code; never DROP private records or
roll back business facts. No historic Problem-to-conversation auto-import.

First slice stores private user messages with server routing hints and exact
Problem/optional prepared execution links. It is not a model response service.
Messages with focus refer to existing work; ambiguity stays recorded until the
user selects a work. Clear independent-goal language is a review hint, never a
CREATE_PROBLEM command. Existing-work actions navigate the original owner UI;
new goals still require that owner's confirmation. Draft/planning source-message
projection and durable action-intent/owner-receipt message types are not enabled
in this first slice; no hidden dispatcher or new execution authority exists.

Controlled isolated PG64335 and BFF tests:34 passed, including10 new cases for
private scope, concurrent CAS, replay/payload collision, persistent reload,
exact work mismatch, revoked link redaction/write rejection, session/CSRF and
feature-off. Actual installed UI evidence follows; no full S1 acceptance claimed.

## Approved continuous handling batch (G1, 2026-11-06)

Authorization: sole successor of stopped writer 01a1ac3d, delegated by
01a1aecf; user approved the same private conversation's draft/planning source
messages, explicit action intents and original-owner receipts. Existing D1-D3
ownership approval applies; no new execution authority. Baseline e9df4600,
generation9, 38 calls/14 unsettled/USD11.126748, queue0 verified before edits.

Implementation plan: additive migration0047 retains0046 unchanged; typed immutable
source references and action/receipt messages within the private owner. Register
read-only adapters over original draft/planning services and existing authorized
Problem reads. Each source fixes exact context/turn/version or planning target,
context/request revision and invocation; all disclosures reauthorize. Result
content not retained is explicit, never reconstructed. Before a confirmed existing
owner POST, record immutable intent/message/actor/time, canonical payload digest,
owner request key, exact source/target and expected owner version. A CAS claim in
that original route admits a single attempt; no generic dispatch endpoint or
second executor. A lost claim response or owner response never auto-retries.
Original response facts or authorized original GET produce success/failure/UNKNOWN
receipts. Planning request-key GET may reconcile; absent safe query keeps UNKNOWN.
Cross-owner writes and conversation receipts are separate transactions.

Frontend carries returnConversation through draft/create/planning navigation,
records user confirmation on the existing action button, displays typed source
and receipt facts in the same C, and retains one original P on followups. Add
read-current receipt recovery, never POST retry from page refresh. Wire original
/tasks and /outcomes directories to authorized current owners without resurrecting
legacy services. Bound logout requests and distinguish unconfirmed revocation.

Validation: new isolated PostgreSQL64335 fixtures with actual owner interfaces
and controlled providers, same C two draft turns -> one P -> same-P planning
clarification; exact source mismatch/revocation/account isolation, CAS/key
collision/concurrent attempt, response loss/message-write failure/restart/login.
No real model or business calls for UI tests, no historical UNKNOWN replay.
Frontend lint/trusted-profile build, required commit hooks, read-only historical
row/budget audit, controlled installation, migration/checksum and feature-off
rollback retention, 1280x900 frozen comparison. Full S1 remains PARTIAL; all six
packages/J01-J12,100-call/USD50 caps and reservations remain outstanding as before.

### Continuous batch candidate evidence (2026-11-06)

Implemented migration0047: message facts and immutable intent records within the
same private owner. Original draft/create/planning/explicit-admission-continue
routes claim at most once before their own operations. A receipt-write failure
does not replace the original owner response; durable known references support
read-only recovery. Where an ID/request payload is not safely retained, UNKNOWN
remains. Original HTTP errors alone never prove no effect. Request-key recovery
compares the original normalized payload before adopting any result. All source
facts reauthorize; revoked facts redact. Controlled transport is explicit.

82 targeted isolated checks passed: PostgreSQL64335 plus actual draft/Problem/
planning service paths with controlled providers, including five-intent same-C
chain, one P, same-P clarification, explicit prepared continuation, failed and
UNKNOWN receipts, source mismatch/revocation/other account, CSRF, CAS, concurrent
original POST, receipt-write loss, read-only exact request recovery and payload
collision. Full repository commit hooks remain required. No new real model calls.

Controlled browser passed ten groups over real isolated owner interfaces:
source/intent/receipt render and reload, two original draft-UI turns in same C
with zero Problem creation, original planning-UI same C/P, legacy404 avoidance,
read-current with no dispatch, pending GET/DELETE logout, network failure and
actual session revocation. Initial browser run found returnConversation appended
to the planning-input API path; corrected API path while preserving navigation.
The failed run is retained in external evidence. Necessary header overlap found
at1280x900 was corrected; final visual capture is recorded in the batch delivery.

/tasks and/outcomes now compose currently authorized Problems and exact readable
executions navigated by the user's private links. This is a bounded current-entry
repair, not a new all-Task/Outcome aggregate. Missing/revoked state never means
zero work or success. Logout waits are bounded; timeout remains unconfirmed.

This closes implementation subchecks of J03/J05 only. Full J03/J05 business
journey, J02/J06, J11 visual acceptance, S1 overall and all92 resource pages remain
OPEN/PARTIAL. P1 immediately returns to supplier/sales capability preparation,
assembly/admission/execution/evidence, starting with six logical requirements and
the registered CLASSIFY_OVERDUE gap. No S2/S3 or general conversation expansion.
