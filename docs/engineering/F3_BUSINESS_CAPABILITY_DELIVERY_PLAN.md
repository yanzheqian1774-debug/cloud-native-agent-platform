# F3 business capability delivery plan

Status: G1 implementation in progress; durable owner and initial frontend candidate verified in isolation, not installed or product-accepted.
Baseline: 0a80395d96b2805b60dfbb5f239f26d0bd436e50. Frozen UI: V6.9-F3.

## Scope and authority

Deliver the frozen capability collection/detail and durable authoring, not a renamed
resource directory. Retain existing authorization, budget, audit and all exact
historical references. OpenClaw remains isolated/off; no new Native execution.

S5-ARCH-018 authority must be read with the forward record in governance REGISTRY:
its decision file still says proposal, while REGISTRY records Human-confirmed,
durably integrated PASS_WITH_CONSTRAINTS and PR 97. Reuse the existing database,
domain-owned typed ports and adapters; no new infrastructure or control-plane owner.

## Inspection findings that constrain implementation

- SolutionBlueprint v1 requires canonical_workflow_revision and role_definition
  references. It cannot truthfully represent an independently authored capability
  lacking a workflow. Keep this existing logical contract and its digests unchanged.
- The saved non-table conversation has a plan, four participants, a fixed Employee,
  Skill, Knowledge and Runtime Profile. These are real exact references; the plan
  has NOT been verified as a published WorkflowDefinition. Employee is NOT Agent.
- BlueprintAuthority is in-memory only. Neither a prototype nor that authority
  proves a durable, trusted business-capability service exists.
- Current authority_configuration OWNER_ACTIONS has no business capability owner.
  Adding explicit actions is not permission to reuse Workflow grants or broaden
  existing administrator grants. Production activation needs its own exact grants.

## Proposed internal representation and interfaces

Use a BusinessCapability revision aggregate in the Console resource domain, with
scope, stable capability ID, immutable revision/digest, predecessor, title, intent,
inputs, outputs, scope/exclusions, manual involvement, acceptance criteria and limits.
A tagged origin is INDEPENDENT, WORKFLOW_REVISION or SAVED_PREPARATION. The latter
records the verified preparation digest, not a fabricated workflow revision.
An optional Blueprint reference is allowed only after exact owner verification.
Typed fixed bindings include EMPLOYEE plus SKILL, MCP, KNOWLEDGE, ONTOLOGY and TOOL
where an existing owner can verify them. Unsupported owner bindings return a clear
reason; they are not invented or silently converted to another kind. Runtime/Profile
remains an execution prerequisite, distinct from the five resource categories.

Repository ports: immutable add/read, scoped bounded list, compare-and-set draft
head, append lifecycle decisions, publication head and command receipts. Reuse
existing PostgreSQL transaction, conflict, schema-compatibility and recovery patterns.
No generic cross-domain mutation and no new database. Public CRDs remain untouched.

Service/API: scope and exact action authorization before lookup; verify each fixed
member against its owning service, digest and scope. Preserve one visible published
version plus one current modification draft. Each edit appends a revision but does
not expose revision administration as the normal business journey. Publication and
reference upgrades use one existing-style consolidated impact confirmation, not a
confirmation per member. Source snapshots and old conversations never upgrade.

## Delivery sequence and acceptance

1. Finish actual saved-conversation -> fixed Knowledge/Skill -> original conversation
   walkthrough with fully loaded content. Record route equality and zero execution.
2. Define aggregate/ports and exact owner/action mapping; implement isolated durable
   save/read with real PostgreSQL. Prove restart/fresh-session equality, replay,
   conflicts, denied member, wrong digest, concurrent draft edits and scope isolation.
3. Connect F3 collection/detail/create/edit to trusted APIs. Independent creation and
   workflow-derived creation must both show truthful source. Do not force workflow.
4. Deliver successor diff, consolidated impacts and publication; verify old execution
   digest and original resource references unchanged. Fresh session reads saved data.
5. Original entry -> capability -> Employee -> multiple fixed resource types -> exact
   original entry. Conversation try-use prepares source context; it does not invoke a
   model or claim a newly successful run while Native policy/budget is unavailable.
6. Install with guarded source-only deployment after required checks; compare actual
   pages to frozen F3, submit complete stage to prototype reviewer with remaining gaps.

Frontend lint/build and focused backend/frontend tests are required for code changes.
Real persisted/browser evidence supplements tests; fixtures are never live acceptance.

## Risks and stop conditions

Resolve authority/action mapping and typed resource owners before enabling live writes.
If existing authorization architecture cannot admit the new resource through its
established configuration seam, or cross-plane/frozen semantics must change, stop that
change for a concrete architecture decision. Continue independent approved work.
Do not silently grant permissions, renew model budgets, restart unknown executions,
change lifecycle meaning, or use Blueprint mandatory workflow fields as placeholders.

## Reviewer acceptance additions (2026-11-11)

Current publication plus one modification draft; genuine independent/workflow sources;
centralized impact confirmation; understandable denied/missing-input reason and next
step. Reviewer feedback is product acceptance guidance, not expanded authority.

## Verified authorization reuse and first implementation slice

The accepted D12 decision explicitly authorizes the configured development admin to
read/use current and future resources in the existing isolated scope. The current
GenerationAuthorizationReader implements it after session/account, active generation
and authority availability checks. Therefore registering a capability owner/action
through the existing seam does not require a new blanket grant for that role. Ordinary
accounts still require exact grants. This is not model authorization or renewal.

First implementation files: business_capability.py (typed immutable revision and
origin), business_capability_postgres.py (caller-owned authorized transaction port),
migrations/0052_business_capability.sql, and matching unit/PostgreSQL tests. This
slice creates no enabled endpoint, no live migration and no publication authority.
Actual durable tests use the existing isolated PostgreSQL instance. Follow with the
trusted owner/API and F3 UI before claiming the capability can be used in the product.
Repository calls cannot replace the required authorization-first owner service.

Trusted draft API slice now adds workbench_business_capability.py, explicit registered
BUSINESS_CAPABILITY CREATE/LIST/READ/REVISE actions, and default-off bootstrap wiring.
Existing D12 authorization is reused; ordinary accounts receive no bootstrap grants.
The migration remains isolated-only. Save and read independently validate Employee,
Skill, MCP, Knowledge and Runtime references through original owners; Ontology/Tool
lack a connected reader and fail with an explicit unavailable reason. Prepared source
and workflow origins remain typed and must be read through their own authority.
Publication, current-published-plus-draft projection and impact confirmation are the
next slice, not inferred from successful draft storage or reference readability.

## Publication and consolidated-change slice

Add an append-only publication receipt on the existing database (migration 0053,
not a rewrite of 0052). Publication is a declaration lifecycle action, not a test
run, model call, execution authorization or business acceptance. Validate the exact
revision's required business fields, fixed resource digests and each resource owner's
published/available facts; unsupported or unreadable prerequisites fail closed.

