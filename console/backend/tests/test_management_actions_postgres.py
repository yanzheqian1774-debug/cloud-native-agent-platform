# ruff: noqa: F401,F811 -- explicit isolated account fixture
"""Isolated real BFF/current grants; not a production authorization exercise."""

import os

import pytest
import test_workbench_employee_commands_postgres as employees
import test_workbench_team_postgres as teams
from agent_console.workbench_employee_relations import operations as relations
from fastapi.testclient import TestClient
from test_development_administrator import login as account_login
from test_development_administrator import setup as admin_setup

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEAM_TEST_DATABASE_URL"),
    reason="Dedicated isolated PostgreSQL required",
)
PREFIX = "/api/workbench/v1"


@pytest.fixture
def app(monkeypatch):
    original = employees.employee_operations
    monkeypatch.setattr(
        employees,
        "employee_operations",
        lambda repository, cursors: (
            *original(repository, cursors),
            *relations(repository, None, cursors),
        ),
    )
    generator = teams.app.__wrapped__(monkeypatch)
    value = next(generator)
    try:
        yield value
    finally:
        generator.close()


def count_facts(app):
    with app.authority.connection_scope() as c:
        return tuple(
            c.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"]
            for table in (
                "digital_employee_definition.facts",
                "team_definition.receipts",
                "authorization_admin.grants",
                "authorization_admin.grant_decisions",
            )
        )


def test_collection_projection_is_read_only_exact_and_current(app):
    with TestClient(app.application, base_url="https://console.example") as c:
        employees.login(c, "alice-secret")
        # CREATE-only employee, no LIST grant: observe own create permission.
        own = c.get(PREFIX + "/employees/capabilities")
        assert own.status_code == 200, own.text
        assert own.json()["result"]["actions"]["CREATE"]["authorized"] is True
        assert (
            c.get(PREFIX + "/teams/capabilities").json()["result"]["actions"]["CREATE"][
                "authorized"
            ]
            is False
        )
        teams.allow(app, "TEAM", "LIST", "team:collection", "list")
        teams.allow(app, "EMPLOYEE", "LIST", "employee:collection", "elist")
        before = count_facts(app)
        first = c.get(PREFIX + "/teams/capabilities").json()["result"]
        assert first["actions"]["CREATE"]["authorized"] is False
        assert first["subjectId"] == "human:alice" and first["target"] is None
        assert (
            c.get(PREFIX + "/employees/capabilities").json()["result"]["actions"][
                "CREATE"
            ]["authorized"]
            is True
        )
        assert count_facts(app) == before
        teams.allow(app, "TEAM", "CREATE", "team:collection", "create")
        assert (
            c.get(PREFIX + "/teams/capabilities").json()["result"]["actions"]["CREATE"][
                "authorized"
            ]
            is True
        )
        with app.authority.connection_scope() as conn:
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='TEAM' AND action='CREATE'"
            )
        assert (
            c.get(PREFIX + "/teams/capabilities").json()["result"]["actions"]["CREATE"][
                "authorized"
            ]
            is False
        )
    with TestClient(app.application, base_url="https://console.example") as other:
        employees.login(other, "bob-secret")
        result = other.get(PREFIX + "/teams/capabilities").json()["result"]
        assert result["subjectId"] == "human:bob"
        assert result["actions"]["CREATE"]["authorized"] is False
        assert (
            other.get(PREFIX + "/teams/capabilities?subject=human:alice").status_code
            >= 400
        )
        with app.authority.connection_scope() as connection:
            connection.execute(
                "UPDATE browser_identity.sessions "
                "SET issued_at=now()-interval '2 hours', "
                "last_seen_at=now()-interval '2 hours', "
                "idle_expires_at=now()-interval '1 hour', "
                "absolute_expires_at=now()-interval '1 hour' "
                "WHERE principal_id='human:bob'"
            )
        assert other.get(PREFIX + "/teams/capabilities").status_code in {401, 403, 404}
    with TestClient(app.application, base_url="https://console.example") as anonymous:
        assert anonymous.get(PREFIX + "/teams/capabilities").status_code in {
            401,
            403,
            404,
        }


