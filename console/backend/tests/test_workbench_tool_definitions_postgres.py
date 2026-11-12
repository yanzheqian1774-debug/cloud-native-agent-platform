"""Real session, CSRF, PostgreSQL and current grants for imported tool drafts."""

import base64
import json
import os
from dataclasses import replace

import pytest
import test_workbench_employee_commands_postgres as fixture
from agent_console.authority_contracts import AuthorityScope
from agent_console.tool_definition_postgres import PostgresToolDefinitionRepository
from agent_console.workbench_tool_definitions import ROOT, tool_definition_operations
from fastapi.testclient import TestClient
from test_tool_import import api
from test_workbench_team_postgres import allow

URL = os.environ.get("TOOL_DEFINITION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Dedicated PostgreSQL required")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(fixture, "DATABASE_URL", URL)
    original = fixture.employee_operations

    def operations(employees, cursors):
        owner = PostgresToolDefinitionRepository(employees.pool)
        owner.migrate(fixture.MIGRATIONS / "0061_tool_definitions.sql")
        return (
            *original(employees, cursors),
            *tool_definition_operations(owner, cursors),
        )

    monkeypatch.setattr(fixture, "employee_operations", operations)
    policy = fixture.WorkbenchBffPolicy
    monkeypatch.setattr(
        fixture,
        "WorkbenchBffPolicy",
        lambda *a, **kw: replace(
            policy(*a, **kw),
            route_body_limits=(
                (ROOT + "/imports", 200000),
                (ROOT + "/import-preview", 200000),
            ),
        ),
    )
    generator = fixture.employee_workbench.__wrapped__()
    value = next(generator)
    try:
        yield value
    finally:
        generator.close()


def command(value=None, key="import:1", **extra):
    return {
        "kind": "API",
        "contentBase64": base64.b64encode(json.dumps(value or api()).encode()).decode(),
        "selected": ["orders"],
        "commandId": key,
        **extra,
    }


def grants(app):
    for action in ["IMPORT", "LIST", "READ_SCOPE"]:
        allow(app, "TOOL", action, "tool:collection", "tool-" + action)


def test_real_csrf_grants_duplicates_revision_and_revoked_replay(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        assert client.get(ROOT).status_code == 401
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        assert (
            client.post(ROOT + "/imports", json=command(), headers=headers).status_code
            == 404
        )
        grants(app)
        assert client.post(ROOT + "/imports", json=command()).status_code == 403
        body = command()
        preview = {k: body[k] for k in ["kind", "contentBase64"]}
        response = client.post(ROOT + "/import-preview", json=preview, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["result"]["persisted"] is False
        assert "original" not in response.json()["result"]["operations"][0]
        saved = client.post(ROOT + "/imports", json=body, headers=headers)
        assert saved.status_code == 200, saved.text
        item = saved.json()["result"]["items"][0]
        assert (
            client.get(ROOT + "/" + item["toolId"]).json()["result"]["revisionId"]
            == item["revisionId"]
        )
        assert client.get(ROOT).json()["result"]["items"][0]["name"] == "orders"
        assert client.post(ROOT + "/imports", json=body, headers=headers).json()[
            "result"
        ]["replayed"]
        assert client.get(ROOT + "/imports/import:1").status_code == 200
        assert (
            client.post(
                ROOT + "/imports", json=command(key="duplicate"), headers=headers
            ).json()["result"]["items"][0]["changed"]
            is False
        )
        value = api()
        value["paths"]["/orders"]["get"]["summary"] = "Updated purpose"
        change = command(value, key="revise:1", expectedVersions={"orders": 1})
        assert (
            client.post(ROOT + "/imports", json=change, headers=headers).status_code
            == 404
        )
        allow(app, "TOOL", "REVISE", item["toolId"] + ":aggregate", "tool-revise")
        changed = client.post(ROOT + "/imports", json=change, headers=headers)
        assert changed.status_code == 200, changed.text
        assert changed.json()["result"]["items"][0]["aggregateVersion"] == 2
        old = client.get(
            ROOT + "/" + item["toolId"], params={"revision": item["revisionId"]}
        ).json()["result"]
        assert old["record"]["purpose"] == ""
        with app.authority.connection_scope() as conn:
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='TOOL' AND action='REVISE'"
            )
        assert client.get(ROOT + "/imports/revise:1").status_code == 404
        assert (
            client.post(ROOT + "/imports", json=change, headers=headers).status_code
            == 404
        )
        with app.authority.connection_scope() as conn:
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='TOOL' AND action='IMPORT'"
            )
        assert (
            client.post(ROOT + "/imports", json=body, headers=headers).status_code
            == 404
        )


