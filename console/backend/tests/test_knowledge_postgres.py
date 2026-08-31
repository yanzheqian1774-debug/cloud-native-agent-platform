import os
import uuid
from pathlib import Path

import pytest
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_postgres import PostgresKnowledgeRepository
from agent_console.knowledge_repository import KnowledgeConflict, KnowledgeNotFound

DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL required")
MIGRATION = Path(__file__).parents[1] / "migrations" / "0003_knowledge_operations.sql"
QUALITY_MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "0005_knowledge_quality_operations.sql"
)


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


def test_real_postgresql_authorized_purge_reduces_history_to_tombstone():
    store = PostgresKnowledgeRepository(DATABASE_URL or "", migration_path=MIGRATION)
    store.migrate()
    service = KnowledgeLifecycleService(store)
    scope = service.scope(f"knowledge-purge-{uuid.uuid4()}", "quality")
    created = service.create(
        scope,
        "human:owner",
        "Purge Knowledge",
        {
            "sourceId": "source:purge",
            "documentId": "document:purge",
            "provenance": "human:owner",
            "content": "Prohibited payload.",
        },
    )["knowledge"]
    store.tombstone(
        scope,
        created["knowledgeId"],
        expected_version=1,
        tombstone={
            "knowledgeId": created["knowledgeId"],
            "authorizationId": "authorization:test",
            "reasonClassification": "PROHIBITED_CONTENT",
            "status": "COMPLETED",
        },
    )
    with pytest.raises(KnowledgeNotFound):
        store.get(scope, created["knowledgeId"])
    with store.pool.connection() as connection:
        row = connection.execute(
            "SELECT tombstone FROM knowledge_operation.purge_tombstones "
            "WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s",
            (scope.namespace, scope.security_domain, created["knowledgeId"]),
        ).fetchone()
    assert row is not None and "Prohibited payload" not in str(row["tombstone"])
    store.pool.close()


def test_real_postgresql_quality_migration_is_checksum_bound_and_scoped():
    store = PostgresKnowledgeRepository(
        DATABASE_URL or "",
        migration_path=MIGRATION,
        quality_migration_path=QUALITY_MIGRATION,
    )
    store.migrate()
    store.migrate_quality()
    scope = KnowledgeLifecycleService.scope(
        f"knowledge-quality-{uuid.uuid4()}", "quality"
    )
    record = {
        "namespace": scope.namespace,
        "securityDomain": scope.security_domain,
        "entityType": "METRIC_FACT",
        "entityId": "metric:test",
        "digest": "a" * 64,
        "body": {"status": "NOT_MEASURABLE"},
    }
    store.put_quality_entity(record)
    assert store.list_quality_entities(scope) == [record]
    assert (
        store.list_quality_entities(
            KnowledgeLifecycleService.scope("foreign", "quality")
        )
        == []
    )
    changed = {
        **record,
        "digest": "b" * 64,
        "body": {"status": "MEASURABLE"},
    }
    store.put_quality_entity(changed)
    store.pool.close()
    recovered = PostgresKnowledgeRepository(
        DATABASE_URL or "",
        migration_path=MIGRATION,
        quality_migration_path=QUALITY_MIGRATION,
    )
    recovered.migrate()
    recovered.migrate_quality()
    assert recovered.list_quality_entities(scope) == [changed]
    recovered.pool.close()
