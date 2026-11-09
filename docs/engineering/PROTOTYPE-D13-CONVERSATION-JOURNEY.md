# D13: same-conversation analysis journey (G1 implementation plan)

User authorization: sending a short question starts understanding, necessary
business clarification, read-only execution and inline results. No separate
business entry or resource approval clicks. Acceptance utterance:
“帮我分析一下最近的销售情况，看看哪里出了问题”.

Scope: Console conversation composition over existing draft, business problem,
planning, resource preparation and Native execution owners. Preserve original
records and all unknown outcomes. No new infrastructure, CRD, lifecycle or
frozen public contract. Internal additive APIs and conversation UI projection.

Implementation:
1. Persist a versioned journey projection inside the existing conversation DB;
   ownership, CSRF, optimistic concurrency, durable operation keys and explicit
   pending states prevent duplicate dispatch on refresh or multiple tabs.
2. Discover current published readable source versions. Offer real source/time
   facts for necessary user clarification; do not infer a business context from
   matching words or reuse a historical problem as a new one.
3. Submit real draft understanding, persist clarification and normalized draft;
   create a new formal problem/criteria and use existing planning and Native
   execution owners. Current development role grants access; all budget,
   source/schema, publication, execution and revocation checks remain active.
4. Display progress, useful failure text and actual result/artifacts inline.
   No product route change is required to finish the journey.
5. Recover original owner results before any repeat; unknown is not retryable.

Validation: isolated PostgreSQL ownership/revocation/CAS tests, frontend journey
and refresh/clarification tests, lint/build and normal repository gates. Freeze
and install checked source; fresh normal login browser with exact utterance,
necessary source/time confirmation, actual execution and inline results. Capture
video/screenshots and original owner IDs; independently check report arithmetic.

Risks: existing model budget and static read-only work scopes; implement bounded
role-based admission without expanding original budget silently. Source data is
synthetic and must be labeled. Fresh work only; no historical Run replay.

## Live authorization timing correction
The live current-role decision is issued during authorization. Sample the resolution clock after that decision, preserving strict future/expiry and complete tuple checks. A known MODEL_AUTHORIZATION_INVALID rejection occurs before invocation creation/provider dispatch; permit an explicit same-conversation continuation with the identical request key. Unknown transport outcomes remain non-replayable.
