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
from agent_console.workbench_bff import PREFIX, WorkbenchBffPolicy


class BeginDraftAssistance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotencyKey: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=16_384)
    parentContextId: str | None = Field(default=None, max_length=128)
    parentTurnId: str | None = Field(default=None, max_length=128)
    expectedParentVersion: int = Field(default=0, ge=0)
    predecessorInvocationId: str | None = Field(default=None, max_length=128)


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
    value = response.invocation
    recovered_without_content = (
        value.state.value == "SUCCEEDED"
        and value.result_kind is not None
        and value.problem_id is None
        and response.clarification_question is None
        and response.title is None
        and response.description is None
    )
    return {
        "result": {
            "contextId": value.context_id,
            "turnId": value.turn_id,
            "turnVersion": value.turn_version,
            "invocationId": value.invocation_id,
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
            "clarificationQuestion": response.clarification_question,
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


def install_draft_assistance_routes(service: DraftAssistanceService):
    def install(app: FastAPI, authenticate, require_csrf, policy: WorkbenchBffPolicy):
        del policy

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

        @app.post(f"{PREFIX}/draft-assistance/invocations", status_code=201)
        def begin(body: BeginDraftAssistance, request: Request):
            return invoke(
                lambda context: service.begin(
                    context,
                    key=body.idempotencyKey,
                    content=body.content,
                    parent_context_id=body.parentContextId,
                    parent_turn_id=body.parentTurnId,
                    expected_parent_version=body.expectedParentVersion,
                    predecessor_invocation_id=body.predecessorInvocationId,
                ),
                request,
            )

        @app.post(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}/resubmit")
        def resubmit(
            invocation_id: str, body: ResubmitDraftAssistance, request: Request
        ):
            def action(context):
                result = service.begin(
                    context, key=body.idempotencyKey, content=body.content
                )
                if result.invocation.invocation_id != invocation_id:
                    raise DraftAssistanceError("DRAFT_ASSISTANCE_NOT_FOUND")
                return result

            return invoke(action, request)

        @app.get(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}")
        def read(invocation_id: str, request: Request):
            _, context = authenticate(request)
            try:
                return _payload(service.read(context, invocation_id))
            except DraftAssistanceError as exc:
                return JSONResponse(
                    status_code=_status(exc.reason_code),
                    content={"reasonCode": exc.reason_code},
                )

        @app.post(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}/observe")
        def observe(invocation_id: str, request: Request):
            return invoke(
                lambda context: service.observe(context, invocation_id), request
            )

        @app.post(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}/cancel")
        def cancel(invocation_id: str, request: Request):
            return invoke(
                lambda context: service.cancel(context, invocation_id), request
            )

        @app.post(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}/reject")
        def reject(invocation_id: str, request: Request):
            return invoke(
                lambda context: service.reject(context, invocation_id), request
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
