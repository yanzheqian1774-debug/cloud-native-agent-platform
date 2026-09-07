# ruff: noqa: E501
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from agent_console.resource_use_application import (
    ResourceUseApplicationService,
    ScopedResourceUseAuthorization,
)
from agent_console.resource_use_domain import (
    ResourceKind,
    ResourceUseBinding,
    ResourceUseConflict,
    ResourceUseFact,
    ResourceUseFactKind,
    canonical_digest,
    canonical_record,
    stable_id,
)
from agent_console.resource_use_knowledge import commit_knowledge_retrieval
from agent_console.resource_use_postgres import PostgresResourceUseRepository
from agent_core.execution_contract import ScopeIdentity

DATABASE_URL = os.environ.get("RESOURCE_USE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATION = Path(__file__).parents[1] / "migrations/0015_resource_use_measurement.sql"


def test_postgres_cas_idempotency_cardinality_restart_and_scope() -> None:
    suffix = uuid.uuid4().hex
    scope = ScopeIdentity(f"resource-use-{suffix}", "acceptance")
    ids = {
        name: f"{name}:{suffix}"
        for name in (
            "definition",
            "revision",
            "employee",
            "assignment",
            "workflow-definition",
            "plan",
            "workflow",
            "task",
            "attempt",
        )
    }
    digest = "a" * 64
    with psycopg.connect(DATABASE_URL or "") as connection:
        connection.execute(
            "INSERT INTO workflow_definition.definitions(namespace,security_domain,workflow_definition_id,aggregate_version,record) VALUES(%s,%s,%s,1,'{}')",
            (scope.namespace, scope.security_domain, ids["workflow-definition"]),
        )
        connection.execute(
            """INSERT INTO execution_authority.plans(namespace,security_domain,plan_id,plan_version,
            workflow_definition_id,workflow_definition_revision_id,workflow_definition_digest,status,
            plan_digest,canonical_bytes,created_at,updated_at) VALUES(%s,%s,%s,1,%s,'revision:1',%s,'APPROVED',%s,'{}',now(),now())""",
            (
                scope.namespace,
                scope.security_domain,
                ids["plan"],
                ids["workflow-definition"],
                digest,
                digest,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.digital_employee_instances(namespace,security_domain,digital_employee_instance_id,definition_revision_id,aggregate_version,record) VALUES(%s,%s,%s,%s,1,'{}')",
            (scope.namespace, scope.security_domain, ids["employee"], ids["revision"]),
        )
        connection.execute(
            "INSERT INTO execution_authority.assignments(namespace,security_domain,assignment_id,digital_employee_instance_id,approved_input_digest,record) VALUES(%s,%s,%s,%s,%s,'{}')",
            (
                scope.namespace,
                scope.security_domain,
                ids["assignment"],
                ids["employee"],
                digest,
            ),
        )
        connection.execute(
            """INSERT INTO execution_authority.workflow_runs(namespace,security_domain,workflow_run_id,
            assignment_id,approved_plan_revision_id,record,control_state,plan_id,plan_version,approved_plan_digest)
            VALUES(%s,%s,%s,%s,'revision:1','{}','RUNNING',%s,1,%s)""",
            (
                scope.namespace,
                scope.security_domain,
                ids["workflow"],
                ids["assignment"],
                ids["plan"],
                digest,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.task_runs(namespace,security_domain,task_run_id,workflow_run_id,record) VALUES(%s,%s,%s,%s,'{}')",
            (scope.namespace, scope.security_domain, ids["task"], ids["workflow"]),
        )
        connection.execute(
            "INSERT INTO execution_authority.attempts(namespace,security_domain,attempt_id,task_run_id,aggregate_digest,record) VALUES(%s,%s,%s,%s,%s,'{}')",
            (
                scope.namespace,
                scope.security_domain,
                ids["attempt"],
                ids["task"],
                digest,
            ),
        )
        connection.execute(
            "INSERT INTO digital_employee_definition.definitions(namespace,security_domain,definition_id,aggregate_version) VALUES(%s,%s,%s,1)",
            (scope.namespace, scope.security_domain, ids["definition"]),
        )
        connection.execute(
            "INSERT INTO digital_employee_definition.revisions(namespace,security_domain,definition_id,revision_id,digest,record) VALUES(%s,%s,%s,%s,%s,'{}')",
            (
                scope.namespace,
                scope.security_domain,
                ids["definition"],
                ids["revision"],
                digest,
            ),
        )
        connection.execute(
            "INSERT INTO digital_employee_definition.instance_bindings(namespace,security_domain,digital_employee_instance_id,definition_id,revision_id,digest) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                scope.namespace,
                scope.security_domain,
                ids["employee"],
                ids["definition"],
                ids["revision"],
                digest,
            ),
        )
        connection.execute(
            """INSERT INTO digital_employee_definition.execution_bindings(namespace,security_domain,
            attempt_id,digital_employee_instance_id,definition_id,revision_id,digest,plan_digest,
            approval_id,authorization_decision_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'approval:1','decision:1')""",
            (
                scope.namespace,
                scope.security_domain,
                ids["attempt"],
                ids["employee"],
                ids["definition"],
                ids["revision"],
                digest,
                digest,
            ),
        )
    use_id = stable_id(
        "resource-use",
        scope.namespace,
        scope.security_domain,
        ids["attempt"],
        "KNOWLEDGE",
        "knowledge:primary",
        "1",
    )
    binding = ResourceUseBinding(
        scope,
        use_id,
        ids["attempt"],
        ResourceKind.KNOWLEDGE,
        "knowledge:primary",
        1,
        "knowledge:1",
        "knowledge-revision:1",
        digest,
        "binding:1",
        digest,
        ids["plan"],
        1,
        digest,
        ids["workflow"],
        ids["task"],
        ids["definition"],
        ids["revision"],
        digest,
        ids["employee"],
        None,
        None,
        "knowledge-retrieval.v1",
        "1",
        "qdrant",
        "1",
        "decision:1",
    )
    now = datetime.now(UTC)
    facts = (
        ResourceUseFact(
            "fact:dispatch",
            use_id,
            ResourceUseFactKind.DISPATCH_RECORDED,
            "KNOWLEDGE_ATTEMPT",
            "binding:1",
            digest,
            now,
            now,
        ),
    )
    payload = canonical_digest(
        {"binding": canonical_record(binding), "facts": [canonical_record(facts[0])]}
    )
    repo = PostgresResourceUseRepository(DATABASE_URL or "", migration_path=MIGRATION)
    repo.migrate()
    first = repo.prepare_dispatch(
        binding, facts, idempotency_key="dispatch:1", payload_digest=payload
    )
    assert (
        repo.prepare_dispatch(
            binding, facts, idempotency_key="dispatch:1", payload_digest=payload
        )
        == first
    )
    with pytest.raises(
        ResourceUseConflict, match="RESOURCE_USE_IDEMPOTENCY_PAYLOAD_MISMATCH"
    ):
        changed = (
            ResourceUseFact(
                "fact:changed",
                use_id,
                ResourceUseFactKind.DISPATCH_RECORDED,
                "KNOWLEDGE_ATTEMPT",
                "binding:changed",
                digest,
                now,
                now,
            ),
        )
        repo.prepare_dispatch(
            binding,
            changed,
            idempotency_key="dispatch:1",
            payload_digest=canonical_digest(
                {
                    "binding": canonical_record(binding),
                    "facts": [canonical_record(changed[0])],
                }
            ),
        )
    assert repo.count(scope) == 1
    assert repo.get_snapshot(ScopeIdentity(scope.namespace, "other"), use_id) is None
    service = ResourceUseApplicationService(
        repo,
        ScopedResourceUseAuthorization(
            scope,
            "actor:1",
            frozenset({"WRITE", "READ", "LIST", "COUNT"}),
            "decision:1",
        ),
    )
    evidence = {
        "evidence": {
            "evidenceId": "knowledge-evidence:1",
            "evidenceDigest": digest,
            "retrievalState": "RETRIEVED",
            "reason": None,
            "citations": [{"citationId": "citation:1"}],
        }
    }
    observed = commit_knowledge_retrieval(
        service,
        scope,
        use_id,
        evidence,
        observed_at=now,
        expected_high_water=1,
        idempotency_key="knowledge:1",
    )
    assert observed.high_water == 2
    assert observed.measurement_ids
    assert (
        commit_knowledge_retrieval(
            service,
            scope,
            use_id,
            evidence,
            observed_at=now,
            expected_high_water=1,
            idempotency_key="knowledge:1",
        )
        == observed
    )
    with pytest.raises(ResourceUseConflict, match="RESOURCE_USE_CAS_MISMATCH"):
        commit_knowledge_retrieval(
            service,
            scope,
            use_id,
            {
                **evidence,
                "evidence": {
                    **evidence["evidence"],
                    "evidenceId": "knowledge-evidence:late",
                },
            },
            observed_at=now,
            expected_high_water=1,
            idempotency_key="knowledge:late",
        )
    repo.close()
    restarted = PostgresResourceUseRepository(
        DATABASE_URL or "", migration_path=MIGRATION
    )
    assert restarted.get_snapshot(scope, use_id) == observed
    restarted.close()
