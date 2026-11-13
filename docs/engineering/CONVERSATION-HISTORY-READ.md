# Retained conversation reply access

Status: candidate; actual account and prototype acceptance still required.

An original conversation may outlive its model-call grant. The selected experience
policy can explicitly enable `historyReadEnabled` to renew previously granted,
exact READ access when its authenticated owner returns to the same conversation.
The current test business window is independent of each eight-hour read lease.
Actual revocation, rejection, disabled accounts, changed identity and expired
business eligibility remain restrictive. The model budget is never reserved or
settled by this operation.

The frontend uses a CSRF-protected POST before reading the original conversation
only when the authenticated capability advertises this policy. GET and owner
`can_read` remain read-only. A transaction locks the conversation and exact target;
refreshes recover current access without creating another grant. Prior call,
cancel and execution permissions are not renewed. Original messages, sources,
ordering, identities and timestamps are not edited.

The history decision has its own policy digest. Enabling history reads preserves
the existing execution-policy digest and therefore does not invalidate admitted
questions or planning contexts. Issuance uses the existing request, decision,
grant and audit owner; there is no new permission store or public CRD.

Current automatic renewal covers retained DRAFT invocation sources belonging to
the exact conversation owner with a prior READ grant. Other source types retain
their existing authorization checks; planning/resource history renewal needs
separate source-bound validation before claiming full coverage. Historical UNKNOWN
records can be viewed when authorized but must never be replayed.

The page distinguishes temporary recovery failure from restricted access and
retains unsent input. Isolated tests cover concurrent refresh, repeated lease
expiry, disabled accounts, source substitution, explicit read revocation,
CSRF/method/body restrictions, unchanged messages and zero provider reservations.
Browser checks cover assistant identity/time/source details, input retention,
refresh, temporary read failure and revoked access. These do not replace actual
ordinary-account verification or demonstrate a model/execution round trip.
