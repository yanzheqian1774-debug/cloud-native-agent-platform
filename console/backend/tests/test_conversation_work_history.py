# ruff: noqa: F401,F811 -- Reuse isolated real authority/session/business fixtures.
"""Only prior exact work READ may renew; history/model/execution state is unchanged."""

import pytest
from agent_console.business_problem_authorization import problem_resource
from agent_console.grant_administration_application import GrantRevocationCommand
from agent_console.workbench_bff import PREFIX
from psycopg.types.json import Jsonb
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup


def snapshot(e):
    with e.repo.connection_scope() as c:
        tables = (
            "private_conversation.journeys",
            "private_conversation.messages",
            "private_conversation.links",
            "draft_assistance.invocation_versions",
            "draft_provider_budget.reservations",
            "draft_provider_budget.settlements",
        )
        tables = (
            *tables,
            *(
                r["name"]
                for r in c.execute(
                    "SELECT schemaname||'.'||tablename name FROM pg_tables "
                    "WHERE schemaname IN ('execution_authority','skill_invocation',"
                    "'business_problem_authority') ORDER BY 1"
                ).fetchall()
            ),
        )
        return {
            t: c.execute(
                "SELECT md5(row_to_json(t)::text) h FROM " + t + " t ORDER BY 1"
            ).fetchall()
            for t in tables
        }


def expired(e):
    resource = problem_resource(e.problem["business_problem_id"])
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE authorization_admin.grants SET "
            "not_before=now()-interval '9 hours',expires_at=now()-interval "
            "'1 hour' WHERE owner='BUSINESS_PROBLEM' AND action='READ' AND "
            "exact_resource=%s",
            (resource,),
        )
    return resource


def prepare(e):
    return e.route_client.post(
        PREFIX + f"/conversations/{e.conv}/history-access",
        headers=e.route_headers,
        json={},
    )


def test_real_expired_problem_read_renews_once_without_model_or_work_write(routed):
    e = routed
    resource = expired(e)
    before = snapshot(e)
    response = prepare(e)
    assert response.status_code == 200, response.text
    response2 = prepare(e)
    assert response2.status_code == 200, response2.text
    assert snapshot(e) == before
    with e.repo.connection_scope() as c:
        rows = c.execute(
            "SELECT g.action,r.purpose FROM authorization_admin.grants g "
            "JOIN authorization_admin.grant_requests r USING(request_id) "
            "WHERE "
            "g.issuer_principal_id='policy:f3-conversation-history-read' "
            "AND g.owner='BUSINESS_PROBLEM' AND g.exact_resource=%s",
            (resource,),
        ).fetchall()
        assert rows == [{"action": "READ", "purpose": "WORKBENCH_PROBLEM"}]
    assert e.route_calls == [] and e.dispatches == []


@pytest.mark.parametrize("mutation", ["link", "version", "revoked"])
def test_work_history_cannot_renew_mismatched_or_revoked_origin(routed, mutation):
    e = routed
    resource = expired(e)
    with e.repo.connection_scope() as c:
        if mutation == "link":
            c.execute(
                "DELETE FROM private_conversation.links WHERE conversation_id=%s",
                (e.conv,),
            )
        elif mutation == "version":
            state = dict(e.work_state)
            state["problem"] = {**state["problem"], "digest": "0" * 64}
            c.execute(
                "UPDATE private_conversation.journeys SET state=%s WHERE "
                "conversation_id=%s",
                (Jsonb(state), e.conv),
            )
        else:
            grant = c.execute(
                "SELECT grant_id FROM authorization_admin.grants WHERE "
                "owner='BUSINESS_PROBLEM' AND action='READ' AND "
                "exact_resource=%s",
                (resource,),
            ).fetchone()["grant_id"]
    if mutation == "revoked":
        e.admission.delegation.grants.revoke_grant(
            e.reviewer,
            GrantRevocationCommand(grant, "USER_REQUESTED", "revoke-work-read", True),
        )
    before = snapshot(e)
    response = prepare(e)
    if mutation == "revoked":
        assert response.status_code == 200, response.text
        assert any(i["state"] == "REVOKED" for i in response.json()["result"]["items"])
    else:
        assert response.status_code in (403, 404, 409), response.text
    assert snapshot(e) == before
    with e.repo.connection_scope() as c:
        assert not c.execute(
            "SELECT 1 FROM authorization_admin.grants WHERE "
            "issuer_principal_id='policy:f3-conversation-history-read' AND "
            "owner='BUSINESS_PROBLEM'"
        ).fetchone()
    assert e.route_calls == [] and e.dispatches == []


def test_history_never_invents_first_work_read(routed):
    e = routed
    resource = expired(e)
    with e.repo.connection_scope() as c:
        # Isolated historical fixture removes only eligibility for this target.
        c.execute(
            "UPDATE authorization_admin.grants SET exact_resource=%s "
            "WHERE owner='BUSINESS_PROBLEM' AND action='READ' AND exact_resource=%s",
            (resource + ":unrelated", resource),
        )
    before = snapshot(e)
    response = prepare(e)
    assert response.status_code == 200, response.text
    assert any(
        i["state"] == "NO_PRIOR_READ" for i in response.json()["result"]["items"]
    )
    assert snapshot(e) == before
    assert e.route_calls == [] and e.dispatches == []
