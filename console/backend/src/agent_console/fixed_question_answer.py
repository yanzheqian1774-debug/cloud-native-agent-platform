"""One human answer to the same service-owned WAIT; no continuation dispatch."""

from pydantic import Field

from .authority_contracts import AuthorityError
from .fixed_question_facts import require
from .fixed_question_interpretation import verified
from .fixed_question_store import FixedQuestionStore
from .fixed_question_types import DelegatedAnswerReceipt, StrictValue
from .native_wait_owner import NativeWaitOwner
from .resource_use_domain import canonical_digest


class AnswerQuestion(StrictValue):
    presentationId: str = Field(min_length=1, max_length=200)
    presentationDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    messageId: str = Field(min_length=1, max_length=200)
    requestKey: str = Field(min_length=1, max_length=200)
    commandId: str = Field(min_length=1, max_length=128)


class FixedQuestionAnswers:
    def __init__(self, presentations, *, settlement_reader, skill_repository):
        if not callable(settlement_reader):
            raise TypeError("FIXED_QUESTION_SETTLEMENT_READER_REQUIRED")
        self.presentations, self.settlement_reader = presentations, settlement_reader
        self.skill_repository = skill_repository

    def status(self, call, conversation, presentation_id, command_id):
        records = self.presentations.delivery.records
        owned = records.owned(call.connection, call.context, conversation, lock=True)
        require(
            owned["owner_id"] == call.context.principal_id
            and owned["archived_at"] is None
        )
        store = FixedQuestionStore(call.connection, records.scope(call.context))
        p = store.presentation(presentation_id)
        require(p is not None and p.identity.conversationId == conversation)
        self.presentations.require_read(call, p)
        value = store.answer(presentation_id)
        if value is not None:
            require(value.commandId == command_id)
        return value

    def accept(self, call, conversation, body):
        ctx, c = call.context, call.connection
        records = self.presentations.delivery.records
        owned = records.owned(c, ctx, conversation, lock=True)
        require(owned["owner_id"] == ctx.principal_id and owned["archived_at"] is None)
        store = FixedQuestionStore(c, records.scope(ctx))
        p = store.presentation(body.presentationId)
        require(p is not None and p.identity.conversationId == conversation)
        require(p.digest == body.presentationDigest and p.actorId == ctx.principal_id)
        self.presentations.require_current(call, p)
        request_digest = canonical_digest(body.model_dump(mode="json"))
        old = store.answer(p.presentationId)
        if old:
            require(
                old.requestDigest == request_digest and old.commandId == body.commandId
            )
            return old, True
        cp, _, _, _ = self.presentations.read(call, conversation, p.identity)
        text, interpretation, proof = verified(
            call,
            p,
            body.messageId,
            body.requestKey,
            settlement_reader=self.settlement_reader,
        )
        value = dict(
            kind="NATIVE_DELEGATED_ANSWER",
            answer=text,
            conversationId=conversation,
            actorId=ctx.principal_id,
            executionSubject=p.identity.executionSubject,
            questionDigest=p.identity.questionDigest,
            presentationDigest=p.digest,
        )
        if interpretation is not None:
            value["verifiedInterpretation"] = interpretation

        def authorize(connection, checkpoint, operation):
            if (
                connection is not c
                or checkpoint != cp
                or operation != "DELEGATED_ANSWER"
            ):
                raise AuthorityError("FIXED_QUESTION_WAIT_OPERATION_INVALID")
            self.presentations.validate_execution(c, checkpoint)

        def delegate(connection, checkpoint, supplied):
            require(connection is c and checkpoint == cp)
            require(supplied.model_dump(mode="json", exclude_none=True) == value)
            self.presentations.require_current(call, p)
            return p

        outcome = NativeWaitOwner(
            authorize,
            self.skill_repository,
            clock=self.presentations.clock,
            authorize_delegated_answer=delegate,
        ).accept_delegated_answer(c, cp, value)
        # A saved WAIT answer without this same atomic owner receipt is a conflict,
        # not a chance to invent a new attribution receipt after a crash.
        require(outcome == {"accepted": True, "replayed": False})
        receipt = DelegatedAnswerReceipt(
            presentationId=p.presentationId,
            presentationDigest=p.digest,
            questionIdentityDigest=p.identity.digest,
            actorId=p.actorId,
            executionSubject=p.identity.executionSubject,
            commandId=body.commandId,
            requestDigest=request_digest,
            inputMessageId=body.messageId,
            interpretationInvocationId=proof["invocationId"],
            interpretationDigest=proof["interpretationDigest"],
            answerDigest=canonical_digest(value),
            generation=call.policy_generation,
            recoveryEpoch=call.recovery_epoch,
            acceptedAt=self.presentations.clock(),
        )
        store.append_answer(receipt)
        return receipt, False
