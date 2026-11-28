"""Read-only recovery hints reveal no unmanageable aggregates or test material."""

from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.owned_skill_access import access_candidates
from agent_console.resource_management import install_management
from fastapi import FastAPI
from fastapi.testclient import TestClient


def fixture_record():
    return {
        "currentDraftRevisionId": "draft",
        "publishedRevisionId": "published",
        "revisions": [
            {"revisionId": name, "digest": digest * 64, "content": "SECRET"}
            for name, digest in [("old", "a"), ("published", "b"), ("draft", "c")]
        ],
        "testResults": [{"actual": "SECRET"}],
        "savedTests": [{"input": "SECRET"}],
    }


@pytest.mark.parametrize("owner,readable", [(True, True), (True, False), (False, True)])
def test_creator_and_current_exact_read_are_both_required(owner, readable):
    record = fixture_record()
    before = deepcopy(record)
    fetched, authorized = [], []

    def require(principal, grant_owner, action, resource):
        authorized.append((grant_owner, action, resource))
        if not readable or not resource.endswith(":published"):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    def get(*args):
        fetched.append(args)
        return record

    value = access_candidates(
        SimpleNamespace(authority=SimpleNamespace(require=require)),
        SimpleNamespace(owned=lambda *args: owner),
        "skill:fixture",
        SimpleNamespace(repository=SimpleNamespace(get=get)),
        "scope",
        "principal",
    )
    if owner and readable:
        assert value == [
            {
                "kind": "skill",
                "identity": "skill:fixture",
                "revisionId": "published",
                "digest": "b" * 64,
            }
        ]
    else:
        assert value == []
    if not owner:
        assert fetched == [] and authorized == []
    assert "SECRET" not in str(value)
    assert all(
        action == "READ_RESOURCE" and not resource.endswith(":old")
        for _, action, resource in authorized
    )
    assert record == before


def test_directory_get_missing_manage_exposes_only_owned_readable_hint(monkeypatch):
    from agent_console import resource_management as module

    record = fixture_record()
    before = deepcopy(record)
    commands = []
    context = SimpleNamespace(
        principal_id="human:owner",
        scope=SimpleNamespace(tenant_id="tenant", security_domain="test"),
    )

    def require(principal, owner, action, resource):
        if action != "READ_RESOURCE" or not resource.endswith(":published"):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    connection = SimpleNamespace(
        execute=lambda *args: SimpleNamespace(
            fetchall=lambda: [{"identity": "skill:fixture"}]
        )
    )
    service = SimpleNamespace(
        scope=lambda *args: SimpleNamespace(namespace="tenant", security_domain="test"),
        repository=SimpleNamespace(get=lambda *args: record),
    )
    manager = SimpleNamespace(
        services={"skill": service},
        owned=lambda *args: True,
        scope=lambda *args: None,
        handle=lambda call: commands.append(call),
    )
    authorizer = SimpleNamespace(
        controller=SimpleNamespace(
            protected_request=lambda: nullcontext(SimpleNamespace(generation=1)),
            readiness=SimpleNamespace(recovery_epoch=1),
        ),
        repository=SimpleNamespace(connection_scope=lambda: nullcontext(connection)),
    )
    monkeypatch.setattr(module, "bind_service", lambda *args: service)
    monkeypatch.setattr(
        module,
        "AuthorizedOwnerAuthority",
        lambda *args: SimpleNamespace(require=require),
    )
    app = FastAPI()
    install_management(manager, authorizer)(
        app,
        lambda request: (None, context),
        lambda *args: pytest.fail("GET must not request CSRF/write"),
        None,
    )
    with TestClient(app) as client:
        response = client.get("/api/workbench/v1/resource-management/skill")
    assert response.status_code == 200
    value = response.json()["result"]
    assert value["items"] == []
    assert len(value["accessCandidates"]) == 1
    assert "SECRET" not in str(value)
    assert commands == [] and record == before
