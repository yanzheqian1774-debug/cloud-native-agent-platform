# General conversation input boundary repair

G1 incident package based on installed 31daadb. No runtime/model operations.

Ordinary source-free messages must be checked against the conversation owner and
exact original user message, not BUSINESS_PROBLEM LIST. A selected source retains
the existing LIST, exact Knowledge READ and immutable content checks. This adds no
business grants. History READ renewal for newly owned conversations requires the
same admitted general context, exact retained source, original subject and prior
READ; denied/revoked grants remain denied. Existing business admission stays exact.

Known input/admission refusal must survive GET recovery. A server-confirmed absent
invocation may not clear a saved refusal and automatically dispatch again.

Verify the real BFF -> private source reader -> admission -> draft owner -> retained
answer -> history owner path with an isolated PostgreSQL ordinary login lacking
business LIST. Provider output is controlled and does not establish model quality.
Negative checks: selected source still denied without LIST; archived/other owner/
wrong message denied; storage failures fail closed; old task journals preserved;
no dispatch on denied input or history readback; exact general lineage required.

## Validation and limits

- 34 targeted tests passed against a newly created isolated PostgreSQL container:
  the actual browser session/CSRF, BFF, source reader, context admission, formal
  exact-grant requests, draft owner, retained answer, refresh and history renewal
  are composed. The ordinary account has no BUSINESS_PROBLEM LIST. Five BFF cases
  cover success and owner/archive/message/selected-source denials. Existing history
  revocation/denial and prior exact admission cases remain covered.
- The model dispatch output and budget implementation in this composition test
  are controlled fixtures. Requestability is test configuration; target validation
  accepts only exact grants derived from stored invocations. No blanket allow
  authorization adapter is used. This does not prove live provider behavior.
- 39 conversation browser tests passed, including saved refusal + absent-invocation
  GET across reload for access denial, unavailable input service and stale source.
  Lint and the production frontend build passed. No visual design changed.
- No policy, model configuration, allowance, runtime, real conversation, or real
  database was changed. Existing failed requests remain saved and are not replayed.
  Deployment and a fresh ordinary-user real-model A/B demonstration remain the
  coordinator's separate acceptance step; C automatic current-task relation
  routing is not included in this repair.