Use one explicit REVIEW_PUBLISH action for an authenticated human with the exact
capability grant; D12 reuses its already-approved role and records that distinct basis.
The submitted reason and consolidated preview digest represent the exact review.
The receipt records actor, current authorization decision, exact revision/digest,
validation scope and preview; no fabricated sample test or unrelated human review.
Expose one preview comparing current published definition to the candidate draft,
including every binding/source/business-field change. Recheck the preview and current
aggregate version in the publishing transaction. Old resource references and saved
conversations are not updated; impact scope is the capability definition only, not
an unsupported global consumer count. New usage must still pass execution admission.

A current head equal to the latest publication has no modification draft. A successor
head is the one modification draft while publication still points to its original
revision. Immutable intermediate drafts and publication receipts remain in history.
Tests must prove stale preview rejection, one publication per replayed command,
reference revocation on replay, published + draft coexistence, restart readback and
unchanged former revision bytes. Startup stays default-off pending full-stage install.

## Frontend candidate (not installed)

Added a default-off capability route and navigation using the existing F3 shell.
The typed client preserves session identity and CSRF, bounds waits, never retries
commands automatically and retains the exact publication command after an unknown
response. Catalogue/detail show truthful draft and publication facts, business
inputs/outputs/limits, fixed composition and consolidated publication differences.
The page does not claim sample execution or offer a disconnected execution button.

Frontend lint/build and three browser tests pass: desktop/mobile fixed details,
explicit publication with same-command retry after connection loss, and content
withdrawal on denial/session expiry. These tests use mocked HTTP and are not live
acceptance. Creation/editing, member drill-down, conversation preparation, trusted
owner browser testing and the complete frozen-prototype comparison remain required.

Frontend authoring follow-up: independent and workflow-derived creation now use
existing published owner lists, including pagination, and save a new fixed revision.
Editing carries the current predecessor and aggregate version. A successful save is
read back before navigation; ambiguous results retain the original command. Exact
Employee/Skill/MCP/Knowledge links carry a bounded capability return and digest;
Employee deep links now verify an explicitly supplied digest. Eight mocked browser
tests pass, including creation sources, successor editing and same-version return.
Two initial create tests exposed an ambiguous select accessible name, corrected with
explicit names. No live deployment, new model call, or full-stage acceptance yet.

## Real browser and final prototype reconciliation

The production-backup migration rehearsal passed on an independent container using
the exact production PostgreSQL 16 image. Existing owner/budget hashes did not change.
An owned independent snapshot now runs the real candidate application and copied
generation18 account configuration, with no model runtime manifest or Native worker.
A real browser saved and published one capability binding the original published
Employee, Skill and Knowledge; refresh and process restart preserved exact content.
SQL confirms one publication and its explicit DEVELOPMENT_ADMINISTRATOR basis.
Three member paths return to the same capability revision; no business writes occurred
in readback verification. Evidence is under real-browser/ in the stage evidence folder.

Integration found resourceReadContext rejected the new capabilityReturn parameter.
The fix admits only a same-origin capability detail with exact revision/digest and
valid conversation locator; external/unknown destinations still fail closed. Ten
resource return regressions pass. The final rendered frozen F3 pages override the
earlier add('cap-detail') definition: the fixed composition table is primary. Candidate
layout was adjusted accordingly; catalogue summaries now expose authorized stored
inputs, outputs and boundaries. Eight capability browser tests and 65 backend tests
pass. Actual pages and prototype images are in real-browser/demo.html. Scoped page
review was requested from the authorized prototype-review thread. Formal acceptance,
column-width polish and main installation remain pending. Do not infer complete
capability use, favorites, sharing, consumer impact or execution from this evidence.

## Capability-to-conversation preparation seam

Reuse the private conversation SOURCE record, its existing idempotency/version checks,
authorization-first source reader and durable message facts. Add an internal typed
CAPABILITY source with exact capability/revision/digest, user objective and supplied
input notes. Resolve it through READ_CAPABILITY_REVISION and require its publication
fact, verified member digests and current source access. Persist the original typed
reference and observed fixed definition facts; reauthorize on read and replay.
This is preparation only (PREPARED_NOT_EXECUTED), not a successful execution receipt.
Do not dispatch a model, infer an execution grant, or silently convert the source
into an unrelated problem/planning action. The use page checks required goal/input,
shows the fixed composition and saves preparation into the existing conversation or
a new private conversation through the normal CSRF routes. The original conversation
must display the input, completion criteria and fixed version with an honest next-step
state. Subsequent execution admission must explicitly consume this snapshot; until
that seam exists, it must not expose a misleading start control.

Review corrections are integrated in this stage: authoritative member display names
from already-authorized reads, package icon and frozen navigation ordering, one origin
label, primary use action, final cap-independent/cap-package/cap-publish references,
and a confirmation screenshot that actually includes the confirmation area. Never
repeat the already completed publication merely to obtain a screenshot.


### Actual preparation-path evidence (2026-11-11)

The isolated real backend/browser now saves one exact published capability preparation
to the existing document-handover conversation. Original messages remain byte-equal;
exactly one SOURCE message is appended. Refresh and owned process restart both read it
back; the detail return retains the fixed digest. No capability re-publication, model
call or execution was performed. Existing business and budget record hashes remain
unchanged across the guarded restart. Evidence: real-browser/source-browser-complete.json
and source-card-browser-complete.json under the capability delivery evidence directory.

The browser check exposed a product defect: preparation details were hidden inside the
legacy receipt disclosure. CAPABILITY SOURCE cards now render inline, with the F3 white
background and one-pixel border. Whitespace-only input is rejected while still editable.
Ten focused browser tests pass, including the visible original-conversation card.
This is preparation evidence only; Native admission consuming this fixed snapshot,
low-intervention authoring and remaining prototype review issues remain incomplete.
Main installation is unchanged; scoped prototype acceptance is not yet passed.


### Nested fixed-member navigation

Carry the existing finite validated capability return through Employee to Skill, MCP
or Knowledge and back. Reuse safeCapabilityReturn; reject duplicate/foreign targets,
retain the exact Employee digest on return, and preserve the originating conversation
inside the capability target. Navigation confers no read or execution authority.
Verify positive nested navigation and hostile return parameters without any writes.


### Verified execution integration constraints

Current ConversationJourney builds criterion measurement from source completionCriteria,
then calls question-activity-input, confirms the resulting proposal, and may run automatic
resource selection before prepareResources / readonly-continuation. Therefore routing a
capability SOURCE card into this unmodified path would not preserve the capability's
fixed bindings or completion criteria. It must not be labelled capability execution.

Next integration must read the owned SOURCE message and reauthorize its exact published
capability before building a new work target; include the capability acceptance criteria
and exclusions in the persisted criteria. The existing SelectEmployeeResources owner can
select an exact Employee after plan confirmation, but resolves pending members and may
create an explicit source-change record. Its result therefore needs exact comparison
against capability bindings before execution preparation; mismatches must surface as a
preparation gap, never silently broaden or substitute the selected source. Use stable
per-source command keys and a persisted association to the new work, retain old journey
and results, and recheck identity, publication, members, authorization and budget.
No new budget or execution authority is inferred from publication or SOURCE visibility.


