"""Explicit v7 successor; no upgrade of a published v6 resource or running job."""

from agent_runtime.native_loop import digest

from .native_document_skill import (
    DURABLE_WAIT_CONFIGURATION,
    NativeDurableDocumentSkillExecutor,
)
from .skill_invocation_domain import ExecutorRevision

TYPED_QUESTION_CONFIGURATION = {
    **DURABLE_WAIT_CONFIGURATION,
    "schemaVersion": "native-document-review.v7",
    "questionContract": "native-question-answer.v1",
    "answerInterpretation": "SINGLE_EXISTING_C1_RESPONSE_EXACT_PERSISTED_REFERENCE",
    "candidateSource": "CURRENT_AUTHORIZED_POLICY_DOCUMENTS_AND_EXACT_RULE_SCOPE",
}


class NativeTypedQuestionDocumentSkillExecutor(NativeDurableDocumentSkillExecutor):
    accepts_typed_questions = True
    revision = ExecutorRevision(
        "native-document-review", "7", digest(TYPED_QUESTION_CONFIGURATION)
    )
