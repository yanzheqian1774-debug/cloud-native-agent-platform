# ruff: noqa: B008
"""Standalone Knowledge router; shared app assembly is intentionally deferred."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from agent_console.knowledge_lifecycle_service import (
    KnowledgeLifecycleFailure,
    KnowledgeLifecycleService,
)
from agent_console.knowledge_repository import (
    KnowledgeNotFound,
    KnowledgeRepositoryError,
    KnowledgeScope,
)
from agent_console.knowledge_schemas import (
    CreateKnowledge,
    DigestCommand,
    KnowledgeResponse,
    PurgeCommand,
    VersionCommand,
)

router = APIRouter(
    prefix="/api/internal/v0.2.2/knowledge", tags=["knowledge-workbench"]
)


def get_knowledge_service() -> KnowledgeLifecycleService:
    raise RuntimeError("KNOWLEDGE_SERVICE_NOT_ASSEMBLED")


def trusted_scope(
    x_namespace: str = Header(default="default"),
    x_security_domain: str = Header(default="default"),
) -> KnowledgeScope:
    return KnowledgeLifecycleService.scope(x_namespace, x_security_domain)


def actor(x_actor: str = Header(default="human:workbench")) -> str:
    return x_actor


def call(operation):
    try:
        return operation()
    except KnowledgeNotFound as exc:
        raise HTTPException(
            status_code=404, detail={"reasonCode": "KNOWLEDGE_NOT_FOUND"}
        ) from exc
    except (KnowledgeLifecycleFailure, KnowledgeRepositoryError, ValueError) as exc:
        code = (
            str(exc)
            if str(exc).isupper() or "_" in str(exc)
            else "KNOWLEDGE_OPERATION_FAILED"
        )
        raise HTTPException(status_code=409, detail={"reasonCode": code}) from exc


@router.get("")
def list_knowledge(
    scope: KnowledgeScope = Depends(trusted_scope),
    service: KnowledgeLifecycleService = Depends(get_knowledge_service),
):
    return call(lambda: service.list(scope))


@router.post("", status_code=status.HTTP_201_CREATED, response_model=KnowledgeResponse)
def create_knowledge(
    command: CreateKnowledge,
    scope: KnowledgeScope = Depends(trusted_scope),
    current_actor: str = Depends(actor),
    service: KnowledgeLifecycleService = Depends(get_knowledge_service),
):
    return call(
        lambda: service.create(
            scope, current_actor, command.name, command.source.model_dump()
        )
    )


@router.get("/{knowledge_id}", response_model=KnowledgeResponse)
def get_knowledge(
    knowledge_id: str,
    scope: KnowledgeScope = Depends(trusted_scope),
    service: KnowledgeLifecycleService = Depends(get_knowledge_service),
):
    return call(lambda: service.get(scope, knowledge_id))


def _route(action: str):
    def endpoint(
        knowledge_id: str,
        command: VersionCommand,
        scope: KnowledgeScope = Depends(trusted_scope),
        current_actor: str = Depends(actor),
        service: KnowledgeLifecycleService = Depends(get_knowledge_service),
    ):
        return call(
            lambda: getattr(service, action)(
                scope, knowledge_id, current_actor, command.expectedVersion
            )
        )

    return endpoint


router.post("/{knowledge_id}/validation", response_model=KnowledgeResponse)(
    _route("validate")
)
router.post("/{knowledge_id}/ingestion", response_model=KnowledgeResponse)(
    _route("ingest")
)
router.post("/{knowledge_id}/rebuild", response_model=KnowledgeResponse)(
    _route("rebuild")
)
router.post("/{knowledge_id}/recovery", response_model=KnowledgeResponse)(
    _route("recover")
)
router.post("/{knowledge_id}/archive", response_model=KnowledgeResponse)(
    _route("archive")
)


@router.post("/{knowledge_id}/reviews", response_model=KnowledgeResponse)
def review(
    knowledge_id: str,
    command: DigestCommand,
    scope: KnowledgeScope = Depends(trusted_scope),
    current_actor: str = Depends(actor),
    service: KnowledgeLifecycleService = Depends(get_knowledge_service),
):
    return call(
        lambda: service.review(
            scope, knowledge_id, current_actor, command.expectedVersion, command.digest
        )
    )


@router.post("/{knowledge_id}/publications", response_model=KnowledgeResponse)
def publish(
    knowledge_id: str,
    command: DigestCommand,
    scope: KnowledgeScope = Depends(trusted_scope),
    current_actor: str = Depends(actor),
    service: KnowledgeLifecycleService = Depends(get_knowledge_service),
):
    return call(
        lambda: service.publish(
            scope, knowledge_id, current_actor, command.expectedVersion, command.digest
        )
    )


@router.post("/{knowledge_id}/purge")
def purge(
    knowledge_id: str,
    command: PurgeCommand,
    response: Response,
    scope: KnowledgeScope = Depends(trusted_scope),
    current_actor: str = Depends(actor),
    service: KnowledgeLifecycleService = Depends(get_knowledge_service),
):
    result = call(
        lambda: service.purge(
            scope,
            knowledge_id,
            current_actor,
            command.expectedVersion,
            command.authorizationId,
            command.reasonClassification,
        )
    )
    if result.get("knowledge", {}).get("lifecycleState") == "RECOVERY_REQUIRED":
        response.status_code = 202
    return result
