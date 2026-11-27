"""Private optional routes. Construction alone never enables delegation."""

from fastapi import Request

from .fixed_question_answer import AnswerQuestion
from .fixed_question_presentation import PresentQuestion
from .private_conversation import ConversationError


def presentation_result(value, *, replayed):
    return dict(
        state="RECORDED",
        presentation=value.model_dump(mode="json"),
        presentationDigest=value.digest,
        replayed=replayed,
        modelDispatched=False,
        continuationDispatched=False,
        answerAuthority="RECHECK_REQUIRED",
    )


def install(app, execute, owner_factory):
    """execute is the original authenticated/CSRF/barrier/transaction boundary.

    Factory must supply fully composed presentation and answer owners; no private
    HTTP request may pass in a callback, issuer, context, policy or interpretation.
    """
    prefix = (
        "/api/workbench/v1/conversations/{conversation}/fixed-work-activity/questions"
    )

    @app.get(prefix)
    def observe(
        conversation: str,
        request: Request,
        eventId: str,
        receiptDigest: str,
        invocationId: str,
        questionKey: str,
    ):
        if set(request.query_params) != {
            "eventId",
            "receiptDigest",
            "invocationId",
            "questionKey",
        }:
            raise ConversationError("FIXED_QUESTION_QUERY_INVALID", 400)

        def read(call, delivery):
            presentations, _ = owner_factory(delivery)
            identity, question = presentations.observe(
                call, conversation, eventId, receiptDigest, invocationId, questionKey
            )
            return dict(
                identity=identity.model_dump(mode="json"),
                question=question,
                answerAuthority="NOT_IMPLIED",
            )

        return execute(request, conversation, read)

    @app.post(prefix + "/presentations")
    def present(conversation: str, request: Request, body: PresentQuestion):
        if request.query_params:
            raise ConversationError("FIXED_QUESTION_QUERY_INVALID", 400)

        def run(call, delivery):
            owner, _ = owner_factory(delivery)
            value, replayed = owner.prepare(call, conversation, body)
            return presentation_result(value, replayed=replayed)

        return execute(request, conversation, run, write=True)

    @app.get(prefix + "/presentations")
    def status(conversation: str, request: Request, commandId: str):
        if set(request.query_params) != {"commandId"} or not 1 <= len(commandId) <= 128:
            raise ConversationError("FIXED_QUESTION_QUERY_INVALID", 400)

        def read(call, delivery):
            owner, _ = owner_factory(delivery)
            value = owner.status(call, conversation, commandId)
            if value is None:
                return dict(
                    state="NOT_RECORDED",
                    conversationId=conversation,
                    commandId=commandId,
                )
            return presentation_result(value, replayed=True)

        return execute(request, conversation, read)

    @app.post(prefix + "/answers")
    def answer(conversation: str, request: Request, body: AnswerQuestion):
        if request.query_params:
            raise ConversationError("FIXED_QUESTION_QUERY_INVALID", 400)

        def run(call, delivery):
            _, answers = owner_factory(delivery)
            receipt, replayed = answers.accept(call, conversation, body)
            return dict(
                state="RECORDED",
                receipt=receipt.model_dump(mode="json"),
                receiptDigest=receipt.digest,
                replayed=replayed,
                modelDispatched=False,
                continuationDispatched=False,
            )

        return execute(request, conversation, run, write=True)

    @app.get(prefix + "/answers")
    def answer_status(
        conversation: str, request: Request, presentationId: str, commandId: str
    ):
        if (
            set(request.query_params) != {"presentationId", "commandId"}
            or not 1 <= len(commandId) <= 128
            or not 1 <= len(presentationId) <= 200
        ):
            raise ConversationError("FIXED_QUESTION_QUERY_INVALID", 400)

        def read(call, delivery):
            _, answers = owner_factory(delivery)
            receipt = answers.status(call, conversation, presentationId, commandId)
            if receipt is None:
                return dict(
                    state="NOT_RECORDED",
                    conversationId=conversation,
                    presentationId=presentationId,
                    commandId=commandId,
                )
            return dict(
                state="RECORDED",
                receipt=receipt.model_dump(mode="json"),
                receiptDigest=receipt.digest,
                replayed=True,
                modelDispatched=False,
                continuationDispatched=False,
            )

        return execute(request, conversation, read)
