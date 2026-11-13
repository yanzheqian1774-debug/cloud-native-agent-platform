# ruff: noqa: F401,F811,E501 -- Shared isolated real grant/owner fixtures.
from dataclasses import replace
from datetime import timedelta

import pytest
from agent_console.authority_contracts import AuthorityError, GrantId
from agent_console.grant_administration_application import GrantRevocationCommand
from agent_console.ontology_domain import OntologyError
from test_ontology_management import (
    automation,
    case,
    create,
    maintained,
    payload,
    repository,
    run,
    services,
)


def preparation(v, key="prepare-read-1", **extra):
    return dict(
        action="PREPARE_READ",
        commandKey=key,
        ontologyId="managed-sales",
        revision=v["revision_id"],
        **extra,
    )


def expire(m, action="READ"):
    with m.a.authority.connection_scope() as c:
        c.execute(
            "UPDATE authorization_admin.grants SET not_before=now()-interval '2 hours', expires_at=now()-interval '1 hour' WHERE owner='BUSINESS_ONTOLOGY' AND action=%s",
            (action,),
        )


def facts(m):
    with m.a.authority.connection_scope() as c:
        return c.execute(
            "SELECT * FROM business_ontology.lifecycle_facts ORDER BY ordinal"
        ).fetchall()


def test_expired_own_read_prepares_once_and_second_expiry_requires_new_key(maintained):
    m = maintained
    first = create(m)
    v = first["outcome"]
    before = facts(m)
    expire(m)
    expire(m, "CREATE")
    with pytest.raises(AuthorityError):
        run(m, read="create-command-1")
    request = preparation(v, expectedVersion=v["version"], digest=v["digest"])
    result = run(m, request)
    assert result["revision"] == v["revision_id"] and result["digest"] == v["digest"]
    assert run(m, request) == result
    assert run(m, read=request["commandKey"]) == result
    assert run(m, read="create-command-1")["writeEligible"] is False
    assert facts(m) == before
    expire(m)
    with pytest.raises(AuthorityError):
        run(m, request)
    again = run(m, preparation(v, "prepare-read-2"))
    assert again["digest"] == v["digest"] and facts(m) == before
    with pytest.raises(OntologyError, match="CONFLICT"):
        run(m, {**request, "digest": "0" * 64})
    with m.a.authority.connection_scope() as c:
        rows = c.execute(
            "SELECT action FROM authorization_admin.grants WHERE owner='BUSINESS_ONTOLOGY'"
        ).fetchall()
        assert [r["action"] for r in rows].count("CREATE") == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "no_prior",
        "other_revision",
        "no_scope",
        "expired_policy",
        "revoked",
        "version",
        "digest",
        "generation",
    ],
)
def test_retained_read_does_not_invent_or_restore_forbidden_rights(
    maintained, mutation
):
    m = maintained
    first = create(m)
    v = first["outcome"]
    expire(m)
    request = preparation(v)
    before = facts(m)
    if mutation == "no_prior":
        with m.a.authority.connection_scope() as c:
            c.execute(
                "UPDATE authorization_admin.grants SET exact_resource=exact_resource||':different' WHERE owner='BUSINESS_ONTOLOGY' AND action='READ'"
            )
    elif mutation == "other_revision":
        request["revision"] = "unknown-revision"
    elif mutation == "no_scope":
        m.manager.policy = m.manager.policy.model_copy(update={"workScopes": ()})
    elif mutation == "expired_policy":
        m.manager.policy = m.manager.policy.model_copy(
            update={
                "workScopes": tuple(
                    s.model_copy(
                        update={
                            "expiresAt": m.manager.grants.clock() - timedelta(seconds=1)
                        }
                    )
                    for s in m.manager.policy.workScopes
                )
            }
        )
    elif mutation == "revoked":
        with m.a.authority.connection_scope() as c:
            grant = c.execute(
                "SELECT grant_id FROM authorization_admin.grants WHERE owner='BUSINESS_ONTOLOGY' AND action='READ'"
            ).fetchone()["grant_id"]
        m.manager.grants.revoke_grant(
            m.a.subject,
            GrantRevocationCommand(
                GrantId(grant), "USER_REQUESTED", "revoke-draft-read", True
            ),
        )
    elif mutation == "version":
        request["expectedVersion"] = 99
    elif mutation == "digest":
        request["digest"] = "0" * 64
    with pytest.raises((AuthorityError, OntologyError)):
        run(m, request, generation=999 if mutation == "generation" else 1)
    assert facts(m) == before


