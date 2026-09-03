import os
import uuid
from pathlib import Path

import pytest
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_postgres import PostgresKnowledgeRepository
from agent_console.knowledge_qdrant import QdrantKnowledgeIndex

DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")
QDRANT_URL = os.environ.get("KNOWLEDGE_TEST_QDRANT_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not QDRANT_URL,
    reason="real disposable PostgreSQL and Qdrant required",
)
MIGRATION = Path(__file__).parents[1] / "migrations" / "0003_knowledge_operations.sql"


def test_real_pv106_lifecycle_ingestion_retrieval_and_citation_readback():
    namespace = f"pv106-{uuid.uuid4()}"
    repository = PostgresKnowledgeRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    repository.migrate()
    index = QdrantKnowledgeIndex(
        QDRANT_URL or "", collection=f"pv106_{uuid.uuid4().hex}"
    )
    service = KnowledgeLifecycleService(repository, index)
    scope = service.scope(namespace, "supplier-quality-preview")

    try:
        value = service.create(
            scope,
            "human:public-preview-owner",
            "PV106 Supplier Quality Knowledge",
            {
                "sourceId": "preview:pv106:source",
                "documentId": "preview:pv106:procedure",
                "provenance": "human-approved:sanitized-public-preview",
                "content": (
                    "Supplier quality anomalies require verified facts and a "
                    "reviewed corrective plan."
                ),
            },
        )["knowledge"]
        value = service.validate(
            scope, value["knowledgeId"], "human:public-preview-owner", 1
        )["knowledge"]
        revision = value["revisions"][-1]
        value = service.review(
            scope,
            value["knowledgeId"],
            "human:public-preview-reviewer",
            2,
            revision["digest"],
        )["knowledge"]
        value = service.publish(
            scope,
            value["knowledgeId"],
            "human:public-preview-publisher",
            3,
            revision["digest"],
        )["knowledge"]
        value = service.ingest(
            scope, value["knowledgeId"], "human:public-preview-operator", 4
        )["knowledge"]
        snapshot_id = value["activeIndexSnapshotId"]
        assert value["lifecycleState"] == "AVAILABLE" and snapshot_id

        value = service.retrieve(
            scope,
            value["knowledgeId"],
            "human:public-preview-owner",
            5,
            "ALLOW",
            "authorization:pv106:integration",
            "corrective plan",
        )["knowledge"]
        readback = service.get(scope, value["knowledgeId"])["knowledge"]
        retrieval = readback["retrievals"][-1]
        citation = retrieval["citations"][0]

        assert retrieval["snapshotId"] == snapshot_id
        assert citation["knowledgeId"] == readback["knowledgeId"]
        assert citation["revisionId"] == revision["revisionId"]
        assert citation["revisionDigest"] == revision["digest"]
        assert citation["documentDigest"] and citation["chunkDigest"]
    finally:
        if "snapshot_id" in locals():
            index.delete_snapshot(
                scope.namespace,
                scope.security_domain,
                value["knowledgeId"],
                snapshot_id,
            )
        index.client.close()
        repository.pool.close()
