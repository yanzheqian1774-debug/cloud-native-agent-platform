# F3 current work directory implementation plan

G1: additive authenticated read adapter for the approved F3 task page. No new
state owner, database, public CRD, execution lifecycle, or authorization policy.
Existing problem collection LIST is the entry prerequisite; every returned run
requires current exact execution and problem READ. Native question and original
conversation access remain separately checked. OpenClaw stays disabled.

## Implementation sequence

1. Validate bounded query parameters and bind signed keyset cursors to the
   authenticated principal, scope, generation, recovery epoch and filters.
   Defaults come from a verified server role, never a query role flag.
2. Read authoritative preparation, progress, initiator and outcome facts in one
   SQL statement using the existing READ COMMITTED owner transaction. Retain
   saved historical success regardless of current rerun admission eligibility.
3. Reuse current authorization, distinguish unavailable from denied, and derive
   counts and pagination from the same complete authorized filtered set. Fail
   explicitly rather than silently truncating a complete directory.
4. Connect the existing F3 page, preserve explicit scope/query selection and
   exact run return position, reject stale responses after answer/cancel.
5. Validate isolated PostgreSQL concurrency and sparse/revoked permissions;
   compare identical dataset cold/warm latency and render actual/prototype views.

Current stage implements step 1 and the internal single-statement fact read
of step 2. The raw fact read is not an authorized response. It does not register
a route, replace the
installed page, or claim directory/performance acceptance. Cursor validation is
not authorization; every page must execute current owner authorization.

Compatibility: existing task reader and generic cursor codec stay unchanged.
No migration or execution replay. Historical records with no verified original
conversation remain readable with exact permissions without inventing a link.

Tests cover malformed parameters, explicit/default scope, cross-user, cross-
filter, cross-generation/recovery cursor reuse, tampering, and equal-time run
key round trips. Later stages require actual authorized-set and concurrency
verification before enabling the page.

## Single-statement projection validation

The raw read joins the exact problem revision and digest, distinct start-command
actors, saved progress version, artifact count and outcome head. Questions and
answers are paired by invocation identity and exact question key without the
legacy 300-record cap. Original links require an explicit execution digest or
an existing exact problem link plus matching saved journey; no title inference.
All nested reads share the statement snapshot under READ COMMITTED. No artifact
body, answer text or model output is returned by this internal projection.

A 10,000-run admission cap raises a 503 capacity error if exceeded; the extra
row is a sentinel, never a partial successful total. This capacity policy will
need measurement at deployment scale. It does not add a stored index or owner.

A current read-only production-source probe found all 34 stored runs, their
exact problem versions, 14 question records and 8 without verified origins.
These are storage facts, not authorized user totals. Data SELECT took about
138 ms in one observation, excluding authorization and UI: no performance
acceptance is claimed. Permission projection and concurrent-writer verification
remain required before route or page activation.

## Authorization availability distinction

The existing generation reader gains an opt-in require_available read flag.
Its default preserves current callers. Unavailable authority, generation or
recovery mismatch, or malformed batch cardinality raises an availability error
in this mode; ordinary denied/revoked grants still return false. Credential,
static/dynamic grant, administrator and revocation rules remain unchanged.
The directory uses this mode within the caller-owned transaction, without a
second lookup or permission cache across requests. This changes failure
reporting only, not authorization policy.

## Authorized paging implementation

The page assembler accepts only the explicit CurrentWorkItem DTO, never raw
snapshot dictionaries. It computes total, exclusive state counts and page items
from the same scope/search/state filtered authorized set. Page cursors retain
the signed user/filter/generation constraints. Equal timestamps use run identity
as the stable second sort key. Every new request reauthorizes; an item revoked
between pages can disappear without invalidating the cursor or being restored.
No full-list immutability is promised across requests.

An actual devadmin authenticated candidate-owner read found 34 visible runs,
21 with the exact current principal as their unique recorded initiator. All 25
previously visible records and all three repaired historical records remain.
The data plus execution/problem root authorization observation was 772 ms;
question, evaluation and origin policy projection plus HTTP/browser remain
unmeasured. The observed totals are for this identity at that read only.

