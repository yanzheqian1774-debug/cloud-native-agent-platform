"""FastAPI application for the AgentOS Workflow Execution Console."""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from kubernetes.client.exceptions import ApiException

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
