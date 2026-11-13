# G1: Direct task-entry historical READ preparation

Confirmed: /tasks only prepares test resources, while the original conversation
explicitly invokes its existing history-access owner. A naturally expired exact
EXECUTION READ therefore hides a known historical task until that conversation
is reopened. Collection LIST is not authority to restore individual execution.

Add a POST-only current-work/history-access adapter to the existing history
installer. It authenticates the current user and CSRF, selects at most 20 owned,
unarchived same-domain conversations with a saved execution and problem link,
and invokes the unchanged history prepare owner under its generation barrier.
Each candidate has its own transaction and all current source/ancestry/prior
READ/denial/revocation checks. No GET writes, new grants without prior READ,
START/USE restoration, model calls, new infrastructure or schema migration.
A bounded selection returns hasMore, partial and an owned-conversation cursor.
A subsequent POST resolves that cursor only in the same current owner/domain and
uses stable (created_at, conversation_id) pagination; no arbitrary target is
accepted. The task page offers continuation to older records without requiring
a conversation visit. candidate failures remain
partial, never a claim of full history restoration. Concurrent calls reuse the
existing per-target history locks and owner idempotency. No raw target or
exception detail is returned.

Frontend: first directory entry and explicit refresh run this POST before the
existing GET; filters/pagination/10-second polling remain GET-only. A failed or
partial preparation does not hide existing readable tasks, but shows an explicit
partial-history notice. Identity is verified before/after preparation and the
existing GET still validates all per-row permissions. Fixed-work placeholder
and details are unchanged.

Validation: isolated PostgreSQL current history owner reuse, selection bounds,
owner/domain/archive exclusion, repeated/concurrent calls and deny/revoke;
controlled browser verifies initial POST then GET, refresh, partial/error, and
no polling writes. Real runtime/model/permissions remain root-only.
