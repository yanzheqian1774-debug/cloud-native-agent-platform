"""Private Skill/MCP Workbench API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from agent_console.skill_mcp_postgres import PostgresSkillMcpRepository
from agent_console.skill_mcp_repository import SkillMcpRepositoryError
from agent_console.skill_mcp_schemas import (
    BindCommand,
    CloneCommand,
    CreateResource,
    DiscoveryCommand,
    EditResource,
    ImportManifest,
    InvokeCommand,
    LifecycleCommand,
    McpInvocationCommand,
    PublishCommand,
    ReviewCommand,
    TestCaseCommand,
    ToolSelectionCommand,
    VersionCommand,
)
from agent_console.skill_mcp_service import SkillMcpFailure, SkillMcpService

router = APIRouter(prefix="/api/internal/v0.2.2/resources")
_service: SkillMcpService | None = None
_startup_error = "SKILL_MCP_STORAGE_UNAVAILABLE"


def configure() -> None:
    global _service, _startup_error
    database_url = os.environ.get("SKILL_MCP_DATABASE_URL", "")
    if not database_url:
        return
    try:
        migration = (
            Path(__file__).parents[2] / "migrations" / "0002_skill_mcp_lifecycle.sql"
        )
        repository = PostgresSkillMcpRepository(
            database_url,
            migration_path=migration,
            min_pool_size=int(os.environ.get("SKILL_MCP_DB_POOL_MIN", "1")),
            max_pool_size=int(os.environ.get("SKILL_MCP_DB_POOL_MAX", "4")),
            timeout=float(os.environ.get("SKILL_MCP_DB_TIMEOUT_SECONDS", "5")),
        )
        repository.migrate()
        _service = SkillMcpService(repository)
        _startup_error = ""
    except (SkillMcpRepositoryError, ValueError):
        _service = None
        _startup_error = "SKILL_MCP_STORAGE_UNAVAILABLE"


configure()


def get_skill_mcp_service() -> SkillMcpService:
    if _service is None:
        raise HTTPException(503, detail={"reasonCode": _startup_error})
    return _service


Service = Annotated[SkillMcpService, Depends(get_skill_mcp_service)]


def principal(
    tenant: Annotated[str, Header(alias="X-Tenant-ID")] = "tenant-a",
    domain: Annotated[str, Header(alias="X-Security-Domain")] = "supplier-quality",
    actor: Annotated[
        str, Header(alias="X-Principal-ID")
    ] = "human:supplier-quality-manager",
) -> tuple[str, str, str]:
    return tenant, domain, actor


Principal = Annotated[tuple[str, str, str], Depends(principal)]


def call(operation):
    try:
        return operation()
    except SkillMcpFailure as exc:
        raise HTTPException(exc.status, detail={"reasonCode": exc.reason}) from exc


@router.get("/{kind}")
def list_resources(kind: str, p: Principal, service: Service):
    return call(lambda: service.list(service.scope(p[0], p[1]), kind))


@router.post("/{kind}", status_code=201)
def create_resource(kind: str, command: CreateResource, p: Principal, service: Service):
    return call(
        lambda: service.project(
            service.create(
                service.scope(p[0], p[1]),
                kind,
                p[2],
                command.name,
                command.content.model_dump(),
            )
        )
    )


@router.post("/{kind}/manifest-import", status_code=201)
def import_manifest(kind: str, command: ImportManifest, p: Principal, service: Service):
    if command.manifestVersion != "skill-mcp-workbench/v1" or command.kind != kind:
        raise HTTPException(422, detail={"reasonCode": "MANIFEST_BOUNDARY_INVALID"})
    return call(
        lambda: service.project(
            service.create(
                service.scope(p[0], p[1]),
                kind,
                p[2],
                command.name,
                command.content.model_dump(),
            )
        )
    )


@router.get("/{kind}/{resource_id}")
def get_resource(kind: str, resource_id: str, p: Principal, service: Service):
    return call(lambda: service.get(service.scope(p[0], p[1]), kind, resource_id))


@router.get("/{kind}/{resource_id}/manifest")
def export_manifest(kind: str, resource_id: str, p: Principal, service: Service):
    return call(
        lambda: service.export_manifest(service.scope(p[0], p[1]), kind, resource_id)
    )


@router.post("/{kind}/{resource_id}/clones", status_code=201)
def clone_resource(
    kind: str,
    resource_id: str,
    command: CloneCommand,
    p: Principal,
    service: Service,
):
    return call(
        lambda: service.clone(
            service.scope(p[0], p[1]),
            kind,
            resource_id,
            p[2],
            command.revisionId,
            command.name,
        )
    )


@router.put("/{kind}/{resource_id}/draft")
def edit_resource(
    kind: str, resource_id: str, command: EditResource, p: Principal, service: Service
):
    return call(
        lambda: service.edit(
            service.scope(p[0], p[1]),
            kind,
            resource_id,
            p[2],
            command.expectedVersion,
            command.content.model_dump(),
        )
    )


@router.post("/{kind}/{resource_id}/validation")
def validate_resource(
    kind: str, resource_id: str, command: VersionCommand, p: Principal, service: Service
):
    return call(
        lambda: service.validate(
            service.scope(p[0], p[1]), kind, resource_id, p[2], command.expectedVersion
        )
    )


@router.post("/{kind}/{resource_id}/reviews")
def review_resource(
    kind: str, resource_id: str, command: ReviewCommand, p: Principal, service: Service
):
    return call(
        lambda: service.review(
            service.scope(p[0], p[1]),
            kind,
            resource_id,
            p[2],
            command.expectedVersion,
            command.digest,
            command.decision,
            command.reason,
        )
    )


@router.post("/{kind}/{resource_id}/publications")
def publish_resource(
    kind: str, resource_id: str, command: PublishCommand, p: Principal, service: Service
):
    return call(
        lambda: service.publish(
            service.scope(p[0], p[1]),
            kind,
            resource_id,
            p[2],
            command.expectedVersion,
            command.digest,
            command.reviewId,
        )
    )


@router.post("/{kind}/{resource_id}/successors")
def successor_resource(
    kind: str, resource_id: str, command: VersionCommand, p: Principal, service: Service
):
    return call(
        lambda: service.successor(
            service.scope(p[0], p[1]), kind, resource_id, p[2], command.expectedVersion
        )
    )


@router.get("/{kind}/{resource_id}/deletion-impact")
def deletion_impact(kind: str, resource_id: str, p: Principal, service: Service):
    return call(lambda: service.impact(service.scope(p[0], p[1]), kind, resource_id))


@router.post("/skill/{resource_id}/bindings")
def bind_resource(
    resource_id: str, command: BindCommand, p: Principal, service: Service
):
    return call(
        lambda: service.bind(
            service.scope(p[0], p[1]),
            resource_id,
            p[2],
            command.expectedVersion,
            command.skillRevisionId,
            command.mcpResourceId,
            command.mcpRevisionId,
            command.capability,
            command.reason,
        )
    )


@router.post("/skill/{resource_id}/invocations")
def invoke_resource(
    resource_id: str, command: InvokeCommand, p: Principal, service: Service
):
    return call(
        lambda: service.invoke(
            service.scope(p[0], p[1]),
            resource_id,
            p[2],
            command.expectedVersion,
            command.bindingId,
            command.authorization,
            command.input,
        )
    )


@router.post("/skill/{resource_id}/tests")
def save_test(
    resource_id: str, command: TestCaseCommand, p: Principal, service: Service
):
    return call(
        lambda: service.save_test(
            service.scope(p[0], p[1]),
            resource_id,
            p[2],
            command.expectedVersion,
            command.name,
            command.input,
            command.expected,
        )
    )


@router.post("/skill/{resource_id}/tests/{test_id}/runs")
def run_test(
    resource_id: str,
    test_id: str,
    command: VersionCommand,
    p: Principal,
    service: Service,
):
    return call(
        lambda: service.run_test(
            service.scope(p[0], p[1]),
            resource_id,
            p[2],
            command.expectedVersion,
            test_id,
        )
    )


@router.post("/mcp/{resource_id}/health")
def health(resource_id: str, command: DiscoveryCommand, p: Principal, service: Service):
    return call(
        lambda: service.health(
            service.scope(p[0], p[1]),
            resource_id,
            p[2],
            command.expectedVersion,
            command.timeoutSeconds,
        )
    )


@router.post("/mcp/{resource_id}/discovery")
def discover(
    resource_id: str, command: DiscoveryCommand, p: Principal, service: Service
):
    return call(
        lambda: service.discover(
            service.scope(p[0], p[1]),
            resource_id,
            p[2],
            command.expectedVersion,
            command.timeoutSeconds,
        )
    )


@router.post("/mcp/{resource_id}/tool-selections")
def select_tools(
    resource_id: str, command: ToolSelectionCommand, p: Principal, service: Service
):
    return call(
        lambda: service.select_tools(
            service.scope(p[0], p[1]),
            resource_id,
            p[2],
            command.expectedVersion,
            command.snapshotId,
            command.toolNames,
            command.reason,
        )
    )


@router.post("/mcp/{resource_id}/tool-invocations")
def invoke_mcp(
    resource_id: str, command: McpInvocationCommand, p: Principal, service: Service
):
    return call(
        lambda: service.invoke_mcp(
            service.scope(p[0], p[1]),
            resource_id,
            p[2],
            command.expectedVersion,
            command.selectionId,
            command.toolName,
            command.authorization,
            command.input,
            command.timeoutSeconds,
            command.cancelRequested,
        )
    )


@router.post("/{kind}/{resource_id}/{action}")
def lifecycle_resource(
    kind: str,
    resource_id: str,
    action: str,
    command: LifecycleCommand,
    p: Principal,
    service: Service,
):
    return call(
        lambda: service.lifecycle(
            service.scope(p[0], p[1]),
            kind,
            resource_id,
            p[2],
            command.expectedVersion,
            action.upper(),
            command.reason,
        )
    )


@router.delete("/{kind}/{resource_id}", status_code=204)
def delete_resource(
    kind: str, resource_id: str, expectedVersion: int, p: Principal, service: Service
):
    call(
        lambda: service.delete_draft(
            service.scope(p[0], p[1]), kind, resource_id, p[2], expectedVersion
        )
    )
    return Response(status_code=204)
