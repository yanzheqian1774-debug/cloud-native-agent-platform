# F3 task attribution — G1 implementation plan

Base: e6f0a3e. Isolated worktree only; no runtime, database, publication or model operations.

## Problem and implementation boundary

The directory labels the unique prepared-start command actor as the requester.
This is not the original user when another authorized operator starts a run.
Keep canonical commands, immutable Problem revisions, assignments and audit intact.
This is an internal read projection correction, not execution or authorization.
No public CRD, frozen Contract, persistence table or permission policy changes.

1. Extend the existing single-statement internal snapshot with bounded original
   Problem/context/invocation/message metadata, excluding message text.
2. Verify the existing exact source chain, following the integrity predicates in
   `native_confirmed_scope._context_start`: unique context, matching tenant/domain,
   subject, context, successful DRAFT_READY and exact Problem identity/revision/digest,
   real original user message and readable owner-scoped conversation. UI journeys
   and generic links alone never establish the requester.
3. Preserve `initiatorId` as the compatible legacy start-actor field; add separate
   original requester, started-by actors and attribution classification. The
   participant/plan snapshot still represents the digital-worker assignee.
4. Apply the same attribution scope predicate before expensive evidence projection
   and during count/page projection. Rotate cursor route identity for changed
   semantics. Keep the frozen prototype scope selector unchanged.
5. Direct-start records with neither context binding nor a conversation origin
   retain their original unique-start-actor
   membership in `initiated`, visibly labelled as historical start records rather
   than verified user questions. A present but unverified binding never falls back
   to a guessed requester. Such records remain in authorized `visible` scope. Describe direct-start provenance in source detail,
   not as an internal migration label in the selector.
6. Keep the F3 table layout. Remove human actors from the assignee column, show
   verified question source or clearly marked historical start source under source,
   and fold start-operation identities into source audit detail. Never claim a
   delegation authorization merely because the two identities differ.

## Authorization and compatibility

Existing LIST, EXECUTION READ and Problem READ run before attribution exposure.
Conversation metadata retains ordinary-owner / verified-development-admin access.
Attribution cannot grant access, start work, renew grants or spend budget. Failed,
ambiguous, absent or unreadable source cannot fabricate a user. Existing start
records remain queryable in the visible scope; no source rows are rewritten.
Additive internal response
fields do not repurpose `initiatorId`. Existing cursors fail normally after semantic
version rotation; new requests restart pagination. No model-recovery files change.

## Validation and delivery

Target tests cover A asks/B starts, repeated/multiple start actors, exact version
mismatch, ambiguous/missing context, wrong author, foreign/private owner, malformed
or failed source, legacy compatibility and identical scope/count/pagination rules.
Run existing current-work tests and frontend lint/build. Browser fixture evidence
at 1440px proves labels/layout/filter dispatch without claiming actual backend or
permission acceptance. Parent integrates and performs real authorized read checks.
No repeated execution to manufacture evidence. Report any missing production proof.

## Implemented validation and remaining acceptance

Backend current-work suite: 80 passed. Frontend directory browser suite: 14 passed;
the attribution case is additionally repeated after completing its metric fixture.
Frontend lint/build passed. Browser fixtures include 1440px and 390px screenshots,
visible/initiated scopes, reload and detail-return focus, with zero mutating requests.
Frozen F3 `#design-picker=tasks` was rendered locally at 1440x900 for comparison.
The five-column hierarchy is preserved; source attribution is separate from worker
assignment and start identities are collapsed. No new scope options were added.

These are isolated tests. New snapshot SQL has not been executed against the live
PostgreSQL service; actual schema/query behavior and existing ordinary-account
records must be checked by the integrating coordinator before acceptance. No actual
model, publication, recovery or execution operation was performed here. Existing
schema migrations for context admission and draft invocations are required; this
change adds no migration or table. Context-bearing historical records without a
verifiable original message remain unknown, not silently treated as direct starts.
The broader original-conversation origin/journey heuristic is unchanged and is not
promoted to immutable requester proof.
