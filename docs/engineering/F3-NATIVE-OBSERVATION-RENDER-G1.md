# G1 — stable execution observation rendering

Observed repeated employee/source-review sections while the same execution polls.
PreparedExecutionPanel gives ExecutionSourceReview and ExecutionRuntimeSection
identical sibling keys. Conditional siblings before them make reconciliation
reuse the wrong keyed slot and retain orphan DOM on updates. Give these distinct
stable presentation identities while retaining their existing contextKey and
execution digest, polling schedule, authorizations and command owners.

Reproduce on the unmodified frontend with repeated ordinary readback, then prove
one source-review and runtime section after many updates and tab switches. No
runtime, DB, credentials, models, task state, or authorization changes.

Controlled browser reproduction on unchanged 0d7c318: after 12 readback cycles,
the source-review region count grew to 30 (expected 1). Initial fixture failures
were missing current loader capability/head responses and are not product evidence.
Only sibling React keys change in production; the readKey supplied to each
component, saved open/tab/query state, polling cadence and owners are unchanged.
