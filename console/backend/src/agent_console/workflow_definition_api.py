"""Private Workflow Definition Workbench API."""

import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from agent_console.agent_binding_validation import BindingResolution
from agent_console.agent_definition_repository import DefinitionScope
from agent_console.runtime_profile_api import get_service as get_runtime_profile_service
from agent_console.workflow_definition_postgres import (
    PostgresWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_repository import (
    WorkflowDefinitionRepositoryError,
)
from agent_console.workflow_definition_schemas import (
    CreateWorkflowDefinition,
    EditWorkflowDefinition,
    PublishCommand,
    ReviewCommand,
    VersionCommand,
)
from agent_console.workflow_definition_service import (
    WorkflowDefinitionFailure,
    WorkflowDefinitionService,
)

router = APIRouter(prefix="/api/internal/v0.2.2/workflow-definitions")
_service = None
_startup_error = "WORKFLOW_DEFINITION_STORAGE_UNAVAILABLE"


class WorkflowDefinitionBindingResolver:
    """Expose published Workflow facts through the durable Agent binding port."""

    def resolve(
        self, scope: DefinitionScope, kind: str, resource_id: str
    ) -> BindingResolution | None:
        if kind != "workflow" or _service is None:
            return None
        try:
            record = _service.repository.get(
                _service.scope(scope.namespace, scope.security_domain), resource_id
            )
        except Exception:
            return None
        revision_id = record.get("publishedRevisionId")
        revision = next(
            (
                item
                for item in record.get("revisions", [])
                if item["revisionId"] == revision_id
            ),
            None,
        )
        if revision is None:
            return None
        digest = revision["digest"]
        if digest.startswith("sha256:"):
            digest = digest.removeprefix("sha256:")
        return BindingResolution(
            resource_id=record["workflowDefinitionId"],
            revision_id=revision["revisionId"],
            digest=digest,
            published=revision["state"] == "PUBLISHED",
            enabled=record.get("enabled", True),
            deprecated=record.get("lifecycleState") == "DEPRECATED",
            compatible=record.get("compatible", True),
        )


binding_resolver = WorkflowDefinitionBindingResolver()


def configure():
    global _service, _startup_error
    url = os.environ.get("WORKFLOW_RUNTIME_DATABASE_URL", "")
    if not url:
        return
    try:
        repository = PostgresWorkflowDefinitionRepository(
            url,
            migration_path=Path(__file__).parents[2]
            / "migrations"
            / "0007_workflow_runtime_profiles.sql",
        )
        repository.migrate()

        def resolve(scope, reference):
            if reference["kind"] != "RUNTIME_PROFILE":
                return False
            try:
                profile = get_runtime_profile_service().repository.get(
                    get_runtime_profile_service().scope(
                        scope.namespace, scope.security_domain
                    ),
                    reference["resourceId"],
                )
            except Exception:
                return False
            return any(
                revision["revisionId"] == reference["revisionId"]
                and revision["digest"] == reference.get("digest", revision["digest"])
                and revision["state"] == "PUBLISHED"
                for revision in profile["revisions"]
            )

        _service = WorkflowDefinitionService(repository, resolve)
        _startup_error = ""
    except (WorkflowDefinitionRepositoryError, ValueError):
        _service = None


configure()


def get_service():
    if _service is None:
        raise HTTPException(503, detail={"reasonCode": _startup_error})
    return _service


Service = Annotated[WorkflowDefinitionService, Depends(get_service)]


def principal(
    tenant: Annotated[str, Header(alias="X-Tenant-ID")] = "tenant-a",
    domain: Annotated[str, Header(alias="X-Security-Domain")] = "supplier-quality",
    actor: Annotated[str, Header(alias="X-Principal-ID")] = "human:workflow-owner",
):
    return tenant, domain, actor


Principal = Annotated[tuple[str, str, str], Depends(principal)]


def call(operation):
    try:
        return operation()
    except WorkflowDefinitionFailure as exc:
        raise HTTPException(exc.status, detail={"reasonCode": exc.reason}) from exc


@router.get("")
def list_definitions(p: Principal, service: Service):
    return call(lambda: service.list(service.scope(p[0], p[1])))


@router.post("", status_code=201)
def create_definition(
    command: CreateWorkflowDefinition, p: Principal, service: Service
):
    return call(
        lambda: service.project(
            service.create(
                service.scope(p[0], p[1]),
                p[2],
                command.name,
                command.content.model_dump(),
            )
        )
    )


@router.get("/{resource_id}")
def get_definition(resource_id: str, p: Principal, service: Service):
    return call(lambda: service.get(service.scope(p[0], p[1]), resource_id))


@router.get("/{resource_id}/comparison")
def compare_definitions(
    resource_id: str,
    leftRevisionId: str,
    rightRevisionId: str,
    p: Principal,
    service: Service,
):
    return call(
        lambda: service.compare(
            service.scope(p[0], p[1]),
            resource_id,
            leftRevisionId,
            rightRevisionId,
        )
    )


@router.put("/{resource_id}/draft")
def edit_definition(
    resource_id: str, command: EditWorkflowDefinition, p: Principal, service: Service
):
    return call(
        lambda: service.project(
            service.edit(
                service.scope(p[0], p[1]),
                resource_id,
                p[2],
                command.expectedVersion,
                command.content.model_dump(),
            )
        )
    )


@router.post("/{resource_id}/validation")
def validate_definition(
    resource_id: str, command: VersionCommand, p: Principal, service: Service
):
    return call(
        lambda: service.project(
            service.validate(
                service.scope(p[0], p[1]), resource_id, p[2], command.expectedVersion
            )
        )
    )


@router.post("/{resource_id}/reviews")
def review_definition(
    resource_id: str, command: ReviewCommand, p: Principal, service: Service
):
    return call(
        lambda: service.project(
            service.review(
                service.scope(p[0], p[1]),
                resource_id,
                p[2],
                command.expectedVersion,
                command.digest,
                command.decision,
                command.reason,
            )
        )
    )


@router.post("/{resource_id}/publications")
def publish_definition(
    resource_id: str, command: PublishCommand, p: Principal, service: Service
):
    return call(
        lambda: service.project(
            service.publish(
                service.scope(p[0], p[1]),
                resource_id,
                p[2],
                command.expectedVersion,
                command.digest,
                command.reviewId,
            )
        )
    )


@router.post("/{resource_id}/successors")
def successor_definition(
    resource_id: str, command: VersionCommand, p: Principal, service: Service
):
    return call(
        lambda: service.project(
            service.successor(
                service.scope(p[0], p[1]), resource_id, p[2], command.expectedVersion
            )
        )
    )
