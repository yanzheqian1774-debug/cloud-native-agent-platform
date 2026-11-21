# Fixed-cycle ordinary followup — G1 successor

Default-off through the already mounted fixed-chat policy. Preserve the frozen
15-file baseline as a separate patch. This slice adds no model call, table,
execution command, ANSWER delegation, or change to a BOUND goal.

POST activity/focus verifies current account, owned non-archived conversation,
BOUND/event/receipt/preparation/run and exact READ using original owners. It
stores a server-created immutable focus link in the existing links table under
conversation CAS and the original request-key replay rules. Client supplies only
identity and expectedConversationVersion/commandId, never result content or a
proof. Existing message focusLinkId points at that link. The ordinary public link
schema does not accept this new internal target.

A stored focus pins a bounded observation: exact artifact digests and the precise
READ set used, progress version/state, event time and source. The original C1
reader consumes that saved message's focus, rechecks current BOUND/receipt and all
pinned READs, and includes only the bounded actual result contents. No current
question/answer token is invented. Subsequent event observations require another
explicit focus. New outputs do not silently rewrite an old model input.

Retained assistant facts carry the fixed focus basis. Display and previous-answer
reuse recheck the same basis before exposing derived content; missing owner or
revoked source READ fails closed. Ordinary chats remain unchanged. This slice
never opens PLAN/START or makes a new independent goal slot; those remain separate.

Validation: strict input identity and digest negatives, same-key CAS replay with
no new link/message/model, wrong message author/focus, artifact digest change,
current READ revocation, history/previous answer denial, old ordinary paths.
Use dedicated 53429 random fixtures if needed; no actual environment.

## Implemented contract and validation boundary

Opt-in FIXED_CHAT_FOLLOWUP_ENABLED=1 plus mounted exact private read policy;
capabilities.fixedWorkFollowup is otherwise false. POST focus accepts the six
exact identity fields, expectedConversationVersion and commandId. Success and GET
focus?commandId=... return RECORDED with identity/focusLinkId/focusDigest and
contentComplete/excerptedArtifactCount. Missing GET is NOT_RECORDED only; an
ambiguous sent POST is not resubmitted automatically. POST replay rechecks rights
before returning the same link. Existing links table is append-only through these
owner paths; no new database immutable-trigger guarantee is claimed.

Each artifact contributes at most 2,000 characters, total excerpts at most 12,000
characters. Inputs explicitly mark every truncated artifact and total completeness;
they do not assert exhaustive review. Larger payload still fails the 24,000-character
projection bound. Original provider byte/token ceilings remain authoritative.
Visible link projection exposes only verified identity and coverage, not internal
grant/artifact proof. Unreadable links expose no retained title/coverage.

Evidence: focus-pg-r4.log, one isolated original-owner BFF chain PASS26.99s. It uses
real session/CSRF/governance and READ issuer, focus/link/message, server relation
reader, replay and formal READ surrender. No model is called: this verifies the
single-C1 input composition, not a real C1 answer. Original provider and BOUND
fixtures remain controlled. Five pure cases pass; the twelve legacy retention
PG tests require the existing guarded64335 endpoint and are deferred until root
releases that fullcheck window. Earlier failed logs are retained (size protection,
wrong nonexistent timestamp column fixed, missing0047 fixture migration fixed).
The focus test imports the separately frozen BFF_TEST_R2 two test files; apply
that dependency before this patch. No frontend is included.
