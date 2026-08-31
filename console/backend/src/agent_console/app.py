"""FastAPI application for the AgentOS Workflow Execution Console."""

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
from agent_core.execution_evidence import (
    AppendDisposition,
    AppendResult,
    AuthorizedEvidenceScope,
    AuthorizedReference,
    EvidenceDigestConflict,
    ExecutionEvidenceRecord,
    ReferenceType,
    ReferenceVisibility,
    SQLiteExecutionEvidenceRepository,
)
from agent_core.execution_evidence import (
    AuthorizationDecision as EvidenceAuthorizationDecision,
)
from agent_core.interface_spine.v0_2 import InternalExecutionEnvelope, SourceTaskRef
from agent_core.representation.v0_2 import (
    AgentDefinitionRef,
    DesiredRuntimeBinding,
    EffectiveRuntimeBinding,
    RuntimeBinding,
    SelectedInstanceEvidence,
    mint_agent_instance_id,
    mint_platform_execution_identity,
)
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
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
from agent_console.live_journey_stream import (
    JourneyResumeUnavailable,
    JourneyStreamFailure,
    JourneyStreamScope,
    format_sse,
)
from agent_console.live_journey_stream_schemas import (
    JourneyEventEnvelope,
    JourneyEventPayload,
)
from agent_console.preview_schemas import PreviewError, PreviewResponse
from agent_console.preview_service import (
    PreviewService,
    PreviewServiceError,
    TrustedPreviewPrincipal,
)
from agent_console.problems import (
    ProblemPlanningError,
    ProblemPlanningService,
)
from agent_console.problems import (
    TrustedPrincipal as ProblemPrincipal,
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
from agent_console.supplier_quality_demo import (
    SupplierQualityDemoFailure,
    SupplierQualityDemoService,
)
from agent_console.supplier_quality_demo_schemas import (
    SupplierQualityDemoError,
    SupplierQualityDemoResetRequest,
    SupplierQualityDemoResetResponse,
    SupplierQualityDemoStartRequest,
    SupplierQualityDemoStartResponse,
)

app = FastAPI(
    title="AgentOS Workflow Execution Console",
    version="0.1.0",
)


class _SupplierQualityExecutionEvidence:
    """Process-local adapter for the existing append-only Evidence port."""

    def __init__(self, clock: Callable[[], datetime]) -> None:
        self._clock = clock
        self._records: dict[str, ExecutionEvidenceRecord] = {}
        self._sequence = 0
        self.references: tuple[AuthorizedReference, ...] = ()

    def append(self, record: ExecutionEvidenceRecord) -> AppendResult:
        decorated = replace(record, references=self.references)
        existing = self._records.get(decorated.evidence_record_id)
        if existing is not None:
            if existing.payload_digest != decorated.payload_digest:
                raise EvidenceDigestConflict("EVIDENCE_DIGEST_CONFLICT")
            return AppendResult(AppendDisposition.REPLAYED, existing)
        self._sequence += 1
        stored = decorated.with_repository_metadata(
            storage_sequence=self._sequence,
            recorded_at=self._clock().isoformat().replace("+00:00", "Z"),
        )
        self._records[stored.evidence_record_id] = stored
        return AppendResult(AppendDisposition.APPENDED, stored)

    def high_water_mark(self, scope: AuthorizedEvidenceScope) -> int:
        return max(
            (
                item.storage_sequence or 0
                for item in self._records.values()
                if item.namespace == scope.namespace
                and item.security_domain == scope.security_domain
            ),
            default=0,
        )

    def read_execution(
        self,
        scope: AuthorizedEvidenceScope,
        platform_execution_identity: str,
        *,
        through_high_water_mark: int,
    ) -> tuple[ExecutionEvidenceRecord, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._records.values()
                    if item.namespace == scope.namespace
                    and item.security_domain == scope.security_domain
                    and item.platform_execution_identity == platform_execution_identity
                    and (item.storage_sequence or 0) <= through_high_water_mark
                ),
                key=lambda item: item.storage_sequence or 0,
            )
        )

    def read_subject(
        self,
        scope: AuthorizedEvidenceScope,
        workflow_identity: str,
        task_identity: str,
        *,
        through_high_water_mark: int,
    ) -> tuple[ExecutionEvidenceRecord, ...]:
        return tuple(
            item
            for item in self._records.values()
            if item.namespace == scope.namespace
            and item.security_domain == scope.security_domain
            and item.workflow_identity == workflow_identity
            and item.task_identity == task_identity
            and (item.storage_sequence or 0) <= through_high_water_mark
        )

    @property
    def records(self) -> tuple[ExecutionEvidenceRecord, ...]:
        return tuple(
            sorted(self._records.values(), key=lambda item: item.storage_sequence or 0)
        )


