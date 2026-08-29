"""FastAPI application for the AgentOS Workflow Execution Console."""

import os
from pathlib import Path
from typing import Annotated

from agent_core.execution_evidence import SQLiteExecutionEvidenceRepository
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from kubernetes.client.exceptions import ApiException
from pydantic import BaseModel, ValidationError

from agent_console.intervention_feedback import (
    CaptureDenied,
    CaptureNotFound,
    CaptureUnavailable,
    InterventionFeedbackFailure,
    InterventionFeedbackService,
    TrustedCapturePrincipal,
    TrustedInterventionTarget,
)
from agent_console.intervention_feedback_schemas import (
    InterventionCaptureCommand,
    InterventionFeedbackError,
    InterventionFeedbackResponse,
    InterventionLifecycleCommand,
    OutcomeFeedbackCommand,
)
from agent_console.live_journey import (
    LiveJourneyCoordinator,
    TrustedJourneyPrincipal,
)
from agent_console.live_journey import (
    LiveJourneyError as JourneyServiceError,
)
from agent_console.live_journey_schemas import (
    ApprovalRequest as JourneyApprovalRequest,
)
from agent_console.live_journey_schemas import (
    CorrectionRequest,
    LiveJourneyError,
    LiveJourneyResponse,
    RerunRequest,
)
from agent_console.preview_schemas import PreviewError, PreviewResponse
from agent_console.preview_service import (
    PreviewService,
    PreviewServiceError,
    TrustedPreviewPrincipal,
)
from agent_console.repository import (
    KubernetesWorkflowRepository,
    WorkflowRepository,
)
from agent_console.schemas import (
    WorkflowExecutionDetail,
    WorkflowRunList,
)
from agent_console.service import WorkflowService

app = FastAPI(
    title="AgentOS Workflow Execution Console",
    version="0.1.0",
)


def get_repository() -> WorkflowRepository:
    """Provide the production Workflow repository."""
    return KubernetesWorkflowRepository()


RepositoryDependency = Annotated[
    WorkflowRepository,
    Depends(get_repository),
]


def get_workflow_service(
    repository: RepositoryDependency,
) -> WorkflowService:
    """Provide the Workflow application service."""
    return WorkflowService(repository)


WorkflowServiceDependency = Annotated[
    WorkflowService,
    Depends(get_workflow_service),
]


def get_preview_principal() -> TrustedPreviewPrincipal:
    """Resolve preview authority from trusted server configuration only."""
    principal = os.environ.get("AGENT_CONSOLE_PREVIEW_PRINCIPAL", "")
    namespace = os.environ.get("AGENT_CONSOLE_PREVIEW_NAMESPACE", "")
    security_domain = os.environ.get("AGENT_CONSOLE_PREVIEW_SECURITY_DOMAIN", "")
    return TrustedPreviewPrincipal(
        principal_id=principal,
        namespace=namespace,
        security_domain=security_domain,
        authorized=bool(principal and namespace and security_domain),
    )


def get_preview_service(repository: RepositoryDependency) -> PreviewService:
    location = os.environ.get("AGENT_EXECUTION_EVIDENCE_DB")
    evidence = SQLiteExecutionEvidenceRepository(Path(location)) if location else None
    return PreviewService(repository, evidence)


PreviewPrincipalDependency = Annotated[
    TrustedPreviewPrincipal, Depends(get_preview_principal)
]
PreviewServiceDependency = Annotated[PreviewService, Depends(get_preview_service)]


_live_journey_service = LiveJourneyCoordinator()


def get_live_journey_principal() -> TrustedJourneyPrincipal:
    """Resolve journey scope from trusted server configuration only."""
    principal = os.environ.get("AGENT_CONSOLE_JOURNEY_PRINCIPAL", "")
    tenant = os.environ.get("AGENT_CONSOLE_JOURNEY_TENANT", "")
    domain = os.environ.get("AGENT_CONSOLE_JOURNEY_SECURITY_DOMAIN", "")
    return TrustedJourneyPrincipal(
        principal_id=principal,
        tenant_id=tenant,
        security_domain=domain,
        authorized=bool(principal and tenant and domain),
    )


