# G1 — original planning preparation continuation

A question-input service authentication failure precedes planning invocation.
Current read-only planning endpoint only reads UNKNOWN/INVALID calls; its 404 is
not proof of absence. Never clear pending on that 404, replay UNKNOWN, change key,
or repeat understanding. Existing /requests recovery reads can settle/adapt and
must not be used for this observation.

Add a default-off (same owned-business policy) exact current-conversation GET.
Verify original subject, source, journal PLAN/pending planning, problem version,
current Problem READ and PLAN PREPARE. Original invocation table and exact
planning_call_preparations (durable key/context binding) must both be absent,
with no recovery binding for the key, before NOT_STARTED. Any retained record
returns RECORDED and never permits new input submission. Missing permission,
partial access, unavailable storage, or changed journal is not absence.

Preflight only checks target/PLAN PREPARE and returns dispatch_count=0; no
preparation or budget owner is written. begin persists preparation, then invocation
claim before budget reserve/model-use/provider. Thus absence of both owner
records excludes those later effects under the existing transaction contracts.

Existing recovery panel rechecks GET on explicit click, then parent verifies
journal/version/key/source and keeps durable pending before running the same
shared PLAN function. No mount/refresh POST; no new model key. Existing owner
idempotency and current authorization protect concurrent tabs. Existing UNKNOWN
recovery remains independent. No migration, permission expansion, real writes.
