"""Private exact human-actor/service-subject question delegation values."""

from datetime import datetime
from typing import Literal

from agent_runtime.native_loop import digest as native_digest
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .native_wait_types import Digest, Identity
from .plan_suggestion_domain import ExactReference
from .resource_use_domain import canonical_digest


class StrictValue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class QuestionIdentity(StrictValue):
    tenantId: Identity
    securityDomain: Identity
    conversationId: Identity
    bindingDigest: Digest
    work: ExactReference
    eventId: Identity
    receiptDigest: Digest
    preparationDigest: Digest
    runId: Identity
    taskId: Identity
    attemptId: Identity
    commandId: Identity
    invocationId: Identity
    questionKey: Identity
    questionDigest: Digest
    checkpointDigest: Digest
    sourceSnapshot: ExactReference
    executionSubject: str = Field(pattern=r"^service:.{1,190}$")
    serviceCredentialId: Identity
    generation: int = Field(strict=True, gt=0)
    recoveryEpoch: int = Field(strict=True, gt=0)

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))

    @property
    def exact_resource(self):
        return "governed-execution:question:" + self.digest


class QuestionPresentation(StrictValue):
    schemaVersion: Literal["fixed-question-presentation.v1"] = (
        "fixed-question-presentation.v1"
    )
    presentationId: Identity
    identity: QuestionIdentity
    actorId: str = Field(pattern=r"^human:.{1,190}$")
    commandId: Identity
    requestDigest: Digest
    policyDigest: Digest
    issuerId: Identity
    grantRequestId: Identity
    grantDecisionId: Identity
    grantId: Identity
    focusLinkId: Identity
    currentQuestionToken: Digest
    question: dict
    createdAt: datetime
    expiresAt: datetime

    @model_validator(mode="after")
    def consistent(self):
        from .fixed_question_context import snapshot

        q, i = self.question, self.identity
        if (
            self.createdAt.tzinfo is None
            or self.expiresAt.tzinfo is None
            or self.createdAt >= self.expiresAt
            or self.actorId == i.executionSubject
            or native_digest(q) != i.questionDigest
            or q.get("kind") != "NATIVE_QUESTION"
            or q.get("principal") != i.executionSubject
            or q.get("workflowRunId") != i.runId
            or q.get("questionKey") != i.questionKey
        ):
            raise ValueError("FIXED_QUESTION_PRESENTATION_INVALID")
        if self.expiresAt > datetime.fromisoformat(q["expiresAt"]):
            raise ValueError("FIXED_QUESTION_EXPIRY_INVALID")
        if (
            snapshot(self.presentationId, i, q, "")["currentQuestionToken"]
            != self.currentQuestionToken
        ):
            raise ValueError("FIXED_QUESTION_TOKEN_INVALID")
        return self

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))

    def require_checkpoint(self, cp):
        from .authority_contracts import AuthorityError

        i, w = self.identity, cp.identity
        if (
            (
                i.tenantId,
                i.securityDomain,
                i.conversationId,
                i.preparationDigest,
                i.runId,
                i.taskId,
                i.attemptId,
                i.commandId,
                i.invocationId,
                i.executionSubject,
                i.questionKey,
                i.questionDigest,
                i.checkpointDigest,
            )
            != (
                w.namespace,
                w.security_domain,
                w.conversation_id,
                w.preparation_digest,
                w.workflow_run_id,
                w.task_id,
                w.attempt_id,
                w.command_id,
                w.skill_invocation_id,
                w.principal_id,
                cp.question_key,
                cp.question_digest,
                cp.digest,
            )
            or i.sourceSnapshot.digest != cp.source_digest
            or self.expiresAt > cp.human_expires_at
            or self.expiresAt > cp.authority_expires_at
        ):
            raise AuthorityError("NATIVE_WAIT_DELEGATION_BINDING_INVALID")


class DelegatedAnswer(StrictValue):
    kind: Literal["NATIVE_DELEGATED_ANSWER"]
    answer: str = Field(min_length=1, max_length=1800)
    conversationId: Identity
    actorId: str = Field(pattern=r"^human:.{1,190}$")
    executionSubject: str = Field(pattern=r"^service:.{1,190}$")
    questionDigest: Digest
    presentationDigest: Digest
    verifiedInterpretation: dict | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if not self.answer.strip():
            raise ValueError("FIXED_QUESTION_EMPTY_ANSWER")
        return self


class DelegatedAnswerReceipt(StrictValue):
    schemaVersion: Literal["fixed-question-answer.v1"] = "fixed-question-answer.v1"
    presentationId: Identity
    presentationDigest: Digest
    questionIdentityDigest: Digest
    actorId: str = Field(pattern=r"^human:.{1,190}$")
    executionSubject: str = Field(pattern=r"^service:.{1,190}$")
    commandId: Identity
    requestDigest: Digest
    inputMessageId: Identity
    interpretationInvocationId: Identity
    interpretationDigest: Digest
    answerDigest: Digest
    generation: int = Field(strict=True, gt=0)
    recoveryEpoch: int = Field(strict=True, gt=0)
    acceptedAt: datetime

    @model_validator(mode="after")
    def separate(self):
        if self.actorId == self.executionSubject or self.acceptedAt.tzinfo is None:
            raise ValueError("FIXED_QUESTION_ANSWER_INVALID")
        return self

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))