Nested navigation is now verified in the actual isolated browser: capability → fixed
Employee → fixed Skill → original Employee → capability → original conversation.
The exact Employee and capability digests survive, with zero business writes. Seventeen
existing resource-return checks and three additional valid/foreign/duplicate capability
return checks pass; frontend lint and build pass. Evidence: nested-return-browser-complete.json.
This does not prove runtime/ontology detail adapters or capability execution.


### Reuse existing Employee facts during authoring

Offer an explicit read-only import of a selected published Employee's exact definition.
Recheck session identity, id/revision/digest and publication before applying facts.
Fill only empty title/intent using saved role/responsibilities, and import supported fixed
member references with their saved responsibility associations. Never overwrite typed
fields or existing bindings; conflicts/unsupported members are reported for review.
Do not infer input data, completion criteria or execution permission. Normal save/publish
owner checks remain mandatory; no model call is needed for this reuse.


Authoring reuse is verified against the real isolated owner: selecting the published
document-handover Employee imports its saved responsibilities and four fixed references,
retains the user-entered title, leaves acceptance criteria blank, and adds no duplicates
on a second import. The demonstration cancels without saving or publishing. Thirteen
capability browser checks pass including denied/mismatched Employee reads; build and
frontend lint pass. Evidence: authoring-import-browser-complete.json and screenshots
14-authoring-import-goal.png / 15-authoring-import-bindings.png. Remaining required
input/output and business boundaries are not inferred from Employee responsibilities.


### Review correction: separate preparation from existing work

A capability SOURCE record is not associated with the existing journey execution.
When a readable PREPARED_NOT_EXECUTED capability record is present, show a current
preparation summary in the rail, explicitly not started. Label the existing journey
progress/result as original work and show its original question/time; preserve all
records and execution status. Do not count historical artifacts toward the preparation
or add confirmation, model calls, state transitions or a new module.


Review ownership correction is verified with a real persisted preparation and the
original completed execution: rail shows current preparation not started separately
from original work progress; the result body retains original question and execution
time under original-work labels. Existing messages are byte-equal after restart and
read-only navigation creates no business writes. Fifteen browser checks cover normal
capability flows and readable/denied preparation alongside old results; lint/build pass.
Evidence: preparation-history-browser-complete.json / 16-preparation-and-original-work.png.
No capability execution, new model invocation or main installation is claimed.


### Fixed capability execution contract seam

Add a read-only, owned conversation SOURCE-message execution-contract endpoint. Resolve
the exact saved source through current capability/member authorization; never accept
a caller-supplied replacement definition or another conversation's message. Return a
canonical contract digest covering scope, conversation/message identity, capability
version, objective/input notes, criteria, boundaries and fixed bindings. State explicitly
NOT_ADMITTED / executionStarted=false; this endpoint grants no model/tool budget.
The existing use page reads this contract after saving and checks exact saved inputs
before returning to the original conversation. Replays reuse the existing SOURCE key.
Next execution-owner integration must consume this contract and persist an explicit
association to the new work; no inferred latest-preparation association is allowed.


The owned source execution-contract endpoint is now exercised through actual PG-backed
API tests (67 relevant checks pass), current frontend save/readback checks (14 pass),
and the real isolated browser reading the existing SOURCE twice. Exact criteria and
bindings match the published owner revision; digest is independently recomputed.
Cross-conversation source access and revoked member permission are rejected. There
are no business writes in real readback and no new execution/model call. Contract state
remains NOT_ADMITTED. Frontend checks exact scope, saved inputs and fixed definition
fields before navigating after save. The execution owner consuming this contract and
persisting a new explicit work association remains incomplete.
Evidence: resolved-execution-contract.json and execution-contract-browser-complete.json.


### Execution-owner consumption of the fixed contract

Extend the existing readonly-continuation request with an optional all-or-none owned
conversation/message/contract-digest reference. Resolve it before the Plan transaction
through ConversationActions, then require current Problem/Criteria provenance, explicit
capability completion criteria and exclusions, and exact prepared resource/Employee
bindings before any assembly or execution grant. Legacy calls retain their exact digest
and behavior. Capability provenance participates in the existing command payload digest
and receipt; a replay with omitted/different provenance cannot reuse or start a run.
The existing plan-based command key still prevents duplicate execution. No new table,
budget renewal, worker activation or model call is introduced. Backend invocation is
not UI execution delivery until the new problem/criteria/plan path is also wired.


Real read-only admission verification exposed a nested authorization advisory-lock wait:
the continuation owner already held the generation transaction while the conversation
resolver opened another authorized read. The owned blocked read was cancelled (no run
started). Fix: resolve private source ownership and capability member READ grants using
the existing AuthorizedOwnerCall connection/authority; do not re-enter authorizer.execute.
This seam uses the accepted same-database conversation/owner deployment. Standalone
conversation contract GET retains its ordinary independently authenticated reader.

### Task-input compatibility correction

Inspection of the actual BusinessProblem owner reveals two incompatibilities in the
initial constraint seam: description is bounded to 2,000 characters, and HUMAN_EVALUATED
measurement permits only rubric. Preserve the full objective as description, use a
bounded display title, and retain complete input notes and the exact contract in the
existing criterion applicability field (already included in its durable digest).
Expose canonical work input alongside the authenticated contract readback; this is
preparation only, not creation or execution. Execution verification must compare the
full applicability contract and rubric, not impossible extra measurement keys. Prove
maximum-length inputs pass actual owner schemas/domain validation without truncation;
then wire creation and explicit association through existing owners.

The second real-browser execution-owner read completed normally: the old plan was
rejected with HTTP 409 CAPABILITY_PROBLEM_INPUT_MISMATCH, preserving the original
conversation and recording zero business writes. The authorization-lock fix is verified
in the owned clone; 85 backend checks passed before the task-input compatibility change.
Evidence: real-browser/execution-owner-r2-browser-complete.json and
execution-owner-r2-original-work-refusal.json. This proves refusal of a mismatched old
work item, not successful admission of a new one. The canonical task-input correction
above supersedes the initial extra-measurement-key approach. Main remains unchanged.

Canonical work-input correction now passes 90 backend checks in 153.48 seconds,
including real PostgreSQL-backed source contract readback, existing continuation
regressions, maximum-length owner schema/domain validation and altered-contract
rejection. Ruff and diff checks pass. No new task/model/execution or main installation
was performed. Evidence: capability-work-input-checkpoint-r1.json and
capability-work-input-checks-r1.txt. New-task creation and explicit saved association
remain the next integration step, not inferred from compatible prepared payloads.

### Original-owner creation from an exact saved capability source

Reuse the existing CREATE_PROBLEM conversation action intent and original owner route.
For a capability source only, permit its exact saved SOURCE message as the intent's
messageId. Verify the owned message facts equal the submitted source and canonical
Problem payload equals the authenticated workInput (owner is current principal, no
Draft invocation, initial owner version zero). Persist the existing intent/message/source
and eventual owner_ref association; do not replace the current journey or infer latest
preparation. All other actions retain their original user-message requirement. Current
capability/member access is rechecked on claim; original owner authorization and receipt
reconciliation remain mandatory. No action-intent endpoint dispatches an owner itself.

