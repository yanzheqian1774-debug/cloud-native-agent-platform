# G1 — clarify saved-answer adoption feedback

Base40caa52, frontend-only isolated follow-up. Presentation reflects backend
facts; it does not change owner state, permissions, retry policy or model calls.
Only a known pre-write adoption guard refusal returned by the adoption POST can
be described as rejected. GET failure, network/5xx and journal-save failures do
not prove adoption absent. Preserve the saved request and existing readback path.
Separate adopted-but-not-written-to-journey, access/read failure, explicit guard
refusal, and unconfirmed adoption response. Keep true execution UNKNOWN handling.
Fold technical codes into details; platform validation never tells users their
answer is wrong. Reuse original routing receipts with optional display notice.
No actual platform/credentials/model/DB operations. Controlled browser coverage
will check refusal, access, uncertain response, saved receipt/writeback failure,
and existing source/UNKNOWN behavior. No automatic retries introduced.

Review refinement: even a pre-write guard refusal only rejects this transaction;
another tab may have adopted the answer. Its heading is '本次接续校验未通过',
without claiming globally absent adoption. Keep the routing receipt UNKNOWN and
existing GET readback, not REVIEW/new dispatch. A committed receipt remains the
only adoption-success evidence. No HTTP code alone changes this rule.

Original clarification display: render nonblank clarificationQuestion verbatim;
otherwise render nonblank dataNeeds verbatim as a list. Generic fallback applies
only when both are empty. No model content rewritten or new call requested.

Explicit continuation after a rejected attempt: only exact adoption GET404
UNDERSTANDING_ADOPTION_NOT_FOUND plus same-key SUCCEEDED saved result and exact
route/message/text/current original owner match exposes the continuation button.
Other404/permission/network failures never expose it. Initial readback is GET
only. Explicit click rechecks the route and existing receipt before any same-key
adoption POST. No model dispatch/new request key is added.

Final review boundary: if a recorded UNDERSTANDING owner target exists, a route
GET4xx during explicit continuation keeps APPLYING/readback, never REVIEW. Neither
403 nor409 proves prior adoption absent. Existing Native and unattempted routing
behavior is unchanged. Covered disabled send after failure and refresh, zero new
model/adoption writes.
