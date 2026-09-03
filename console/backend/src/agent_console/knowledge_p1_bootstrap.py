"""Deterministic real-domain bootstrap for the later local P1 demonstration."""

from __future__ import annotations

from typing import Any

from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_repository import KnowledgeScope


def bootstrap_p1_knowledge(
    service: KnowledgeLifecycleService,
    scope: KnowledgeScope,
    *,
    actor: str = "human:p1-bootstrap",
) -> dict[str, Any]:
    """Use lifecycle APIs only; callers own an isolated scope and cleanup."""
    created = service.create(
        scope,
        actor,
        "供应商质量 8D 纠正措施知识",
        {
            "sourceId": "knowledge-source:p1-supplier-quality-8d",
            "collectionId": "knowledge-collection:p1-supplier-quality",
            "documentId": "knowledge-document:p1-8d-corrective-action",
            "documentVersion": "1",
            "kind": "TEXT",
            "provenance": "DEMO_CONFIGURATION",
            "content": "供应商必须先完成遏制措施,再验证根因和永久纠正措施。",
        },
        knowledge_id="knowledge:p1-supplier-quality",
        revision_id="knowledge-revision:p1-supplier-quality-v1",
    )["knowledge"]
    validated = service.validate(
        scope, created["knowledgeId"], actor, created["aggregateVersion"]
    )["knowledge"]
    reviewed = service.review(
        scope,
        created["knowledgeId"],
        actor,
        validated["aggregateVersion"],
        validated["revisions"][0]["digest"],
    )["knowledge"]
    published = service.publish(
        scope,
        created["knowledgeId"],
        actor,
        reviewed["aggregateVersion"],
        reviewed["revisions"][0]["digest"],
    )["knowledge"]
    return service.ingest(
        scope,
        created["knowledgeId"],
        actor,
        published["aggregateVersion"],
        job_id="knowledge-ingestion:p1-supplier-quality-v1",
        snapshot_id="knowledge-snapshot:p1-supplier-quality-v1",
    )
