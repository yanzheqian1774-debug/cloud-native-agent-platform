# ruff: noqa: E501
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from agent_console.business_problem_domain import (
    BusinessProblemConflict,
    BusinessProblemNotAuthorized,
    BusinessProblemRevision,
    BusinessProblemState,
    CriterionType,
    PlanProblemBinding,
    SuccessCriteriaSetRevision,
    SuccessCriterionRevision,
    canonical_digest,
)
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.execution_domain import ScopeIdentity

DATABASE_URL = os.environ.get("EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")
MIGRATIONS = Path(__file__).parents[1] / "migrations"


@pytest.fixture(autouse=True)
def isolated_database() -> None:
    global DATABASE_URL
    original_url = DATABASE_URL or ""
    database_name = f"impl261_{uuid.uuid4().hex}"
    admin = psycopg.connect(original_url, autocommit=True)
    admin.execute(f'CREATE DATABASE "{database_name}"')
    DATABASE_URL = original_url.rsplit("/", 1)[0] + f"/{database_name}"
    try:
        yield
    finally:
        DATABASE_URL = original_url
        admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
            (database_name,),
        )
        admin.execute(f'DROP DATABASE "{database_name}"')
        admin.close()


def repository() -> PostgresBusinessProblemRepository:
    with psycopg.connect(DATABASE_URL or "") as connection:
        for version in range(1, 13):
            connection.execute(
                next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
            )
    value = PostgresBusinessProblemRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0013_business_problem_authority.sql",
    )
    value.migrate()
    return value


def test_durable_history_scope_cas_idempotency_and_exact_plan_binding() -> None:
    store = repository()
    suffix = uuid.uuid4().hex
    scope = ScopeIdentity(f"tenant-{suffix}", "domain")
    now = datetime.now(UTC)
    problem = BusinessProblemRevision(
        scope,
        f"problem-{suffix}",
        f"problem-revision-{suffix}",
        1,
        None,
        "质量",
        "改善供应商质量",
        "owner",
        "actor",
        now,
    )
    payload = canonical_digest(problem.digest_contract())
    assert (
        store.create_problem(
            problem, idempotency_key="create", payload_digest=payload, authorized=True
        )
        == problem
    )
    assert (
        store.create_problem(
            problem, idempotency_key="create", payload_digest=payload, authorized=True
        )
        == problem
    )
    with pytest.raises(BusinessProblemConflict, match="IDEMPOTENCY_PAYLOAD_MISMATCH"):
        store.create_problem(
            problem, idempotency_key="create", payload_digest="0" * 64, authorized=True
        )
    with pytest.raises(
        BusinessProblemNotAuthorized, match="BUSINESS_PROBLEM_NOT_FOUND"
    ):
        store.get_problem(scope, problem.business_problem_id, authorized=False)
    assert (
        store.list_problems(ScopeIdentity("foreign", "domain"), authorized=True) == ()
    )

    criterion = SuccessCriterionRevision(
        scope,
        f"criterion-{suffix}",
        f"criterion-revision-{suffix}",
        1,
        None,
        CriterionType.NUMERIC_THRESHOLD,
        {"operator": "LT", "threshold": 1, "unit": "percent"},
        ("METRIC",),
        "deterministic",
        "v1",
        {"supplier": "controlled"},
        "actor",
        now,
    )
    store.add_criterion_revision(
        criterion,
        expected_version=None,
        idempotency_key="criterion",
        payload_digest=criterion.digest,
        authorized=True,
    )
    criteria_set = SuccessCriteriaSetRevision(
        scope,
        f"set-{suffix}",
        problem.business_problem_id,
        problem.revision_id,
        1,
        None,
        (criterion.revision_id,),
        "actor",
        now,
    )
    store.add_criteria_set_revision(
        criteria_set,
        expected_version=1,
        idempotency_key="set",
        payload_digest=criteria_set.digest,
        authorized=True,
    )
    successor_problem = BusinessProblemRevision(
        scope,
        problem.business_problem_id,
        f"problem-revision-2-{suffix}",
        2,
        problem.revision_id,
        "质量改善",
        "改善供应商连续交付质量",
        "owner",
        "actor",
        now,
    )
    store.add_problem_revision(
        successor_problem,
        expected_version=2,
        idempotency_key="problem-successor",
        payload_digest=successor_problem.digest,
        authorized=True,
    )
    successor_criterion = SuccessCriterionRevision(
        scope,
        criterion.success_criterion_id,
        f"criterion-revision-2-{suffix}",
        2,
        criterion.revision_id,
        CriterionType.NUMERIC_THRESHOLD,
        {"operator": "LTE", "threshold": 1, "unit": "percent"},
        ("METRIC",),
        "deterministic",
        "v1",
        {"supplier": "controlled"},
        "actor",
        now,
    )
    store.add_criterion_revision(
        successor_criterion,
        expected_version=1,
        idempotency_key="criterion-successor",
        payload_digest=successor_criterion.digest,
        authorized=True,
    )
    successor_set = SuccessCriteriaSetRevision(
        scope,
        f"set-2-{suffix}",
        problem.business_problem_id,
        successor_problem.revision_id,
        2,
        criteria_set.set_revision_id,
        (successor_criterion.revision_id,),
        "actor",
        now,
    )
    store.add_criteria_set_revision(
        successor_set,
        expected_version=3,
        idempotency_key="set-successor",
        payload_digest=successor_set.digest,
        authorized=True,
    )
    assert (
        store.get_criterion_revision(scope, criterion.revision_id, authorized=True)
        == criterion
    )
    assert (
        store.get_criteria_set_revision(
            scope, criteria_set.set_revision_id, authorized=True
        )
        == criteria_set
    )
    version = store.transition(
        scope,
        problem.business_problem_id,
        BusinessProblemState.ACTIVE,
        actor_id="actor",
        expected_version=4,
        event_id=f"event-{suffix}",
        idempotency_key="transition",
        payload_digest="1" * 64,
        authorized=True,
    )
    assert version == 5
    assert [
        event.event_type
        for event in store.get_lifecycle(
            scope, problem.business_problem_id, authorized=True
        )
    ] == ["INITIAL", "TRANSITION"]
    with pytest.raises(BusinessProblemConflict, match="STALE_AGGREGATE_VERSION"):
        store.transition(
            scope,
            problem.business_problem_id,
            BusinessProblemState.IN_PROGRESS,
            actor_id="actor",
            expected_version=4,
            event_id=f"stale-{suffix}",
            idempotency_key="stale",
            payload_digest="2" * 64,
            authorized=True,
        )

    with store.pool.connection() as connection, connection.transaction():
        connection.execute(
            "INSERT INTO workflow_definition.definitions(namespace,security_domain,workflow_definition_id,aggregate_version,record) VALUES (%s,%s,%s,1,'{}')",
            (scope.namespace, scope.security_domain, f"workflow-{suffix}"),
        )
        connection.execute(
            "INSERT INTO execution_authority.plans(namespace,security_domain,plan_id,plan_version,workflow_definition_id,workflow_definition_revision_id,workflow_definition_digest,status,aggregate_version,plan_digest,canonical_bytes,created_at,updated_at) VALUES (%s,%s,%s,1,%s,'revision',%s,'APPROVED',1,%s,%s,now(),now())",
            (
                scope.namespace,
                scope.security_domain,
                f"plan-{suffix}",
                f"workflow-{suffix}",
                "a" * 64,
                "b" * 64,
                b"{}",
            ),
        )
    binding = PlanProblemBinding(
        scope,
        f"binding-{suffix}",
        f"plan-{suffix}",
        1,
        "b" * 64,
        problem.business_problem_id,
        successor_problem.revision_id,
        successor_problem.digest,
        successor_set.set_revision_id,
        successor_set.digest,
        "actor",
        now,
    )
    store.bind_plan(
        binding,
        expected_problem_version=5,
        idempotency_key="bind",
        payload_digest=binding.digest,
        authorized=True,
    )
    store.pool.close()

    restarted = PostgresBusinessProblemRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0013_business_problem_authority.sql",
    )
    restarted.migrate()
    assert restarted.get_problem(
        scope, problem.business_problem_id, authorized=True
    ) == (problem, successor_problem)
    assert (
        restarted.bind_plan(
            binding,
            expected_problem_version=5,
            idempotency_key="bind",
            payload_digest=binding.digest,
            authorized=True,
        )
        == binding
    )
    assert (
        restarted.get_plan_binding(scope, binding.binding_id, authorized=True)
        == binding
    )
    restarted.pool.close()