Original-owner creation seam passes 102 regression checks in 216.63 seconds. The
real PostgreSQL Problem integration retains the original SOURCE message, persists
intent message/source/owner_ref association, returns an OWNER_RECEIPT, and rejects
repeat dispatch without model calls. That test uses a controlled capability reader;
the separate real published-capability owner test proves saved-source equality,
cross-conversation rejection, changed-input rejection and intent replay. An additional
revocation check proves withdrawal before claim leaves claimed_at and owner_ref empty
(2 targeted checks pass in 5.41 seconds). Ruff/diff checks pass. No live browser creation
or main installation is claimed. Evidence: capability-original-creation-checkpoint-r1.json,
capability-original-creation-checks-r1.txt, capability-creation-revocation-checks-r1.txt.

### Visible capability work association in the original conversation

Derive preparation status only from a readable CREATE_PROBLEM intent whose messageId
matches that exact SOURCE, followed by a readable OWNER_RECEIPT with the same intentId
and a Problem reference. Do not infer from latest work, title, capability identity alone,
or a generic SUCCEEDED status. Show goal recorded separately from execution; ambiguous
or claimed-without-receipt remains awaiting verification. Preserve original work display.
Capability ACTION_INTENT records must retain their original read-only reconciliation
controls instead of being incorrectly rendered as another preparation card. No new model
call, automatic retry or additional confirmation is introduced by status rendering.

Explicit association rendering passes 14 capability UI checks plus 7 preparation/history
checks (21 distinct cases). Build passes. A real isolated authenticated browser then
submitted one intent and one original CREATE_PROBLEM request, obtaining a persisted
Problem and original-conversation OWNER_RECEIPT. The actual page shows goal recorded,
retains original work, and survives refresh. Database verification confirms exact
source-message/intent/problem association and unchanged original execution, budget and
resource-definition hashes. No model/execution was started. This is original-owner API
submission plus actual status UI evidence, not yet a user-click creation-to-execution
journey. Evidence: real-browser/capability-creation-browser-complete.json,
capability-creation-database-complete.json, and 19-capability-created-original-conversation.png.
Main remains unchanged; consolidated prototype acceptance remains pending.

### User action through existing Problem and Criteria owners

After the existing use-page input check and source-contract readback, continue the same
user submission through the original CREATE_PROBLEM intent/owner, existing criterion,
criteria-set and ACTIVE transition endpoints. Use contract-derived stable command keys;
reconcile a claimed creation through its existing intent instead of repeating creation.
Read exact Problem revision and existing criteria sets before continuation. Preserve full
contract in criterion applicability; reject altered scope/target/criteria rather than
substituting. Recheck browser identity before writes, bound requests, and retain original
source submission on failure. Activation is preparation for planning, not a model call,
execution authorization or successful result. Update action copy to describe goal and
criteria preparation truthfully; do not add a separate confirmation for each owner.

The same use-page submission now creates the original-owner Problem, fixed criterion,
criteria set and ACTIVE preparation state. Twenty-three relevant UI cases pass, including
lost creation response reconciled without a second create and UNKNOWN receipt refusing
redispatch. Frontend lint/build pass. Real isolated browser clicks (not direct script
owner submission) saved a new source, goal and criteria, returned to the original
conversation, and survived refresh. Owner readback verifies exact contract applicability
and criterion membership; database checks preserve original execution/budget/resource
hashes and the previous explicit association. No model or execution was started.
Evidence: capability-use-work-checkpoint-r1.json and its real-browser references.
Unfinished preparation after leaving the input view still needs a source-specific resume
entry. Planning, fixed-resource preparation and execution-result return remain incomplete;
main and full prototype acceptance remain unchanged.

### Resume saved preparation in the original conversation

Add a source-specific recovery action on the existing capability SOURCE card. Read the
owned fixed contract and reconcile the associated creation intent, then inspect existing
criteria and criteria sets before writing. A fully prepared work item performs reads only;
partial preparation continues with the same contract-derived keys. Reject changed target,
conflicting criteria, multiple associations, denied reads and UNKNOWN creation outcomes.
No latest-source inference, new confirmation flow, model dispatch or execution is added.
Abort future steps on view/session change and retain saved owner outcomes for later readback.

Source-specific resume is now verified in the actual isolated UI using two existing
records: the earlier Problem-only preparation gained its criterion/set/ACTIVE state with
three owner writes, zero new Problems/sources; the already-complete record and the
refreshed resumed record were then checked read-only with zero additional writes.
Original messages and journey are equal, both explicit associations remain intact, and
original execution/budget/resource hashes are unchanged. Twenty-eight distinct frontend
cases are covered (27 initial full cases, then 5 targeted cases after the added concurrent
target-change guard); lint/build/diff pass. Evidence: capability-resume-checkpoint-r1.json
and its actual browser/database references. This closes leaving-the-input-view preparation
recovery, not planning/model/execution or full product acceptance. Main remains unchanged.

### Fixed-capability planning input

Add a read-only preparation operation beside question-activity-input, using its existing
BUSINESS_PROBLEM LIST grant plus exact current Problem/Criteria and saved capability
owner/member reads. Resolve the owned source on the existing AuthorizedOwnerCall
connection, verify current Problem/Criteria against the fixed contract, and derive the
source only from its exact Knowledge binding. Observe registered operations only from
its fixed Employee and supported fixed business members, never global visible candidates.
Feed the existing PlanningRequest owner a fresh target and bounded instructions; complete
objective, input notes and constraints already travel through persisted criterion
applicability in Planning's business_context. No historical plan or task graph is copied.
Preserve long exclusions through deterministic labelled <=500-character boundary parts;
keep short boundaries byte-identical. Unsupported multiple-source/tool bindings fail
explicitly. No model/budget/worker activation or execution in this preparation operation.

Planning admission must also read the persisted claimed CREATE_PROBLEM intent on the
same authorized connection and require exactly one matching source-message/Problem
revision/digest association. Matching text and copied criterion metadata alone are not
proof of association. Reuse this check in capability execution admission as well.

Fixed-capability planning input passes 118 backend checks in 177.83 seconds, including
real PostgreSQL fixed-Employee observation without global candidate scanning, exact
claimed source/Problem association, and existing planning/continuation regressions.
Actual authenticated isolated browser requests produced stable fresh PlanningRequest
input for the newly prepared document work, with four registered fixed-member operations;
wrong digest and wrong Problem were rejected. Original messages, journey and execution/
budget/resource hashes remain unchanged. Ruff/format/diff pass. No model invocation,
proposal, plan, or execution was created. Evidence: capability-planning-input-checkpoint-r1.json
and its browser/database references. Source-specific planning/execution journal and the
real governed model/confirmation/resource/execution path remain incomplete. Main unchanged.

### Source-specific planning/execution journal

