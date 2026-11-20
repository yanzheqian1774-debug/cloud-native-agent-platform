"""Real private HTTP boundary; controlled owner/resource ports, no DB writes."""

from contextlib import nullcontext
from types import SimpleNamespace as NS
from urllib.parse import quote

import pytest
from agent_console import resource_management as module
from agent_console.authority_contracts import AuthorityError
from agent_console.skill_mcp_repository import SkillMcpNotFound
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from fastapi.testclient import TestClient
from test_workbench_bff import SessionStub


@pytest.fixture
def client(monkeypatch):
    s = NS(
        scope_denied=False,
        read_denied=False,
        revision_denied=False,
        unknown=False,
        lookups=[],
        requirements=[],
    )
    identity = "skill-definition:cbb032f6-e3a9-4cb9-94b0-0e04c4d8900c"
    record = {
        "resourceId": identity,
        "revisions": [{"revisionId": "revision:one", "digest": "a" * 64}],
    }

    def get(scope, kind, value):
        s.lookups.append(value)
        if s.unknown:
            raise RuntimeError("STORAGE_UNAVAILABLE")
        if value != identity:
            raise SkillMcpNotFound("RESOURCE_NOT_FOUND")
        return record

    def scope(context, kind):
        if s.scope_denied:
            raise AuthorityError("RESOURCE_MANAGEMENT_SCOPE_DENIED")

    class Authority:
        def __init__(self, *args):
            pass

        def require(self, principal, owner, action, target):
            s.requirements.append((owner, action, target))
            if s.read_denied or (s.revision_denied and action == "READ_RESOURCE"):
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    monkeypatch.setattr(module, "AuthorizedOwnerAuthority", Authority)
    service = NS(repository=NS(get=get), scope=lambda *args: args)
    monkeypatch.setattr(module, "bind_service", lambda *args: service)
    from agent_console import skill_resource_testing

    monkeypatch.setattr(
        skill_resource_testing,
        "version_impact",
        lambda rec: {"current": rec["revisions"][0]},
    )
    from agent_console import resource_dependency_impact

    monkeypatch.setattr(
        resource_dependency_impact, "project", lambda *a: {"incoming": []}
    )
    c = NS(execute=lambda *args: NS(fetchall=lambda: []))
    a = NS(
        controller=NS(
            protected_request=lambda: nullcontext(NS(generation=1)),
            readiness=NS(recovery_epoch=1),
        ),
        repository=NS(connection_scope=lambda: nullcontext(c)),
    )
    m = NS(scope=scope, owned=lambda *args: True, services={"skill": service})
    sessions = SessionStub()
    app = create_workbench_bff(
        sessions,
        a,
        WorkbenchBffPolicy("workbench.example", "https://workbench.example"),
        route_installers=(module.install_management(m, a),),
    )
    with TestClient(
        app, base_url="https://workbench.example", raise_server_exceptions=False
    ) as client:
        client.cookies.set("__Host-workbench_session", sessions.secret)
        yield client, s, identity


@pytest.mark.parametrize(
    "missing", ["cbb032f6-e3a9-4cb9-94b0-0e04c4d8900c", "skill-definition:missing"]
)
def test_missing_exact_id_is_json404_then_same_connection_valid_read(client, missing):
    c, s, identity = client
    root = "/api/workbench/v1/resource-management/skill/"
    response = c.get(root + quote(missing, safe="") + "/impact")
    assert response.status_code == 404
    assert response.json()["reasonCode"] == "RESOURCE_NOT_FOUND"
    good = c.get(root + quote(identity, safe="") + "/impact")
    assert good.status_code == 200, good.text
    assert good.json()["result"]["current"]["revisionId"] == "revision:one"
    assert s.lookups == [missing, identity]
    assert s.requirements[0][1] == "MANAGE_RESOURCE"


@pytest.mark.parametrize("mode", ["scope_denied", "read_denied"])
def test_denied_subject_cannot_probe_existence(client, mode):
    c, s, _ = client
    setattr(s, mode, True)
    response = c.get("/api/workbench/v1/resource-management/skill/missing/impact")
    assert response.status_code in (403, 404)
    assert response.json()["reasonCode"] != "RESOURCE_NOT_FOUND"
    assert s.lookups == []


def test_unexpected_storage_failure_is_not_false_notfound(client):
    c, s, identity = client
    s.unknown = True
    response = c.get(
        "/api/workbench/v1/resource-management/skill/"
        + quote(identity, safe="")
        + "/impact"
    )
    assert response.status_code == 500


def test_unauthenticated_request_never_reads_resource(client):
    c, s, _ = client
    c.cookies.clear()
    assert (
        c.get("/api/workbench/v1/resource-management/skill/missing/impact").status_code
        == 401
    )
    assert s.lookups == []


def test_existing_resource_requires_exact_revision_read(client):
    c, s, identity = client
    s.revision_denied = True
    response = c.get(
        "/api/workbench/v1/resource-management/skill/"
        + quote(identity, safe="")
        + "/impact"
    )
    assert response.status_code == 404
    assert response.json()["reasonCode"] == "AUTHORIZATION_NOT_FOUND"
    assert "result" not in response.json()
    assert s.lookups == [identity]
    assert s.requirements[-1][1] == "READ_RESOURCE"
