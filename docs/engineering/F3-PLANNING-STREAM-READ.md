# F3 planning progress exact READ repair

G1 bounded owner-admission correction. After validated same-context problem creation,
request PLAN READ for only plan:prepared:<created problem> through the existing
request/decision/audit path. No wildcard, provider change, replay, settlement, or
UNKNOWN mutation. Reinvoking after with the original create receipt can add this
missing grant without creating the problem again; revoked grants remain revoked.

Validation: persisted exact grants, idempotent after-only backfill, real browser
session and CSRF through BFF SSE with matching/missing/other/revoked READ. The
stream action is controlled offline; no external model is called.