Introduce an additive private-conversation UI journal keyed by tenant/domain/conversation/
exact saved capability SOURCE message. Retain the legacy conversation journey unchanged.
Store append-only versions with stable command key, payload digest, actor and contract
digest; CAS on the prior journal version serializes using the existing owned-conversation
lock. Replay reauthorizes the source; a changed body under one key conflicts. The record
is UI continuation metadata, never authority for Problem/Plan/execution or proof of success.
Every resumed action must re-read its owner. Read/save reauthorize the owned capability
contract outside the conversation lock to avoid nested authorization lock waits. Archived
conversations cannot gain new journal versions. Capabilities off means these routes stay
absent. Migration 0054 uses the same database, explicit migration/compatibility checks,
no startup DDL, no changes to original messages/journey/owners, and no new infrastructure.
Verify cross-source isolation, replay, stale CAS, revocation, fresh session readback and
preservation of old journey before connecting real planning/model calls.

Source-specific journal candidate passes 35 targeted backend checks in 15.36 seconds
(capability source, capability owner routes and BFF regression), including real PostgreSQL
two-source isolation, legacy journey preservation, command replay/conflict, stale CAS,
contract mismatch, cross-conversation denial, revoked-member read/replay denial, retained
versions and database deletion refusal. Ruff and format pass. Evidence:
capability-journal-checkpoint-r1.json / capability-journal-checks-r2.txt. Migration 0054
has only run in the isolated test fixture; browser clone and main remain unchanged.
Frontend integration, actual model/execution and consolidated prototype acceptance remain open.

Isolated runtime migration exposed an existing ledger compatibility gap: production
private_conversation.schema_migrations has version/checksum/applied_at and no adapter.
Failed migration transactions rolled back before process replacement. Corrected migration
and compatibility to preserve that schema and insert named columns; fixture now mirrors
it and applies the migration twice. 35 checks pass in 16.12s (journal-checks-r4).
Owned clone restarted as PID 4778 only after explicit migration; authenticated browser
saved one journal version, verified replay, rejected stale/changed contract, reloaded
and read it back, and confirmed other source and legacy journey unchanged. Database
owner/budget/resource hashes unchanged, old ledger versions 1/2 preserved with 54 added.
Evidence: capability-journal-checkpoint-r2.json and real-browser/capability-journal-*.
Frontend integration and model/execution remain open; main unchanged.

Frontend continuation integration: after current owner goal/criteria/lifecycle verification,
initialize the exact-source UI journal only when version zero. Preserve any existing
matching Problem journal (including later phases), never rewind it during preparation
recheck. Read back after write; unknown responses recover through read-before-write on
explicit retry. Display saved progress inline as historical continuation metadata, not
execution success. Verify session before/after reads and writes, abort on unmount, and
withdraw stale display during context changes. No additional model calls.

Frontend exact-source preparation journal integration passes 30 browser fixture cases
in 32.2s, including lost journal response recovery and preserving later phase on preparation
recheck. Lint/build pass (existing large bundle warning). Owned clone PID 5198 installed
the candidate frontend. Actual authenticated UI rechecked the already-created first
source work, appended exactly one journal version, displayed it, restored it after reload,
and rechecked again without any new owner or journal writes. Other source and original
journey/messages remained identical; owner/budget/resource database hashes unchanged.
Viewed screenshot 23-capability-journal-ui.png and added demonstration section 8.
Evidence: capability-journal-ui-checkpoint-r1.json and corresponding browser/database
receipts. Model planning/execution is not connected, main remains E22, and consolidated
prototype acceptance remains pending. Do not treat preparation journal as execution proof.

Next phase: expose original-conversation planning using existing planning-v2 owner API
and SSE without a new provider. Re-read fixed planning input and owner preflight, then
CAS a source journal PLANNING_PENDING claim with stable request key before dispatch.
No automatic dispatch on mount, refresh, or an unknown result. Recover using the existing
read-only request endpoint; verify request key and Problem identity before presenting
proposal/clarification. Record invocation identity only, not a copied claim of execution.
Keep authorization/budget/adaptive owner behavior; do not renew exhausted Native policies.
Unavailable model configuration must be visible before a model dispatch, and a pending
request must remain non-replayable even if the transport disconnects.

Planning UI candidate: same source journal CAS before planning-v2 model dispatch, existing
SSE progress, and explicit read-only request recovery are wired inline. 33 distinct frontend
cases covered across regression and targeted rerun (initial 32 pass/1 async assertion race;
3 targeted pass after awaiting save completion). Lint/full-flags build pass. Clone PID 5829
actual UI performs fixed input and preflight, shows PLANNING_NOT_CONFIGURED, and performs
zero model, owner or journal writes; original hashes unchanged. Screenshot 24 viewed, demo
section 9 added. Evidence capability-planning-ui-checkpoint-r1.json. Main unchanged.
Inspection found a remaining adaptive-chain gap: planning_adaptive.projection returns the
last child request, while current frontend validation expects root key and read-only route
reads only root invocation. Current conservative check stops mismatches; before real
adaptive execution, add owner read-only chain recovery with exact root/child provenance.
Clarification answers, proposal confirmation/fixed-resource execution, business wording and
real bounded model configuration also remain open. No Native budget renewal authorized here.

Adaptive recovery integration: add a separate planning-v2 read-only-chain endpoint,
leaving existing settlement-aware recovery endpoints unchanged. Read each existing
invocation with settle_receipt=False, validate deterministic child key, predecessor
identity and unchanged exact ProblemTarget, and return explicit root provenance with
the final projection. No provider observation, settlement, reservation or dispatch.
Frontend will use this owner projection after dispatch and on recovery; root-key equality
must be checked on the envelope rather than incorrectly requiring a child to reuse it.

Adaptive readonly-chain candidate passes 36 planning productization checks in 7.41s
with real PostgreSQL invocation records and controlled provider; strict read wrapper
asserts settle_receipt=False for every root/child and provider call count unchanged.
Five negative/unit checks reject detached key/predecessor/target and unbounded loops.
Frontend now consumes explicit root provenance and the final owned invocation after
dispatch or recovery; four targeted cases pass in 17.8s including a different child key.
Backend lint/format/diff and frontend test build pass. Evidence:
capability-readonly-chain-checkpoint-r1.json. This source is not yet installed to the
isolated runtime (still PID 5829) or main; no real model call or completed business run
has been demonstrated. Clarification submission and subsequent owner execution remain open.

Clarification continuation: user answer stays in original conversation using an invocation-
specific message key. Before saving, reread source journal and owner read-only chain and
require terminal NEEDS_CLARIFICATION for the same invocation. Reconcile an existing
message before writing; differing text under the same key conflicts. Save next preparation
with predecessor invocation/root and accumulated answers, preserving fixed capability
contract. Fresh planning input/preflight is required before successor dispatch, with the
existing owner's target/predecessor/request-revision checks still enforced. No new model
call occurs merely from saving an answer or refreshing. Keep source journal command keys
bounded even after successor request keys include an invocation identity.