def get_live_journey_service() -> LiveJourneyCoordinator:
    """Return the explicitly configured in-memory Technical Preview coordinator."""
    return _live_journey_service


JourneyPrincipalDependency = Annotated[
    TrustedJourneyPrincipal, Depends(get_live_journey_principal)
]
JourneyServiceDependency = Annotated[
    LiveJourneyCoordinator, Depends(get_live_journey_service)
]

_intervention_feedback_service = InterventionFeedbackService()


def get_intervention_feedback_service() -> InterventionFeedbackService:
    """Return the bounded in-memory Package 6A fact service."""
    return _intervention_feedback_service


InterventionFeedbackServiceDependency = Annotated[
    InterventionFeedbackService, Depends(get_intervention_feedback_service)
]


def _capture_principal(principal: TrustedJourneyPrincipal) -> TrustedCapturePrincipal:
    return TrustedCapturePrincipal(
        principal_id=principal.principal_id,
        tenant_id=principal.tenant_id,
        security_domain=principal.security_domain,
        authorized=principal.authorized,
    )


def _capture_target(
    journey_id: str,
    principal: TrustedJourneyPrincipal,
    journey_service: LiveJourneyCoordinator,
) -> TrustedInterventionTarget:
    """Resolve authorization and exact Package 5 identities before capture reads."""
    try:
        journey = journey_service.get(journey_id, principal)
    except JourneyServiceError as exc:
        if exc.state == "DENIED":
            raise CaptureDenied() from exc
        if exc.state == "NOT_FOUND":
            raise CaptureNotFound() from exc
        raise CaptureUnavailable("UPSTREAM_JOURNEY_AUTHORITY_UNAVAILABLE") from exc
    predecessor = journey.predecessor
    successor = journey.successor
    return TrustedInterventionTarget(
        journey_id=journey.journeyId,
        tenant_id=successor.identity.tenantId,
        security_domain=successor.identity.securityDomain,
        provenance=journey.provenance,
        predecessor_revision_id=(
            None
            if predecessor is None
            else predecessor.identity.canonicalWorkflowRevisionId
        ),
        predecessor_digest=(
            None if predecessor is None else predecessor.identity.canonicalDigest
        ),
        successor_revision_id=successor.identity.canonicalWorkflowRevisionId,
        successor_digest=successor.identity.canonicalDigest,
        platform_execution_identity=successor.identity.platformExecutionIdentity,
        outcome_id=None if successor.outcome is None else successor.outcome.outcomeId,
        execution_evidence_ids=tuple(successor.identity.evidenceIds),
    )


def _capture_command[CommandModel: BaseModel](
    model: type[CommandModel], payload: dict[str, object]
) -> CommandModel:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise InterventionFeedbackFailure("CAPTURE_COMMAND_INVALID") from exc


def _capture_http_error(exc: InterventionFeedbackFailure) -> HTTPException:
    payload = InterventionFeedbackError(
        state=exc.state,
        reasonCode=exc.reason_code,
    )
    return HTTPException(status_code=exc.status_code, detail=payload.model_dump())


