import os

import pytest
import test_workbench_employee_commands_postgres as fixture
import test_workbench_tool_definitions_postgres as tool_fixture
from fastapi.testclient import TestClient
from test_workbench_team_postgres import allow
from test_workbench_tool_definitions_postgres import ROOT, command, grants
from test_workbench_tool_definitions_postgres import app as tool_app


@pytest.fixture
def app(monkeypatch):
    # Imported app has no inherited module skip mark; require an explicit test DSN.
    url = (
        tool_fixture.URL
        or os.environ.get("AUTHORITY_I2_TEST_DATABASE_URL")
        or os.environ.get("AUTHORITY_I1_TEST_DATABASE_URL")
    )
    if not url:
        raise RuntimeError("TOOL_TEST_DATABASE_REQUIRED")
    monkeypatch.setattr(tool_fixture, "URL", url)
    yield from tool_app.__wrapped__(monkeypatch)


def test_current_ordinary_authority_csrf_publish_test_and_candidates(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        grants(app)
        allow(app, "TOOL", "MAINTAIN_SCOPE", "tool:collection", "maintain:tool")
        saved = client.post(ROOT + "/imports", json=command(), headers=headers).json()[
            "result"
        ]["items"][0]
        tool = saved["toolId"]
        content = {
            "name": "contract",
            "purpose": "synthetic only",
            "inputSchema": {"type": "object"},
            "outputSchema": {"type": "object"},
            "sideEffect": "read-only",
        }
        r = client.post(
            ROOT + "/" + tool + "/draft",
            json={
                "expectedVersion": 1,
                "commandId": "edit:contract",
                "content": content,
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        current = client.get(ROOT + "/" + tool).json()["result"]

        def cmd(action, key):
            return dict(
                action=action,
                commandId=key,
                expectedVersion=current["aggregateVersion"],
                revisionId=current["revisionId"],
                digest=current["digest"],
            )

        body = cmd("validate", "validate:bff")
        assert (
            client.post(ROOT + "/" + tool + "/commands", json=body).status_code == 403
        )
        r = client.post(ROOT + "/" + tool + "/commands", json=body, headers=headers)
        assert r.status_code == 200, r.text
        publish = cmd("publish", "publish:bff")
        assert (
            client.post(
                ROOT + "/" + tool + "/commands", json=publish, headers=headers
            ).status_code
            == 404
        )
        allow(app, "TOOL", "PUBLISH", tool + ":aggregate", "publish:tool")
        r = client.post(ROOT + "/" + tool + "/commands", json=publish, headers=headers)
        assert r.status_code == 200, r.text
        current = client.get(ROOT + "/" + tool).json()["result"]
        case = cmd("test", "test:bff") | {
            "testName": "cannot invent",
            "input": {"synthetic": True},
            "expectedOutput": {"invented": True},
        }
        assert (
            client.post(
                ROOT + "/" + tool + "/commands", json=case, headers=headers
            ).status_code
            == 404
        )
        allow(app, "TOOL", "TEST", tool + ":aggregate", "test:tool")
        r = client.post(ROOT + "/" + tool + "/commands", json=case, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["result"]["testResult"]["actual"] is None
        assert not r.json()["result"]["testResult"]["actualExecution"]
        assert client.get(ROOT + "/imports/test:bff").status_code == 200
        r = client.get(ROOT + "/" + tool + "/history")
        assert r.status_code == 200, r.text
        assert len(r.json()["result"]["commands"]) == 3
        candidates = client.get(ROOT + "/candidates").json()["result"]["items"]
        assert (
            len(candidates) == 1
            and candidates[0]["revisionId"] == current["revisionId"]
        )

        with app.authority.connection_scope() as connection:
            connection.execute(
                "DELETE FROM "
                "authorization_admin.effective_grants WHERE "
                "owner='TOOL' AND action='TEST'"
            )
        assert (
            client.post(
                ROOT + "/" + tool + "/commands", json=case, headers=headers
            ).status_code
            == 404
        )
        # The real ordinary Employee command must still read the exact Tool;
        # publishing it is not permission to bind it.
        allow(app, "EMPLOYEE", "CREATE", "employee:collection", "employee:create")
        allow(
            app,
            "AGENT",
            "READ",
            f"agent:{app.agent_id}:{app.agent_revision_id}",
            "agent:read",
        )
        employee = fixture.create_body(
            app,
            command_id="employee:tool-candidate",
            definition_id="employee:tool-candidate",
        )
        employee["members"].append(
            {
                "kind": "TOOL",
                "resourceId": tool,
                "revisionId": current["revisionId"],
                "digest": current["digest"],
            }
        )
        with app.authority.connection_scope() as connection:
            connection.execute(
                "DELETE FROM "
                "authorization_admin.effective_grants WHERE "
                "owner='TOOL' AND action='READ_SCOPE'"
            )
        denied = client.post(
            "/api/workbench/v1/employees", json=employee, headers=headers
        )
        assert denied.status_code == 404, denied.text
        allow(
            app,
            "TOOL",
            "READ",
            tool + ":" + current["revisionId"],
            "tool:exact-candidate-read",
        )
        created = client.post(
            "/api/workbench/v1/employees", json=employee, headers=headers
        )
        assert created.status_code == 201, created.text
