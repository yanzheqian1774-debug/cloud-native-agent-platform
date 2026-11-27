"""Server-only C1 question context, bound to an immutable explicit presentation."""

from .conversation_relation_context import sealed_snapshot
from .fixed_question_facts import require


def snapshot(presentation_id, identity, question, message_id):
    target = dict(
        kind="NATIVE",
        invocationId=identity.invocationId,
        questionKey=identity.questionKey,
        questionDigest=identity.questionDigest,
        executionDigest=identity.preparationDigest,
        runId=identity.runId,
        taskId=identity.taskId,
        attemptId=identity.attemptId,
        expiresAt=question["expiresAt"],
        delegationPresentationId=presentation_id,
        questionIdentityDigest=identity.digest,
    )
    current = dict(
        goal="回答当前固定工作明确提出的必要问题",
        scope="仅回答已呈现的问题, 不改变固定工作目标或安排",
        stage="FIXED_CYCLE_QUESTION",
        currentQuestion=question["question"],
        currentQuestionType="NATIVE",
    )
    if question.get("answerContract") is not None:
        current["answerContract"] = question["answerContract"]
    return sealed_snapshot(identity.conversationId, message_id, target, current)


def from_presentation(presentation, message_id):
    result = snapshot(
        presentation.presentationId,
        presentation.identity,
        presentation.question,
        message_id,
    )
    require(result["currentQuestionToken"] == presentation.currentQuestionToken)
    return result