## Optional metadata projection

Native question metadata uses the existing development-role restriction and
all prepared participant resource reads; unavailable access is null, not zero.
Answered question digests must match; cancelled, cancel-requested and terminal
runs are not pending input. Conversation links use the existing owner/admin
policy and supported schema version; current journey matches are preferred.
Evaluation summaries use exact evaluation, criterion, evidence and resource
grants and the existing PreparedResultReview.snapshot integrity checks. This
is a read, not evaluate/confirm. Progress version changes during integrity
checks abort the page rather than mixing observations. No current-admission
validation is added to historical reads.

Latest authenticated real-data candidate projection read: 34 visible, 21 own,
25+9 page sizes, 26 readable conversation links and 33 readable outcomes.
Full projection observation about 5.5 seconds, versus root-only 772 ms in an
earlier observation; not a controlled benchmark. Existing per-run evaluation
checks add work and must be measured before optimization. Thirty targeted
tests passed. Real concurrent-writer, HTTP and actual-page acceptance remain.

## Route integration and enablement

GET /api/workbench/v1/current-work is registered through the existing BFF and
nonempty business-problem collection LIST grant. Query validation rejects
unknown/duplicate fields; normal browser login and identity checks apply.
Bootstrap enables it only with CURRENT_WORK_DIRECTORY_ENABLED=true and the
existing prepared execution coordinator. It is off by default pending actual
page, concurrent-writer and installed-service validation. Rollback disables the
route; no data migration or history change is involved.

The real in-process BFF with current authenticated devadmin and production
owner database returned visible 34 (25+9) and initiated 21, rejected forged
cursors and malformed parameters, and rejected unauthenticated reads. This
uses an isolated candidate app, not the installed listening server. Normal
login/idle maintenance occurs; no business mutation or model call. Forty
directory tests and 47 BFF/bootstrap/route checks passed (overlapping suites,
not additive distinct tests). Full normal commit validation follows.

## F3 page integration

The existing task page uses the directory only when
VITE_CURRENT_WORK_DIRECTORY_ENABLED=true. Attention and results retain their
existing readers. The task table, detail component and shared F3 styles are
reused. Scope selection, query and state changes reset pagination; session-bound
view storage preserves an explicit scope selection and exact-run scroll/focus
on return. Requests are cancelled on selection/query/identity changes; late
responses cannot overwrite newer reads. Fixed-work remains explicitly pending.

List metadata adds saved plan version, distinct participant instance count,
completed task count and saved progress timestamp from the same snapshot; it
does not fabricate full detail objects or artifact contents. Opening a task
continues to use the existing exact-execution detail read and permissions.

## Page review corrections and evidence

The prototype reviewer accepted the five scoped corrections: compact scope row
in the filter area, underline tabs and wide search, stable table columns,
explicit pending-input/execution-complete wording, equal 1424x820 comparison
and 390px row actions/pagination. Mobile horizontal table scrolling is retained
and its position restores on detail return. The frozen F3 package is unchanged.

Six candidate page tests and 32 existing task/result/attention regressions pass.
Fresh authorized candidate-list replay plus a live installed exact detail read
verified the saved document task, readable report, same focus and scroll
220 -> 220. The reviewer independently reviewed evidence/visuals, not a separate
browser operation. New directory installed HTTP, real concurrent writers and
controlled performance measurements remain unverified; replay duration is not
an API latency result.

## Page-only result verification optimization

Measurements on the same identity/versions showed most directory time in
optional metadata projection. Counts and filters depend on run state and
authorized questions, not business resolution or outcome integrity. First
project all authorized matching run/question metadata without outcomes, select
the signed page, then run unchanged result permission/integrity checks only for
returned rows. Do not cache permissions or results between requests. Each
subsequent page reauthorizes and verifies its own result evidence. Off-page
outcomes are never exposed or counted as validated.

Verify response equality (excluding observation timestamps) against the eager
implementation on the same record versions for both pages/scopes, and compare
paired timings. Do not infer a stable percentile from a few observations.