class _SupplierQualityExecutionAuthority:
    """Composition-root access to frozen Core identity and Evidence contracts."""

    def __init__(
        self,
        clock: Callable[[], datetime],
        opaque_id: Callable[[], str],
    ) -> None:
        self._clock = clock
        self._opaque_id = opaque_id
        self.evidence_repository = _SupplierQualityExecutionEvidence(clock)

    @staticmethod
    def scope(namespace: str, security_domain: str) -> AuthorizedEvidenceScope:
        return AuthorizedEvidenceScope(namespace, security_domain)

    def attach_knowledge_references(
        self,
        *,
        namespace: str,
        security_domain: str,
        evidence_id: str,
        citation_ids: tuple[str, ...],
    ) -> None:
        reference_kwargs: dict[str, Any] = {
            "namespace": namespace,
            "security_domain": security_domain,
            "authorization_decision": EvidenceAuthorizationDecision.ALLOW,
            "reason_code": "KNOWLEDGE_REFERENCE_ALLOWED",
            "visibility": ReferenceVisibility.BOTH,
            "source_identity": "knowledge-retrieval",
            "provenance": "live-execution",
        }
        self.evidence_repository.references = (
            AuthorizedReference(
                reference_identity=evidence_id,
                reference_type=ReferenceType.EVIDENCE,
                **reference_kwargs,
            ),
            *(
                AuthorizedReference(
                    reference_identity=citation_id,
                    reference_type=ReferenceType.CITATION,
                    **reference_kwargs,
                )
                for citation_id in citation_ids
            ),
        )

    def create_envelope(
        self,
        *,
        namespace: str,
        definition_id: str,
        task_id: str,
        binding_id: str,
        provider_ref: str,
        runtime_mode: str,
        package_ref: str,
        selection_reason: str,
        configuration: Mapping[str, str],
    ) -> InternalExecutionEnvelope:
        instance_id = mint_agent_instance_id(lambda: f"instance:{self._opaque_id()}")
        execution_identity = mint_platform_execution_identity(
            lambda: f"execution:{self._opaque_id()}"
        )
        definition_ref = AgentDefinitionRef(namespace, definition_id)
        binding = RuntimeBinding(
            binding_id=binding_id,
            provider_ref=provider_ref,
            mode=runtime_mode,
            package_ref=package_ref,
            configuration=configuration,
        )
        return InternalExecutionEnvelope(
            definition_ref=definition_ref,
            selected_instance_id=instance_id,
            execution_identity=execution_identity,
            desired_runtime_binding=DesiredRuntimeBinding(binding),
            effective_runtime_binding=EffectiveRuntimeBinding(
                binding, resolved_at=self._clock()
            ),
            selection_evidence=SelectedInstanceEvidence(
                definition_ref=definition_ref,
                instance_id=instance_id,
                authority="published-role-matching",
                reason=selection_reason,
                selected_at=self._clock(),
            ),
            source_task_ref=SourceTaskRef(namespace, task_id),
        )


