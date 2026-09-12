"""Focused 299 service-level persistence acceptance on real PostgreSQL."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from agent_console.business_plan_postgres import PostgresProblemPlanUnitOfWork
from agent_console.business_problem_application import BusinessProblemApplication
from agent_console.business_problem_domain import BusinessProblemConflict
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.business_problem_schemas import (
    CreateBusinessProblem,
    CreateCriteriaSetRevision,
    CreateCriterionRevision,
    ReviseBusinessProblem,
)

DATABASE_URL = os.environ.get("BUSINESS_PROBLEM_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="299 exclusive real PostgreSQL required"
)
MIGRATIONS = Path(__file__).parents[1] / "migrations"


class ExactAuthority:
    """Record application authorization calls without modeling a browser session."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def require(self, principal, owner: str, action: str, resource: str):
        self.calls.append((owner, action, resource))
        return SimpleNamespace(decision_id=f"service-test:{len(self.calls)}")


@pytest.fixture
def database_url():
    source = DATABASE_URL or ""
    database_name = f"impl299_{uuid.uuid4().hex}"
    with psycopg.connect(source, autocommit=True) as admin:
        admin.execute(
            psycopg.sql.SQL("CREATE DATABASE {}").format(
                psycopg.sql.Identifier(database_name)
            )
        )
        target = psycopg.conninfo.make_conninfo(source, dbname=database_name)
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
                    psycopg.sql.Identifier(database_name)
                )
            )


def open_service(database_url: str):
    repository = PostgresBusinessProblemRepository(
        database_url,
        migration_path=MIGRATIONS / "0013_business_problem_authority.sql",
    )
    repository.migrate()
    authority = ExactAuthority()
    application = BusinessProblemApplication(
        PostgresProblemPlanUnitOfWork(repository, object()),
        authority,
        object(),
        object(),
        object(),
    )
    return application, repository, authority


def test_problem_criteria_partial_success_replay_cas_and_restart(database_url) -> None:
    application, repository, authority = open_service(database_url)
    principal = SimpleNamespace(
        principal_id="human:299-owner",
        tenant_id="tenant-299",
        security_domain="quality",
    )

    create = CreateBusinessProblem(
        title="供应商质量",
        description="降低逃逸缺陷",
        ownerId=principal.principal_id,
        idempotencyKey="299-create-problem",
    )
    created = application.create_problem(principal, create)["revision"]
    assert application.create_problem(principal, create)["revision"] == created
    problem_id = created["business_problem_id"]
    assert application.read_problem(principal, problem_id)["revisions"] == [created]

    criterion_create = CreateCriterionRevision(
        criterionType="HUMAN_EVALUATED",
        measurement={"rubric": "连续三批缺陷率低于百分之一"},
        requiredEvidenceKinds=[],
        evaluatorType="HUMAN",
        evaluatorVersion="v1",
        applicability={},
        idempotencyKey="299-create-criterion",
    )
    criterion = application.criterion(principal, criterion_create)["revision"]
    assert application.criterion(principal, criterion_create)["revision"] == criterion

    stale_set = CreateCriteriaSetRevision(
        problemRevisionId=created["revision_id"],
        orderedCriterionRevisionIds=[criterion["revision_id"]],
        expectedVersion=2,
        idempotencyKey="299-create-set",
    )
    with pytest.raises(BusinessProblemConflict, match="STALE_AGGREGATE_VERSION"):
        application.criteria_set(principal, problem_id, stale_set)

    # The first owner command committed, but failed set membership discloses nothing.
    assert (
        application.read_criterion(principal, criterion["revision_id"])["revision"]
        == criterion
    )
    assert application.read_sets(principal, problem_id)["revisions"] == []
    assert application.read_criteria(principal, problem_id)["revisions"] == []
    assert application.criterion(principal, criterion_create)["revision"] == criterion

    create_set = stale_set.model_copy(update={"expectedVersion": 1})
    first_set = application.criteria_set(principal, problem_id, create_set)["revision"]
    assert (
        application.criteria_set(principal, problem_id, create_set)["revision"]
        == first_set
    )

    revise_problem = ReviseBusinessProblem(
        predecessorRevisionId=created["revision_id"],
        expectedVersion=2,
        title="供应商质量改善",
        description="稳定降低逃逸缺陷",
        ownerId=principal.principal_id,
        idempotencyKey="299-revise-problem",
    )
    revised = application.revise_problem(principal, problem_id, revise_problem)[
        "revision"
    ]
    assert (
        application.revise_problem(principal, problem_id, revise_problem)["revision"]
        == revised
    )
    with pytest.raises(
        BusinessProblemConflict, match="BUSINESS_PROBLEM_REVISION_STALE"
    ):
        application.revise_problem(
            principal,
            problem_id,
            revise_problem.model_copy(update={"idempotencyKey": "299-stale-problem"}),
        )

    revise_criterion = CreateCriterionRevision(
        successCriterionId=criterion["success_criterion_id"],
        predecessorRevisionId=criterion["revision_id"],
        expectedVersion=1,
        criterionType="HUMAN_EVALUATED",
        measurement={"rubric": "连续五批缺陷率低于百分之一"},
        requiredEvidenceKinds=[],
        evaluatorType="HUMAN",
        evaluatorVersion="v1",
        applicability={},
        idempotencyKey="299-revise-criterion",
    )
    revised_criterion = application.criterion(principal, revise_criterion)["revision"]
    assert (
        application.criterion(principal, revise_criterion)["revision"]
        == revised_criterion
    )
    with pytest.raises(BusinessProblemConflict, match="STALE_AGGREGATE_VERSION"):
        application.criterion(
            principal,
            revise_criterion.model_copy(
                update={"idempotencyKey": "299-stale-criterion"}
            ),
        )

    revise_set = CreateCriteriaSetRevision(
        problemRevisionId=revised["revision_id"],
        predecessorSetRevisionId=first_set["set_revision_id"],
        orderedCriterionRevisionIds=[revised_criterion["revision_id"]],
        expectedVersion=3,
        idempotencyKey="299-revise-set",
    )
    revised_set = application.criteria_set(principal, problem_id, revise_set)[
        "revision"
    ]
    assert (
        application.criteria_set(principal, problem_id, revise_set)["revision"]
        == revised_set
    )
    with pytest.raises(BusinessProblemConflict, match="STALE_AGGREGATE_VERSION"):
        application.criteria_set(
            principal,
            problem_id,
            revise_set.model_copy(
                update={
                    "expectedVersion": 3,
                    "idempotencyKey": "299-stale-set",
                }
            ),
        )

    repository.pool.close()
    recovered, recovered_repository, recovered_authority = open_service(database_url)
    try:
        detail = recovered.read_problem(principal, problem_id)
        assert detail["problem"]["current_revision_id"] == revised["revision_id"]
        assert detail["revisions"] == [created, revised]
        assert recovered.read_sets(principal, problem_id)["revisions"] == [
            first_set,
            revised_set,
        ]
        assert recovered.read_criteria(principal, problem_id)["revisions"] == [
            criterion,
            revised_criterion,
        ]
        assert (
            recovered.read_criterion(principal, revised_criterion["revision_id"])[
                "revision"
            ]
            == revised_criterion
        )
        assert recovered_authority.calls
    finally:
        recovered_repository.pool.close()

    assert authority.calls
