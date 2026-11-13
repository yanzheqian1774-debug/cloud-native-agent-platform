"""Real adoption/create/bind and history BFF; controlled model/source fixtures."""

# ruff: noqa: F401,F811 -- Isolated shared fixtures.
import json
from dataclasses import replace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.draft_assistance import DraftAssistanceError, DraftResultKind
from agent_console.grant_administration_application import GrantRevocationCommand
from agent_console.understanding_adoption_history import source
from agent_console.understanding_adoption_origin import AdoptionOrigin
from agent_console.workbench_bff import PREFIX
from psycopg.types.json import Jsonb
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_conversation_work_history import expired, snapshot
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted, answer
from test_understanding_adoption_business import adopted_business


@pytest.fixture
def history(adopted_business):
    e = adopted_business
    e.problem = json.loads(json.dumps(e.created["revision"], default=str))
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO private_conversation.links "
            "(tenant_id,security_domain,conversation_id,link_id,target,"
            "created_by,request_key,request_digest) "
            "VALUES(%s,%s,%s,'adopted-work',%s,%s,'adopted-work','fixture')",
            (
                e.context.scope.tenant_id,
                e.context.scope.security_domain,
                e.conv,
                Jsonb(
                    {
                        "problemId": e.problem["business_problem_id"],
                        "revisionId": e.problem["revision_id"],
                        "problemDigest": e.problem["digest"],
                    }
                ),
                e.context.principal_id,
            ),
        )
        c.execute(
            "UPDATE private_conversation.journeys SET state=%s WHERE "
            "conversation_id=%s",
            (
                Jsonb({"phase": "PLAN", "key": "adopted-work", "problem": e.problem}),
                e.conv,
            ),
        )
    expired(e)
    return e


def history_request(e):
    return e.adoption_client.post(
        PREFIX + f"/conversations/{e.conv}/history-access",
        headers=e.adoption_headers,
        json={},
    )


@pytest.mark.parametrize("adopted", ["BUSINESS_DATA"], indirect=True)
@pytest.mark.parametrize("expired_lineage", [False, True])
def test_adopted_work_history_renews_exact_read_without_consuming_result(
    history, expired_lineage
):
    e = history
    if expired_lineage:
        with e.repo.connection_scope() as c:
            c.execute(
                "UPDATE authorization_admin.grants SET not_before=now()-interval "
                "'9 hours',expires_at=now()-interval '1 hour' "
                "WHERE owner='DRAFT_ASSISTANCE'"
            )
    before = snapshot(e)
    with e.repo.connection_scope() as c:
        adoption = c.execute(
            "SELECT record FROM draft_assistance.result_adoptions ORDER BY "
            "result_invocation_id"
        ).fetchall()
    response = history_request(e)
    assert response.status_code == 200, response.text
    assert history_request(e).status_code == 200
    assert snapshot(e) == before
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT record FROM draft_assistance.result_adoptions ORDER BY "
                "result_invocation_id"
            ).fetchall()
            == adoption
        )
        grants = c.execute(
            "SELECT owner,action FROM authorization_admin.grants WHERE "
            "issuer_principal_id='policy:f3-conversation-history-read' AND "
            "owner='BUSINESS_PROBLEM'"
        ).fetchall()
        assert grants == [{"owner": "BUSINESS_PROBLEM", "action": "READ"}]
    assert len(e.calls) == 1


@pytest.mark.parametrize("adopted", ["BUSINESS_DATA"], indirect=True)
@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "version",
        "subject",
        "tenant",
        "revoked",
        "no_prior",
        "original_context_revoked",
        "result_context_revoked",
        "conversation",
    ],
)
def test_adopted_history_rejects_inexact_or_revoked_ancestry(history, mutation):
    e = history
    context = e.context
    with e.repo.connection_scope() as c:
        if mutation in {"source", "version"}:
            identity = (e.adopted_result if mutation == "source" else e.original)[
                "invocationId"
            ]
            change = (
                {"inputSource": {"source": {"digest": "wrong"}}}
                if mutation == "source"
                else {}
            )
            c.execute(
                "INSERT INTO draft_assistance.invocation_versions "
                "SELECT namespace,security_domain,invocation_id,aggregate_version+1,"
                "state,record || %s || jsonb_build_object("
                "'aggregateVersion',aggregate_version+1),now() "
                "FROM draft_assistance.invocation_versions "
                "WHERE invocation_id=%s ORDER BY aggregate_version DESC LIMIT 1",
                (Jsonb(change), identity),
            )
        elif mutation.endswith("context_revoked"):
            identity = (
                e.original if mutation.startswith("original") else e.adopted_result
            )["contextId"]
            admission_id = c.execute(
                "SELECT admission_id FROM authorization_admin.context_call_decisions "
                "WHERE context_id=%s",
                (identity,),
            ).fetchone()["admission_id"]
        elif mutation == "subject":
            context = replace(context, principal_id="another-principal")
        elif mutation == "tenant":
            context = replace(
                context, scope=replace(context.scope, tenant_id="another-tenant")
            )
        elif mutation == "no_prior":
            c.execute(
                "UPDATE authorization_admin.grants SET "
                "exact_resource=exact_resource||':unrelated' WHERE "
                "owner='DRAFT_ASSISTANCE' AND exact_resource=%s",
                ("draft-assistance:invocation:" + e.original["invocationId"],),
            )
        elif mutation == "revoked":
            grant = c.execute(
                "SELECT grant_id FROM authorization_admin.grants WHERE "
                "owner='DRAFT_ASSISTANCE' AND exact_resource=%s LIMIT 1",
                ("draft-assistance:invocation:" + e.original["invocationId"],),
            ).fetchone()["grant_id"]
    if mutation.endswith("context_revoked"):
        e.admission.revoke(e.reviewer, identity, admission_id)
    if mutation == "revoked":
        e.admission.delegation.grants.revoke_grant(
            e.reviewer,
            GrantRevocationCommand(grant, "USER_REQUESTED", "revoke-ancestry", True),
        )
    before = snapshot(e)
    with (
        e.repo.connection_scope() as c,
        pytest.raises((DraftAssistanceError, AuthorityError)),
    ):
        source(
            e.admission.understanding_adoption,
            c,
            context,
            e.adopted_result["invocationId"],
            "another-conversation" if mutation == "conversation" else e.conv,
        )
    if mutation in {
        "source",
        "version",
        "no_prior",
        "original_context_revoked",
        "result_context_revoked",
    }:
        response = history_request(e)
        assert response.status_code in (403, 404, 409), response.text
    assert snapshot(e) == before
    assert len(e.calls) == 1


def test_actual_general_adoption_never_establishes_business_history(adopted):
    e = adopted
    e.kind = DraftResultKind.DRAFT_READY
    path, value = answer(e)
    response = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert response.status_code == 200, response.text
    owner = e.adoption_client.app.state.understanding_adoption
    resolver = AdoptionOrigin(
        e.admission,
        owner.routing.authorization.context_admission,
        owner.routing.profile,
        enabled=True,
    )
    with (
        e.repo.connection_scope() as c,
        pytest.raises(DraftAssistanceError, match="BUSINESS_SCOPE_DENIED"),
    ):
        source(resolver, c, e.context, value["invocationId"], e.conv)
