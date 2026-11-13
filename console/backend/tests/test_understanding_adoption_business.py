"""Actual create/bind/planning-read owners; controlled model and target registry."""

# ruff: noqa: F401,F811 -- Isolated shared fixtures.
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import ExactGrant
from agent_console.business_plan_postgres import PostgresProblemPlanUnitOfWork
from agent_console.business_problem_application import BusinessProblemApplication
from agent_console.business_problem_authorization import problem_resource
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.business_problem_schemas import CreateBusinessProblem
from agent_console.context_call_admission import bind_problem
from agent_console.conversation_planning_admission import ConversationPlanningAdmission
from agent_console.conversation_work_authorization import ConversationWorkAuthorization
from agent_console.draft_assistance import (
    DraftAssistanceError,
    DraftResultKind,
    DraftScope,
)
from agent_console.draft_assistance_authorization import model_grant
from agent_console.understanding_adoption_origin import AdoptionOrigin
from agent_console.workbench_bff import PREFIX
from agent_console.workbench_business_problem import OwnerPrincipal
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted, answer
from test_understanding_adoption_source import select


@pytest.fixture
def adopted_business(adopted):
    e = adopted
    selected = select(e)
    e.kind = DraftResultKind.DRAFT_READY
    path, value = answer(e)
    response = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert response.status_code == 200, response.text
    owner = e.adoption_client.app.state.understanding_adoption
    root = e.admission
    routing = owner.routing.authorization.context_admission
    root.understanding_adoption = AdoptionOrigin(
        root, routing, owner.routing.profile, enabled=True
    )
    planning = NS(
        configuration={
            **root.configuration,
            "model_target": model_grant(
                e.draft.repository.get(
                    DraftScope.from_context(e.context), value["invocationId"]
                )
            ).exact_resource,
        },
        repository=e.repo,
        delegation=root.delegation,
    )
    planning.conversation_experience = ConversationPlanningAdmission(
        root, planning.configuration
    )
    work = ConversationWorkAuthorization(planning)
    create_grant = ExactGrant("BUSINESS_PROBLEM", "CREATE", problem_resource())
    members = {create_grant}
    grants = work.grants
    generation = grants.generation
    grants._generation_provider = lambda: replace(
        generation,
        requestability=(
            *generation.requestability,
            *(
                RequestabilityRule(
                    g.owner, g.action, g.exact_resource, work._purpose(g)
                )
                for g in members
            ),
        ),
    )
    previous = grants.target_validator
    grants.target_validator = NS(
        is_known_exact_target=lambda ctx, g, **kw: (
            g in members or previous.is_known_exact_target(ctx, g, **kw)
        )
    )
    command = CreateBusinessProblem(
        title=value["draft"]["title"],
        description=value["draft"]["description"],
        ownerId=e.context.principal_id,
        idempotencyKey="adopted-create",
    )
    payload = {**command.model_dump(), "draftInvocationId": value["invocationId"]}
    work.before(e.context, "CREATE_PROBLEM", payload, {}, (create_grant,))
    migration = Path(__file__).parents[1] / "migrations"
    repository = PostgresBusinessProblemRepository(
        e.repo.pool.conninfo,
        migration_path=migration / "0013_business_problem_authority.sql",
        creator_receipt_migration_path=migration
        / "0020_business_problem_creator_receipt.sql",
    )
    app = BusinessProblemApplication(
        PostgresProblemPlanUnitOfWork(repository, None), None, None, None, None
    )

    def create(call):
        app.authority = call.authority
        principal = OwnerPrincipal(
            e.context.principal_id,
            e.context.scope.tenant_id,
            e.context.scope.security_domain,
        )
        created = app.create_problem(principal, command, connection=call.connection)
        assert bind_problem(call.connection, e.context, created, value["invocationId"])
        return created

    try:
        created = e.draft.authorization.owner_authorization.execute(
            e.context,
            (create_grant,),
            operation="CREATE_PROBLEM",
            payload=payload,
            path={},
            query={},
            handler=create,
        )
        identity = created["revision"]["business_problem_id"]
        members.update(
            (
                ExactGrant("BUSINESS_PROBLEM", "READ", problem_resource(identity)),
                ExactGrant("PLAN", "PREPARE", "plan:prepare:" + identity),
                ExactGrant("PLAN", "READ", "plan:prepared:" + identity),
                ExactGrant(
                    "MODEL_GOVERNANCE",
                    "INVOKE_MODEL",
                    planning.configuration["model_target"],
                ),
            )
        )
        work.after(e.context, "CREATE_PROBLEM", payload, created)
        with e.repo.connection_scope() as c:
            bound = planning.conversation_experience.require_source(
                planning, c, e.context, identity
            )[0]
            assert bound["understanding_input_source"]["source"] == selected
            assert bound["context_id"] == value["contextId"]
            assert bound["context_id"] != e.original["contextId"]
        assert created["revision"]["description"] == value["draft"]["description"]
        assert len(e.calls) == 1
        e.adopted_result, e.created = value, created
        yield e
    finally:
        repository.pool.close()


@pytest.mark.parametrize("adopted", ["BUSINESS_DATA"], indirect=True)
def test_exact_business_origin_creates_and_plans_from_adopted_actual_source(
    adopted_business,
):
    assert (
        adopted_business.created["revision"]["description"]
        == adopted_business.adopted_result["draft"]["description"]
    )


def test_general_question_adoption_does_not_grant_business_scope(adopted):
    e = adopted
    e.kind = DraftResultKind.DRAFT_READY
    path, value = answer(e)
    response = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert response.status_code == 200, response.text
    owner = e.adoption_client.app.state.understanding_adoption
    origin = AdoptionOrigin(
        e.admission,
        owner.routing.authorization.context_admission,
        owner.routing.profile,
        enabled=True,
    )
    with (
        e.repo.connection_scope() as c,
        pytest.raises(DraftAssistanceError, match="BUSINESS_SCOPE_DENIED"),
    ):
        origin.business_source(c, e.context, value["invocationId"])
    assert len(e.calls) == 1