def test_exact_team_and_employee_actions_do_not_infer_mutation_from_read(app):
    with TestClient(app.application, base_url="https://console.example") as c:
        csrf = employees.login(c, "alice-secret")
        employee = teams.prepare_employee(app, c, csrf)
        body = teams.team_body(employee)
        member = body["members"][0]
        ref = (
            f"employee:{member['employeeDefinitionId']}:{member['employeeRevisionId']}"
        )
        teams.allow(app, "EMPLOYEE", "READ", ref, "member")
        teams.allow(app, "TEAM", "CREATE", "team:collection", "create")
        assert (
            c.post(
                PREFIX + "/teams", json=body, headers=employees.unsafe_headers(csrf)
            ).status_code
            == 201
        )
        teams.allow(
            app, "TEAM", "READ", f"team:{body['teamId']}:{body['revisionId']}", "read"
        )
        team_url = PREFIX + f"/teams/{body['teamId']}/revisions/{body['revisionId']}"
        employee_url = (
            PREFIX + f"/employees/{member['employeeDefinitionId']}/revisions/"
            f"{member['employeeRevisionId']}/authoring"
        )
        before = count_facts(app)
        assert (
            c.get(team_url).json()["result"]["maintenanceActions"]["actions"]["REVISE"][
                "authorized"
            ]
            is False
        )
        value = c.get(employee_url)
        assert value.status_code == 200, value.text
        actions = value.json()["result"]["maintenanceActions"]["actions"]
        assert actions["CREATE"]["authorized"] is True
        assert all(
            actions[a]["authorized"] is False
            for a in ("VALIDATE", "APPROVE", "PUBLISH")
        )
        assert count_facts(app) == before
        teams.allow(app, "TEAM", "REVISE", f"team:{body['teamId']}:aggregate", "revise")
        assert (
            c.get(team_url).json()["result"]["maintenanceActions"]["actions"]["REVISE"][
                "authorized"
            ]
            is True
        )
        with app.authority.connection_scope() as connection:
            connection.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='TEAM' AND action='CREATE'"
            )
        owner_result = c.get(team_url).json()["result"]
        owner_actions = owner_result["maintenanceActions"]["actions"]
        assert owner_actions["REVISE"]["authorized"] is True
        assert owner_actions["SELECT_OWNER"]["authorized"] is False
        teams.allow(
            app,
            "EMPLOYEE",
            "VALIDATE",
            f"employee:{member['employeeDefinitionId']}:aggregate",
            "validate",
        )
        actions = c.get(employee_url).json()["result"]["maintenanceActions"]["actions"]
        assert actions["VALIDATE"] == {"authorized": True, "lifecycleEligible": True}
        assert actions["PUBLISH"] == {"authorized": False, "lifecycleEligible": False}
        with app.authority.connection_scope() as conn:
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='EMPLOYEE' AND action='READ'"
            )
        assert c.get(employee_url).status_code == 404


def test_configured_development_administrator_uses_existing_authorizer(admin_setup):
    from dataclasses import replace

    from agent_console.authority_contracts import AuthorityError
    from agent_console.grant_administration_application import (
        GenerationAuthorizationReader,
    )
    from agent_console.workbench_management_actions import collection_projection
    from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization

    repo, generation, service, reader = admin_setup
    _, context = service.authenticate_session(account_login(service, "devadmin").value)
    owner = WorkbenchOwnerAuthorization(employees.Controller(generation), repo, reader)

    def read(current_owner, subject, operation, kind):
        def handler(call):
            assert call.decisions == ()
            value = collection_projection(call, kind)
            assert call.authority.decisions == {}
            return value

        return current_owner.execute(
            subject,
            (),
            operation=operation,
            payload={},
            path={},
            query={},
            handler=handler,
        )

    for operation, kind in (
        ("READ_TEAM_CAPABILITIES", "TEAM"),
        ("READ_EMPLOYEE_CAPABILITIES", "EMPLOYEE"),
    ):
        assert (
            read(owner, context, operation, kind)["actions"]["CREATE"]["authorized"]
            is True
        )
    disabled = GenerationAuthorizationReader(
        replace(generation, development_administrator=False),
        repo,
        repo,
        recovery_epoch=1,
    )
    readonly = WorkbenchOwnerAuthorization(
        employees.Controller(generation), repo, disabled
    )
    assert (
        read(readonly, context, "READ_TEAM_CAPABILITIES", "TEAM")["actions"]["CREATE"][
            "authorized"
        ]
        is False
    )
    with pytest.raises(AuthorityError):
        read(
            owner,
            replace(context, principal_id="human:forged"),
            "READ_TEAM_CAPABILITIES",
            "TEAM",
        )