def _journey_http_error(exc: JourneyServiceError) -> HTTPException:
    payload = LiveJourneyError(
        state=exc.state,
        reasonCode=exc.reason_code,
        message="Live planning journey is unavailable",
    )
    return HTTPException(status_code=exc.status_code, detail=payload.model_dump())


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Return Console process health."""
    return {"status": "ok"}


@app.get(
    "/api/v1/workflows",
    response_model=WorkflowRunList,
)
def list_workflows(
    service: WorkflowServiceDependency,
) -> WorkflowRunList:
    """List Workflow executions."""
    return service.list_workflows()


@app.get(
    "/api/v1/workflows/{namespace}/{name}",
    response_model=WorkflowExecutionDetail,
)
def get_workflow(
    namespace: str,
    name: str,
    service: WorkflowServiceDependency,
) -> WorkflowExecutionDetail:
    """Return one Workflow execution projection."""
    try:
        return service.get_workflow(
            namespace=namespace,
            name=name,
        )
    except ApiException as exc:
        if exc.status == 404:
            raise HTTPException(
                status_code=404,
                detail="workflow not found",
            ) from exc

        raise


@app.get(
    "/api/internal/preview/v1/executions/{namespace}/{workflow_name}/{task_name}",
    response_model=PreviewResponse,
    responses={
        403: {"model": PreviewError},
        404: {"model": PreviewError},
        500: {"model": PreviewError},
        503: {"model": PreviewError},
    },
)
def get_execution_preview(
    namespace: str,
    workflow_name: str,
    task_name: str,
    principal: PreviewPrincipalDependency,
    service: PreviewServiceDependency,
    response: Response,
    if_none_match: Annotated[str | None, Header()] = None,
) -> PreviewResponse | Response:
    """Return one authorization-first internal Technical Preview snapshot."""
    try:
        preview = service.get_preview(
            principal=principal,
            namespace=namespace,
            workflow_name=workflow_name,
            task_name=task_name,
        )
    except PreviewServiceError as exc:
        payload = PreviewError(
            state=exc.state,
            reasonCode=exc.reason_code,
            message="Execution preview is unavailable",
        )
        raise HTTPException(
            status_code=exc.status_code, detail=payload.model_dump()
        ) from exc
    etag = f'"{preview.sharedSnapshotId}"'
    if if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, no-cache"
    return preview


@app.get(
    "/api/internal/preview/v1/live-planning-journeys/{journey_id}",
    response_model=LiveJourneyResponse,
    responses={
        403: {"model": LiveJourneyError},
        404: {"model": LiveJourneyError},
        503: {"model": LiveJourneyError},
    },
)
def get_live_planning_journey(
    journey_id: str,
    principal: JourneyPrincipalDependency,
    service: JourneyServiceDependency,
) -> LiveJourneyResponse:
    """Return equal Product and Technical projections of one live journey."""
    try:
        return service.get(journey_id, principal)
    except JourneyServiceError as exc:
        raise _journey_http_error(exc) from exc


@app.post(
    "/api/internal/preview/v1/live-planning-journeys/{journey_id}/corrections",
    response_model=LiveJourneyResponse,
)
def correct_live_planning_journey(
    journey_id: str,
    request: CorrectionRequest,
    principal: JourneyPrincipalDependency,
    service: JourneyServiceDependency,
) -> LiveJourneyResponse:
    try:
        return service.correct(
            journey_id,
            principal,
            predecessor_revision_id=request.predecessorRevisionId,
            predecessor_digest=request.predecessorDigest,
            objective=request.objective,
            reason_code=request.reasonCode,
        )
    except JourneyServiceError as exc:
        raise _journey_http_error(exc) from exc


@app.post(
    "/api/internal/preview/v1/live-planning-journeys/{journey_id}/approvals",
    response_model=LiveJourneyResponse,
)
def approve_live_planning_journey(
    journey_id: str,
    request: JourneyApprovalRequest,
    principal: JourneyPrincipalDependency,
    service: JourneyServiceDependency,
) -> LiveJourneyResponse:
    try:
        return service.approve(
            journey_id,
            principal,
            candidate_digest=request.candidateDigest,
            decision=request.decision,
            reason_code=request.reasonCode,
            replay_identity=request.replayIdentity,
        )
    except JourneyServiceError as exc:
        raise _journey_http_error(exc) from exc


@app.post(
    "/api/internal/preview/v1/live-planning-journeys/{journey_id}/reruns",
    response_model=LiveJourneyResponse,
)
def rerun_live_planning_journey(
    journey_id: str,
    request: RerunRequest,
    principal: JourneyPrincipalDependency,
    service: JourneyServiceDependency,
) -> LiveJourneyResponse:
    try:
        return service.rerun(
            journey_id,
            principal,
            revision_id=request.canonicalWorkflowRevisionId,
            digest=request.canonicalDigest,
        )
    except JourneyServiceError as exc:
        raise _journey_http_error(exc) from exc


@app.get(
    "/api/internal/preview/v1/live-planning-journeys/{journey_id}/intervention-feedback",
    response_model=InterventionFeedbackResponse,
    responses={
        403: {"model": InterventionFeedbackError},
        404: {"model": InterventionFeedbackError},
        503: {"model": InterventionFeedbackError},
    },
)
def get_intervention_feedback(
    journey_id: str,
    principal: JourneyPrincipalDependency,
    journey_service: JourneyServiceDependency,
    capture_service: InterventionFeedbackServiceDependency,
) -> InterventionFeedbackResponse:
    """Return authorization-first equal Product and Technical fact projections."""
    try:
        target = _capture_target(journey_id, principal, journey_service)
        return capture_service.project(_capture_principal(principal), target)
    except InterventionFeedbackFailure as exc:
        raise _capture_http_error(exc) from exc


@app.post(
    "/api/internal/preview/v1/live-planning-journeys/{journey_id}/interventions",
    response_model=InterventionFeedbackResponse,
)
def capture_intervention(
    journey_id: str,
    request: dict[str, object],
    principal: JourneyPrincipalDependency,
    journey_service: JourneyServiceDependency,
    capture_service: InterventionFeedbackServiceDependency,
) -> InterventionFeedbackResponse:
    """Append one immutable intervention fact without changing upstream authority."""
    try:
        target = _capture_target(journey_id, principal, journey_service)
        command = _capture_command(InterventionCaptureCommand, request)
        capture_principal = _capture_principal(principal)
        capture_service.capture_intervention(capture_principal, target, command)
        return capture_service.project(capture_principal, target)
    except InterventionFeedbackFailure as exc:
        raise _capture_http_error(exc) from exc


@app.post(
    "/api/internal/preview/v1/live-planning-journeys/{journey_id}/interventions/"
    "{intervention_event_id}/lifecycle",
    response_model=InterventionFeedbackResponse,
)
def append_intervention_lifecycle(
    journey_id: str,
    intervention_event_id: str,
    request: dict[str, object],
    principal: JourneyPrincipalDependency,
    journey_service: JourneyServiceDependency,
    capture_service: InterventionFeedbackServiceDependency,
) -> InterventionFeedbackResponse:
    """Append an EXCLUDED, RETAINED, or TOMBSTONED lifecycle fact."""
    try:
        target = _capture_target(journey_id, principal, journey_service)
        command = _capture_command(InterventionLifecycleCommand, request)
        capture_principal = _capture_principal(principal)
        capture_service.append_intervention_lifecycle(
            capture_principal, target, intervention_event_id, command
        )
        return capture_service.project(capture_principal, target)
    except InterventionFeedbackFailure as exc:
        raise _capture_http_error(exc) from exc


@app.post(
    "/api/internal/preview/v1/live-planning-journeys/{journey_id}/outcome-feedback",
    response_model=InterventionFeedbackResponse,
)
def capture_outcome_feedback(
    journey_id: str,
    request: dict[str, object],
    principal: JourneyPrincipalDependency,
    journey_service: JourneyServiceDependency,
    capture_service: InterventionFeedbackServiceDependency,
) -> InterventionFeedbackResponse:
    """Append one feedback version against an exact Outcome/Evidence pair."""
    try:
        target = _capture_target(journey_id, principal, journey_service)
        command = _capture_command(OutcomeFeedbackCommand, request)
        capture_principal = _capture_principal(principal)
        capture_service.capture_feedback(capture_principal, target, command)
        return capture_service.project(capture_principal, target)
    except InterventionFeedbackFailure as exc:
        raise _capture_http_error(exc) from exc