Clarification UI now saves the answer in the original conversation, reconciles an
existing identical message after unknown response, persists successor predecessor/root
and answers, and continues only from the explicit save-and-continue gesture. Refresh
never queues a call. Stable successor/message keys hash the contract and invocation
identity so long owner IDs cannot exceed API limits. Existing model owner validates
predecessor terminal clarification and exact target. Real PostgreSQL/controlled-provider
regression: 37 pass in 8.55s, including original clarification preserved, successor target
and answers retained, duplicate begin causes no additional call. Six frontend targeted
cases pass in 21.8s; two clarification cases rerun after bounded-key change pass in 17.2s.
Test build and lint pass. Evidence capability-clarification-checkpoint-r1.json.
Actual model, updated-runtime verification, fixed bottom composer placement, proposal
confirmation/execution and consolidated prototype acceptance remain open. Main and owned
clone PID 5829 remain unchanged; no new model call or policy renewal.

Fixed-composer alignment: reuse the conversation's existing dock and portal. Maintain
an explicit UI-only selected source; validated clarification readback may focus that
source, and another pending work must be selected before its answer form is shown.
Selection is never an execution association. Suppress the original journey/native
composer while capability input is selected, offering an explicit return to that work.
Keep draft answers per principal/conversation/source/request key, preserving them when
switching work or refreshing. No new backend writes or model calls from selection.

Fixed-composer candidate: explicit source focus routes capability clarification to the
existing dock, original understanding/Native composers offer a return-to-work action
while another source is active. Draft key includes principal/conversation/source/request.
Successful answer refreshes actual conversation messages as well as the source journal.
78 combined conversation/capability cases pass (1.3m), including old Native/input/stream/
Markdown/message styling cases. Final six targeted checks pass in 20.3s after adding
refresh-draft and immediate answer-message readback assertions. Lint/test build pass.
Evidence capability-fixed-composer-checkpoint-r1.json. This change is not installed;
owned clone remains PID 5829 and main remains E22. Still open: current source progress
in right rail, actual model/authority integration, proposal confirmation/execution, and
consolidated actual-page/prototype acceptance.

Source progress rail: add a dedicated capability slot separate from original work.
Selecting a source for planning/clarification changes only presentation focus, never
owner association. Show immediate local pending state, stream byte count, verified
returned proposal/clarification, or historical journal awaiting readback. Never infer
live execution or successful result from saved UI phase alone. Hide stale preparation
heading only while this source's progress component is actually mounted. Preserve
original work rail and non-readable source withdrawal. No narration model calls.

Current-source rail integration passes eight targeted frontend checks in 22.2s,
including visible waiting before the one model response, returned proposal with no
execution claim, unconfigured model, clarification and original-work separation.
Lint/full-flags build pass. Updated candidate (including readonly-chain, clarification
and fixed-composer source) installed only to owned clone PID 7499. Actual authenticated
page displays human-readable configuration gap in both message and rail; only input
and preflight requests, zero invocation or owner/journal mutations. Original hashes
unchanged. Screenshot 25 viewed and demonstration section 10 added. Evidence:
capability-progress-ui-checkpoint-r1.json. Main E22 unchanged.
Read-only main configuration/budget audit saved separately: current Native f3 ledger
24/24 reservations with no unsettled entries and policy expiry 2026-11-10T19:40:27Z.
Historical original planning/understanding ledgers have independent-admission history;
do not infer available new-call authority from old configured caps or clone copies.
Before real-model bringup, resolve exact context/model authority and a valid bounded
policy without resetting or silently renewing existing exhausted windows.

Governed capability planning admission (G1): D8 accepted standing development signatures
and aggregate 100 calls/USD50; D11 retains that same shared ledger including UNKNOWN.
D12 enables current devadmin resource use. Existing development_journey_admission uses
these ceilings but demands a prior model-understanding draft, which capability-created
Problems intentionally do not have. Add an alternative provenance check only for current
D12 devadmin and capability feature enabled: exact claimed CREATE_PROBLEM source owned
by this actor, current owned published capability/member reads, unchanged current target
and canonical criteria. Reuse original one-invocation staged admission, account/generation,
model grants, budget lock and audit. Record truthful capability_source with no fabricated
draft/source context. Recheck provenance on replay; no existing ledger/cap/settlement or
Native expired policy modification. Bootstrap callback uses the existing authorized owner
port on the same connection to avoid nested authorization deadlock. Negative/revocation
and existing draft-path regressions required before real dispatch.

Capability model-admission candidate passes 13 role/admission/bootstrap checks in
29.78s and six exact-source negatives in 0.70s. The real PG admission regression uses
a controlled provenance callback and proves same shared ceilings, one-call staging,
no fabricated draft, provenance recheck on replay and changed/absent-source refusal;
source adapter tests independently exercise canonical criteria, target, ambiguity and
revoked-reader refusal. This is not real provider or complete configured-owner proof.
Lint/diff pass. Evidence capability-model-admission-checkpoint-r1.json. Main and owned
clone unchanged; no credential or budget mutation. Standing D8 approval allows existing
100/USD50 operational signatures, so no repeated general permission request is needed.
Paid calls must not use copied clone ledger capacity as an extra spending window. Keep
clone model disabled while finishing confirmation/execution and review, then use the
original authoritative budget in controlled delivery, or an explicitly accepted bounded
isolation arrangement. Do not invent a second ledger or discard paid clone receipts.

Source-bound confirmation (G1 continuation): extend the existing automatic confirmation
request with an optional complete capability source reference. Capability-marked current
criteria require that reference; legacy requests remain supported. Before policy decisions
or confirmation writes, and in the confirmation current-state callback, re-read the owned
source, validate its digest and claimed Problem association, then check exact target,
completion criteria and exclusion boundaries. No new confirmation owner or budget.

Source-bound confirmation implemented in the existing policy owner. Partial references
are rejected; capability-marked criteria cannot omit their source. Owned source/digest,
claimed Problem association, full criteria and exclusions are rechecked in the existing
current-state callback before confirmation. 27 targeted unit cases pass in 0.71s;
32 combined PostgreSQL legacy confirmation/resource-recovery and constraint cases pass
in 35.61s. Lint and diff checks pass. Source association negatives use controlled readers;
this is not real capability provider-to-execution evidence. Not installed to clone or main.
Next: fixed-resource selection integration, frontend confirmation, actual governed model
and original-conversation results with consolidated review.

Fixed resource selection (G1 continuation): reuse the existing employee-selection owner,
add complete capability provenance, validate before replay, require exact bound Employee,
and check derived business resources against the fixed contract before any source-change
or successor confirmation. Recheck successor constraints before writing. Preserve legacy
command hashes by excluding only newly absent capability fields. No global resource scan.

Fixed selection implemented: provenance and exact Employee checked before command replay;
derived business resources checked before source-change/successor writes; successor full
constraints checked before confirmation. Legacy command digest excludes new absent fields.
34 PostgreSQL and unit checks pass in 35.04s, including real selection-owner rejection of
wrong Employee revision and undeclared resources with zero new proposal/command receipts.
Those two tests use a controlled provenance reader, not a full real-source E2E. Legacy
automatic selection/recovery remains passing. Lint/diff pass. Main/clone unchanged.
Next is original-conversation frontend confirmation and fixed-selection orchestration,
followed by actual owner/model/execution validation and consolidated prototype review.

