# Prototype alignment package 03 — continuous business delivery

Authority: user's 2026-11-03 instruction to complete package 02 and continue
package 03 in dependency order, handling ordinary implementation autonomously.
Depends on the shared workspace changes in package 02 on the current branch.
No reopening of closed 323, no change to 324 business grants, no merge/release.

## G1 implementation plan: exact planning entry and recovery

Current PlanningEntry retains the old PlanningInput when the URL's problem
changes. A failed new read can leave generation enabled against a mismatched
visible target. Fix the view's ownership binding before continuing business
orchestration. Scope: PlanningEntry and focused browser regression tests, using
existing planning-input GET and existing planning invocation POST. No endpoint,
state, persistence, model admission, budget, execution or contract change.

Bind read state to the exact problem parameter, hide obsolete target content,
disable generation while loading/unavailable, permit explicit GET recovery,
show the returned confirmed goal and source, and keep refresh read-only. Reject
an empty problem before issuing a request. Keep all invocation recovery under
PlanningDialogue's existing opaque request identity and admission boundaries.
Test delayed reads, failed reads, explicit GET recovery, problem switching,
source return, input persistence, reload and absence of mutations.

## Remaining sequence

1. Exact target entry and existing source/plan/resource/result readbacks.
2. P04 save/activate/enter-planning orchestration, with separately durable steps,
   fail-stop and unknown recovery. This batch does not claim that orchestration.
3. Continue the original case only after valid scoped identity and actual object
   readback; original supplier-delivery standards and resource versions are preserved.
   The old cost 4-stage/6-task plan is regression only, not this case's Plan.
4. Resource preparation, independent execution grant, traceable run, evaluation
   against the original standards and human business acceptance.

Current absence of a live session blocks only real-case validation, not the
frontend correctness fix or controlled verification. No repeated unknown calls,
new provider costs, fabricated identity or fixture-as-real completion.


## Engineering checkpoint and corrected case binding

The entry ownership fix and its generation/continuation guards are implemented.
Three new browser cases pass, including unavailable read recovery without POST,
same-page target switches with delayed replies, and missing problem context.
Shared and existing history/admission/criteria tests remain part of the evidence.

Further inspection of the complete 324 handoff corrects the package-01 script:
that script incorrectly promoted the old cost regression into the business
acceptance mainline. The 2026-09-22 handoff records supplier-delivery problem
5fe6a7c9-3f92-5a09-bd91-bf3380109087 and six original standards, with planning
invocation f078a876-eef8-4cb5-ae69-83bf6cfccd42 OUTCOME_UNKNOWN and no same-case
Plan. Its single incremental call was used. These are historical code-handoff
facts, not a current live-state certification. A valid scoped session must first
read back the current problem/request. If it remains unknown, supplier-verifiable
result/usage and formal recovery basis are required; login alone cannot permit
retry or create a new allowance. Do not substitute the cost Plan or fixture.

Full save/activate/planning orchestration and real business acceptance remain
open; this checkpoint is not completion of package 03. Existing 323/324 sessions,
grants, UNKNOWN records and budget reservations are unchanged.
