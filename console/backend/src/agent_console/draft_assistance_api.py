"""Trusted Workbench routes for governed Problem Draft Assistance."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from agent_console.draft_assistance import (
    DraftAssistanceError,
    DraftAssistanceService,
    DraftResponse,
)
from agent_console.responses_deadline import cancellable_request
from agent_console.workbench_bff import PREFIX, WorkbenchBffPolicy


class BeginDraftAssistance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotencyKey: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=16_384)
    parentContextId: str | None = Field(default=None, max_length=128)
    parentTurnId: str | None = Field(default=None, max_length=128)
    expectedParentVersion: int = Field(default=0, ge=0)
    predecessorInvocationId: str | None = Field(default=None, max_length=128)
    conversationRouting: bool = False
    failedRetryOf: str | None = Field(default=None, min_length=1, max_length=128)
    conversationId: str | None = Field(default=None, min_length=1, max_length=128)
    conversationMessageId: str | None = Field(
        default=None, min_length=1, max_length=128
    )


class ResubmitDraftAssistance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotencyKey: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=16_384)


class LinkDraftProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problemId: str = Field(min_length=1, max_length=128)
    problemRevisionId: str = Field(min_length=1, max_length=128)
    problemDigest: str = Field(pattern=r"^[0-9a-f]{64}$")


def _status(reason: str) -> int:
    if reason == "CONVERSATION_FAILED_RETRY_IN_PROGRESS":
        return 503
    if reason.startswith("CONVERSATION_FAILED_RETRY_"):
        return 409
    if (
        reason.startswith("CONTEXT_ADMISSION_")
        or reason == "DRAFT_AUTHORIZATION_UNAVAILABLE"
    ):
        return 403
    if reason in {
        "IDEMPOTENCY_PAYLOAD_MISMATCH",
        "IDEMPOTENCY_REPLAY_UNVERIFIABLE",
        "IDEMPOTENCY_REPLAY_WINDOW_EXPIRED",
        "DRAFT_STATE_CONFLICT",
        "DRAFT_PROBLEM_LINK_CONFLICT",
        "DRAFT_TURN_VERSION_CONFLICT",
    }:
        return 409
    if reason in {
        "DRAFT_STORAGE_UNAVAILABLE",
        "RESOURCE_USE_STORAGE_UNAVAILABLE",
        "EVIDENCE_STORAGE_UNAVAILABLE",
        "TRANSPORT_AMBIGUOUS",
        "CREDENTIAL_RESOLUTION_FAILED",
        "CONVERSATION_UNDERSTANDING_UNAVAILABLE",
    }:
        return 503
    if reason in {
        "DRAFT_CONTENT_INVALID",
        "IDEMPOTENCY_KEY_INVALID",
        "OUTPUT_SCHEMA_INVALID",
    }:
        return 422
    return 404


def _payload(response: DraftResponse) -> dict[str, Any]:
    from .understanding_source_presentation import source_input_observation

    value = response.invocation
    recovered_without_content = (
        value.state.value == "SUCCEEDED"
        and value.result_kind is not None
        and value.result_kind.value != "CURRENT_QUESTION_ANSWER"
        and value.problem_id is None
        and response.clarification_question is None
        and response.title is None
        and response.description is None
        and response.answer is None
        and not response.data_needs
    )
    return {
        "result": {
            "sourceInputObservation": source_input_observation(response),
            "contextId": value.context_id,
            "turnId": value.turn_id,
            "turnVersion": value.turn_version,
            "invocationId": value.invocation_id,
            "submittedAt": value.created_at.isoformat(),
            "state": value.state.value,
            "aggregateVersion": value.aggregate_version,
            "resultKind": value.result_kind.value if value.result_kind else None,
            "reasonCode": (
                value.owner_write_reason_code
                or value.reason_code
                or (
                    "RESULT_CONTENT_NOT_RETAINED" if recovered_without_content else None
                )
            ),
            "contentDisposition": value.content_disposition,
            "settlementStatus": value.settlement_status,
            "localWorkerState": (
                "REAPED" if value.local_cleanup.get("reaped") else "CLEANUP_NOT_PROVEN"
            )
            if value.local_cleanup
            else "NOT_OBSERVED",
            "remoteCancellation": "NOT_PROVEN",
            "clarificationQuestion": response.clarification_question,
            "understanding": response.understanding,
            **(
                {"answer": response.answer, "dataNeeds": response.data_needs or []}
                if value.result_kind
                and value.result_kind.value in {"DIRECT_ANSWER", "NEEDS_DATA"}
                else {}
            ),
            "draft": (
                {"title": response.title, "description": response.description}
                if response.title and response.description
                else None
            ),
            # Exact identifiers belong to separately authorized owner read paths.
            "resourceUseId": None,
            "evidenceId": None,
            "resourceUseRecorded": value.resource_use_id is not None,
            "evidenceRecorded": value.evidence_id is not None,
            "problemId": value.problem_id,
            "problemRevisionId": value.problem_revision_id,
            "problemDigest": value.problem_digest,
            **({"inputSource": value.input_source} if value.input_source else {}),
            **(
                {"conversationRoute": value.conversation_route}
                if value.conversation_route
                else {}
            ),
            "transport": "SYNTHETIC" if response.synthetic else "REAL_PROVIDER",
            "requestAuthorizationRequestId": (
                value.authorization.request_authorization_request_id
                if value.authorization
                else None
            ),
            "modelAuthorizationRequestId": (
                value.authorization.model_authorization_request_id
                if value.authorization
                else None
            ),
        }
    }


def install_draft_assistance_routes(
    service: DraftAssistanceService,
    routing_service=None,
    *,
    retained_routing_services=(),
):
    def install(app: FastAPI, authenticate, require_csrf, policy: WorkbenchBffPolicy):
        del policy

        def service_for(context, identity):
            from .draft_assistance import DraftScope

            value = service.repository.get(DraftScope.from_context(context), identity)
            if value and value.conversation_context:
                matches = [
                    candidate
                    for candidate in (routing_service, *retained_routing_services)
                    if candidate
                    and candidate.profile.profile_revision_id
                    == value.profile_revision_id
                ]
                if len(matches) != 1 or (
                    value.snapshot is not None
                    and matches[0].profile.profile_digest
                    != value.snapshot.profile_digest
                ):
                    raise DraftAssistanceError(
                        "CONVERSATION_ROUTING_SERVICE_UNAVAILABLE"
                    )
                return matches[0]
            return service

        app.state.conversation_draft_service_for = service_for
        app.state.conversation_draft_reader = lambda ctx, identity: _payload(
            service_for(ctx, identity).read(ctx, identity)
        )["result"]
        from .conversation_relation_validation import (
            install as install_relation_validation,
        )

        install_relation_validation(
            app, authenticate, service, service_for, _payload, _status
        )

        from .understanding_adoption_api import install as install_adoption

        install_adoption(app, authenticate, require_csrf)

        def invoke(action, request: Request):
            session, context = authenticate(request)
            require_csrf(request, session)
            try:
                return _payload(action(context))
            except DraftAssistanceError as exc:
                return JSONResponse(
                    status_code=_status(exc.reason_code),
                    content={"reasonCode": exc.reason_code},
                )

        @app.get(f"{PREFIX}/draft-assistance/capabilities")
        def capabilities(request: Request):
            from .conversation_relation_admission import available
            from .understanding_source_presentation import current_source_capability

            _, context = authenticate(request)
            return {
                "result": {
                    "selectedSourceContext": current_source_capability(
                        routing_service,
                        available(routing_service, context)
                        and getattr(app.state, "understanding_adoption", None)
                        is not None,
                    ),
                    "conversationUnderstanding": service.profile.adapter_revision
                    in {"v3", "v3-execution", "v3-relation"},
                    "conversationRelationRouting": available(routing_service, context),
                    "initialUnderstandingAdoption": (
                        routing_service is not None
                        and routing_service.profile.adapter_revision
                        in {
                            "v3-relation-adoption",
                            "v3-relation-adoption-source",
                            "v3-relation-adoption-source-answers",
                            "v4-structured-conversation",
                        }
                        and getattr(app.state, "understanding_adoption", None)
                        is not None
                        and available(routing_service, context)
                    ),
                }
            }

        @app.get(
            f"{PREFIX}/conversations/{{conversation}}/understanding-results/{{message_id}}"
        )
        def read_conversation_result(
            conversation: str, message_id: str, requestKey: str, request: Request
        ):
            from .conversation_answer_retention import read_retained, require_target
            from .draft_assistance import DraftScope
            from .private_conversation import ConversationError, digest

            _, context = authenticate(request)
            actions = getattr(request.app.state, "conversation_actions", None)
            if not actions or not 1 <= len(requestKey) <= 128:
                return JSONResponse(
                    status_code=404,
                    content={"reasonCode": "CONVERSATION_RESULT_NOT_FOUND"},
                )
            try:
                require_target(
                    actions, context, conversation, message_id, allow_archived=True
                )
                key = "conversation:" + digest([conversation, message_id, requestKey])
                invocation = service.repository.get_by_key(
                    DraftScope.from_context(context), context.principal_id, key
                )
                if invocation is None:
                    # Ownership and exact request key were checked above. The
                    # service persists an invocation before budget reservation or
                    # dispatch. Re-submission MUST use the same key: the owner's
                    # CAS still fences a concurrent request after this observation.
                    return JSONResponse(
                        status_code=404,
                        content={"reasonCode": "CONVERSATION_REQUEST_NOT_DISPATCHED"},
                    )
                value = _payload(
                    service_for(context, invocation.invocation_id).read(
                        context, invocation.invocation_id
                    )
                )["result"]
                return {
                    "result": read_retained(
                        actions,
                        context,
                        conversation,
                        value,
                        request_key=requestKey,
                        message_id=message_id,
                    )
                }
            except ConversationError as exc:
                return JSONResponse(
                    status_code=exc.status, content={"reasonCode": exc.reason}
                )
            except DraftAssistanceError as exc:
                return JSONResponse(
                    status_code=_status(exc.reason_code),
                    content={"reasonCode": exc.reason_code},
                )

        @app.get(f"{PREFIX}/conversations/{{conversation}}/understanding-failures")
        def understanding_failures(conversation: str, request: Request):
            _, context = authenticate(request)
            from .conversation_understanding_failure import discover
            from .private_conversation import ConversationError

            try:
                actions = getattr(request.app.state, "conversation_actions", None)
                if not actions:
                    raise DraftAssistanceError("CONVERSATION_UNDERSTANDING_UNAVAILABLE")
                return {
                    "result": discover(
                        actions,
                        context,
                        conversation,
                        service,
                        service_for,
                        _payload,
                        getattr(
                            request.app.state, "conversation_relation_reader", None
                        ),
                        getattr(
                            request.app.state,
                            "conversation_adoption_source_input",
                            None,
                        ),
                    )
                }
            except ConversationError as exc:
                return JSONResponse(
                    status_code=exc.status, content={"reasonCode": exc.reason}
                )
            except DraftAssistanceError as exc:
                return JSONResponse(
                    status_code=_status(exc.reason_code),
                    content={"reasonCode": exc.reason_code},
                )

        @app.post(f"{PREFIX}/draft-assistance/invocations", status_code=201)
        async def begin(body: BeginDraftAssistance, request: Request):
            from .conversation_actions import original_action

            active_service = routing_service if body.conversationRouting else service

            def action(context):
                from .conversation_answer_retention import require_target, retain
                from .private_conversation import ConversationError, digest

                conversation = body.conversationId
                if body.failedRetryOf and not body.conversationRouting:
                    raise DraftAssistanceError(
                        "CONVERSATION_FAILED_RETRY_CONTEXT_CHANGED"
                    )
                if body.conversationRouting and (
                    active_service is None
                    or active_service.profile.adapter_revision
                    not in {
                        "v3-relation",
                        "v3-relation-adoption",
                        "v3-relation-adoption-source",
                        "v3-relation-adoption-source-answers",
                        "v4-structured-conversation",
                    }
                    or not conversation
                    or body.parentContextId
                    or body.parentTurnId
                    or body.predecessorInvocationId
                ):
                    raise DraftAssistanceError("CONVERSATION_ROUTING_CONTEXT_INVALID")
                actions = getattr(request.app.state, "conversation_actions", None)
                if conversation:
                    if request.headers.get("x-conversation-id") or request.headers.get(
                        "x-conversation-intent"
                    ):
                        return JSONResponse(
                            status_code=409,
                            content={"reasonCode": "CONVERSATION_CONTEXT_CONFLICT"},
                        )
                    if not actions or active_service.profile.adapter_revision not in {
                        "v3",
                        "v3-execution",
                        "v3-relation",
                        "v3-relation-adoption",
                        "v3-relation-adoption-source",
                        "v3-relation-adoption-source-answers",
                        "v4-structured-conversation",
                    }:
                        raise DraftAssistanceError(
                            "CONVERSATION_UNDERSTANDING_UNAVAILABLE"
                        )
                    try:
                        require_target(
                            actions,
                            context,
                            conversation,
                            body.conversationMessageId,
                            body.content,
                        )
                    except ConversationError as exc:
                        return JSONResponse(
                            status_code=exc.status, content={"reasonCode": exc.reason}
                        )
                    key = "conversation:" + digest(
                        [conversation, body.conversationMessageId, body.idempotencyKey]
                    )
                else:
                    key = body.idempotencyKey

                def invoke_owner():
                    from .conversation_experience_admission import begin_bound
                    from .conversation_relation_context import bind_snapshot
                    from .conversation_source_input import bind_attachment

                    snapshot = None
                    if body.conversationRouting:
                        routing_reader = getattr(
                            request.app.state, "conversation_relation_reader", None
                        )
                        if routing_reader is None:
                            raise DraftAssistanceError(
                                "CONVERSATION_ROUTING_CONTEXT_UNAVAILABLE"
                            )
                        snapshot = routing_reader(
                            context, conversation, body.conversationMessageId, service
                        )

                    adoption = (
                        body.conversationRouting
                        and active_service.profile.adapter_revision
                        in {
                            "v3-relation-adoption",
                            "v3-relation-adoption-source",
                            "v3-relation-adoption-source-answers",
                            "v4-structured-conversation",
                        }
                    )
                    reader = getattr(
                        request.app.state,
                        "conversation_adoption_source_input"
                        if adoption
                        else "conversation_source_input",
                        None,
                    )
                    attachment = (
                        reader(context, conversation, body.conversationMessageId)
                        if conversation
                        and reader is not None
                        and (
                            not body.conversationRouting
                            or (
                                adoption
                                and (snapshot.get("target") or {}).get("kind")
                                == "UNDERSTANDING"
                            )
                        )
                        else None
                    )
                    if body.failedRetryOf:
                        from .conversation_source_input import current_source_metadata
                        from .conversation_understanding_failure import (
                            require,
                            require_snapshot,
                            successor_key,
                        )

                        original = (
                            service_for(context, body.failedRetryOf)
                            .read(context, body.failedRetryOf)
                            .invocation
                        )
                        require(
                            body.idempotencyKey == successor_key(original.invocation_id)
                        )
                        with bind_attachment(attachment):
                            selected = current_source_metadata()
                        require_snapshot(
                            original,
                            subject=context.principal_id,
                            conversation=conversation,
                            message_id=body.conversationMessageId,
                            snapshot=snapshot,
                            source=selected,
                        )
                        from .conversation_understanding_failure import retry_content

                        text_digest = retry_content(
                            actions,
                            context,
                            conversation,
                            body.conversationMessageId,
                            body.content,
                        )
                        snapshot = {
                            **snapshot,
                            "failedRetryOf": original.invocation_id,
                            "failedRetryInputDigest": text_digest,
                        }
                    from .conversation_understanding_failure import begin_retry

                    with bind_attachment(attachment), bind_snapshot(snapshot):
                        value = _payload(
                            (begin_retry if body.failedRetryOf else begin_bound)(
                                active_service,
                                context,
                                conversation=conversation,
                                message_id=body.conversationMessageId,
                                question_only=body.conversationRouting,
                                key=key,
                                content=body.content,
                                parent_context_id=body.parentContextId,
                                parent_turn_id=body.parentTurnId,
                                expected_parent_version=body.expectedParentVersion,
                                predecessor_invocation_id=body.predecessorInvocationId,
                            )
                        )
                    if conversation:
                        try:
                            value["result"] = retain(
                                actions,
                                context,
                                conversation,
                                value["result"],
                                request_key=body.idempotencyKey,
                                message_id=body.conversationMessageId,
                            )
                        except Exception:
                            # Preserve the result; do not claim retention.
                            value["result"]["conversationDelivery"] = {
                                "state": "SAVE_FAILED"
                            }
                    return value

                try:
                    return original_action(
                        request,
                        context,
                        "DRAFT",
                        body.model_dump(
                            mode="json",
                            exclude_none=True,
                            exclude=set()
                            if body.conversationRouting
                            else {"conversationRouting"},
                        ),
                        invoke_owner,
                    )
                except ConversationError as exc:
                    return JSONResponse(
                        status_code=exc.status, content={"reasonCode": exc.reason}
                    )

            # Preserve the original owner error mapping and cancellation deadline.
            def submit():
                session, context = authenticate(request)
                require_csrf(request, session)
                try:
                    return action(context)
                except DraftAssistanceError as exc:
                    return JSONResponse(
                        status_code=_status(exc.reason_code),
                        content={"reasonCode": exc.reason_code},
                    )

            from .model_stream_api import model_response, stream_authorization

            authorize = stream_authorization(
                request,
                authenticate,
                require_csrf,
                (active_service or service).authorize_stream,
            )

            return await model_response(request, submit, authorize)

        @app.post(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}/resubmit")
        async def resubmit(
            invocation_id: str, body: ResubmitDraftAssistance, request: Request
        ):
            def action(context):
                result = service.begin(
                    context, key=body.idempotencyKey, content=body.content
                )
                if result.invocation.invocation_id != invocation_id:
                    raise DraftAssistanceError("DRAFT_ASSISTANCE_NOT_FOUND")
                return result

            return await cancellable_request(request, lambda: invoke(action, request))

        @app.get(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}")
        def read(invocation_id: str, request: Request):
            _, context = authenticate(request)
            try:
                return _payload(
                    service_for(context, invocation_id).read(context, invocation_id)
                )
            except DraftAssistanceError as exc:
                return JSONResponse(
                    status_code=_status(exc.reason_code),
                    content={"reasonCode": exc.reason_code},
                )

        @app.get(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}/readiness")
        def readiness(invocation_id: str, request: Request):
            _, context = authenticate(request)
            try:
                return {
                    "result": service_for(context, invocation_id).read_readiness(
                        context, invocation_id
                    )
                }
            except DraftAssistanceError as exc:
                return JSONResponse(
                    status_code=_status(exc.reason_code),
                    content={"reasonCode": exc.reason_code},
                )

        @app.get(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}/usage")
        def usage(invocation_id: str, request: Request):
            from .authority_contracts import AuthorityError

            _, context = authenticate(request)
            try:
                return {
                    "result": service_for(context, invocation_id).read_usage(
                        context, invocation_id
                    )
                }
            except (DraftAssistanceError, AuthorityError):
                return JSONResponse(
                    status_code=404, content={"reasonCode": "PROVIDER_USAGE_NOT_FOUND"}
                )

        @app.post(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}/observe")
        def observe(invocation_id: str, request: Request):
            return invoke(
                lambda context: service_for(context, invocation_id).observe(
                    context, invocation_id
                ),
                request,
            )

        @app.post(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}/cancel")
        def cancel(invocation_id: str, request: Request):
            return invoke(
                lambda context: service_for(context, invocation_id).cancel(
                    context, invocation_id
                ),
                request,
            )

        @app.post(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}/reject")
        def reject(invocation_id: str, request: Request):
            return invoke(
                lambda context: service_for(context, invocation_id).reject(
                    context, invocation_id
                ),
                request,
            )

        @app.post(
            f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}/problem-link"
        )
        def link_problem(invocation_id: str, body: LinkDraftProblem, request: Request):
            return invoke(
                lambda context: service.link_problem(
                    context,
                    invocation_id,
                    problem_id=body.problemId,
                    problem_revision_id=body.problemRevisionId,
                    problem_digest=body.problemDigest,
                ),
                request,
            )

    return install
