# Persisted C2 answer recovery — G1

Base6ec5636; isolated frontend-only implementation. No real browser/session/DB/model
operation or fake sessionStorage restoration. Reuse existing conversation, exact
understanding result, route and adoption GET owners. No backend policy change.

Problem: routing restoration currently starts only from sessionStorage. A saved
CURRENT_QUESTION result whose adoption failed loses its visible continuation when
a browser context closes, even though server message facts and original CLARIFY
journey remain durable.

Plan: after the current understanding-question owner registers, inspect durable
assistant message facts and their exact user message. Require own principal,
SUCCEEDED/DRAFT CURRENT_QUESTION facts with requestKey/userMessageId/invocationId;
read exact saved result, route and adoption by those identifiers. Require one and
only one matching current owner target, no latest/time/title guesses. Existing
adoption already reflected in current journey is not offered again. Ambiguous,
foreign, stale, incomplete or unauthorized records never become actionable.

Discovery is GET only, including refresh/new browser context. Show an explicit
'核对并继续已有回答' action only after exact verification. Recheck route/current
owner again on click and reuse the existing answer/adoption handler: existing
receipt reads back; otherwise same recorded request can be adopted once. Never
call a model from restoration or manufacture a new question/request key.

Tests: empty storage/browser-context closure after adoption failure; retained
adoption before journey write; already applied; other principal; unrelated/stale
question; two exact matching candidates; ambiguous/independent relations; GET
permission failure. Assert no automatic POST/model calls and exact one explicit
continuation. Existing local recovery and normal routing regressions retained.
No styling redesign; existing composer button/status conventions remain.

Journey bootstrap also installs the already-read durable journal before awaiting
source discovery. This preserves the current question owner if the source list is
slow/unavailable. The late list update is applied only if the original in-memory
journal is still current and no answer is in flight; it cannot replace a newer
adoption/journal. No source-list response creates a server write.
