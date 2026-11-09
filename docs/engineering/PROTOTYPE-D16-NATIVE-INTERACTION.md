# D16 Native interaction and document tools (G1 implementation plan)

User authorizes Native clarification in the original conversation, live observable
steps, non-tabular adapters and independent OpenClaw continuation.

Implement task-internal interaction without changing any Task/Workflow/CRD state.
An admitted RUNNING Skill may await an answer within its existing 480-second
supervised dispatch deadline (each question at most 180 seconds). Store the
question and answer under the existing Skill invocation journal, with exact Run,
Attempt, principal, question digest and expiration. Current authorization is
checked on reads, answers and every subsequent effect. Replays/conflicting answers
fail closed; uncertain effects are never restarted. Expiration preserves records;
long-duration suspended-task recovery remains outside this stage.

Extend the existing prepared-execution BFF with scoped progress and answer
operations. Read observable structured actions and tool outputs, never hidden
reasoning or credentials. The original conversation polls this owner projection,
shows pending questions, records replies, and continues the already running task.
Reload may read a pending question but cannot redispatch it.

Add a distinct document-review executor and source family, reusing current
Knowledge, Skill, employee assembly and Native model budget owners. Tools list,
read and search Markdown documents, compare a submitted document's sections with
an explicitly chosen policy, and produce cited completeness findings. An ambiguous
policy scope requires user clarification; missing sections are not evidence of
unsafe deployment or proof of a business resolution. No arbitrary filesystem
access, external writes, new database, lifecycle or authorization architecture.

Validate journal conflicts, wrong principal/Run/question, timeout/cancellation,
no duplicate model dispatch, live reads before completion, and exact citations.
Run isolated owner and browser checks plus normal repository checks. Real-model
acceptance uses a non-table handover document and the user's in-conversation
scope answer, then shows subsequent policy-dependent tools and returned report.
Keep OpenClaw checkout, budget and live platform processes isolated.
