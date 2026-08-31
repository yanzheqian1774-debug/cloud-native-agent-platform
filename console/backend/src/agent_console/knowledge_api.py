# ruff: noqa: B008
"""Private Knowledge Workbench API and deployment composition."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from agent_console.knowledge_lifecycle_service import (
    KnowledgeLifecycleFailure,
    KnowledgeLifecycleService,
)
from agent_console.knowledge_postgres import PostgresKnowledgeRepository
from agent_console.knowledge_qdrant import QdrantKnowledgeError, QdrantKnowledgeIndex
from agent_console.knowledge_quality import (
    KnowledgeQualityFailure,
    KnowledgeQualityService,
)
from agent_console.knowledge_repository import (
    KnowledgeNotFound,
    KnowledgeRepositoryError,
    KnowledgeScope,
)
from agent_console.knowledge_schemas import (
    CreateKnowledge,
    DigestCommand,
    DuplicateDecisionCommand,
    EvaluationCommand,
    ImportPreviewCommand,
    KnowledgeResponse,
    PurgeCommand,
    RetrievalCommand,
    SearchCommand,
    SuccessorCommand,
    VersionCommand,
)

router = APIRouter(
    prefix="/api/internal/v0.2.2/knowledge", tags=["knowledge-workbench"]
)
_service: KnowledgeLifecycleService | None = None
_quality_service: KnowledgeQualityService | None = None
_startup_error = "KNOWLEDGE_STORAGE_UNAVAILABLE"


def configure() -> None:
    global _service, _quality_service, _startup_error
    database_url = os.environ.get("KNOWLEDGE_DATABASE_URL", "")
    qdrant_url = os.environ.get("KNOWLEDGE_QDRANT_URL", "")
    if not database_url or not qdrant_url:
        return
    try:
        migration = (
            Path(__file__).parents[2] / "migrations" / "0003_knowledge_operations.sql"
        )
        repository = PostgresKnowledgeRepository(
            database_url,
            migration_path=migration,
            quality_migration_path=Path(__file__).parents[2]
            / "migrations"
            / "0005_knowledge_quality_operations.sql",
            min_pool_size=int(os.environ.get("KNOWLEDGE_DB_POOL_MIN", "1")),
            max_pool_size=int(os.environ.get("KNOWLEDGE_DB_POOL_MAX", "4")),
            timeout=float(os.environ.get("KNOWLEDGE_DB_TIMEOUT_SECONDS", "5")),
        )
        repository.migrate()
        repository.migrate_quality()
        qdrant = QdrantKnowledgeIndex(qdrant_url)
        qdrant.ensure_collection()
        _service = KnowledgeLifecycleService(repository, qdrant)
        _quality_service = KnowledgeQualityService(repository, qdrant)
        _startup_error = ""
    except (KnowledgeRepositoryError, QdrantKnowledgeError, ValueError):
        _service = None
        _quality_service = None
        _startup_error = "KNOWLEDGE_STORAGE_UNAVAILABLE"


configure()


def get_knowledge_service() -> KnowledgeLifecycleService:
    if _service is None:
        raise HTTPException(503, detail={"reasonCode": _startup_error})
    return _service


def get_quality_service() -> KnowledgeQualityService:
    if _quality_service is None:
        raise HTTPException(503, detail={"reasonCode": _startup_error})
    return _quality_service


def trusted_scope(
    x_namespace: str = Header(default="tenant-a", alias="X-Tenant-ID"),
    x_security_domain: str = Header(
        default="supplier-quality", alias="X-Security-Domain"
    ),
) -> KnowledgeScope:
    return KnowledgeLifecycleService.scope(x_namespace, x_security_domain)


def actor(
    x_actor: str = Header(default="human:workbench", alias="X-Principal-ID"),
) -> str:
    return x_actor


def call(operation):
    try:
        return operation()
    except KnowledgeNotFound as exc:
        raise HTTPException(
            status_code=404, detail={"reasonCode": "KNOWLEDGE_NOT_FOUND"}
        ) from exc
    except (
        KnowledgeLifecycleFailure,
        KnowledgeQualityFailure,
        KnowledgeRepositoryError,
        ValueError,
    ) as exc:
        code = (
            str(exc)
            if str(exc).isupper() or "_" in str(exc)
            else "KNOWLEDGE_OPERATION_FAILED"
        )
        status_code = 404 if code == "KNOWLEDGE_ACCESS_DENIED" else 409
        if code in {"KNOWLEDGE_STORAGE_UNAVAILABLE", "QDRANT_UNAVAILABLE"}:
            status_code = 503
        raise HTTPException(
            status_code=status_code, detail={"reasonCode": code}
        ) from exc


@router.get("/operations/dashboard")
def quality_dashboard(
    scope: KnowledgeScope = Depends(trusted_scope),
    service: KnowledgeQualityService = Depends(get_quality_service),
):
    return call(lambda: service.dashboard(scope))


@router.post("/operations/search")
def quality_search(
    command: SearchCommand,
    scope: KnowledgeScope = Depends(trusted_scope),
    service: KnowledgeQualityService = Depends(get_quality_service),
):
    return call(
        lambda: service.search(
            scope,
            query=command.query,
            mode=command.mode,
            top_k=command.topK,
            knowledge_id=command.knowledgeId,
            source_id=command.sourceId,
            document_id=command.documentId,
            content_type=command.contentType,
            revision_id=command.revisionId,
            snapshot_id=command.snapshotId,
        )
    )


@router.get("/operations/metadata")
def quality_metadata(
    scope: KnowledgeScope = Depends(trusted_scope),
    service: KnowledgeQualityService = Depends(get_quality_service),
):
    return call(lambda: service.metadata(scope))


@router.get("/operations/evaluations")
def quality_evaluation_runs(
    scope: KnowledgeScope = Depends(trusted_scope),
    service: KnowledgeQualityService = Depends(get_quality_service),
):
    return call(
        lambda: service.repository.list_quality_entities(scope, "EVALUATION_RUN")
    )


@router.post("/operations/evaluations")
def quality_evaluate(
    command: EvaluationCommand,
    scope: KnowledgeScope = Depends(trusted_scope),
    service: KnowledgeQualityService = Depends(get_quality_service),
):
    return call(lambda: service.evaluate(scope, command.model_dump()))


@router.post("/operations/imports/preview")
def quality_import_preview(
    command: ImportPreviewCommand,
    scope: KnowledgeScope = Depends(trusted_scope),
    service: KnowledgeQualityService = Depends(get_quality_service),
):
    return call(
        lambda: service.import_preview(
            scope, format=command.format, content=command.content
        )
    )


@router.post("/operations/imports/{import_job_id}/execute")
def quality_import_execute(
    import_job_id: str,
    scope: KnowledgeScope = Depends(trusted_scope),
    current_actor: str = Depends(actor),
    service: KnowledgeQualityService = Depends(get_quality_service),
):
    return call(lambda: service.execute_import(scope, import_job_id, current_actor))


@router.get("/operations/export")
def quality_export(
    scope: KnowledgeScope = Depends(trusted_scope),
    service: KnowledgeQualityService = Depends(get_quality_service),
):
    return call(lambda: service.export(scope))


@router.post("/operations/duplicates/scan")
def quality_duplicates(
    scope: KnowledgeScope = Depends(trusted_scope),
    service: KnowledgeQualityService = Depends(get_quality_service),
):
    return call(lambda: service.duplicates(scope))


@router.get("/operations/duplicates")
def quality_duplicate_queue(
    scope: KnowledgeScope = Depends(trusted_scope),
    service: KnowledgeQualityService = Depends(get_quality_service),
):
    return call(lambda: service.duplicate_queue(scope))


@router.post("/operations/duplicates/decisions")
def quality_duplicate_decision(
    command: DuplicateDecisionCommand,
    scope: KnowledgeScope = Depends(trusted_scope),
    current_actor: str = Depends(actor),
    service: KnowledgeQualityService = Depends(get_quality_service),
):
    return call(
        lambda: service.decide_duplicate(
            scope,
            candidate_id=command.candidateId,
            classification=command.classification,
            actor=current_actor,
        )
    )


@router.post("/{knowledge_id}/operations/summaries")
def quality_summary(
    knowledge_id: str,
    scope: KnowledgeScope = Depends(trusted_scope),
    service: KnowledgeQualityService = Depends(get_quality_service),
):
    return call(lambda: service.summarize(scope, knowledge_id))


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


@router.post("/{knowledge_id}/successors", response_model=KnowledgeResponse)
def successor(
    knowledge_id: str,
    command: SuccessorCommand,
    scope: KnowledgeScope = Depends(trusted_scope),
    current_actor: str = Depends(actor),
    service: KnowledgeLifecycleService = Depends(get_knowledge_service),
):
    return call(
        lambda: service.successor(
            scope,
            knowledge_id,
            current_actor,
            command.expectedVersion,
            command.content,
        )
    )


@router.post("/{knowledge_id}/retrievals", response_model=KnowledgeResponse)
def retrieve(
    knowledge_id: str,
    command: RetrievalCommand,
    scope: KnowledgeScope = Depends(trusted_scope),
    current_actor: str = Depends(actor),
    service: KnowledgeLifecycleService = Depends(get_knowledge_service),
):
    return call(
        lambda: service.retrieve(
            scope,
            knowledge_id,
            current_actor,
            command.expectedVersion,
            command.authorization,
            command.authorizationDecisionId,
            command.query,
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
