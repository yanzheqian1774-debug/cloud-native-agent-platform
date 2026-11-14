# Question preparation observation semantics (G1)

Base bcedac1. The member observer distinguishes READ_UNAVAILABLE/UNVERIFIED from
observed missing operations, but QuestionActivityInput discarded that distinction.
Check observation state before calculating capability gaps. Unreadable or
unverified observation returns a blocked preparation with no planning request,
no TOOL gaps, zero model calls and no execution. Preserve observed genuine
missing-operation semantics. coverageComplete is not an authorization flag (the
current observer deliberately returns false even for usable member declarations).

Both existing planning views explain incomplete reading/verification, keep the
original question, and do not call planning preflight/model when blocked. The
conversation uses its existing planning-start-status readback before explicit
same-key preparation retry; no new retry/dispatch path. Early preparation service
503 is labeled as scheme preparation, preserving prior successful understanding;
this preparation attempt did not call the planning model. Unknown model dispatch
states retain their existing read-only handling. No permissions/grants change.

Validate actual input handler through isolated PG with controlled observer states
READ_UNAVAILABLE, UNVERIFIED, observed missing tools and normal ready; preserve
original service authentication tests. Browser tests cover blocked observation,
503, retained draft and explicit recheck without model calls. Existing F3 markup
and styling stay unchanged. No actual platform changes or model calls.
