import contextlib
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.knowledge_attempt_postgres import (
    PostgresAttemptKnowledgeEvidenceRepository,
)
from agent_console.knowledge_attempt_retrieval import (
    AttemptKnowledgeFailure,
    AttemptKnowledgeRequest,
    AttemptKnowledgeRetrievalService,
)
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_p1_bootstrap import bootstrap_p1_knowledge
from agent_console.knowledge_postgres import PostgresKnowledgeRepository
from agent_console.knowledge_qdrant import QdrantKnowledgeIndex
from agent_console.resource_use_application import (
    ResourceUseApplicationService,
    ScopedResourceUseAuthorization,
)
from agent_console.resource_use_domain import (
    ResourceKind,
    ResourceUseBinding,
    stable_id,
)
from agent_console.resource_use_postgres import PostgresResourceUseRepository
from agent_core.execution_contract import ScopeIdentity
from employee_identity_support import start_chain
from test_execution_application_postgres import approved_plan

DATABASE_URL = os.environ.get("RESOURCE_USE_TEST_DATABASE_URL")
QDRANT_URL = os.environ.get("KNOWLEDGE_TEST_QDRANT_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL or not QDRANT_URL,
    reason="real dedicated PostgreSQL 15 and Qdrant required",
)
MIGRATIONS = Path(__file__).parents[1] / "migrations"


class CountingIndex:
    def __init__(self, target):
        self.target = target
        self.search_count = 0

    def search(self, *args, **kwargs):
        self.search_count += 1
        return self.target.search(*args, **kwargs)


class TerminalRollbackRepository(PostgresResourceUseRepository):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.insert_count = 0

    def _insert_facts(self, connection, scope, facts, offset):
        self.insert_count += 1
        if self.insert_count == 2:
            raise RuntimeError("INJECTED_TERMINAL_ROLLBACK")
        return super()._insert_facts(connection, scope, facts, offset)


def scenario(repository_type=PostgresResourceUseRepository):
    suffix = uuid.uuid4().hex
    authority = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    employee_revision, instance, _, command, started = start_chain(
        authority, DATABASE_URL or "", approved_plan(suffix)
    )
    execution = started.identity
    knowledge = PostgresKnowledgeRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0003_knowledge_operations.sql",
    )
    evidence = PostgresAttemptKnowledgeEvidenceRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0012_knowledge_attempt_retrieval.sql",
    )
    qdrant = QdrantKnowledgeIndex(QDRANT_URL or "", collection=f"resource_use_{suffix}")
    resource_repository = repository_type(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0015_resource_use_measurement.sql",
    )
    knowledge.migrate()
    evidence.migrate()
    resource_repository.migrate()
    qdrant.ensure_collection()
    scope = KnowledgeLifecycleService.scope(
        execution.scope.namespace, execution.scope.security_domain
    )
    record = bootstrap_p1_knowledge(
        KnowledgeLifecycleService(knowledge, qdrant), scope
    )["knowledge"]
    revision = record["revisions"][0]
    request = AttemptKnowledgeRequest(
        str(execution.attempt.attempt_id),
        str(instance.instance_id),
        None,
        f"knowledge-binding:{suffix}",
        record["knowledgeId"],
        revision["revisionId"],
        revision["digest"],
        record["activeIndexSnapshotId"],
        "ALLOW",
        "execution-decision",
        "根因 永久纠正措施",
    )
    knowledge_binding = {
        "namespace": scope.namespace,
        "securityDomain": scope.security_domain,
        "bindingId": request.binding_id,
        "attemptId": request.attempt_id,
        "digitalEmployeeInstanceId": request.digital_employee_instance_id,
        "agentInstanceId": None,
        "knowledgeId": request.knowledge_id,
        "revisionId": request.revision_id,
        "revisionDigest": request.revision_digest,
        "snapshotId": request.snapshot_id,
        "authorizationDecisionId": request.authorization_decision_id,
    }
    from agent_console.knowledge_pack import canonical_digest as knowledge_digest

    binding_digest = knowledge_digest(
        knowledge_binding, domain="attempt-knowledge-binding.v1"
    )
    resource_scope = ScopeIdentity(scope.namespace, scope.security_domain)
    use_id = stable_id(
        "resource-use",
        scope.namespace,
        scope.security_domain,
        request.attempt_id,
        "KNOWLEDGE",
        "knowledge:primary",
        "1",
    )
    binding = ResourceUseBinding(
        resource_scope,
        use_id,
        request.attempt_id,
        ResourceKind.KNOWLEDGE,
        "knowledge:primary",
        1,
        request.knowledge_id,
        request.revision_id,
        request.revision_digest,
        request.binding_id,
        binding_digest,
        command.approved_plan.plan_id,
        command.approved_plan.plan_version,
        command.approved_plan.plan_digest,
        str(execution.workflow_run.workflow_run_id),
        str(execution.task_run.task_run_id),
        employee_revision.definition_id,
        employee_revision.revision_id,
        employee_revision.digest,
        str(instance.instance_id),
        None,
        None,
        "knowledge-retrieval.v1",
        "1",
        "qdrant",
        "1",
        "execution-decision",
    )
    application = ResourceUseApplicationService(
        resource_repository,
        ScopedResourceUseAuthorization(
            resource_scope,
            "test",
            frozenset({"WRITE", "READ"}),
            "execution-decision",
        ),
    )
    counting = CountingIndex(qdrant)
    retrieval = AttemptKnowledgeRetrievalService(knowledge, evidence, counting)
    return {
        "authority": authority,
        "knowledge": knowledge,
        "evidence": evidence,
        "qdrant": qdrant,
        "resource": resource_repository,
        "application": application,
        "retrieval": retrieval,
        "counting": counting,
        "scope": scope,
        "request": request,
        "binding": binding,
    }