Original-conversation confirmation UI (G1 continuation): read the returned proposal from
its owner and exact source before confirming through existing policy. Persist pending
before POST; lost responses recover only through history GET matching exact proposal
revision/digest/target. No automatic confirmation on refresh and no model invocation.
Store confirmed plan reference in the source journal only after owner readback.

Original-conversation confirmation candidate is wired below the returned proposal. It
re-reads source and proposal, records pending before dispatch, and recovers lost responses
only by exact history match. Confirmed plan reference is saved before showing completion.
Seven controlled browser cases pass in 22.6s (normal/lost/mismatched confirmation plus
stream/lost/unconfigured/adaptive planning); lint and feature-enabled build pass, with
existing large-chunk warning. No actual provider or owner browser E2E claimed. Main and
owned clone unchanged. Current explicit confirmation control is an intermediate candidate;
consolidate with resource preparation under the standing policy before product acceptance.
Remaining: resource preparation/execution UI, original-ledger real-model validation,
actual-page/prototype review, broader management delivery.

Selection recovery (G1 continuation): expose GET on the existing fixed employee-selection
route, using existing immutable command receipts. Revalidate current source association,
source Plan, policy and readable resources. Match stored capability source and predecessor
reference; never scan/select/confirm/dispatch on GET. Persist capability source in new
selection receipts; no new table or infrastructure.

Fixed-selection recovery and original-conversation resource preparation candidate complete.
GET reads existing receipts with exact predecessor/policy/source checks, no selection
mutation. Frontend persists selecting/preparing phases before writes, reads receipts,
checks fixed bindings, and retains ready plan/resource key. Interrupted POSTs recover
without reposting; verified selection can continue into first resource preparation.
Regression found legacy selection lacked target reads before the newly added source check;
moved bounded policy target-read grant stage before current_input (same transaction,
revocation preserved), rather than skipping authorization. 16 backend cases pass in
47.13s, including twice-read selection and missing receipt; 11 controlled browser cases
pass in 25.8s including normal, selection-response-loss, preparation-response-loss and
wrong Employee stopping. Lint/build/diff pass; existing chunk warning remains. No main or
clone installation; controlled UI is not real provider proof. Next: consolidate policy
confirmation/resource preparation into one continuation, execute and return results to
this exact source, then governed real-model rehearsal and consolidated prototype review.

Exact-source execution UI (G1 continuation): reuse readonly-continuation owner and its
immutable capabilitySource receipt. Persist pending before POST; on refresh or uncertain
response use GET only. Verify source Plan/digest, principal, Problem and execution digest
before rendering. Persist execution reference after owner readback; live polling reads
only. Reuse existing inline delivery/process views rather than navigate away or create a
second execution. Distinguish technical success from business acceptance.

Exact-source execution candidate wired into the original conversation: pending journal
before one readonly-continuation POST, read-only receipt recovery/live polling, source
Plan/principal/Problem/capability/digest verification, source-bound execution reference,
inline document results and existing process view. No navigation or secondary Run.
Technical completion and undetermined business outcome stay distinct. Document/tabular
artifact provenance now validates exact sourceSnapshot like other analytical reports.
11 controlled browser cases pass in 34.8s for confirmation/resources/execution; final
9 execution and desktop/mobile document regression cases pass in 24.6s. A timing-sensitive
lost-response assertion was corrected to verify durable pending, one POST and reload
recovery rather than require a transient error which successful automatic GET can clear.
Lint, feature-enabled build and diff pass; known chunk warning persists. Not installed
to clone/main and not real provider evidence. Next: consolidate confirmation/resources/
execution into a continuous policy-authorized journey, then real owner rehearsal and
governed original-ledger provider proof, consolidated prototype acceptance and deployment.

Continuous candidate journey (G1): keep automatic advancement as in-memory intent from
this user's active planning action, not a persisted execution grant. On verified PLAN_READY,
PLAN_CONFIRMED and RESOURCES_READY advance once through existing policy owners. Any error
stops local advancement. Refresh never reconstructs start intent from journal phases;
recovery reads remain available and existing owner authorization/budget/audit decide each
step. Necessary clarification remains in the fixed composer; its explicit answer resumes
this same journey without adding model calls for narration.

Continuous live intent wired across verified planning, policy confirmation, fixed resource
preparation and execution. Error stops advancement; refresh preserves read-only recovery.
Nine targeted cases pass in 23.0s including one model/confirmation/selection/preparation/
execution call each and no intermediate approval clicks; 97 combined browser cases pass
in 1.6m. Lint/full-flags build/diff pass. Candidate installed only on guarded owned clone
PID 10724 (birth Wed Nov 11 09:50:38 2026), index-CSDgR-pC.js. Actual authenticated page
shows model-not-configured in original conversation and right rail; zero owner/journal
mutations, unchanged original execution/budget hashes, two existing journal rows.
Screenshot 26 viewed. Main PID 90827 unchanged. Real provider/Native remains unproven.
Observed historical preparation copy still says downstream progress is not connected;
include copy cleanup in consolidated product pass. Next: real owner/provider rehearsal
using original authoritative ledger and valid Native policy, final prototype review.

Release preparation: live read-only audit confirms current Native f3 ledger used24,
unsettled0, actual cost167930 microusd; configuration expired at 2026-11-10T19:40:27Z.
A concrete new verification window proposal (8 calls/USD1/24h, one new capability source,
no old replay or automatic renewal) was submitted to the user; it is NOT authorized or
activated yet. Other delivery continues. Old preparation copy now describes available
in-conversation continuation instead of incorrectly saying the path is not connected.
Normal commit hooks found imported-fixture lint and an unset-DSN fixture attempting a
default local PostgreSQL connection. Re-exported the actual shared fixture and enforce
the dedicated-DSN requirement inside it, including imported use. Eight affected tests
pass on isolated real PostgreSQL in 35.98s; no assertion removed. First commit rejected;
normal hooks will run again, without bypass. No main deployment or new paid model call.

### Catalogue interaction continuation — 2026-11-11

Implement F3 catalogue card/list presentation over the same authorized owner records,
including keyword filtering and an explicit filtered-empty state. Both presentations
must open the exact selected revision and preserve the return-conversation context.
Do not synthesize domain labels from prose or expose nonfunctional favourite controls.
This UI-only increment introduces no owner writes, authorization changes, model calls,
or schema changes. Account/workspace-persistent preferences and domain metadata remain
required follow-on work, not satisfied by component state. Validate both layouts,
filtering, detail return, narrow screens, and existing capability tests; run frontend
lint and build. Consolidated prototype acceptance remains pending.

Validation of this increment: frontend lint/build passed; capability browser suite
44/44 passed in 56.2s. Initial run 43 passed/1 failed due to a timing assumption:
visible initial progress precedes the request reaching the route. The test now
waits for exactly one request before releasing the held response, retaining its
refresh/no-replay assertions. Desktop/mobile screenshots inspected. Evidence:
`work/evidence/f3-business-capability-design-20261111/catalogue-layout-r1` in the
continuation workspace. Controlled API data, not real-provider acceptance. Main
runtime unchanged; account/workspace persistence and full-catalogue filtering
remain unfinished.