Paired authenticated in-process BFF verification completed with three samples per
case. All nine paired responses were identical except readAt. Median milliseconds:
visible first page 5370.45 -> 5037.92; second page 5568.58 -> 1993.35;
initiated 3710.05 -> 3514.88. Single-page responses avoid a duplicate projection.
These measurements exclude network/rendering and do not establish stable p95.
No model calls or business writes occurred. Real isolated PostgreSQL answer/cancel
contention also passed five checks, including observed lock wait and answer replay;
this is not an installed HTTP cancellation test. Same-commit installation remains
outstanding. Evidence: f3-task-directory-query-review-20261110.

## Incomplete question visibility before installation

Preserve the existing Native read authorization. Add questionStatusComplete to
the internal directory response, calculated across authorized scope/search rows
before state filtering and paging. A running row with unreadable question status
is unknown, not verified non-waiting. Render waiting totals as unconfirmed when
coverage is incomplete and explain the waiting filter may be partial; do not
claim no waiting tasks. PENDING remains preparing execution, not recovery unknown.
Test ordinary/denied visibility, off-page unknown rows and waiting empty state.

## Exact-grant lock transport optimization

The measured visible request executes 1657 database statements; most time is
in exact grant checks. First optimize only the lock transport: inspect optional
schema availability once per bundle, enqueue each existing delegation SHARE lock
then grant SHARE lock in exactly the input order, and synchronize all commands
before the existing locked checkpoint and dynamic authorization reads. Do not
change SQL predicates, transaction isolation, lock strength/order, time/expiry,
revocation decisions, audit, or cache decisions. Legacy single-lock helper keeps
its synchronous default. PostgreSQL errors must still abort the transaction and
surface as authority unavailable. Compare against the committed synchronous
lock implementation using identical current directory handler and data. Verify
existing owner/revocation concurrency and delegation regressions in isolated DB.

Ordered lock pipeline: isolated authority/delegation/identity regression 66 tests passed without skips, including owner/revocation serialization and identity stop/revocation lock order. Nine paired real authenticated BFF responses were identical except readAt. Median ms: visible first 5949.38 -> 3220.19; second 2331.14 -> 1282.61; initiated 4214.99 -> 2396.32. Three observations per case, network/render excluded; performance target remains NOT MET. No live database cache eviction, model calls or business writes.

## Dynamic grant-state transport optimization

After ordered locks finish, enqueue the existing per-grant SELECT statements in
input order and synchronize before interpreting any result or entering bounded
fallback decisions. Reuse the exact same SQL and row-to-state interpretation
for synchronous single-grant and pipelined bundle paths. Preserve each SQL
statement boundary, lock/credential/generation checkpoints, expiry predicates
and deny/unavailable outcomes. This changes transport only; no cross-request
cache, role shortcut, wider grant, runtime capability or audit change. Compare
to dd4435a using the same handler and lock pipeline; verify mixed/expired/revoked,
generation/epoch mismatch, task delegation and owner concurrency in isolated DB.

Dynamic-state pipeline verification: 66 isolated authority/delegation/identity tests passed; foundation tests initially lacked their distinct database environment variable and were skipped, then all 14 foundation plus 2 pipeline failure/order tests were run explicitly against the isolated database and passed. Nine paired BFF responses equal except readAt; visible first median 2974.00 -> 1954.67 ms, second 1302.36 -> 845.86, initiated 1935.60 -> 1617.39. Three paired samples do not establish complete-page p95; directory performance remains unaccepted.

## Read-route event-loop blocking isolation

Installed full-page samples exceed two seconds. Resource timing correlation is
not causal proof. Reproduce a blocked authentication/owner read while an unrelated
light request should remain responsive, with a bounded watchdog preventing hangs.
For GET operations only, move synchronous authentication and the entire owner
transaction into the existing framework thread pool. Connections are opened,
authorized, used and closed within that worker invocation, never shared across
threads. Keep request validation, exact grants, post-commit behavior, denial/error
mapping, generation barriers, and write/idempotency routes unchanged. Verify light
request responsiveness and all BFF/Native stream behavior before deployment.
Directory gray remains performance-unaccepted. Rollback script has not been
exercised; next deployment must verify disable/restore and the original entry.

