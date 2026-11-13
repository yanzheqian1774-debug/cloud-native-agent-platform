# F3 fixed-input routing — G1 frontend plan

Isolated base 6e7016b. This package owns PrivateConversation, ConversationAnswer,
NativeLiveProgress, new routing hooks, API types and controlled browser tests.
The understanding agent alone owns Journey and backend routing/model adaptation.
No real model, database, runtime, publication or frozen prototype changes.

The opt-in conversationRelationRouting capability activates one unchanged F3
composer. Save each user message once, invoke the existing governed understanding
API with conversationRouting=true and no client-supplied task or parent context.
The server resolves current work/question context and returns a saved relation.
Independent answers only refresh messages; they never reset the Journey, reload
it, change its pending/UNKNOWN state, or acknowledge its pending question.

Before any current-question answer, read the server's exact route again and match
it to a registered existing owner callback. The callback accepts original text
and the already-saved message ID. Native retains existing exact-question POST;
Journey planning/understanding callbacks are implemented by its sole owner.
Unknown, stale, ambiguous or unsupported routing never guesses a callback or
restarts work. Ambiguous/work-change results remain inline, without manual mode
selectors or hidden entry points. No automatic target changes or cancellation.

Message and model request IDs are scope-bound and retained for read-only recovery.
Refresh reads status only, never automatically invokes a model or owner callback.
After recovering an exact-question result, an explicit continuation may revalidate
that same route; it is not a new mode or new model call. Response-unknown owner
writes are not repeated. Keep the draft during waits and show actual progress.

Tests cover ordinary active planning, execution pending/UNKNOWN, independent reply,
exact question routing, changed target refusal, ambiguity, double-submit, stream
failure, reload recovery, and no feature capability. Assert unchanged primary
journal/run and zero unintended owner writes. Screenshots verify the same F3 dock.
Real activation/configuration and end-to-end services remain the parent integrator's
responsibility; fixtures are not live execution acceptance.

## Integration boundaries

The new capability must be scoped to the admitted identity/profile; an unadmitted
user must retain the legacy owner input rather than receiving a nonfunctional
routing composer. This frontend does not activate or publish a model profile.

Journey owner registration and its saved-message adoption are a separate, single-
writer change. Planning/understanding continuation needs combined integration
verification after that package lands. Native answer acknowledgement can be
recovered by reading the exact invocation/question/digest and saved answer. A
planning/understanding callback with unknown acknowledgement remains unresolved
until its owning journal can establish adoption; it is never automatically replayed.

If the initial message append loses its acknowledgement, this package can recover
the exact saved message but cannot prove that model dispatch never occurred. It
therefore preserves the message and draft without issuing another model request.
This is an explicit remaining recovery gap, not a completed continuation.

Reply positioning is opt-in for the newly saved reply ID only. Existing send and
scroll behavior stays unchanged; user wheel/key/touch or reading away suppresses
reply repositioning. The same F3 layout and CSS are retained.
