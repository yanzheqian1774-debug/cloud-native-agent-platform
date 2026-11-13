# G1 — retained maintainer draft READ

Observed: ordinary maintainer capabilities remain valid while exact draft READ derived by the previous successful maintenance command expires after 1800s. GET and receipt GET correctly refuse; repeating a lifecycle command cannot repair this.

Reuse POST /ontology-maintenance/commands with a separate PREPARE_READ facade request (not an ontology lifecycle Action), and GET /commands/{key} for its immutable read receipt. No new endpoint, database, scope or lifecycle state. Authenticate the current maintenance policy/issuer and current generation. Resolve a permitted non-CREATE maintenance action under the existing exact ontology scope or verified creator lineage. Require a prior exact same-subject ontology READ grant; never infer first READ from a prefix, USE or a role. Explicit rejection/revocation blocks renewal.

Under existing logical ontology and command-key locks, read the requested exact revision through its owner, bind current aggregate version and immutable content digest, actor, scope, request bytes, policy digest/generation and original READ grant. Optional expected version/digest must match if supplied. Only READ is issued by the existing grant-request/decision audit owner, bounded by current policy and TTL. No CREATE/REVISE/REVIEW/PUBLISH/USE renewal. Existing successful command and historical receipts remain untouched.

Unknown POST outcome: retain the original persisted key; only GET its receipt, never resend automatically or change revision. Reuse of a key with changed bytes rejects. GET receipt performs current exact READ and original actor/scope checks; it does not require the old policy window and never writes. If expired again, a new explicit preparation is necessary, not replay of the old key.

Frontend: on detail entry, first attempt normal GET. Only an authorization denial with current server maintenance eligibility may prepare retained READ before retrying GET. Same identity/scope is checked before dispatch and after response; business-only account does not POST. No change to frozen four tabs or write controls. Pending preparation is separate from lifecycle command state and preserved on refresh. A refresh may GET the pending receipt but cannot replay POST. Show a bounded read-recovery action if unresolved.

Validation: real isolated PG expired READ renewal; no prior READ, foreign actor/scope/revision, denied/revoked, expired policy/generation, key conflict, digest/version mismatch; new creation actual owner receipt path; lifecycle and execution state unchanged; receipt GET no write. Browser expired maintainer detail loads once, business-only denial no POST, UNKNOWN refresh GET-only, account/selection change cannot apply old result. Actual runtime/configuration/publication remain root-only.

## Isolated verification

2026-11-13: 24 owner/real isolated PostgreSQL + BFF regression cases passed in 59.42s (includes existing lifecycle compatibility); 20 browser cases passed in 29.5s (all existing ontology page cases plus renewal, second expiry, business-reader denial, UNKNOWN GET-only and identity switch). Browser run rebuilt production frontend successfully. Changed frontend lint, Ruff and diff checks passed. Session for the BFF route test is a controlled SessionStub; grants, requests/decisions, owner rows and receipt persistence are real isolated PG. This is not deployed ordinary-account evidence.

First iterations corrected test fixture imports and an assertion referencing a nonexistent request-key column; production scope was not widened to satisfy tests. Root requested patch delivery without starting another full hook; coordinator performs the integrated full hook and real runtime verification.
