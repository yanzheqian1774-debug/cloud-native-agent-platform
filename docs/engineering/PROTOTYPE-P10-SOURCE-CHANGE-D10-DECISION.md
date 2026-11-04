# D10 — Formal source change under existing planning/resource owners

Status: ACCEPTED by explicit user decision on 2026-11-04: “批准D10，继续实施”. Implementation/validation remain separate; approval alone dispatches nothing.

Authority: user instruction to complete P08/P10 and package03, and advance the
package04 grouped resource/configuration capabilities. Ordinary dev/test grants
remain preauthorized. This decision concerns a new persisted source-change
provenance, not routine grant issuance or a new model allowance.

## Current boundary and requested change

Current ProposalRevision admits governed model invocations and the specifically
approved synthetic/execution successors. The P10 composer can request a new model
suggestion, but it is not an immutable, exact old/new-source change request and
cannot safely replace the source/mapping on an already approved/executed plan.
Adding that source-change object and non-model proposal provenance is a persisted
contract/state semantic addition. AGENTS.md and ARCHITECTURE_GATES.md require a
human decision for frozen Contract or State architecture changes.

Approve this concrete additive mechanism:

1. Existing planning owner records an immutable source-change request in existing
   PostgreSQL (additive migration, no new database/service). Bind tenant/domain,
   current principal, exact problem and criteria, predecessor proposal/Plan
   revision/digest, old/new exact published Knowledge references and content
   digests, explanation, compatibility/impact evidence and actor-scoped request
   key. Idempotency and current-head checks are transactional. Failed/stale reads
   stop without changing the approved plan or source.
2. Reuse the existing source owner for publication/content/schema checks and
   exact per-source READ authorization. P08 discovery conveys only currently
   readable published versions, never authorization or execution readiness.
   Compatibility means a declared supported source schema/executor contract,
   not inferred natural-language equivalence or proof that a connector ran.
3. Prepare an append-only successor suggestion with explicit source-change
   provenance. Add optional versioned provenance only on new records; old
   serialization/digests and all original proposal/Plan/Run/artifact/UNKNOWN
   facts retain their exact identities. Never pretend this is a model reply.
4. The successor displays old/new source, unchanged/affected fields and guards.
   It preserves business rules, tasks, dependencies and original history. It
   replaces exact source references only, withdraws obsolete mapping commitments
   and returns to planning-only boundaries. Existing Plan approval is a separate
   explicit operation; neither preparing, confirming, reading nor reloading a
   change starts a Run or consumes model budget. Discard leaves the old Plan.
5. Changed source content cannot silently inherit content-bound criteria. Show
   criterion impacts and block confirmable source replacement until the existing
   criteria owner has saved/confirmed a suitable new criterion/set revision and
   the exact current target is selected. Identical content with a different
   published source identity/version may retain the same content-bound criteria.
   No automated relaxation or rewriting of old standards.
6. Subsequent execution still requires fresh source-bound resource assembly,
   execution revision confirmation and independent exact grants/admission under
   existing owners. Old source/Skill/Task authority cannot be borrowed. D9/D8
   remain independently scoped; original aggregate100 calls/USD50 including all
   reservations remains, no provider/call/timeout/settlement/lifecycle bypass.

## Affected components and compatibility

Planning DTO/proposal provenance and same-owner repository/BFF; source owner
compatibility readback; P08/P10 frontend and tests. Additive storage on existing
PostgreSQL only. No CRD/API-group/authentication/tenant/runtime/Fleet change. Old
API/records remain valid, old replay identities remain unchanged. No mutable
source pointer or second planning/execution authority.

## Alternatives and recommendation

A. Continue conversational model replanning only: compatible, but cannot satisfy
   formal P10 source-change audit, exact version review or model-free preparation.
B. Mutate the current Plan/source or label a hand-built model reply: rejected;
   loses approval lineage, provenance and original results.
C. Above explicit source-change successor under the existing owner: recommended.

## Concrete development acceptance

Prepare/read/refresh/relogin/discard create no model invocation or Run. Authorized
same-content new published source yields one immutable request/successor, exact
old/new comparison and separate confirmation; original supplier and sales Runs
retain artifacts/evaluation/Human decisions. Test denial, cross-scope refs,
unpublished/disabled/corrupt sources, changed schema, criteria content mismatch,
newer head, concurrent submit, idempotency conflict, lost response/GET recovery,
new input retention and revoked permissions. Explicitly test changed-content
criteria conflict; do not count it as successful replacement. Capture P08/P10
original vs actual plus keyboard, narrow, error and denied states. Then regress
both existing actual cases read-only; new execution tests use isolated runs only.
