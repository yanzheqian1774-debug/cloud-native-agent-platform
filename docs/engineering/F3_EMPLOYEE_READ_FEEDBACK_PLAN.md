# Employee read feedback and bounded waiting

G1 frontend-only. Existing authoring and resource-directory reads have no timeout,
so version cards, selected version facts and member names can remain loading.
Bound each read sequence to 8 seconds, and collection work to a 20-second batch
plus final identity verification. Keep at most three concurrent authoring reads.
Preserve before/after identity checks and exact parent/digest verification.
No automatic retries, commands, model calls, policy or public API changes.

Provide explicit retry of collection version facts and member-name reads after
failure; selected version retry already exists. Distinguish pending, failed,
withdrawn and authoritative draft NONE. Publication NOT_AVAILABLE remains unknown:
the current API does not distinguish absent publication from denied reads.
Do not invent a NONE publication status or infer current from listed revision order.

Validate stalled reads terminate, retry uses fresh reads without accepting late
responses, expiry/identity withdrawal and existing version/return regressions.
Use one browser session for actual installed checks to respect login throttling.

Retry presentation: after confirming the same principal, a timed-out collection
reread may retain previously verified exact version content under an explicit
stale label. It must not retain a current-publication claim. Explicit denied/not
found responses withdraw previous version facts; identity change/expiry clears
all cached facts. Member-name retry keeps the fixed member link and expanded
version evidence. No automatic retry and no new execution authority.
