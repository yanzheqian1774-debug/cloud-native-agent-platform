"""297 Product read foundation; this is not durable HTTP acceptance."""

import os
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from agent_console.business_problem_domain import (
    BusinessProblemConflict,
    BusinessProblemError,
    BusinessProblemNotAuthorized,
    BusinessProblemRevision,
    BusinessProblemState,
    CriterionType,
    SuccessCriteriaSetRevision,
    SuccessCriterionRevision,
)
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.business_problem_schemas import (
    CreateBusinessProblem,
    CreateCriterionRevision,
    TransitionBusinessProblem,
)
from agent_console.execution_domain import ScopeIdentity
from pydantic import ValidationError

MIGRATIONS = Path(__file__).parents[1] / "migrations"


@pytest.mark.parametrize("failed_migration", ("0011", "0013", "0020"))
def test_configured_business_problem_initialization_failure_stops_startup_and_closes(
    monkeypatch, failed_migration
):
    from agent_console import app, business_problem_bootstrap

    opened = []

    class Pool:
        closed = False

        def close(self):
            self.closed = True

    class Repository:
        def __init__(
            self,
            _database_url,
            *,
            migration_path,
            creator_receipt_migration_path=None,
        ):
            self.migration_path = migration_path
            self.creator_receipt_migration_path = creator_receipt_migration_path
            self.pool = Pool()
            opened.append(self)

        def migrate(self):
            paths = (self.migration_path, self.creator_receipt_migration_path)
            if any(
                path is not None and path.name.startswith(failed_migration)
                for path in paths
            ):
                raise RuntimeError(f"{failed_migration}_INITIALIZATION_FAILED")

        def compatibility(self):
            return None

    monkeypatch.setattr(
        business_problem_bootstrap,
        "PostgresWorkflowControlRepository",
        Repository,
    )
    monkeypatch.setattr(
        business_problem_bootstrap,
        "PostgresBusinessProblemRepository",
        Repository,
    )
    monkeypatch.setattr(
        business_problem_bootstrap,
        "PostgresWorkflowDefinitionRepository",
        Repository,
    )
    monkeypatch.setenv("EXECUTION_DATABASE_URL", "postgresql://configured")
    monkeypatch.setattr(app, "_digital_employee_assembly", object())
    monkeypatch.setattr(app, "_business_problem_application", object())

    with pytest.raises(RuntimeError, match=f"{failed_migration}_INITIALIZATION_FAILED"):
        app._configure_business_problems()

    assert app._business_problem_application is None
    assert opened
    assert all(repository.pool.closed for repository in opened)


@pytest.mark.parametrize(
    "method",
    ["get_aggregate", "list_criterion_revisions", "list_criteria_set_revisions"],
)
def test_read_denial_precedes_connection(method):
    # No pool exists: a denied read must never try to acquire a connection.
    store = object.__new__(PostgresBusinessProblemRepository)
    with pytest.raises(BusinessProblemNotAuthorized):
        getattr(store, method)(
            ScopeIdentity("tenant", "domain"), "id", authorized=False
        )


@pytest.mark.parametrize(
    "field", ["scope", "actorId", "authorizationDecision", "approved"]
)
def test_problem_schema_rejects_client_authority(field):
    with pytest.raises(ValidationError):
        CreateBusinessProblem.model_validate(
            dict(
                title="问题", description="说明", ownerId="owner", idempotencyKey="key"
            )
            | {field: "client-assertion"}
        )


def test_schema_does_not_invent_criterion_retirement():
    with pytest.raises(ValidationError):
        CreateCriterionRevision.model_validate(
            {
                "criterionType": "NOT_MEASURABLE",
                "measurement": {"reason": "NOT_MEASURABLE"},
                "requiredEvidenceKinds": [],
                "evaluatorType": "declared",
                "evaluatorVersion": "v1",
                "idempotencyKey": "key",
                "state": "RETIRED",
            }
        )
    with pytest.raises(ValidationError):
        TransitionBusinessProblem(
            toState="RETIRED", expectedVersion=1, idempotencyKey="key"
        )


@pytest.fixture
def database_url():
    url = os.environ.get("BUSINESS_PROBLEM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("297 exclusive PostgreSQL required")
    name = f"impl297_{uuid.uuid4().hex}"
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(
            psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name))
        )
        target = psycopg.conninfo.make_conninfo(url, dbname=name)
        try:
            with psycopg.connect(target) as connection:
                for version in range(1, 13):
                    connection.execute(
                        next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
                    )
            yield target
        finally:
            admin.execute(
                psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    psycopg.sql.Identifier(name)
                )
            )


