# G1: bound confirmed scope to the current problem context

Approved task: avoid historical conversation goals making a new problem's scope
ambiguous. No new module, endpoint, authority or model call.

Read the exact execution problem link owned by the initiating user. Resolve its
BUSINESS_PROBLEM context object and successful DRAFT_READY invocation, then verify
the admission's subject, scope, context and conversation. Use its immutable first
user message as the inclusive sequence lower bound; keep the existing link-created
upper time bound. Never use mutable journey state, a guessed last sentence or a
fixed environment. Cross-conversation/message/principal mismatches return no scope.

Keep the existing 32-message/32768-character limits within the verified context.
Within-current-context conflicting or uncertain instructions still require a question.
Legacy records without context lineage may inherit scope only when exactly one
original user message exists before the link; multiple messages are not assumed
one task merely because the count is small. Existing single-message legacy evidence
is preserved. No historical message or saved evidence is rewritten.

Tests use isolated PostgreSQL and cover historical ambiguity/current explicit scope,
current reversal, current ambiguity, missing/mismatched lineage, another conversation,
message count bounds, legacy multi-message refusal and source preservation. Runtime
continues comparing exact captured evidence during execution. Current live executions
and private configuration are outside this patch.
