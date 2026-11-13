"""Canonical existing-work fixture; real exact READ decision and business owner."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import ExactGrant
from agent_console.business_plan_postgres import PostgresProblemPlanUnitOfWork
from agent_console.business_problem_application import BusinessProblemApplication
from agent_console.business_problem_authorization import problem_resource
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.business_problem_schemas import CreateBusinessProblem
from agent_console.context_call_admission import bind_problem
from agent_console.draft_assistance import (
    DraftResultKind,
    ObservationState,
    ProviderObservation,
)
from agent_console.grant_administration_application import (
    GrantDecisionCommand,
    GrantRequestCommand,
)
from agent_console.workbench_business_problem import OwnerPrincipal
from psycopg.types.json import Jsonb
from test_local_accounts_postgres import login


def existing_work(e, authorizer, sessions):
    migrations = Path(__file__).parents[1] / "migrations"
    with e.repo.connection_scope() as c:
        for version in range(1, 13):
            c.execute(next(migrations.glob(f"{version:04d}_*.sql")).read_text())
    repository = PostgresBusinessProblemRepository(
        e.repo.pool.conninfo,
        migration_path=migrations / "0013_business_problem_authority.sql",
        creator_receipt_migration_path=migrations
        / "0020_business_problem_creator_receipt.sql",
    )
    repository.migrate()
    app = BusinessProblemApplication(
        PostgresProblemPlanUnitOfWork(repository, None), None, None, None, None
    )
    command = CreateBusinessProblem(
        title="核对生产交接资料",
        description="只读检查已有材料完整性,不发布或修改外部系统。",
        ownerId=e.reviewer.principal_id,
        idempotencyKey="existing-work",
    )

    def create(call):
        app.authority = call.authority
        principal = OwnerPrincipal(
            e.business.principal_id,
            e.business.scope.tenant_id,
            e.business.scope.security_domain,
        )
        return app.create_problem(principal, command, connection=call.connection)

    revision = authorizer.execute(
        e.business,
        (ExactGrant("BUSINESS_PROBLEM", "CREATE", problem_resource()),),
        operation="CREATE_PROBLEM",
        payload=command.model_dump(),
        path={},
        query={},
        handler=create,
    )["revision"]
    grant = ExactGrant(
        "BUSINESS_PROBLEM", "READ", problem_resource(revision["business_problem_id"])
    )
    grants = e.admission.delegation.grants
    generation = grants.generation
    grants._generation_provider = lambda: replace(
        generation,
        requestability=(
            *generation.requestability,
            RequestabilityRule(
                grant.owner, grant.action, grant.exact_resource, "WORKBENCH_PROBLEM"
            ),
        ),
    )
    previous_validator = grants.target_validator
    grants.target_validator = NS(
        is_known_exact_target=lambda context, member, **kwargs: (
            member == grant
            or previous_validator.is_known_exact_target(context, member, **kwargs)
        )
    )
    requested = grants.submit_request(
        e.reviewer, GrantRequestCommand("WORKBENCH_PROBLEM", (grant,), "existing-read")
    )
    admin_secret = login(sessions, "devadmin")
    _, administrator = sessions.authenticate_session(admin_secret.value)
    grants.decide_request(
        administrator,
        GrantDecisionCommand(
            requested.request_id,
            True,
            "ISOLATED_READ",
            "TICKET",
            "controlled-test",
            None,
            datetime.now(UTC) + timedelta(hours=1),
            "existing-read-decision",
        ),
    )
    version = e.client.get(
        "/api/workbench/v1/conversations/" + e.conv + "/head"
    ).json()["result"]["conversation"]["version"]
    goal = e.post(
        f"/conversations/{e.conv}/messages",
        {
            "content": "请核对生产交接资料",
            "expectedVersion": version,
            "idempotencyKey": "original-goal",
        },
    ).json()["result"]["identity"]
    dispatch = e.draft.transport.dispatch
    e.draft.transport.dispatch = lambda **kw: ProviderObservation(
        "offline-source:" + kw["invocation_id"],
        ObservationState.SUCCEEDED,
        correlation="source-fixture",
        result_kind=DraftResultKind.DRAFT_READY,
        title=command.title,
        description=command.description,
        input_tokens=10,
        output_tokens=20,
    )
    try:
        original = e.post(
            "/draft-assistance/invocations",
            {
                "content": "请核对生产交接资料",
                "idempotencyKey": "original-understanding",
                "conversationId": e.conv,
                "conversationMessageId": goal,
            },
        )
        assert original.status_code in (200, 201), original.text
        source = original.json()["result"]
        assert source["resultKind"] == "DRAFT_READY", source
        assert source["conversationDelivery"]["state"] == "SAVED", source
    finally:
        e.draft.transport.dispatch = dispatch
    revision = json.loads(json.dumps(revision, default=str))
    with e.repo.connection_scope() as c:
        assert bind_problem(
            c, e.reviewer, {"revision": revision}, source["invocationId"]
        )
        target = {
            "problemId": revision["business_problem_id"],
            "revisionId": revision["revision_id"],
            "problemDigest": revision["digest"],
        }
        c.execute(
            "INSERT INTO private_conversation.links "
            "(tenant_id,security_domain,conversation_id,link_id,target,"
            "created_by,request_key,request_digest) "
            "VALUES(%s,%s,%s,'existing-work',%s,%s,'existing-work','fixture')",
            (
                e.context.scope.tenant_id,
                e.context.scope.security_domain,
                e.conv,
                Jsonb(target),
                e.reviewer.principal_id,
            ),
        )
        state = {
            "phase": "PLAN",
            "pending": "planning",
            "error": "OUTCOME_UNKNOWN",
            "key": "existing-work",
            "problem": revision,
            "userMessageId": goal,
        }
        c.execute(
            "INSERT INTO private_conversation.journeys "
            "(tenant_id,security_domain,conversation_id,version,state) "
            "VALUES(%s,%s,%s,7,%s)",
            (
                e.context.scope.tenant_id,
                e.context.scope.security_domain,
                e.conv,
                Jsonb(state),
            ),
        )
    version = e.client.get(
        "/api/workbench/v1/conversations/" + e.conv + "/head"
    ).json()["result"]["conversation"]["version"]
    e.message = e.post(
        f"/conversations/{e.conv}/messages",
        {
            "content": "你好",
            "expectedVersion": version,
            "idempotencyKey": "independent-message",
        },
    ).json()["result"]["identity"]
    return app, repository, revision, state
