# ruff: noqa: F401,F811,E501 -- Reuse isolated PostgreSQL and ordinary-session fixtures.
"""New POST adapter, real prior-READ owner; prepared metadata is controlled."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from agent_console.execution_preparation_postgres import PreparedExecutionStore
from agent_console.grant_administration_application import GrantRevocationCommand
from agent_console.workbench_bff import PREFIX
from psycopg.types.json import Jsonb
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_conversation_work_history import expired, snapshot
from test_execution_preparation import preparation
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup


def work(e):
    p = preparation()
    ref = e.problem
    p = p.model_copy(
        update={
            "namespace": e.reviewer.scope.tenant_id,
            "security_domain": e.reviewer.scope.security_domain,
            "semantics": p.semantics.model_copy(
                update={
                    "target": p.semantics.target.model_copy(
                        update={
                            "problem": p.semantics.target.problem.model_copy(
                                update={
                                    "resource_id": ref["business_problem_id"],
                                    "revision_id": ref["revision_id"],
                                    "digest": ref["digest"],
                                }
                            )
                        }
                    )
                }
            ),
        }
    )
    with e.repo.connection_scope() as c:
        PreparedExecutionStore(c).migrate()
        c.execute(
            "CREATE TABLE execution_authority.prepared_candidates(namespace text,security_domain text,digest text,record jsonb,prepared_by text,PRIMARY KEY(namespace,security_domain,digest))"
        )
        c.execute(
            "INSERT INTO execution_authority.prepared_candidates VALUES(%s,%s,%s,%s,%s)",
            (
                p.namespace,
                p.security_domain,
                p.digest,
                Jsonb(p.model_dump(mode="json")),
                e.reviewer.principal_id,
            ),
        )
        c.execute(
            "UPDATE private_conversation.journeys SET state=jsonb_set(state,'{execution}',%s) WHERE conversation_id=%s",
            (Jsonb(p.digest), e.conv),
        )
        invocation_id = c.execute(
            "SELECT invocation_id FROM authorization_admin.context_call_objects WHERE owner='BUSINESS_PROBLEM' AND resource_id=%s",
            (ref["business_problem_id"],),
        ).fetchone()["invocation_id"]
    from agent_console.draft_assistance import DraftScope

    # Append the isolated source fixture; never rewrite immutable history.
    original = e.draft.repository.get(
        DraftScope.from_context(e.reviewer), invocation_id
    )
    e.draft._replace(
        original, input_source={"source": p.source_snapshot.model_dump(mode="json")}
    )
    return expired(e)


def post(e):
    return e.route_client.post(
        PREFIX + "/current-work/history-access", headers=e.route_headers, json={}
    )


@pytest.mark.parametrize(
    "mode",
    [
        "renew",
        "revoked",
        "denied",
        "archived",
        "foreign_owner",
        "foreign_domain",
        "missing_link",
    ],
)
def test_directory_preparation_keeps_original_history_boundary(routed, mode):
    e = routed
    resource = work(e)
    with e.repo.connection_scope() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE owner='BUSINESS_PROBLEM' AND action='READ' AND exact_resource=%s",
            (resource,),
        ).fetchone()["grant_id"]
        if mode == "archived":
            c.execute(
                "UPDATE private_conversation.conversations SET archived_at=now() WHERE conversation_id=%s",
                (e.conv,),
            )
        elif mode == "foreign_owner":
            c.execute(
                "UPDATE private_conversation.conversations SET owner_id='other' WHERE conversation_id=%s",
                (e.conv,),
            )
        elif mode == "foreign_domain":
            c.execute(
                "UPDATE private_conversation.journeys SET security_domain='foreign' WHERE conversation_id=%s",
                (e.conv,),
            )
        elif mode == "missing_link":
            c.execute(
                "DELETE FROM private_conversation.links WHERE conversation_id=%s",
                (e.conv,),
            )
    if mode == "revoked":
        e.admission.delegation.grants.revoke_grant(
            e.reviewer,
            GrantRevocationCommand(grant, "USER_REQUESTED", "directory-revoke", True),
        )
    if mode == "denied":
        from agent_console.authority_contracts import ExactGrant
        from agent_console.grant_administration_application import (
            GrantDecisionCommand,
            GrantRequestCommand,
        )
        from test_local_accounts_postgres import login

        grants = e.admission.delegation.grants
        with e.repo.connection_scope() as c:
            purpose = c.execute(
                "SELECT r.purpose FROM authorization_admin.grants g JOIN authorization_admin.grant_requests r USING(request_id) WHERE g.grant_id=%s",
                (grant,),
            ).fetchone()["purpose"]
        req = grants.submit_request(
            e.reviewer,
            GrantRequestCommand(
                purpose,
                (ExactGrant("BUSINESS_PROBLEM", "READ", resource),),
                "directory-denied",
            ),
        )
        secret = login(e.routing_sessions, "devadmin")
        _, admin = e.routing_sessions.authenticate_session(secret.value)
        grants.decide_request(
            admin,
            GrantDecisionCommand(
                req.request_id,
                False,
                "DENIED",
                "TICKET",
                "test-denial",
                None,
                None,
                "directory-deny",
            ),
        )
    before = snapshot(e)
    if mode == "renew":
        assert (
            e.route_client.get(PREFIX + "/current-work/history-access").status_code
            == 405
        )
        denied = e.route_client.post(PREFIX + "/current-work/history-access", json={})
        assert denied.status_code == 403, denied.text
        assert snapshot(e) == before
    if mode == "renew":
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = list(pool.map(lambda _: post(e), range(2)))
        assert all(r.status_code == 200 for r in first)
        response = first[0]
    else:
        response = post(e)
    assert response.status_code == 200, response.text
    value = response.json()["result"]
    assert value["hasMore"] is False
    assert value["checked"] == (1 if mode in {"renew", "revoked", "denied"} else 0)
    with e.repo.connection_scope() as c:
        renewed = c.execute(
            "SELECT action FROM authorization_admin.grants WHERE issuer_principal_id='policy:f3-conversation-history-read' AND owner='BUSINESS_PROBLEM' AND exact_resource=%s",
            (resource,),
        ).fetchall()
    assert renewed == ([{"action": "READ"}] if mode == "renew" else [])
    if mode in {"revoked", "denied"}:
        assert value["partial"] is True
    if mode == "renew":
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: post(e), range(2)))
        assert all(r.status_code == 200 for r in results)
        with e.repo.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM authorization_admin.grants WHERE issuer_principal_id='policy:f3-conversation-history-read' AND owner='BUSINESS_PROBLEM' AND exact_resource=%s",
                    (resource,),
                ).fetchone()["n"]
                == 1
            )
    assert snapshot(e) == before
    assert e.route_calls == [] and e.dispatches == []


def test_same_timestamp_pages_are_complete_and_cursor_is_owner_bound(
    routed, monkeypatch
):
    from agent_console import current_work_history_access as module

    e = routed
    work(e)
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE private_conversation.conversations SET archived_at=now() WHERE conversation_id=%s",
            (e.conv,),
        )
        for i in range(25):
            identity = f"page-{i:02d}"
            c.execute(
                "INSERT INTO private_conversation.conversations(tenant_id,security_domain,conversation_id,owner_id,title,request_key,request_digest,created_at) VALUES(%s,%s,%s,%s,'historical',%s,'fixture','2026-01-01')",
                (
                    e.reviewer.scope.tenant_id,
                    e.reviewer.scope.security_domain,
                    identity,
                    e.reviewer.principal_id,
                    identity,
                ),
            )
            c.execute(
                "INSERT INTO private_conversation.journeys(tenant_id,security_domain,conversation_id,version,state) SELECT tenant_id,security_domain,%s,version,state FROM private_conversation.journeys WHERE conversation_id=%s",
                (identity, e.conv),
            )
            c.execute(
                "INSERT INTO private_conversation.links(tenant_id,security_domain,conversation_id,link_id,target,created_by,request_key,request_digest) SELECT tenant_id,security_domain,%s,link_id,target,created_by,request_key,request_digest FROM private_conversation.links WHERE conversation_id=%s",
                (identity, e.conv),
            )
    called = []

    def effective(service, records, ctx, identity, c):
        called.append(identity)
        return {"available": True, "items": [{"state": "EFFECTIVE"}]}

    monkeypatch.setattr(module, "prepare", effective)
    first = post(e).json()["result"]
    assert first["checked"] == 20 and first["nextConversationId"] == "page-05"
    second = e.route_client.post(
        PREFIX + "/current-work/history-access",
        headers=e.route_headers,
        json={"afterConversationId": first["nextConversationId"]},
    )
    assert second.status_code == 200, second.text
    assert second.json()["result"]["checked"] == 5
    assert called == [f"page-{i:02d}" for i in reversed(range(25))]
    rejected = e.route_client.post(
        PREFIX + "/current-work/history-access",
        headers=e.route_headers,
        json={"afterConversationId": "foreign-cursor"},
    )
    assert rejected.status_code in (403, 404), rejected.text
    assert len(called) == 25