def close(value):
    for name in ("evidence", "knowledge", "resource", "authority"):
        with contextlib.suppress(Exception):
            value[name].pool.close()


def test_real_postgres_qdrant_atomic_terminal_restart_and_zero_redispatch():
    value = scenario()
    try:
        first = value["retrieval"].retrieve_with_resource_use(
            value["scope"],
            value["request"],
            value["application"],
            value["binding"],
        )
        assert first["retrievalState"] == "RETRIEVED"
        assert value["counting"].search_count == 1
        assert (
            value["resource"]
            .get_snapshot(value["binding"].scope, value["binding"].resource_use_id)
            .high_water
            == 2
        )
        restarted_evidence = PostgresAttemptKnowledgeEvidenceRepository(
            DATABASE_URL or "",
            migration_path=MIGRATIONS / "0012_knowledge_attempt_retrieval.sql",
        )
        restarted_resource = PostgresResourceUseRepository(
            DATABASE_URL or "",
            migration_path=MIGRATIONS / "0015_resource_use_measurement.sql",
        )
        restarted = AttemptKnowledgeRetrievalService(
            value["knowledge"], restarted_evidence, value["counting"]
        )
        replay = restarted.retrieve_with_resource_use(
            value["scope"],
            value["request"],
            ResourceUseApplicationService(
                restarted_resource, value["application"].authorization
            ),
            value["binding"],
        )
        assert replay == first
        assert value["counting"].search_count == 1
        restarted_evidence.pool.close()
        restarted_resource.pool.close()
    finally:
        close(value)


def test_terminal_rollback_leaves_durable_dispatch_and_recovery_never_redispatches():
    value = scenario(TerminalRollbackRepository)
    try:
        with pytest.raises(RuntimeError, match="INJECTED_TERMINAL_ROLLBACK"):
            value["retrieval"].retrieve_with_resource_use(
                value["scope"],
                value["request"],
                value["application"],
                value["binding"],
            )
        assert value["counting"].search_count == 1
        assert (
            value["evidence"].get_evidence_for_binding(
                value["scope"], value["request"].binding_id
            )
            is None
        )
        restarted_resource = PostgresResourceUseRepository(
            DATABASE_URL or "",
            migration_path=MIGRATIONS / "0015_resource_use_measurement.sql",
        )
        recovery = AttemptKnowledgeRetrievalService(
            value["knowledge"], value["evidence"], value["counting"]
        )
        with pytest.raises(
            AttemptKnowledgeFailure, match="KNOWLEDGE_RESULT_PENDING_CONFIRMATION"
        ):
            recovery.retrieve_with_resource_use(
                value["scope"],
                value["request"],
                ResourceUseApplicationService(
                    restarted_resource, value["application"].authorization
                ),
                value["binding"],
            )
        assert value["counting"].search_count == 1
        restarted_resource.pool.close()
    finally:
        close(value)


def test_exact_lineage_rejection_precedes_qdrant_and_concurrent_replay_is_single_call():
    value = scenario()
    try:
        with pytest.raises(ValueError, match="RESOURCE_USE_LINEAGE_MISMATCH"):
            value["retrieval"].retrieve_with_resource_use(
                value["scope"],
                value["request"],
                value["application"],
                replace(value["binding"], plan_digest="f" * 64),
            )
        assert value["counting"].search_count == 0
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    value["retrieval"].retrieve_with_resource_use,
                    value["scope"],
                    value["request"],
                    value["application"],
                    value["binding"],
                )
                for _ in range(2)
            ]
            results, pending = [], []
            for future in futures:
                try:
                    results.append(future.result())
                except AttemptKnowledgeFailure as error:
                    pending.append(str(error))
        assert len(results) + len(pending) == 2
        assert results
        assert set(pending) <= {"KNOWLEDGE_RESULT_PENDING_CONFIRMATION"}
        assert all(result == results[0] for result in results)
        assert value["counting"].search_count == 1
    finally:
        close(value)
