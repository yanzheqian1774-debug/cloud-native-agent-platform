"""Ordinary exact planning-start observations; no provider dispatch on GET."""

# ruff: noqa: F401,F811 -- Shared isolated owners and session fixtures.
from types import SimpleNamespace

import pytest
from agent_console.conversation_planning_recovery import migrate
from agent_console.execution_domain import ScopeIdentity
from agent_console.owned_business_planning_start_read import (
    OwnedBusinessPlanningStartRead,
)
from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
from agent_console.plan_suggestion_postgres import PostgresPlanningRepository
from agent_console.planning_call_admission import PlanningCallAdmission
from agent_console.workbench_bff import PREFIX, SESSION_COOKIE
from fastapi.encoders import jsonable_encoder
from owned_business_planning_support import activate_created
from psycopg.types.json import Jsonb
from test_local_accounts_postgres import login
from test_owned_business_creation_read import (
    adopted,
    counters,
    env,
    ordinary,
    owned_created,
    owned_ready,
    pgmark,
    routed,
    setup,
)

pytestmark = [pgmark, pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)]


@pytest.mark.parametrize(
    "variant", ["absent", "claimed", "prepared", "changed_key", "other_user", "revoked"]
)
def test_planning_start_read_checks_all_original_owners(owned_created, variant):
    e = activate_created(owned_created)
    planning = PostgresPlanningRepository(e.repo.pool)
    planning.migrate()
    invocations = PostgresPlanningInvocations(planning)
    invocations.migrate()
    PlanningCallAdmission.migrate(SimpleNamespace(repository=e.repo))
    migrate(SimpleNamespace(repository=e.repo))
    key = "initial-work:planning"
    with e.repo.connection_scope() as c:
        state = c.execute(
            "SELECT state FROM private_conversation.journeys WHERE conversation_id=%s",
            (e.conv,),
        ).fetchone()["state"]
        state.update(
            phase="PLAN",
            pending="planning",
            problem=jsonable_encoder(e.created["revision"]),
            source=e.business_result["inputSource"],
            planningRequestKey=key,
            criterion=e.business_criterion["revision"]["revision_id"],
        )
        c.execute(
            "UPDATE private_conversation.journeys SET state=%s "
            "WHERE conversation_id=%s",
            (Jsonb(state), e.conv),
        )
    if variant == "claimed":
        invocations.claim(
            ScopeIdentity(e.context.scope.tenant_id, e.context.scope.security_domain),
            e.context.principal_id,
            key,
            "a" * 64,
            {"target": {"invocation_id": "retained-claim"}},
        )
    if variant == "prepared":
        with e.repo.connection_scope() as c:
            c.execute(
                "INSERT INTO authorization_admin.planning_call_preparations "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    e.context.scope.tenant_id,
                    e.context.scope.security_domain,
                    e.context.principal_id,
                    key,
                    e.business_result["contextId"],
                    "a" * 64,
                    Jsonb({"fixture": "partial-preparation-must-block"}),
                ),
            )
    if variant == "other_user":
        secret = login(e.routing_sessions)
        e.adoption_client.cookies.set(SESSION_COOKIE, secret.value)
    if variant == "revoked":
        from agent_console.grant_administration_application import (
            GrantRevocationCommand,
        )

        with e.repo.connection_scope() as c:
            grant = c.execute(
                "SELECT grant_id FROM authorization_admin.grants WHERE "
                "subject_principal_id=%s AND owner='PLAN' "
                "AND action='PREPARE' AND exact_resource=%s",
                (
                    e.context.principal_id,
                    "plan:prepare:" + e.created["revision"]["business_problem_id"],
                ),
            ).fetchone()
        e.business_owner.grants.revoke_grant(
            e.context,
            GrantRevocationCommand(
                grant["grant_id"],
                "TEST_WITHDRAWAL",
                "planning-start-revoke",
                surrender=True,
            ),
        )
    e.adoption_client.app.state.owned_business_planning_start_read = (
        OwnedBusinessPlanningStartRead(
            e.business_owner,
            e.draft.authorization.owner_authorization,
            e.business_repository,
        )
    )
    before, calls = counters(e), len(e.calls)
    response = e.adoption_client.get(
        PREFIX + f"/conversations/{e.conv}/planning-start-status",
        params={
            "draftInvocationId": e.business_result["invocationId"],
            "requestKey": "different" if variant == "changed_key" else key,
        },
    )
    if variant == "changed_key":
        assert response.status_code == 409, response.text
    elif variant in ("other_user", "revoked"):
        assert response.status_code == 403, response.text
    else:
        assert response.status_code == 200, response.text
        assert response.json()["result"]["state"] == (
            "NOT_STARTED" if variant == "absent" else "RECORDED"
        )
    assert before == counters(e) and calls == len(e.calls)
