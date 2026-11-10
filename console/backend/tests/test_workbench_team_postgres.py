"""Real session/CSRF/exact-grant team operations on a disposable database."""

import os

import pytest
import test_workbench_employee_commands_postgres as employee_fixture
from agent_console.authority_contracts import ExactGrant
from agent_console.team_definition_postgres import PostgresTeamDefinitionRepository
from agent_console.workbench_team import team_operations
from fastapi.testclient import TestClient

URL = os.environ.get("TEAM_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Dedicated PostgreSQL required")
PREFIX = "/api/workbench/v1"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(employee_fixture, "DATABASE_URL", URL)
    original = employee_fixture.employee_operations

    def operations(repository, cursors):
        teams = PostgresTeamDefinitionRepository(repository.pool)
        teams.migrate(employee_fixture.MIGRATIONS / "0051_team_definition.sql")
        return (
            *original(repository, cursors),
            *team_operations(teams, repository, cursors),
        )

    monkeypatch.setattr(employee_fixture, "employee_operations", operations)
    generator = employee_fixture.employee_workbench.__wrapped__()
    value = next(generator)
    try:
        yield value
    finally:
        generator.close()


def allow(app, owner, action, resource, key, principal="human:alice"):
    employee_fixture.insert_dynamic_grant(
        app.authority,
        app.now,
        principal=principal,
        grant=ExactGrant(owner, action, resource),
        key=key,
    )


def prepare_employee(app, client, csrf):
    allow(
        app, "AGENT", "READ", f"agent:{app.agent_id}:{app.agent_revision_id}", "agent"
    )
    body = employee_fixture.create_body(
        app, command_id="create:employee", definition_id="employee:team-member"
    )
    response = client.post(
        PREFIX + "/employees", json=body, headers=employee_fixture.unsafe_headers(csrf)
    )
    assert response.status_code == 201, response.text
    return response.json()["result"]


def team_body(employee):
    return {
        "teamId": "team:quality",
        "revisionId": "team-revision:1",
        "title": "交接核对团队",
        "goal": "核对上线交接材料",
        "ownerId": "human:alice",
        "expectedVersion": 0,
        "commandId": "save:1",
        "members": [
            {
                "employeeDefinitionId": employee["employeeDefinitionId"],
                "employeeRevisionId": employee["employeeDefinitionRevisionId"],
                "employeeDigest": employee["employeeDefinitionDigest"],
                "responsibility": "核对缺失说明",
                "handoff": "交付缺失项清单",
            }
        ],
    }


def test_real_session_team_save_requires_own_and_exact_member_grants(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        csrf = employee_fixture.login(client, "alice-secret")
        employee = prepare_employee(app, client, csrf)
        body = team_body(employee)
        headers = employee_fixture.unsafe_headers(csrf)
        assert (
            client.post(PREFIX + "/teams", json=body, headers=headers).status_code
            == 404
        )
        allow(app, "TEAM", "CREATE", "team:collection", "team-create")
        assert (
            client.post(PREFIX + "/teams", json=body, headers=headers).status_code
            == 404
        )
        member = body["members"][0]
        allow(
            app,
            "EMPLOYEE",
            "READ",
            f"employee:{member['employeeDefinitionId']}:{member['employeeRevisionId']}",
            "member-read",
        )
        assert client.post(PREFIX + "/teams", json=body).status_code == 403
        bad = {**body, "members": [{**member, "employeeDigest": "f" * 64}]}
        rejected = client.post(PREFIX + "/teams", json=bad, headers=headers)
        assert rejected.status_code == 409, rejected.text
        saved = client.post(PREFIX + "/teams", json=body, headers=headers)
        assert saved.status_code == 201, saved.text
        assert saved.json()["result"]["replayed"] is False
        replay = client.post(PREFIX + "/teams", json=body, headers=headers)
        assert replay.status_code == 201, replay.text
        assert replay.json()["result"]["replayed"] is True
        with app.authority.connection_scope() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) AS n FROM team_definition.receipts"
                ).fetchone()["n"]
                == 1
            )
            # Revocation is checked before replay, not skipped because content exists.
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='EMPLOYEE'"
            )
        assert (
            client.post(PREFIX + "/teams", json=body, headers=headers).status_code
            == 404
        )


def test_revision_edit_read_list_and_employee_content_unchanged(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        csrf = employee_fixture.login(client, "alice-secret")
        headers = employee_fixture.unsafe_headers(csrf)
        employee = prepare_employee(app, client, csrf)
        body = team_body(employee)
        member = body["members"][0]
        allow(app, "TEAM", "CREATE", "team:collection", "team-create")
        allow(
            app,
            "EMPLOYEE",
            "READ",
            f"employee:{member['employeeDefinitionId']}:{member['employeeRevisionId']}",
            "member-read",
        )
        assert (
            client.post(PREFIX + "/teams", json=body, headers=headers).status_code
            == 201
        )
        successor = {
            **body,
            "revisionId": "team-revision:2",
            "predecessorRevisionId": "team-revision:1",
            "expectedVersion": 1,
            "commandId": "save:2",
            "goal": "核对回退说明",
        }
        assert (
            client.post(PREFIX + "/teams", json=successor, headers=headers).status_code
            == 404
        )
        allow(app, "TEAM", "REVISE", "team:team:quality:aggregate", "team-revise")
        assert (
            client.post(PREFIX + "/teams", json=successor, headers=headers).status_code
            == 201
        )
        stale = {**successor, "revisionId": "team-revision:3", "commandId": "save:3"}
        assert (
            client.post(PREFIX + "/teams", json=stale, headers=headers).status_code
            == 409
        )
        path = PREFIX + "/teams/team:quality/revisions/team-revision:1"
        assert client.get(path).status_code == 404
        allow(app, "TEAM", "READ", "team:team:quality:team-revision:1", "team-read")
        result = client.get(path)
        assert result.status_code == 200, result.text
        assert result.json()["result"]["aggregateVersion"] == 2
        assert result.json()["result"]["headRevisionId"] == "team-revision:2"
        assert result.json()["result"]["revision"]["goal"] == body["goal"]
        allow(app, "TEAM", "LIST", "team:collection", "team-list")
        second = {**body, "teamId": "team:z-other", "commandId": "save:other"}
        assert (
            client.post(PREFIX + "/teams", json=second, headers=headers).status_code
            == 201
        )
        listing = client.get(PREFIX + "/teams?pageSize=1")
        assert listing.status_code == 200, listing.text
        assert listing.json()["result"]["items"][0]["revisionId"] == "team-revision:2"
        cursor = listing.json()["result"]["nextCursor"]
        assert cursor
        next_page = client.get(
            PREFIX + "/teams", params={"pageSize": 1, "cursor": cursor}
        )
        assert next_page.status_code == 200, next_page.text
        assert next_page.json()["result"]["items"][0]["teamId"] == "team:z-other"
        assert next_page.json()["result"]["nextCursor"] is None
        assert (
            client.get(
                PREFIX + "/teams", params={"pageSize": 2, "cursor": cursor}
            ).status_code
            == 422
        )
        read_employee = client.get(
            PREFIX
            + f"/employees/{member['employeeDefinitionId']}/revisions/"
            + member["employeeRevisionId"]
        )
        assert read_employee.status_code == 200, read_employee.text
        assert (
            read_employee.json()["result"]["employeeDefinitionDigest"]
            == member["employeeDigest"]
        )
        assert read_employee.json()["result"]["aggregateVersion"] == 1
