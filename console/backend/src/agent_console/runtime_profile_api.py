"""Private Runtime Profile Workbench API."""

import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from agent_console.runtime_profile_postgres import PostgresRuntimeProfileRepository
from agent_console.runtime_profile_repository import RuntimeProfileRepositoryError
from agent_console.runtime_profile_schemas import (
    CreateRuntimeProfile,
    EditRuntimeProfile,
    PublishCommand,
    ReviewCommand,
    VersionCommand,
)
from agent_console.runtime_profile_service import (
    RuntimeProfileFailure,
    RuntimeProfileService,
)

router = APIRouter(prefix="/api/internal/v0.2.2/runtime-profiles")
_service = None
_startup_error = "RUNTIME_PROFILE_STORAGE_UNAVAILABLE"


def configure():
    global _service, _startup_error
    url = os.environ.get("WORKFLOW_RUNTIME_DATABASE_URL", "")
    if not url:
        return
    try:
        repository = PostgresRuntimeProfileRepository(
            url,
            migration_path=Path(__file__).parents[2]
            / "migrations"
            / "0007_workflow_runtime_profiles.sql",
        )
        repository.migrate()
        _service = RuntimeProfileService(repository)
        _startup_error = ""
    except (RuntimeProfileRepositoryError, ValueError):
        _service = None


configure()


def get_service():
    if _service is None:
        raise HTTPException(503, detail={"reasonCode": _startup_error})
    return _service


Service = Annotated[RuntimeProfileService, Depends(get_service)]


def principal(
    tenant: Annotated[str, Header(alias="X-Tenant-ID")] = "tenant-a",
    domain: Annotated[str, Header(alias="X-Security-Domain")] = "supplier-quality",
    actor: Annotated[str, Header(alias="X-Principal-ID")] = "human:runtime-owner",
):
    return tenant, domain, actor


Principal = Annotated[tuple[str, str, str], Depends(principal)]


def call(operation):
    try:
        return operation()
    except RuntimeProfileFailure as exc:
        raise HTTPException(exc.status, detail={"reasonCode": exc.reason}) from exc


@router.get("")
def list_profiles(p: Principal, service: Service):
    return call(lambda: service.list(service.scope(p[0], p[1])))


@router.post("", status_code=201)
def create_profile(command: CreateRuntimeProfile, p: Principal, service: Service):
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
def get_profile(resource_id: str, p: Principal, service: Service):
    return call(lambda: service.get(service.scope(p[0], p[1]), resource_id))


@router.put("/{resource_id}/draft")
def edit_profile(
    resource_id: str, command: EditRuntimeProfile, p: Principal, service: Service
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
def validate_profile(
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
def review_profile(
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
def publish_profile(
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
def successor_profile(
    resource_id: str, command: VersionCommand, p: Principal, service: Service
):
    return call(
        lambda: service.project(
            service.successor(
                service.scope(p[0], p[1]), resource_id, p[2], command.expectedVersion
            )
        )
    )
