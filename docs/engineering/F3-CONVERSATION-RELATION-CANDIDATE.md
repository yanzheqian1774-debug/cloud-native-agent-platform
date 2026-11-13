C: Single-composer automatic relation routing — isolated candidate, NOT enabled
2026-11-13. No runtime/database/model operations. Existing published r5 unchanged.

Verified current gaps
- PrivateConversation.send starts understanding only without focused work/links.
- ConversationJourney.answer mutates the active journal to UNDERSTAND. Reusing it
  for unrelated questions would replace active task state and is prohibited.
- Planning clarification goes directly to answerPlanning. Native input goes to
  native-answers with invocationId/questionKey/questionDigest. Neither has a
  semantic relation classifier before accepting an arbitrary user message.
- r5 strict schema returns intent ANSWER/TASK and result kind. It has no relation
  to the pending owner question. DRAFT_READY cannot safely mean a current-question
  answer: it may instead represent a new task. Keyword inference is insufficient.

Minimal immutable policy successor (proposed name, not registered)
- Preserve v3-execution instruction/schema bytes and historic validation.
- New adapter revision v3-relation extends existing understanding result with:
  relation: INDEPENDENT | CURRENT_QUESTION | CURRENT_WORK | AMBIGUOUS
  currentQuestionToken: null or the single server-supplied opaque token
- Add result kind CURRENT_QUESTION_ANSWER. It is valid only with CURRENT_QUESTION,
  a current matching token, no generated answer/draft/dataNeeds, and intent TASK.
  Submit the ORIGINAL user message to the original owner, never model-rewritten text.
- INDEPENDENT uses existing DIRECT_ANSWER / NEEDS_* / DRAFT_READY rules. DRAFT_READY
  does not create or replace work while a current task is active; it yields a new
  task proposal with an explicit business confirmation, not an implicit reset.
- CURRENT_WORK is for questions about or changes to the existing work, not answering
  an unrelated pending question. History-only/no-rerun remains ANSWER. Work changes
  use existing review/confirmation; do not submit them as clarification answers.
- AMBIGUOUS requires NEEDS_CLARIFICATION and asks the single necessary business
  question inline. The original task question and UNKNOWN remain untouched.
- Non-CURRENT_QUESTION responses require currentQuestionToken=null. Reject all
  inconsistent combinations rather than interpreting their prose.

Authoritative minimal context (server assembled)
- Authenticate and verify exact owned original user message first.
- Resolve the current active work from durable exact conversation/problem links and
  the existing journal, then read current owner records under their existing READ
  grants. A client-side cached state is not the target authority.
- Include only confirmed goal, applicable scope/constraints, current stage, and the
  current unresolved owner question text. No entire source document, resource list,
  credentials, hidden record, prior unrelated task, or internal permission labels.
- Server keeps an exact mapping from currentQuestionToken to owner + problem/run +
  invocation + question key/digest + current revision + original subject/conversation.
  The model selects a token but cannot manufacture authority or new owner targets.
- If a current owner cannot be read, do not assume no task/question. Do not dispatch
  an empty-context router that might misclassify a brief answer. Keep input and state
  and report the narrow read failure without automatic retry.

One input, one understanding call
- Keep the existing F3 single fixed composer. No new switch or folded input.
- A server-backed per-message understanding request records its route independently
  of the active journey. Existing conversation response facts/understanding-results
  supply answer readback; no replacement of main task journal for ordinary answers.
- The same understanding call classifies relation and produces DIRECT_ANSWER when
  appropriate; do not add a second routing model call or a model progress call.
- When CURRENT_QUESTION_ANSWER returns, re-read the exact current owner tuple and
  verify current state/expiry/subject/scope, then submit the original message once
  using the owner's existing idempotency/CAS and authorization. If the question
  changed or expired, preserve the old route and ask for the current question;
  never retarget the answer to the newest question or automatically rerun a model.
- Failed/UNKNOWN router calls retain the exact key and budget reservation. Refresh
  performs GET only. A successful direct answer leaves old work and UNKNOWN intact.
- Route consumption needs durable exactly-once proof binding understanding invocation
  + exact original message to the existing owner answer receipt. Reuse existing owner
  idempotency keys and conversation facts; do not introduce a second ledger. If the
  existing facts schema cannot express this atomic boundary, add an owner-local
  append-only record/migration with explicit review, not browser localStorage alone.

Existing reusable governance
- DraftPolicy registry and draft_assistance_policy strict validators; no r5 mutation.
- Existing model_governance_postgres immutable revision/validation/publication path.
- Existing profile/provider binding and provider_profile_pricing shared-root pricing.
- Existing context_call admission/account/source validation, allowanceId and ledger.
- Existing conversation retention/understanding-results exact message+request key.
- Planning and Native owner answer ports with their current exact version/CAS checks.
- Candidate package must include policy/model/profile/pricing digests, actual free
  model revision number, predecessor published r5, unchanged allowance+expiry proof,
  tests, and NEEDS_HUMAN_REVIEW. No human review fact is generated by this design.