def _create_supplier_quality_execution_authority(
    clock: Callable[[], datetime],
    opaque_id: Callable[[], str],
) -> _SupplierQualityExecutionAuthority:
    return _SupplierQualityExecutionAuthority(clock, opaque_id)


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
_supplier_quality_root = os.environ.get("AGENT_CONSOLE_SUPPLIER_QUALITY_ROOT")
_supplier_quality_demo_service = SupplierQualityDemoService(
    materialized_root=(
        None if not _supplier_quality_root else Path(_supplier_quality_root)
    ),
    live_journeys=_live_journey_service,
    execution_authority_factory=_create_supplier_quality_execution_authority,
)
_problem_planning_service = ProblemPlanningService()


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


def get_supplier_quality_demo_service() -> SupplierQualityDemoService:
    """Return the bounded process-local Package 7 composition bridge."""
    return _supplier_quality_demo_service


SupplierQualityDemoDependency = Annotated[
    SupplierQualityDemoService, Depends(get_supplier_quality_demo_service)
]


def get_problem_planning_service() -> ProblemPlanningService:
    return _problem_planning_service


ProblemPlanningDependency = Annotated[
    ProblemPlanningService, Depends(get_problem_planning_service)
]


def _problem_principal(
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")] = "tenant-a",
    security_domain: Annotated[
        str, Header(alias="X-Security-Domain")
    ] = "supplier-quality",
    principal_id: Annotated[
        str, Header(alias="X-Principal-ID")
    ] = "human:supplier-quality-manager",
) -> ProblemPrincipal:
    return ProblemPrincipal(tenant_id, security_domain, principal_id)


ProblemPrincipalDependency = Annotated[ProblemPrincipal, Depends(_problem_principal)]

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


def _demo_http_error(exc: SupplierQualityDemoFailure) -> HTTPException:
    payload = SupplierQualityDemoError(
        state=exc.state,
        reasonCode=exc.reason_code,
        message="Supplier quality live journey is unavailable",
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


@app.post(
    "/api/internal/demo/v1/supplier-quality-journeys",
    response_model=SupplierQualityDemoStartResponse,
    responses={
        403: {"model": SupplierQualityDemoError},
        409: {"model": SupplierQualityDemoError},
        422: {"model": SupplierQualityDemoError},
        503: {"model": SupplierQualityDemoError},
    },
)
def start_supplier_quality_demo(
    request: SupplierQualityDemoStartRequest,
    principal: JourneyPrincipalDependency,
    service: SupplierQualityDemoDependency,
) -> SupplierQualityDemoStartResponse:
    """Start or exactly replay the one authorized Package 7 live journey."""
    try:
        return service.start(request, principal)
    except SupplierQualityDemoFailure as exc:
        raise _demo_http_error(exc) from exc


@app.delete(
    "/api/internal/demo/v1/supplier-quality-journeys/{journey_id}",
    response_model=SupplierQualityDemoResetResponse,
    responses={
        403: {"model": SupplierQualityDemoError},
        404: {"model": SupplierQualityDemoError},
        503: {"model": SupplierQualityDemoError},
    },
)
def reset_supplier_quality_demo(
    journey_id: str,
    request: SupplierQualityDemoResetRequest,
    principal: JourneyPrincipalDependency,
    service: SupplierQualityDemoDependency,
) -> SupplierQualityDemoResetResponse:
    """Clear only exact bridge-owned transient registration and replay state."""
    try:
        return service.reset(journey_id, request, principal)
    except SupplierQualityDemoFailure as exc:
        raise _demo_http_error(exc) from exc
    except JourneyServiceError as exc:
        raise _journey_http_error(exc) from exc


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
    demo_service: SupplierQualityDemoDependency,
) -> LiveJourneyResponse:
    """Return equal Product and Technical projections of one live journey."""
    try:
        if demo_service.owns(journey_id):
            return demo_service.get(journey_id, principal)
        return service.get(journey_id, principal)
    except JourneyServiceError as exc:
        raise _journey_http_error(exc) from exc