def test_concurrent_lifecycle_cas_has_one_winner() -> None:
    store = repository()
    suffix = uuid.uuid4().hex
    scope = ScopeIdentity(f"cas-{suffix}", "domain")
    now = datetime.now(UTC)
    problem = BusinessProblemRevision(
        scope,
        f"problem-{suffix}",
        f"revision-{suffix}",
        1,
        None,
        "title",
        "description",
        "owner",
        "actor",
        now,
    )
    store.create_problem(
        problem,
        idempotency_key="create",
        payload_digest=problem.digest,
        authorized=True,
    )

    def advance(index: int) -> object:
        try:
            return store.transition(
                scope,
                problem.business_problem_id,
                BusinessProblemState.ACTIVE,
                actor_id="actor",
                expected_version=1,
                event_id=f"event-{index}-{suffix}",
                idempotency_key=f"transition-{index}",
                payload_digest=canonical_digest({"index": index}),
                authorized=True,
            )
        except BusinessProblemConflict as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(advance, range(2)))
    assert results.count(2) == 1
    assert sum(isinstance(result, str) for result in results) == 1
    store.pool.close()


def test_transaction_rolls_back_missing_criterion_membership() -> None:
    store = repository()
    suffix = uuid.uuid4().hex
    scope = ScopeIdentity(f"rollback-{suffix}", "domain")
    now = datetime.now(UTC)
    problem = BusinessProblemRevision(
        scope,
        f"problem-{suffix}",
        f"revision-{suffix}",
        1,
        None,
        "title",
        "description",
        "owner",
        "actor",
        now,
    )
    store.create_problem(
        problem,
        idempotency_key="create",
        payload_digest=problem.digest,
        authorized=True,
    )
    invalid_set = SuccessCriteriaSetRevision(
        scope,
        f"set-{suffix}",
        problem.business_problem_id,
        problem.revision_id,
        1,
        None,
        ("missing-revision",),
        "actor",
        now,
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        store.add_criteria_set_revision(
            invalid_set,
            expected_version=1,
            idempotency_key="set",
            payload_digest=invalid_set.digest,
            authorized=True,
        )
    with store.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS count FROM business_problem_authority.criteria_sets WHERE namespace=%s",
                (scope.namespace,),
            ).fetchone()["count"]
            == 0
        )
    store.pool.close()
