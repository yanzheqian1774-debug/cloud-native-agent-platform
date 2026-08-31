import os
import uuid
from pathlib import Path

import pytest
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_postgres import PostgresKnowledgeRepository
from agent_console.knowledge_repository import KnowledgeConflict

DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL required")
MIGRATION = Path(__file__).parents[1] / "migrations" / "0003_knowledge_operations.sql"


def test_real_postgresql_migration_scope_and_optimistic_concurrency():
    store = PostgresKnowledgeRepository(DATABASE_URL or "", migration_path=MIGRATION)
    store.migrate()
    service = KnowledgeLifecycleService(store)
    scope = service.scope(f"knowledge-postgres-{uuid.uuid4()}", "quality")
    created = service.create(
        scope,
        "human:owner",
        "Postgres Knowledge",
        {
            "sourceId": "source:postgres",
            "documentId": "document:postgres",
            "provenance": "human:owner",
            "content": "Authoritative procedure.",
        },
    )["knowledge"]
    changed = {**created, "aggregateVersion": 2}
    store.replace(
        changed,
        expected_version=1,
        fact={"factId": f"knowledge-fact:{uuid.uuid4()}", "event": "CONFORMANCE"},
    )
    with pytest.raises(KnowledgeConflict):
        store.replace(
            changed,
            expected_version=1,
            fact={"factId": f"knowledge-fact:{uuid.uuid4()}", "event": "STALE"},
        )
    assert store.list(service.scope("foreign", "quality")) == []
    store.pool.close()
