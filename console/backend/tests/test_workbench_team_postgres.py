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
        ungranted = {
            **body,
            "workLinks": [
                {
                    "workflowRunId": "run:not-readable",
                    "preparationDigest": "a" * 64,
                    "problemId": "problem:hidden",
                    "problemRevisionId": "revision:hidden",
                    "problemDigest": "b" * 64,
                }
            ],
        }
        assert (
            client.post(PREFIX + "/teams", json=ungranted, headers=headers).status_code
            == 404
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
        work = client.get(path + "/work")
        assert work.status_code == 200, work.text
        assert work.json()["result"]["linkedCount"] == 0
        assert work.json()["result"]["items"] == []
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


def test_linked_work_requires_current_grants_on_save_replay_and_read(app):
    """Real BFF/session/CSRF/SQL; synthetic owner facts, no executor or model."""
    from agent_console.execution_preparation_postgres import PreparedExecutionStore
    from psycopg.types.json import Jsonb
    from test_execution_preparation import preparation

    scope = employee_fixture.SCOPE
    p = preparation().model_copy(
        update={"namespace": scope.tenant_id, "security_domain": scope.security_domain}
    )
    ref = p.semantics.target.problem
    with app.authority.connection_scope() as conn:
        for version in range(15, 51):
            files = list(employee_fixture.MIGRATIONS.glob(f"{version:04d}_*.sql"))
            if files:
                conn.execute(files[0].read_text())
        conn.execute(
            "CREATE TABLE IF NOT EXISTS private_conversation.journeys "
            "(tenant_id text NOT NULL,security_domain text NOT "
            "NULL,conversation_id text NOT NULL,version bigint NOT NULL,state "
            "jsonb NOT NULL,updated_at timestamptz NOT NULL DEFAULT "
            "now(),PRIMARY KEY(tenant_id,security_domain,conversation_id))"
        )
        key = (p.namespace, p.security_domain)
        conn.execute(
            "INSERT INTO business_problem_authority.problems VALUES "
            "(%s,%s,%s,'human:alice','DRAFT',1,%s,'human:alice',now(),now())",
            (*key, ref.resource_id, ref.revision_id),
        )
        conn.execute(
            "INSERT INTO business_problem_authority.problem_revisions VALUES "
            "(%s,%s,%s,%s,1,NULL,%s,%s,'测试关联工作','隔离合成记录','human:alice','human:"
            "alice',now())",
            (*key, ref.resource_id, ref.revision_id, ref.digest, b"{}"),
        )
        conn.execute(
            "INSERT INTO execution_authority.digital_employee_instances "
            "(namespace,security_domain,digital_employee_instance_id,definitio"
            "n_revision_id,aggregate_version,record) VALUES "
            "(%s,%s,%s,'fixture',1,%s)",
            (*key, p.root_instance_id, Jsonb({})),
        )
        conn.execute(
            "INSERT INTO execution_authority.assignments VALUES (%s,%s,%s,%s,%s,%s)",
            (*key, p.root_assignment_id, p.root_instance_id, "a" * 64, Jsonb({})),
        )
        conn.execute(
            "INSERT INTO execution_authority.workflow_runs "
            "(namespace,security_domain,workflow_run_id,assignment_id,approved"
            "_plan_revision_id,record) VALUES (%s,%s,%s,%s,'fixture-plan',%s)",
            (*key, p.run_id, p.root_assignment_id, Jsonb({})),
        )
        PreparedExecutionStore(conn).attach(p)
    with TestClient(app.application, base_url="https://console.example") as client:
        csrf = employee_fixture.login(client, "alice-secret")
        headers = employee_fixture.unsafe_headers(csrf)
        employee = prepare_employee(app, client, csrf)
        body = team_body(employee)
        body["workLinks"] = [
            {
                "workflowRunId": p.run_id,
                "preparationDigest": p.digest,
                "problemId": ref.resource_id,
                "problemRevisionId": ref.revision_id,
                "problemDigest": ref.digest,
            }
        ]
        allow(app, "TEAM", "CREATE", "team:collection", "work-team-create")
        allow(
            app,
            "EMPLOYEE",
            "READ",
            f"employee:{employee['employeeDefinitionId']}:{employee['employeeDefinitionRevisionId']}",
            "work-employee-read",
        )
        assert (
            client.post(PREFIX + "/teams", json=body, headers=headers).status_code
            == 404
        )
        allow(
            app,
            "EXECUTION",
            "READ",
            "governed-execution:prepared:" + p.digest,
            "work-execution",
        )
        assert (
            client.post(PREFIX + "/teams", json=body, headers=headers).status_code
            == 404
        )
        allow(
            app,
            "BUSINESS_PROBLEM",
            "READ",
            "business-problem:" + ref.resource_id,
            "work-problem",
        )
        wrong = {
            **body,
            "workLinks": [
                {**body["workLinks"][0], "problemRevisionId": "wrong-revision"}
            ],
        }
        assert (
            client.post(PREFIX + "/teams", json=wrong, headers=headers).status_code
            == 422
        )
        saved = client.post(PREFIX + "/teams", json=body, headers=headers)
        assert saved.status_code == 201, saved.text
        assert client.post(PREFIX + "/teams", json=body, headers=headers).json()[
            "result"
        ]["replayed"]
        allow(
            app, "TEAM", "READ", "team:team:quality:team-revision:1", "work-team-read"
        )
        path = PREFIX + "/teams/team:quality/revisions/team-revision:1/work"
        read = client.get(path)
        assert read.status_code == 200, read.text
        assert read.json()["result"]["items"][0]["workflowRunId"] == p.run_id
        with app.authority.connection_scope() as conn:
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants WHERE "
                "owner='EXECUTION'"
            )
        assert (
            client.post(PREFIX + "/teams", json=body, headers=headers).status_code
            == 404
        )
        hidden = client.get(path)
        assert hidden.status_code == 200, hidden.text
        assert hidden.json()["result"]["items"] == []
        assert hidden.json()["result"]["unavailableCount"] == 1
        with app.authority.connection_scope() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM team_definition.receipts"
                ).fetchone()["n"]
                == 1
            )
