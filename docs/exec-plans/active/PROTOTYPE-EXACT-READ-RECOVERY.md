# Original planning exact READ request and status recovery (G1)

2026-11-06. Sole writer, installed0dcce754f15b. Ledger41calls/16unsettled/
USD12.598116; no pending Native/model job. Existing three failed research calls,
all UNKNOWN reservations and original records remain immutable. This is the next
explicitly requested finite slice; no successor chat or approval platform.

## Existing authority and necessary additive reads

Use existing POST /authorization/grant-requests and independent /decisions.
Applicant submission never approves anything. No PREPARE/APPROVE/continue/model/
diagnostic permission is requested. No onApproved continuation or automatic
planning/usage GET: even an original planning GET can invoke settlement recovery,
so authorization status inspection must not call that path.

1. Original planning invocation repository adds minimal owned-failure metadata
   read, joining the actual invocation_results row. Only durable INVALID or
   OUTCOME_UNKNOWN is eligible; missing durable result cannot use read()'s UNKNOWN
   fallback. Match caller/scope/original request_key and expose only exact root,
   invocation and request identities needed for READ, not body/result/measurement.
2. Existing grant owner supplies exact READ target classification and current
   requestability/revocation. Historical approved grant rows distinguish renewal
   from first READ per member; mixed histories remain explicit. Old two usage
   targets are renewals; salesR2 usage was never granted and is first READ.
3. Add applicant+scope-bound GET by original grant idempotency key. Inspect only
   existing SUBMIT_GRANT_REQUEST claims; no claim/insert/replay. Multiple distinct
   results across epochs are ambiguous and refused. Return original request,
   independent decision category/date/window, and exact current READ status.
   Existing request/decision schemas and writes remain compatible. No raw ticket
   basis, credential material or foreign applicant metadata is projected.

## Frontend finite state and boundaries

Embed on original recovery cards, including request-only pages whose PLAN READ
expired. Display exact object, caller scope, purpose, reason, prior/new READ and
owner-chosen validity window (before decision, explicitly unset). Inputs are not
editable arbitrary grant builders. Exact PLAN/READ uses WORKBENCH_PLANNING;
usage uses only RESOURCE_USE/READ + EVIDENCE/READ_MEASUREMENT under
PROVIDER_USAGE_REVIEW. The decision link goes to the existing independent owner.

Only explicit applicant action sends one POST. Persist its key before dispatch,
bound to principal/tenant/domain/original request/target/purpose. Double clicks,
refresh, login, tab switching and response loss never create a fresh request or
replay POST. Unknown outcome recovers only GET by the original key; 404 is not
proof that no POST reached the owner. Rejected/expired/revoked/pending/unreadable
states are distinct. No recovery button renews a revoked grant or auto-approves.
If a new request is needed, it requires a separate explicit action and state
proof, not a missing response. View/mount epochs and before/after identity checks
withdraw old actionable state. Same-conversation return is preserved.

## Verification and delivery

Isolated64335 tests: durable terminal versus fallback, exact caller/tenant/key,
no raw result disclosure, history classification, key recovery/ambiguity,
pending/reject/expire/revoke, denied self/cross-scope decisions, no settlement.
Browser: explicit-only writes, double click/lost response/reload original key,
identity/view changes, exact set receipt matching, honest statuses and no automatic
read/continue/model/Run after approval. Regress S04 and existing access boundaries.

Before real effects fixed source, mandatory full hooks and immutable installation.
Actual UI requests may be created under the approved exact READ scope; leave them
pending unless the original independent owner actually decides. Engineering
fixtures never count as real decisions. Audit business/ledger/reservations and
settlements unchanged; authorization request/audit additions counted separately.
Screenshot1280x900, finite installed artifact, concrete entry and boundary evidence.
Then this chat waits for orchestrator combined review. Whole dual-case/S04/J11/
92-row/six-package acceptance and old diagnostic ineligibility remain OPEN.

## Implemented finite source and release checks

Durable owned-result metadata, exact target/history eligibility and original-key
status reads are implemented. Explicit original-request read-only route preserves
the normal PLAN READ gate but sets settle_receipt=False. Marker-aware startup
suppresses legacy planning reads, including invocation-only links, and preserves
original request identity. Web Locks plus storage rechecks serialize tabs; only
null means no marker. Damaged/empty markers, scope changes and conflicting
locators block actions. Owner decisions never automatically continue anything.

42 isolated backend checks passed.52 resource browser checks passed, including
S04, response loss, simultaneous/stale tabs, identity/leave races, bad markers,
invocation-only recovery and conflicting locators. S04 absent-operation fixtures
were separated to avoid unroute/session races; assertions remain intact. Full
mandatory commit checks and installed real pending applications follow. Controlled
approval/rejection fixtures are engineering evidence only.
