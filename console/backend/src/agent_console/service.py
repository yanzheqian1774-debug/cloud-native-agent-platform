"""Application services for the Workflow Execution Console."""

from agent_console.projection import (
    project_workflow_detail,
    project_workflow_summary,
)
from agent_console.repository import WorkflowRepository
from agent_console.schemas import (
    WorkflowExecutionDetail,
    WorkflowRunList,
)


class WorkflowService:
    """Read-only Workflow execution use cases."""

    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def list_workflows(self) -> WorkflowRunList:
        workflows = self._repository.list_workflows()

        items = [project_workflow_summary(workflow) for workflow in workflows]

        items.sort(
            key=lambda item: item.createdAt or "",
            reverse=True,
        )

        return WorkflowRunList(items=items)

    def get_workflow(
        self,
        namespace: str,
        name: str,
    ) -> WorkflowExecutionDetail:
        workflow = self._repository.get_workflow(
            namespace=namespace,
            name=name,
        )

        tasks = self._repository.list_workflow_tasks(
            namespace=namespace,
            workflow_name=name,
        )

        return project_workflow_detail(
            workflow,
            tasks,
        )