The original route failed both bounded responsiveness reproductions (blocked authentication and blocked owner delayed unrelated health response until watchdog release). The candidate passes both, and native-progress denial/unavailability still return JSON before SSE headers. Existing AUTHORIZATION_NOT_FOUND mapping remains 404 (the initial new test incorrectly expected 403 and was corrected to the established mapping). Initial BFF/query/model-stream suite: 59 passed; final focused suite: 4 passed; isolated PostgreSQL owner/revocation/stream checks: 21 passed, no skips. Real-page performance contribution remains unmeasured until controlled deployment; current installed gray remains at 6ebf2ad and performance-unaccepted.

## Exact grant lookup index (controlled maintenance candidate)

Real-page worker-only deployment 89d6744 failed the unchanged paging deadline
and was reverted to 6ebf2ad; its causal responsiveness tests do not prove faster
pages. Disable/restore drill is now exercised. Diagnostics in the delivery
workspace show 1300 execute invocations for a visible first page and repeated
full scans of 4205 grant rows. Existing grant indexes begin with grant_id or
decision_id, whereas locks and state readers use principal/scope/exact target.

Add an opt-in, concurrent, non-unique six-column B-tree index matching those
existing equality predicates. Preserve all query SQL, ORDER BY grant_id, row
locks, expiry/revocation/generation checks, audit and historical migrations.
Do not auto-run it on startup or change the base migration checksum. Existing
index or invalid index must be inspected, never silently replaced. Maintenance
must run outside a transaction, with bounded lock/statement timeouts and exact
index-definition validation, and retain before/after catalog evidence. Rollback
removes only this verified index concurrently; never restore business data.

Validate on isolated PostgreSQL with owner/revocation concurrency tests and the
index present. Compare complete real authorized responses and full-page samples
before performance acceptance. The temporary-table experiment (4205 copied rows)
changed an absent lookup from a 335-block scan to a 2-block index lookup with
identical outputs; four-query median 7.55 -> 6.73 ms is not a page-speed claim.
No new public contract, permission shortcut, infrastructure or model call.

Commit verification exposed two existing real-network tests expiring at STARTUP
before reaching the behavior they assert (one-second total in the shared fixture).
Keep short startup/phase deadline tests unchanged. Parsing and stalled TLS cases
now explicitly use the existing five-second real-network setup allowance; TLS
also requires peer acceptance within 2.5 seconds and keeps its one-second connect
limit, CONNECT-stage assertion, cleanup and no-replay checks. This is a test-only
separation of startup scheduling from network-stage behavior; production deadlines
and the unchanged five-second directory paging acceptance are unaffected. Original
failed suite reports remain in the delivery evidence, not replaced by later passes.

## Terminal snapshot read transport (candidate)

Post-index profiling shifts the main cost to per-page terminal outcome integrity
snapshots. Batch only independent, already-authorized SQL reads inside the same
caller-owned connection/transaction: (1) criteria-set plus problem revision,
after the existing EXECUTION/BUSINESS_PROBLEM/SUCCESS_CRITERIA_SET checks and run
progress lock; (2) artifacts, resource-use snapshots and event high-water, after
all original output evidence/resource grants have passed. Retain separate SQL
statements in their original order, synchronize before any fetch/validation,
and retain every existing integrity check, run lock and error predicate. Criteria
members still read after their exact grants. No cache or skipped integrity read.
Database transport failure aborts the owner transaction without returning partial
results. Earlier dispatch of already-authorized reads may reveal storage failure
before local integrity validation; it never produces a successful partial result.

Compare old and new snapshots using same real data/authority, preserving entire
response except readAt; test pipeline synchronization/failure, corrupted evidence,
and existing owner/revocation semantics in isolation. The isolated delivery worktree starts at installed 6ebf2ad and excludes the
uninstalled 89d6744 worker experiment. Only index maintenance, its checks, the
network-test setup correction and terminal-read batching enter this candidate.
F3 is frozen; no frontend source changes.