### G1 — Own capability catalogue preferences

Add an append-only preferences aggregate in the existing PostgreSQL capability
schema, keyed by tenant, security domain, and authenticated principal. GET/POST
`business-capabilities/preferences` use the existing directory LIST admission;
this permits only the caller's UI preferences, never editing another user's data
or resource authority. No caller-supplied account/scope is accepted. POST is CSRF
protected by the existing BFF, CAS/versioned and command-idempotent. A saved
favorite identifies a capability, not a frozen execution revision; saving must
verify current READ on a real current published or head revision. UI listing still
filters through the resource owner. Removing a favorite requires no resource read.
Persist query, layout, favorites-only choice, and scroll offset with bounded input;
keep fields typed and reject extra fields. Record policy decision and actor scope.
Use migration 0055 with immutable trigger/checksum/schema validation, explicit
installation only; startup never migrates. Conflict/lost response must stop writes
and reconcile from the original command/read. Do not silently overwrite another
session's preferences. Existing histories and model budgets remain untouched.
Validate real PostgreSQL account/scope isolation, CAS, replay, CSRF, permission
revocation, and immutability before frontend integration and deployment.

Own-preferences validation: 7 real PostgreSQL/BFF tests passed (22.37s),
frontend lint/build passed, 45 capability browser tests passed (55.8s), plus the
added lost-response readback check passed (14.7s including build). Explicitly
installed 0055 in the owned clone only and restarted its verified process; ready
PID 15260 at https://127.0.0.1:60662. Actual authenticated browser saved favorite,
query and list/favorites modes, refreshed, opened exact detail and returned;
state matched the two immutable scoped preference rows. Existing execution,
budget and resource hashes unchanged; zero model calls and no new runs. Initial
restart helper failed before migration/process stop due to missing local import
paths; paths were corrected, and the one guarded restart then completed. Do not
repeat completed mutation scripts. Actual images 27/28 and database/browser
receipts are in `real-browser`; this is real preference persistence, not model
execution acceptance. Main unchanged. Scroll restoration, home synchronization,
domain metadata/full-catalogue filtering and consolidated review remain open.

### G1 — Domain metadata and whole-catalogue filtering

Extend the non-frozen capability definition with optional `business_domain` (80
characters, explicit author input). Omit absent values from canonical records so
all old content digests and fixed references remain identical. Domain edits are
ordinary immutable successors, visible in publication diff; never rewrite old
published records or infer categories from free prose. Old entries display unset.
Add owner-side keyword/domain/favorites filtering before matching-page pagination,
retaining exact READ checks and published-before-draft selection. Bind continuation
cursors to account, query/domain and the saved favorite set. Enumerate available
domain labels only from currently readable selected definitions. Use chunked reads
in the existing database (no index/service dependency); large-directory latency
remains a measured follow-up, not claimed optimized. Preference JSON adds a domain
field with default-all for old records. Frontend cancels obsolete filter reads and
never presents a stale filtered result as current. Validate legacy digest identity,
domain diff, filters beyond the first raw page, revoked/unreadable exclusion, and
cursor rejection across filters/accounts. Preserve all execution and budget gates.

Domain/filter validation: 19 backend checks passed (38.22s); 46 capability browser
checks passed plus the added combined-filter persistence check (19.0s including
build). Latest frontend lint/build and backend lint/format passed. Explicit owned
clone restart completed, PID 16183, frontend index-BKVxCHTQ.js. Actual authenticated
browser appended a metadata successor, reviewed/published it, filtered by its
运营管理 domain and existing favorite, then refreshed successfully. The old revision
and original conversation source contract are byte-equivalent; database comparison
shows only business_domain/revision_id/predecessor_revision_id changed. Definitions
remain 1, revisions/receipts/publications now 2 each, both publications use the real
development-administrator policy basis. Existing execution/resource/budget hashes
unchanged; zero provider calls and zero new runs. Evidence images 29/30 and
capability-catalogue-{browser,database}-complete.json are in real-browser. Do not
rerun the completed mutation script. Domain options refresh on detail return after
publication. Remaining: scroll/home synchronization, consolidated prototype review,
large-directory performance characterization, and overall project delivery. Main
runtime unchanged; this does not close real-model acceptance.

### Home favourites continuation

Replace the home placeholder with the same authorized favourites-only catalogue
reader. Show at most three real readable capabilities, exact revision/digest links,
and an explicit directory entry. Re-read on return/focus and manual refresh; logout
withdraws content. Do not create a second bookmark store, grant rights, or start work.
Preserve a validated home return marker through nested fixed-resource navigation.
Keep feature-disabled installations on the existing resource entry. Validate home
read/error/withdrawal, exact links and zero writes; then verify the installed clone.
Scroll restoration remains part of this catalogue package and is not closed here.

Home favourite validation: 10 home regressions passed (16.8s), two fixed-return
checks passed (15.7s), frontend lint and full-feature build passed. Owned clone
restart completed at PID 16823, bundle index-CHD9mceF.js. Actual authenticated browser
opened the saved published capability from home, traversed its fixed Employee and
returned with capability revision/digest and home origin preserved. Removing then
restoring the favourite updated home correctly; exactly two preference writes,
zero resource mutations, zero model calls and no new executions. Database readback
matches the final preference and protected execution/budget/resource hashes.
Evidence: capability-home-{browser,database}-complete.json and screenshots 31–33
in real-browser. Do not repeat completed mutation/restart scripts. Main unchanged.
Scroll restoration and consolidated prototype acceptance remain open.

### Catalogue position restoration

Persist scrollTop together with loadedCount in the existing own-account preference
record. Old records default to the first 50 rows. On return/refresh, read matching
pages only through current owner authorization until the saved extent or catalogue
end, then restore the scroll container (clamped when data shrinks). Bound replay to
10,000 rows and a 30-second combined read deadline; repeated cursors fail explicitly.
Never persist resource payloads or reuse stale records to restore position. New
filters reset extent/position; layout changes reset position. Suppress scroll writes
while loading/restoring or viewing a detail. Keep save feedback height stable to
avoid scroll-driven save loops. Validate second-page refresh, detail return, filter
reset, schema bounds and no domain/execution writes.

Scroll validation: 49 capability browser checks passed, including restoring 60
rows across two owner pages, refresh and detail return, resetting new filters, and
no idle autosave loop. Seven real PostgreSQL preference tests passed (24.86s),
frontend lint/full-feature build passed. Actual clone browser at PID 17576 restored
405px after refresh and after detail return, without idle write loops. Installed
asset index-Dl5WLAgN.js. Only personal preferences changed; no new model calls or
executions. Evidence capability-scroll-browser-complete.json and images 34–35.
The initial controlled scroll assertion incorrectly referenced a browser global
instead of passing the expected coordinate; corrected the test argument without
changing its tolerance. Main remains unchanged; consolidated prototype acceptance
and project-wide delivery remain open.