def test_foreign_scope_never_reads_drafts_or_receipts(app, monkeypatch):
    with (
        TestClient(app.application, base_url="https://console.example") as client,
        TestClient(app.application, base_url="https://console.example") as foreign,
    ):
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        fixture.login(foreign, "foreign-secret")
        grants(app)
        item = client.post(ROOT + "/imports", json=command(), headers=headers).json()[
            "result"
        ]["items"][0]
        with monkeypatch.context() as patch:
            patch.setattr(fixture, "SCOPE", AuthorityScope("tenant-b", "quality"))
            for action in ["LIST", "READ_SCOPE", "IMPORT"]:
                allow(
                    app,
                    "TOOL",
                    action,
                    "tool:collection",
                    "foreign-" + action,
                    principal="human:foreign",
                )
        assert foreign.get(ROOT).json()["result"]["items"] == []
        assert foreign.get(ROOT + "/" + item["toolId"]).status_code == 404
        assert foreign.get(ROOT + "/imports/import:1").status_code == 404


def test_file_limit_honors_route_envelope_without_expanding_other_routes(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        grants(app)
        value = api()
        value["info"] = {"description": "x" * 98000}
        body = command(value)
        assert len(json.dumps(body).encode()) > 128 * 1024
        response = client.post(ROOT + "/imports", json=body, headers=headers)
        assert response.status_code == 200, response.text
        value["info"]["description"] = "x" * 100001
        assert (
            client.post(
                ROOT + "/imports", json=command(value, key="too-big"), headers=headers
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/workbench/v1/employees", json=body, headers=headers
            ).status_code
            == 413
        )
        assert (
            client.post(
                ROOT + "/imports",
                json=command(key="boolean-version", expectedVersions={"orders": True}),
                headers=headers,
            ).status_code
            == 422
        )


def test_edit_preserves_source_history_and_does_not_require_import_again(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        grants(app)
        item = client.post(ROOT + "/imports", json=command(), headers=headers).json()[
            "result"
        ]["items"][0]
        allow(app, "TOOL", "REVISE", item["toolId"] + ":aggregate", "edit")
        with app.authority.connection_scope() as conn:
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='TOOL' AND action='IMPORT'"
            )
        body = {
            "commandId": "edit:1",
            "expectedVersion": 1,
            "content": {
                "name": "订单明细查询",
                "purpose": "核对订单信息",
                "inputSchema": {"type": "object"},
                "outputSchema": None,
                "sideEffect": "read-only",
            },
        }
        response = client.post(
            ROOT + "/" + item["toolId"] + "/draft", json=body, headers=headers
        )
        assert response.status_code == 200, response.text
        updated = response.json()["result"]["items"][0]
        assert updated["aggregateVersion"] == 2
        assert client.post(
            ROOT + "/" + item["toolId"] + "/draft", json=body, headers=headers
        ).json()["result"]["replayed"]
        assert client.get(ROOT + "/imports/edit:1").status_code == 200
        current = client.get(ROOT + "/" + item["toolId"]).json()["result"]
        old = client.get(
            ROOT + "/" + item["toolId"], params={"revision": item["revisionId"]}
        ).json()["result"]
        assert current["sourceDigest"] == old["sourceDigest"]
        assert (
            current["record"]["name"] == "订单明细查询"
            and old["record"]["name"] == "orders"
        )
        assert current["record"]["validation"] is None
        assert current["record"]["operation"]["name"] == "orders"
        assert current["publishedRevisionId"] is None
        invalid = {**body, "commandId": "edit:stale"}
        assert (
            client.post(
                ROOT + "/" + item["toolId"] + "/draft", json=invalid, headers=headers
            ).status_code
            == 409
        )


def test_scope_read_never_masks_exact_revocation(app):
    from test_workbench_business_process_postgres import revoke

    with (
        TestClient(app.application, base_url="https://console.example") as client,
        TestClient(app.application, base_url="https://console.example") as admin,
    ):
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        grants(app)
        item = client.post(ROOT + "/imports", json=command(), headers=headers).json()[
            "result"
        ]["items"][0]
        allow(
            app, "TOOL", "READ", item["toolId"] + ":" + item["revisionId"], "exact-read"
        )
        revoke(app, admin, "exact-read", "revoke-tool-read")
        assert client.get(ROOT + "/" + item["toolId"]).status_code == 404
        assert client.get(ROOT).json()["result"]["items"] == []
        assert client.get(ROOT + "/imports/import:1").status_code == 404
        assert (
            client.post(ROOT + "/imports", json=command(), headers=headers).status_code
            == 404
        )


def test_effect_declaration_round_trip_and_selection_boundary(app):
    grants(app)
    with TestClient(app.application, base_url="https://console.example") as client:
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        invalid = command(effects={"not-selected": "read-only"})
        assert (
            client.post(ROOT + "/imports", json=invalid, headers=headers).status_code
            == 422
        )
        body = command(effects={"orders": "creates-file"})
        saved = client.post(ROOT + "/imports", json=body, headers=headers)
        assert saved.status_code == 200, saved.text
        item = saved.json()["result"]["items"][0]
        value = client.get(ROOT + "/" + item["toolId"]).json()["result"]
        assert value["record"]["operation"]["sideEffect"] == "creates-file"
        assert value["record"]["validation"] is None
        assert not value["executionAuthorized"]
        body["effects"]["orders"] = "read-only"
        assert (
            client.post(ROOT + "/imports", json=body, headers=headers).status_code
            == 409
        )
