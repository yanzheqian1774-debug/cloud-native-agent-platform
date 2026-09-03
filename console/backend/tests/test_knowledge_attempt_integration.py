# ruff: noqa: E501
import contextlib
import json
import os
import uuid
from pathlib import Path

import psycopg
import pytest
from agent_console.knowledge_attempt_postgres import (
    PostgresAttemptKnowledgeEvidenceRepository,
)
from agent_console.knowledge_attempt_retrieval import (
    AttemptKnowledgeRequest,
    AttemptKnowledgeRetrievalService,
)
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_p1_bootstrap import bootstrap_p1_knowledge
from agent_console.knowledge_postgres import PostgresKnowledgeRepository
from agent_console.knowledge_qdrant import QdrantKnowledgeIndex

DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")
QDRANT_URL = os.environ.get("KNOWLEDGE_TEST_QDRANT_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not QDRANT_URL, reason="real PostgreSQL 15 and Qdrant required"
)
MIGRATIONS = Path(__file__).parents[1] / "migrations"


def test_real_postgres_qdrant_attempt_retrieval_restart_and_cleanup():
    suffix = uuid.uuid4().hex
    namespace, domain = f"knowledge-attempt-{suffix}", "supplier-quality"
    attempt_id, employee_id = f"attempt:{suffix}", f"digital-employee:{suffix}"
    qdrant = QdrantKnowledgeIndex(
        QDRANT_URL or "", collection=f"knowledge_attempt_{suffix}"
    )
    knowledge = PostgresKnowledgeRepository(
        DATABASE_URL or "", migration_path=MIGRATIONS / "0003_knowledge_operations.sql"
    )
    evidence = PostgresAttemptKnowledgeEvidenceRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0012_knowledge_attempt_retrieval.sql",
    )
    scope = KnowledgeLifecycleService.scope(namespace, domain)
    snapshot_id = "knowledge-snapshot:p1-supplier-quality-v1"
    try:
        knowledge.migrate()
        with psycopg.connect(DATABASE_URL or "") as connection:
            connection.execute(
                (MIGRATIONS / "0008_execution_runtime_authority.sql").read_text()
            )
            connection.execute(
                "INSERT INTO execution_authority.digital_employee_instances(namespace,security_domain,digital_employee_instance_id,definition_revision_id,aggregate_version,record) VALUES (%s,%s,%s,'definition:p1',1,'{}')",
                (namespace, domain, employee_id),
            )
            connection.execute(
                "INSERT INTO execution_authority.assignments(namespace,security_domain,assignment_id,digital_employee_instance_id,approved_input_digest,record) VALUES (%s,%s,%s,%s,%s,'{}')",
                (namespace, domain, f"assignment:{suffix}", employee_id, "a" * 64),
            )
            connection.execute(
                "INSERT INTO execution_authority.workflow_runs(namespace,security_domain,workflow_run_id,assignment_id,approved_plan_revision_id,record) VALUES (%s,%s,%s,%s,'plan:p1','{}')",
                (namespace, domain, f"workflow-run:{suffix}", f"assignment:{suffix}"),
            )
            connection.execute(
                "INSERT INTO execution_authority.task_runs(namespace,security_domain,task_run_id,workflow_run_id,record) VALUES (%s,%s,%s,%s,'{}')",
                (namespace, domain, f"task-run:{suffix}", f"workflow-run:{suffix}"),
            )
            attempt_record = {
                "assignment": {"digital_employee_instance_id": employee_id}
            }
            connection.execute(
                "INSERT INTO execution_authority.attempts(namespace,security_domain,attempt_id,task_run_id,aggregate_digest,record) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    namespace,
                    domain,
                    attempt_id,
                    f"task-run:{suffix}",
                    "b" * 64,
                    json.dumps(attempt_record),
                ),
            )
        evidence.migrate()
        qdrant.ensure_collection()
        lifecycle = KnowledgeLifecycleService(knowledge, qdrant)
        record = bootstrap_p1_knowledge(lifecycle, scope)["knowledge"]
        revision = record["revisions"][0]
        request = AttemptKnowledgeRequest(
            attempt_id,
            employee_id,
            None,
            f"knowledge-binding:{suffix}",
            record["knowledgeId"],
            revision["revisionId"],
            revision["digest"],
            snapshot_id,
            "ALLOW",
            f"authorization:{suffix}",
            "根因 永久纠正措施",
        )
        result = AttemptKnowledgeRetrievalService(knowledge, evidence, qdrant).retrieve(
            scope, request
        )
        assert result["retrievalState"] == "RETRIEVED"
        evidence.pool.close()
        evidence = PostgresAttemptKnowledgeEvidenceRepository(
            DATABASE_URL or "",
            migration_path=MIGRATIONS / "0012_knowledge_attempt_retrieval.sql",
        )
        evidence.migrate()
        assert (
            evidence.get_evidence(scope, result["evidence"]["evidenceId"])
            == result["evidence"]
        )
    finally:
        with contextlib.suppress(Exception):
            qdrant.delete_snapshot(
                namespace, domain, "knowledge:p1-supplier-quality", snapshot_id
            )
        with psycopg.connect(DATABASE_URL or "") as connection:
            connection.execute(
                "DELETE FROM knowledge_attempt.retrieval_evidence WHERE namespace=%s",
                (namespace,),
            )
            connection.execute(
                "DELETE FROM knowledge_attempt.bindings WHERE namespace=%s",
                (namespace,),
            )
            connection.execute(
                "DELETE FROM knowledge_operation.lifecycle_facts WHERE namespace=%s",
                (namespace,),
            )
            connection.execute(
                "DELETE FROM knowledge_operation.knowledge WHERE namespace=%s",
                (namespace,),
            )
            for table in (
                "attempts",
                "task_runs",
                "workflow_runs",
                "assignments",
                "digital_employee_instances",
            ):
                connection.execute(
                    f"DELETE FROM execution_authority.{table} WHERE namespace=%s",
                    (namespace,),
                )
        evidence.pool.close()
        knowledge.pool.close()