def test_product_reads_history_cas_scope_and_restart(database_url):
    def open_store():
        repository = PostgresBusinessProblemRepository(
            database_url,
            migration_path=MIGRATIONS / "0013_business_problem_authority.sql",
        )
        repository.migrate()
        return repository

    scope = ScopeIdentity("tenant", "domain")
    now = datetime.now(UTC)
    problem = BusinessProblemRevision(
        scope,
        "problem",
        "revision-1",
        1,
        None,
        "质量",
        "改善质量",
        "owner",
        "actor",
        now,
    )
    criterion = SuccessCriterionRevision(
        scope,
        "criterion",
        "criterion-1",
        1,
        None,
        CriterionType.DETERMINISTIC_BOOLEAN,
        {"expected": True},
        ("METRIC",),
        "deterministic",
        "v1",
        {},
        "actor",
        now,
    )
    first_set = SuccessCriteriaSetRevision(
        scope,
        "set-1",
        "problem",
        "revision-1",
        1,
        None,
        ("criterion-1",),
        "actor",
        now,
    )
    successor = replace(
        problem,
        revision_id="revision-2",
        revision=2,
        predecessor_revision_id="revision-1",
        description="改善交付质量",
        digest="",
    )
    second_set = replace(
        first_set,
        set_revision_id="set-2",
        problem_revision_id="revision-2",
        revision=2,
        predecessor_set_revision_id="set-1",
        digest="",
    )
    store = open_store()
    try:
        store.create_problem(
            problem,
            idempotency_key="create",
            payload_digest=problem.digest,
            authorized=True,
        )
        assert (
            store.list_criteria_set_revisions(scope, "problem", authorized=True) == ()
        )
        store.add_criterion_revision(
            criterion,
            expected_version=None,
            idempotency_key="criterion",
            payload_digest=criterion.digest,
            authorized=True,
        )
        # Criterion membership is explicit: unbound criteria are not inferred.
        assert store.list_criterion_revisions(scope, "problem", authorized=True) == ()
        store.add_criteria_set_revision(
            first_set,
            expected_version=1,
            idempotency_key="set-1",
            payload_digest=first_set.digest,
            authorized=True,
        )
        before = store.get_aggregate(scope, "problem", authorized=True)
        assert before.aggregate_version == 2
        with pytest.raises(
            BusinessProblemConflict, match="BUSINESS_PROBLEM_REVISION_STALE"
        ):
            store.add_problem_revision(
                successor,
                expected_version=1,
                idempotency_key="revision",
                payload_digest=successor.digest,
                authorized=True,
            )
        assert store.get_aggregate(scope, "problem", authorized=True) == before
        store.add_problem_revision(
            successor,
            expected_version=2,
            idempotency_key="revision",
            payload_digest=successor.digest,
            authorized=True,
        )
        store.add_criteria_set_revision(
            second_set,
            expected_version=3,
            idempotency_key="set-2",
            payload_digest=second_set.digest,
            authorized=True,
        )
        store.transition(
            scope,
            "problem",
            BusinessProblemState.ACTIVE,
            actor_id="actor",
            expected_version=4,
            event_id="active",
            idempotency_key="active",
            payload_digest="a" * 64,
            authorized=True,
        )
        expected = store.get_aggregate(scope, "problem", authorized=True)
        assert expected.aggregate_version == 5
        assert expected.current_revision_id == "revision-2"
        assert expected.current_state == BusinessProblemState.ACTIVE
        for method in (
            "get_aggregate",
            "list_criterion_revisions",
            "list_criteria_set_revisions",
        ):
            for foreign in (
                ScopeIdentity("other", "domain"),
                ScopeIdentity("tenant", "other"),
            ):
                with pytest.raises(
                    BusinessProblemError, match="BUSINESS_PROBLEM_NOT_FOUND"
                ):
                    getattr(store, method)(foreign, "problem", authorized=True)
    finally:
        store.pool.close()
    restarted = open_store()
    try:
        assert restarted.get_aggregate(scope, "problem", authorized=True) == expected
        assert restarted.get_problem(scope, "problem", authorized=True) == (
            problem,
            successor,
        )
        assert restarted.list_criteria_set_revisions(
            scope, "problem", authorized=True
        ) == (first_set, second_set)
        # Reusing one criterion in two sets yields one immutable revision.
        assert restarted.list_criterion_revisions(
            scope, "problem", authorized=True
        ) == (criterion,)
    finally:
        restarted.pool.close()


def test_foreign_problem_revision_is_rejected_before_revision_lookup():
    from types import SimpleNamespace

    store = object.__new__(PostgresBusinessProblemRepository)
    statements = []

    def execute(query, _arguments):
        statements.append(query)
        assert len(statements) == 1
        assert "business_problem_authority.problems" in query
        return SimpleNamespace(
            fetchone=lambda: {"current_revision_id": "authorized-revision"}
        )

    connection = SimpleNamespace(execute=execute)
    target = SimpleNamespace(
        scope=ScopeIdentity("tenant", "domain"),
        business_problem_id="authorized-problem",
        problem_revision_id="unrelated-revision",
    )
    with pytest.raises(BusinessProblemConflict, match="PLAN_PROBLEM_BINDING_MISMATCH"):
        store.validate_plan_target(connection, target, 1, authorized=True)
    assert len(statements) == 1