Minimum acceptance matrix
1. Active Native question + hello -> direct answer; original question/run unchanged.
2. Active planning question + unrelated knowledge -> direct; plan/goal/journal unchanged.
3. Old planning UNKNOWN + unrelated question -> direct; UNKNOWN/reservation untouched.
4. Clear answer to exact current Native question -> same question owner once.
5. Clear planning clarification -> same problem/invocation/version once.
6. Ambiguous short reply -> inline clarification; no task answer or new task.
7. Current question expires/changes during model call -> no stale or retargeted answer.
8. New task request while active -> explicit proposal; no old goal replacement.
9. View old result/do not rerun -> no execution; only authorized available evidence.
10. Denied/archived/cross-user/cross-chat target -> deny without existence disclosure.
11. Router stream disconnect/UNKNOWN/reload -> GET only, no duplicate calls or answers.
12. Prompt text in source/old answer tries to change relation -> treated as data.

Delivery ordering
A/B d25d57c admits new owned conversations and fixes refusal/progress presentation.
C remains unaccepted. Next: review this G1 design, implement isolated successor and
exact route binding/validator tests; prepare full concrete review package. Publish
only via the existing approved governance path. Real model + original-task
preservation acceptance remains root's separate controlled runtime verification.

## Integration findings (not yet accepted)

The isolated frontend foundation includes 0354d1d and the ordinary input
boundary fix 26487b7, plus d4d78c7 current-work direct-answer handling. The
candidate explicitly requires scopeMode=EXISTING_BUSINESS_WORK. Both server
and fixed-input integration exclude initial UNDERSTAND/CLARIFY. This stage
preserves the original input route there rather than dispatching twice.

Three real isolated PostgreSQL/BFF cases passed in 38.74 seconds after Docker
recovery: existing formal work plus unrelated answer, exact account capability,
and retained-record profile selection. They use real sessions, independent
administrator approval, business owner records and exact context linkage, with
controlled model output and budget. Retention and refresh are exercised; the
original journal remains unchanged; one allowance/ledger remains. Renewal is
rejected with the matching relation service absent, then succeeds with that exact
configured service. No real model acceptance is claimed. The interrupted earlier
PG setup and the obsolete-port retry did not dispatch a test body; their failures
remain recorded in external evidence.

An unresolved boundary is the initial UNDERSTANDING question. Calling the existing
Journey.answer callback after a relation-only model output would call the old
understanding model again. This is not an accepted single-call implementation.
The current candidate is disabled and must not be promoted as completing that
path. A safe single-call adoption would need a full understanding result in the
same structured output plus exact original invocation/context/turn acceptance.
The source then participates in business-problem and planning source lineage;
copying fields, replacing a context, or simply exempting a general context from
business authorization is not acceptable. Native and planning question handoff
retain their own owner checks; neither authorizes this additional bridge.

Another compatibility requirement is that history READ renewal chooses the
explicitly configured policy matching the retained invocation context. A new
relation-profile record must never be interpreted under the current default r5
profile. The added selector is restricted to the configured original and relation
services and preserves original-principal, exact-source and prior-READ checks.
All configurations remain candidates; original budgets, expiry and UNKNOWN state
remain unchanged.

## C1 current validation and remaining acceptance

- Six isolated PostgreSQL/BFF cases passed (43.57 s): formal work unchanged,
  exact identity capability, saved-profile readback, history renewal, archive,
  missing link and stale problem rejection before controlled model dispatch.
- Twenty-three pure policy/token/stage-gate tests passed. Legacy r5 is unchanged.
- Combined fixed-input browser run ended with passed last-run status, including
  initial-understanding gate and exact planning callback with saved-message reuse.
  These browser routes are controlled fixtures, not a real provider/owner journey.
- Current frontend lint passed with one existing callback dependency warning;
  current build passed. Full package hook is still pending at this writing.
- Exact offline configuration is in external evidence
  `f3-understanding-parallel-20261113/relation-intent-candidate-r1`.
  It is not registered or approved. Sequence 4 was reported free by the coordinator;
  it must be checked again before formal registration. No model review fact exists.

Before runtime enablement, verify actual Native and planning owner handoff with the
new profile, same input/one understanding call, stable result reads and original
work/UNKNOWN unchanged. The fixture tests do not prove model semantic quality or
production owner continuation. Before claiming all C complete, implement and test
the initial UNDERSTANDING single-call adoption bridge described above. Neither
an extra mode selector nor a second understanding call satisfies that requirement.
