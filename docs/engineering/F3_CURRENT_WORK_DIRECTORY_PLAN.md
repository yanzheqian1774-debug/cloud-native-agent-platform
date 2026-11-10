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