def test_explicit_denial_and_another_actor_do_not_allow_read_renewal(maintained):
    from dataclasses import replace

    from agent_console.authority_contracts import ExactGrant
    from agent_console.grant_administration_application import (
        GrantDecisionCommand,
        GrantRequestCommand,
    )

    m = maintained
    v = create(m)["outcome"]
    expire(m)
    reviewer = replace(
        m.a.subject,
        principal_id=m.reviewer.principal_id,
        session_id_or_service_credential_id=m.reviewer.credential_id,
    )
    with pytest.raises(AuthorityError, match="NOT_FOUND"):
        run(m, preparation(v), subject=reviewer)
    grants = m.manager.grants
    grant = ExactGrant(
        "BUSINESS_ONTOLOGY",
        "READ",
        "business-ontology:managed-sales:" + v["revision_id"],
    )
    request = grants.submit_request(
        m.a.subject,
        GrantRequestCommand("ONTOLOGY_MAINTENANCE", (grant,), "deny-exact-draft-read"),
    )
    issuer = m.manager.policy.authenticate(grants, m.a.subject)
    grants.decide_request(
        issuer,
        GrantDecisionCommand(
            request.request_id,
            False,
            "USER_REQUESTED",
            "TICKET",
            "isolated-read-denial",
            None,
            None,
            "deny-exact-read-decision",
        ),
    )
    with pytest.raises(AuthorityError, match="DENIED"):
        run(m, preparation(v))


def test_http_prepare_read_csrf_and_read_receipt_get_have_no_lifecycle_writes(
    maintained,
):
    from contextlib import nullcontext
    from types import SimpleNamespace

    from agent_console.ontology_management_api import install_ontology_management
    from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
    from fastapi.testclient import TestClient
    from test_workbench_bff import SessionStub

    m = maintained
    v = create(m)["outcome"]
    expire(m)
    before = facts(m)
    m.a.adapter.controller.protected_request = lambda: nullcontext(
        SimpleNamespace(generation=1)
    )
    session = SessionStub()
    session.context = m.a.subject
    app = create_workbench_bff(
        session,
        m.a.adapter,
        WorkbenchBffPolicy("workbench.example", "https://workbench.example"),
        route_installers=(install_ontology_management(m.manager, m.a.adapter),),
    )
    with TestClient(app, base_url="https://workbench.example") as client:
        client.cookies.set("__Host-workbench_session", session.secret)
        root = "/api/workbench/v1/ontology-maintenance/commands"
        body = preparation(v)
        assert client.post(root, json=body).status_code == 403
        headers = {"Origin": "https://workbench.example", "X-CSRF-Token": "csrf-token"}
        assert (
            client.post(
                root, json={**body, "actor": "forged"}, headers=headers
            ).status_code
            == 422
        )
        response = client.post(root, json=body, headers=headers)
        assert response.status_code == 200, response.text
        assert client.get(root + "/" + body["commandKey"]).json() == response.json()
        assert facts(m) == before
        m.manager.policy = m.manager.policy.model_copy(update={"enabled": False})
        assert client.get(root + "/" + body["commandKey"]).status_code == 200
        assert client.post(
            root, json={**body, "commandKey": "new-disabled-read"}, headers=headers
        ).status_code in (403, 404)


def test_created_scope_read_renewal_uses_real_creator_record_not_prefix(maintained):
    from test_ontology_management import controlled_creation_scopes

    m = maintained
    reviewer = controlled_creation_scopes(m)
    first = run(
        m,
        dict(
            action="CREATE",
            commandKey="created-read-owner",
            ontologyId="managed-new-read",
            expectedVersion=0,
            content=m.content,
            reason="isolated creator receipt",
        ),
    )
    v = first["outcome"]
    expire(m)
    request = {**preparation(v), "ontologyId": "managed-new-read"}
    assert run(m, request)["digest"] == v["digest"]
    with pytest.raises(AuthorityError, match="NOT_FOUND"):
        run(m, request, subject=reviewer)
