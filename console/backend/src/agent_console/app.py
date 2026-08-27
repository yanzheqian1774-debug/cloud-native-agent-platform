"""FastAPI application for the AgentOS Workflow Execution Console."""

import os
from pathlib import Path
from typing import Annotated

from agent_core.execution_evidence import SQLiteExecutionEvidenceRepository
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from kubernetes.client.exceptions import ApiException

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
