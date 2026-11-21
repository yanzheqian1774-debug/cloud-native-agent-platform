# Fixed-cycle delivery to the originating conversation — G1

## Scope and original authorities

The existing 0073 BOUND fact identifies the human-owned conversation, immutable
work revision, confirmed problem, and input source. The existing 0070 service
planning record plus 0069 committed trigger receipt identify each real event and
prepared execution. This addition derives a read projection from those records;
it does not append chat messages, invoke a model, create a plan, submit START,
change a schedule, delegate ANSWER, or revive UNKNOWN/terminal execution.
The existing Human model-admission lease is not a history-read authority.

The change is G1: private owner composition and bounded BFF endpoints; no public
CRD, Task/Skill lifecycle, authentication architecture, or storage migration.
Default off. Existing Team activity and ordinary chat paths remain unchanged.

## Trust and exact identity

Every endpoint authenticates the current browser session, checks the current
account through the original authority reader, and reads the original owned,
non-archived conversation. It then checks persisted columns against canonical
JSON/digests for the handoff and BOUND fact and matches subject/conversation/work/
team/target/source ancestry. A saved service preparation must match its policy,
work/event, source-binding digest, target and exact committed receipt. A stored
preparation must match receipt run/preparation digest and saved resource snapshot.
No client-supplied reference creates eligibility. No global LIST is required.

A new private, SHA-pinned default-off read policy enumerates exact original
conversation + subject/scope + BOUND digest + work tuple and an immutable global
expiry. It does not authorize service execution. Its independent issuer is the
already configured resource-preparation issuer; ordinary per-request current
credential, current deny/revoke, target validation and <=1h TTL still apply.
All new grant members are explicit READ / READ_REFERENCE actions derived from
that one verified event and existing saved result-owner facts. No USE, INVOKE,
START, ANSWER or model rights are issued. Expiry is intersected with the private
policy and existing issuer lifetime. Policy disable, expiry, archived chat,
revoked account or denied/revoked exact READ fails closed.

## API contract

Capability `fixedWorkActivity` is false unless the exact private owner is mounted.

GET `/api/workbench/v1/conversations/{id}/fixed-work-activity?cursor=...`:
result has conversationId, state NO_BOUND_WORK|BOUND, bindingDigest, work exact
reference, problem exact reference, inputSource (original BOUND input), trigger,
workTitle, items, hasMore, nextCursor, partial, answerDelegation=UNAVAILABLE.
Discovery begins with committed 0070 planning preparations, before START. Each
item is discriminated by phase PLANNING|EXECUTION. PLANNING has discoveryDigest,
planningState RECORDED|PREPARED|REQUIRES_REVIEW and no run, preparation, receipt,
source snapshot or READ target digest. recordedAt is nullable, never fabricated
from the scheduled date. EXECUTION carries the exact committed receiptDigest,
preparationDigest, runId, actual sourceSnapshot, readTargetDigest and optional
execution state/version under current exact EXECUTION READ. scheduledAt,
plannedLocalDate and timezone come from the saved policy event window.
Pagination is 20+1 ordered by (scheduledAt DESC,eventId DESC), with a signed
scope/conversation/binding/policy cursor. No next event is invented.

POST `.../fixed-work-activity/read-access` accepts bindingDigest, workDigest,
eventId, receiptDigest, preparationDigest, runId, readTargetDigest, commandId and
optional previousCommandId. GET at that path accepts commandId/eventId/receiptDigest
and returns the same identity, state NOT_PREPARED|READ_READY|EXPIRED|UNKNOWN,
original/currentReadTargetDigest and SAME|STRICT_SUPERSET|INCOMPATIBLE relation.
Original grant request/decision records are the receipt; no new storage is added.
After an ambiguous POST only the original key is observed. A different key needs
an explicitly identified completed predecessor: READ_READY permits only a strict
superset, EXPIRED permits explicit same/superset renewal. UNKNOWN, deny, revoke,
shrink or changed roots do not permit automatic fresh-key access.

Targets include only the same preparation's existing READ facts. EVIDENCE and
RESOURCE_USE targets are intersected with actual saved artifacts/snapshots, not
future planned attempts. A successor request records the full finite target
snapshot; when expanding a still-live receipt its expiry is capped by that
receipt, so existing READs receive no early lease extension. Full result access
continues to be enforced by the original prepared-execution reader.

Original 0066 admission and original context revocations are checked against the
0073 saved ancestry. Their expired model lease is not renewed and does not act as
historical READ authorization. Owned conversation locking serializes archive.

## Transaction and lock discipline

Use the existing controller protected request and same connection transaction.
Acquire original governance lock before owned conversation / grant-owner locks.
BOUND, immutable receipt/preparation and policy checks precede any grant write.
Deny/revoke checks precede submit and independent issuer decision in the same
transaction; exceptions roll back the entire finite preparation. GET is read-only.
Uncertain POST transport is resolved through the same request key, never a retry
with a guessed new key. No separate pool or service impersonation.

## Validation and evidence limits

45 pure tests cover private policy/file bounds, persisted source identity,
retained admission/context provenance, static tombstone identity and READ target
successor rules. These include controlled read ports; they do not claim an actual
platform revocation operation. One disposable 53429 integration case uses original
service planning, continuation, grant request/decision and prepared execution
owners: discover planning before START, read the same committed event afterwards,
prepare finite READs, replay without another grant request, and formally surrender
EXECUTION READ then reject new access. Latest unchanged end-to-end run is
pg-final-r2.log: 1 passed in 16.81s. BOUND/Human context facts are immutable fixture
setup; provider/Kubernetes are controlled. No actual model/platform is exercised.

Not yet demonstrated by this backend package: real product BFF mounting, >20-event
pagination, parallel tabs, actual 24-hour wait, and live-growing target sets through
a real running worker. Their implementation and pure transition tests are not
substitutes for those end-to-end checks. Frontend validation is a separate package.

## Explicit remaining boundaries

Necessary-question ANSWER delegation is not available from this read policy.
Do not enable the existing TARGET_REVIEW_ONLY PLAN continuation merely to make
chat input editable; it requires a separately verified read-only assistant route.
No automatic cycle launch, no claim of business acceptance, and no false saved
assistant messages. Actual deployment and two natural cycles remain root-owned.
