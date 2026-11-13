# Existing expired-input recovery: read-only findings

No actual Run, question, attempt, permission or model was changed by this audit.
The reported task is UNKNOWN and its Run RECOVERY_REQUIRED. A loop STOPPED /
NATIVE_INPUT_EXPIRED record is not permission to overwrite the owner outcome.

Existing owner route:
POST /api/workbench/v1/prepared-executions/{digest}/retry
body: taskId, expectedAttemptOrdinal, idempotencyKey.
The BFF and prepared control owner require exact EXECUTION RETRY; the control
journal binds original preparation digest, actor, action and payload, and the
same key reads the existing command result. The coordinator additionally
requires original EXECUTION START, exact participant START and independent
SKILL INVOKE_SKILL for the next ordinal. PreparedExecutionGrantTargets can
recognize the ordinal only up to the frozen participant.max_attempts.

This route is NOT presently a valid recovery path for the reported Run:
1. prepared_execution_observations maps Native RECOVERY_REQUIRED to UNKNOWN.
2. execution_preparation RETRY requires RETRY_WAIT and expressly rejects a Run
   in RECOVERY_REQUIRED; there is no exposed UNKNOWN-to-retry adjudication owner.
3. readonly_instance_assembly fixes max_attempts=1. The existing frozen
   preparation cannot admit ordinal2; editing this changes its digest.
4. execution_grants supplies only ordinal1 invocation admission, no RETRY grant.
5. PreparedExecutionPanel shows retry only for RETRY_WAIT; the original
   ConversationJourney passes readOnly=true. Its existing buttons cannot be
   enabled by clearing journal flags or faking a task state.
6. readonly_continuation_worker only admits PENDING/RUNNING receipts with the
   exact current policy digest, root/source/subject/agent and unexpired work.
   A generic key change or model allowance does not satisfy those boundaries.

Safe current operations: read original execution, Native progress/questions,
records/attempt/dispatch outcomes, usage and existing artifacts; preserve all
old UNKNOWN reservations and expired input. Do not submit an answer to the old
question, replay the old invocation, modify max_attempts or make a new Plan to
bypass the failed original work.

Required design before further execution: a distinct evidence-backed recovery
owner must bind the same root/conversation/Plan and exact original attempt,
retain the old UNKNOWN and frozen preparation, record independent limited
successor authority and budget/expiry, and specify how that successor coexists
with the max_attempts=1 contract. Either an existing accepted architecture
explicitly covers this additive recovery, or lifecycle/contract changes require
G2 review. Merely adding attempt2 grants cannot solve the three hard barriers.
No such new recovery owner has been implemented or claimed to exist here.