@app.get(
    "/api/internal/preview/v1/live-planning-journeys/{journey_id}/events",
    response_class=StreamingResponse,
)
def stream_live_planning_journey(
    journey_id: str,
    request: Request,
    principal: JourneyPrincipalDependency,
    service: JourneyServiceDependency,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Authorize first, then frame one shared backend-issued event stream."""
    try:
        journey = service.get(journey_id, principal)
        identity = journey.successor.identity
        scope = JourneyStreamScope(
            identity.tenantId, identity.securityDomain, journey.journeyId
        )
        # Authorization is deliberately rechecked immediately before cursor access.
        service.get(journey_id, principal)
        subscription = service.event_source.replay_and_subscribe(scope, last_event_id)
    except JourneyServiceError as exc:
        raise _journey_http_error(exc) from exc
    except JourneyResumeUnavailable:
        sequence = service.event_source.next_sequence(scope)
        event = JourneyEventEnvelope(
            journeyId=journey_id,
            eventId=(
                "journey-event:resume:"
                + hashlib.sha256(
                    f"{scope.key}:{last_event_id}:{sequence}".encode()
                ).hexdigest()
            ),
            sequence=sequence,
            occurredAt=datetime.now(UTC),
            eventType="RESUME_UNAVAILABLE",
            stage="RESUME",
            status="UNAVAILABLE",
            terminal=True,
            reasonCode="RESUME_UNAVAILABLE",
            localizationKey="liveJourney.event.resumeUnavailable",
            identity=identity,
            payload=JourneyEventPayload(
                revision=journey.successor.revision,
                limitationCodes=["SAME_PROCESS_REPLAY_UNAVAILABLE"],
            ),
        )

        async def unavailable():
            yield format_sse(event)

        return StreamingResponse(
            unavailable(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except JourneyStreamFailure as exc:
        raise HTTPException(status_code=503, detail=exc.reason_code) from exc

    async def frames():
        try:
            async for event in subscription.events():
                if await request.is_disconnected():
                    break
                # Reauthorize before every replayed or live delivery.
                authorized = service.get(journey_id, principal).successor.identity
                if (
                    authorized.tenantId,
                    authorized.securityDomain,
                    journey_id,
                ) != scope.key:
                    break
                yield format_sse(event)
                if event.terminal:
                    break
        finally:
            subscription.close()

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post(
    "/api/internal/preview/v1/live-planning-journeys/{journey_id}/corrections",
    response_model=LiveJourneyResponse,
)
def correct_live_planning_journey(
    journey_id: str,
    request: CorrectionRequest,
    principal: JourneyPrincipalDependency,
    service: JourneyServiceDependency,
    demo_service: SupplierQualityDemoDependency,
) -> LiveJourneyResponse:
    try:
        if demo_service.owns(journey_id):
            return demo_service.correct(
                journey_id,
                principal,
                predecessor_revision_id=request.predecessorRevisionId,
                predecessor_digest=request.predecessorDigest,
                objective=request.objective,
                reason_code=request.reasonCode,
            )
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
    demo_service: SupplierQualityDemoDependency,
) -> LiveJourneyResponse:
    try:
        if demo_service.owns(journey_id):
            return demo_service.approve(
                journey_id,
                principal,
                candidate_digest=request.candidateDigest,
                decision=request.decision,
                reason_code=request.reasonCode,
                replay_identity=request.replayIdentity,
            )
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
    demo_service: SupplierQualityDemoDependency,
) -> LiveJourneyResponse:
    try:
        if demo_service.owns(journey_id):
            return demo_service.rerun(
                journey_id,
                principal,
                revision_id=request.canonicalWorkflowRevisionId,
                digest=request.canonicalDigest,
            )
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


def _problem_http_error(exc: ProblemPlanningError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail={"reasonCode": exc.reason})


def _problem_analysis_sse(events: Any) -> Any:
    for event in events:
        yield (
            f"id: {event['eventId']}\n"
            f"event: {event['eventType']}\n"
            f"data: {json.dumps(event, ensure_ascii=False, separators=(',', ':'))}\n\n"
        ).encode()


@app.post("/api/internal/v0.2.1/problem-analysis-streams")
def begin_problem_analysis_stream(
    command: dict[str, Any],
    principal: ProblemPrincipalDependency,
    service: ProblemPlanningDependency,
) -> StreamingResponse:
    """Emit real incremental interpretation and pause for Human clarification."""
    try:
        events = service.begin_analysis(command, principal)
        return StreamingResponse(
            _problem_analysis_sse(events), media_type="text/event-stream"
        )
    except ProblemPlanningError as exc:
        raise _problem_http_error(exc) from exc


@app.post("/api/internal/v0.2.1/problem-analysis-streams/{stream_id}/resume")
def resume_problem_analysis_stream(
    stream_id: str,
    response: dict[str, Any],
    principal: ProblemPrincipalDependency,
    service: ProblemPlanningDependency,
) -> StreamingResponse:
    """Resume after Human clarification and stream real planning artifacts."""
    try:
        events = service.resume_analysis(stream_id, response, principal)
        return StreamingResponse(
            _problem_analysis_sse(events), media_type="text/event-stream"
        )
    except ProblemPlanningError as exc:
        raise _problem_http_error(exc) from exc


@app.get("/api/internal/v0.2.1/problem-analysis-streams/{stream_id}/events")
def replay_problem_analysis_stream(
    stream_id: str,
    principal: ProblemPrincipalDependency,
    service: ProblemPlanningDependency,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Authorized replay after one exact event without duplicate delivery."""
    try:
        events = service.replay_analysis(stream_id, last_event_id, principal)
        return StreamingResponse(
            _problem_analysis_sse(events), media_type="text/event-stream"
        )
    except ProblemPlanningError as exc:
        raise _problem_http_error(exc) from exc


@app.post("/api/internal/v0.2.1/problems")
def create_problem_plan(
    command: dict[str, Any],
    principal: ProblemPrincipalDependency,
    service: ProblemPlanningDependency,
) -> dict[str, Any]:
    """Submit a formal Problem and produce one reviewable inert plan."""
    try:
        return service.create(command, principal)
    except (ProblemPlanningError, httpx.HTTPError) as exc:
        failure = (
            exc
            if isinstance(exc, ProblemPlanningError)
            else ProblemPlanningError("CONTROLLED_PROVIDER_UNAVAILABLE", 503)
        )
        raise _problem_http_error(failure) from exc


@app.get("/api/internal/v0.2.1/problems")
def list_problem_plans(
    principal: ProblemPrincipalDependency,
    service: ProblemPlanningDependency,
) -> list[dict[str, Any]]:
    return service.list(principal)


@app.get("/api/internal/v0.2.1/problems/{problem_id}")
def get_problem_plan(
    problem_id: str,
    principal: ProblemPrincipalDependency,
    service: ProblemPlanningDependency,
) -> dict[str, Any]:
    try:
        return service.get(problem_id, principal)
    except ProblemPlanningError as exc:
        raise _problem_http_error(exc) from exc


@app.post("/api/internal/v0.2.1/problems/{problem_id}/corrections")
def correct_problem_plan(
    problem_id: str,
    command: dict[str, Any],
    principal: ProblemPrincipalDependency,
    service: ProblemPlanningDependency,
) -> dict[str, Any]:
    try:
        return service.correct(problem_id, command, principal)
    except ProblemPlanningError as exc:
        raise _problem_http_error(exc) from exc


@app.post("/api/internal/v0.2.1/problems/{problem_id}/interventions")
def intervene_problem_plan(
    problem_id: str,
    command: dict[str, Any],
    principal: ProblemPrincipalDependency,
    service: ProblemPlanningDependency,
) -> dict[str, Any]:
    """Record one governed Human decision and create an immutable successor."""
    try:
        return service.intervene(problem_id, command, principal)
    except ProblemPlanningError as exc:
        raise _problem_http_error(exc) from exc


@app.post("/api/internal/v0.2.1/problems/{problem_id}/approvals")
def approve_problem_plan(
    problem_id: str,
    command: dict[str, Any],
    principal: ProblemPrincipalDependency,
    service: ProblemPlanningDependency,
) -> dict[str, Any]:
    try:
        return service.approve(problem_id, command, principal)
    except ProblemPlanningError as exc:
        raise _problem_http_error(exc) from exc
