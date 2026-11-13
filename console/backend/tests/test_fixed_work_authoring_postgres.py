"""Ordinary session and exact grants on disposable PostgreSQL, no trigger execution."""

import json
from datetime import timedelta

import pytest
import test_workbench_team_postgres as teams
from agent_console.fixed_work_authoring_postgres import compatibility, migrate
from agent_console.workbench_fixed_work import fixed_work_operations
from fastapi.testclient import TestClient
from test_fixed_work_authoring import body

pytestmark = teams.pytestmark


@pytest.fixture
def app(monkeypatch, tmp_path):
    original = teams.team_operations
    policy_path = tmp_path / "authoring.json"

    def operations(repository, employees, cursors):
        with repository.pool.connection() as c, c.transaction():
            migrate(c)
        return (
            *original(repository, employees, cursors),
            *fixed_work_operations(policy_path, lambda: value.now, cursors),
        )

    monkeypatch.setattr(teams, "team_operations", operations)
    generator = teams.app.__wrapped__(monkeypatch)
    value = next(generator)
    value.policy_path = policy_path
    try:
        yield value
    finally:
        generator.close()


def setup(app, client, *, revise=True):
    csrf = teams.employee_fixture.login(client, "alice-secret")
    employee = teams.prepare_employee(app, client, csrf)
    team = teams.team_body(employee)
    teams.allow(app, "TEAM", "CREATE", "team:collection", "create-team")
    teams.allow(
        app,
        "EMPLOYEE",
        "READ",
        f"employee:{employee['employeeDefinitionId']}:{employee['employeeDefinitionRevisionId']}",
        "member",
    )
    headers = teams.employee_fixture.unsafe_headers(csrf)
    saved = client.post(teams.PREFIX + "/teams", json=team, headers=headers)
    assert saved.status_code == 201, saved.text
    with app.authority.connection_scope() as c:
        row = c.execute("SELECT digest FROM team_definition.revisions").fetchone()
    teams.allow(app, "TEAM", "READ", "team:team:quality:team-revision:1", "team-read")
    if revise:
        teams.allow(app, "TEAM", "REVISE", "team:team:quality:aggregate", "team-revise")
    policy = dict(
        schemaVersion="fixed-work-authoring-policy.v1",
        policyId="test-authoring",
        enabled=True,
        expiresAt=(app.now + timedelta(hours=1)).isoformat(),
        scopes=[
            dict(
                tenantId="tenant-a",
                securityDomain="domain-a",
                subjectId="human:alice",
                teamId=team["teamId"],
                teamRevisionId=team["revisionId"],
                teamDigest=row["digest"],
                operations=["READ", "SAVE"],
            )
        ],
    )
    # Derive scope from the fixture's persisted team.
    with app.authority.connection_scope() as c:
        scope = c.execute(
            "SELECT namespace,security_domain FROM team_definition.revisions"
        ).fetchone()
    policy["scopes"][0].update(
        tenantId=scope["namespace"], securityDomain=scope["security_domain"]
    )
    app.policy_path.write_text(json.dumps(policy))
    app.policy_path.chmod(0o600)
    return (
        teams.PREFIX
        + "/teams/team:quality/revisions/team-revision:1/fixed-work-drafts",
        headers,
        policy,
    )


def test_ordinary_save_replay_revise_read_and_conflicts(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        url, h, _ = setup(app, client)
        first = client.post(url, json=body(), headers=h)
        assert first.status_code == 201, first.text
        result = first.json()["result"]
        assert result["executionEnabled"] is False and result["triggerCreated"] is False
        assert client.post(url, json=body(), headers=h).json()["result"] == result
        read = client.get(url + "/work:1/revisions/revision:1")
        assert read.status_code == 200, read.text
        assert read.json()["result"] == result
        assert (
            client.post(url, json={**body(), "title": "改变"}, headers=h).status_code
            == 409
        )
        newer = {
            **body(),
            "revisionId": "revision:2",
            "commandId": "save:2",
            "expectedVersion": 1,
            "predecessorRevisionId": "revision:1",
            "instruction": "更新说明",
        }
        saved = client.post(url, json=newer, headers=h)
        assert saved.status_code == 201, saved.text
        assert (
            client.post(
                url,
                json={**newer, "revisionId": "revision:3", "commandId": "save:3"},
                headers=h,
            ).status_code
            == 409
        )
        assert (
            client.get(url + "/work:1/revisions/revision:1").json()["result"] == result
        )
        with app.authority.connection_scope() as c:
            compatibility(c)
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_authoring.receipts"
                ).fetchone()["n"]
                == 2
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM team_definition.revisions"
                ).fetchone()["n"]
                == 1
            )


def test_two_gates_and_policy_withdrawal(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        url, h, policy = setup(app, client, revise=False)
        assert client.post(url, json=body(), headers=h).status_code == 404
        teams.allow(
            app, "TEAM", "REVISE", "team:team:quality:aggregate", "later-revise"
        )
        policy["enabled"] = False
        app.policy_path.write_text(json.dumps(policy))
        assert client.post(url, json=body(), headers=h).status_code == 503
        policy["enabled"] = True
        policy["scopes"][0]["subjectId"] = "human:bob"
        app.policy_path.write_text(json.dumps(policy))
        assert client.post(url, json=body(), headers=h).status_code == 403
        policy["scopes"][0]["subjectId"] = "human:alice"
        app.policy_path.write_text(json.dumps(policy))
        assert client.post(url, json=body(), headers=h).status_code == 201
        policy["expiresAt"] = (app.now - timedelta(seconds=1)).isoformat()
        app.policy_path.write_text(json.dumps(policy))
        assert client.post(url, json=body(), headers=h).status_code == 503
        assert client.get(url + "/work:1/revisions/revision:1").status_code == 503
        with app.authority.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_authoring.receipts"
                ).fetchone()["n"]
                == 1
            )


def test_read_revocation_blocks_exact_saved_configuration(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        url, h, _ = setup(app, client)
        assert client.post(url, json=body(), headers=h).status_code == 201
        with app.authority.connection_scope() as c:
            c.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='TEAM' AND action='READ'"
            )
        assert client.get(url + "/work:1/revisions/revision:1").status_code == 404
        assert client.post(url, json=body(), headers=h).status_code == 404


def test_duplicate_revision_rolls_back_head_and_receipt(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        url, h, _ = setup(app, client)
        assert client.post(url, json=body(), headers=h).status_code == 201
        second = {
            **body(),
            "revisionId": "revision:2",
            "commandId": "save:2",
            "expectedVersion": 1,
            "predecessorRevisionId": "revision:1",
        }
        assert client.post(url, json=second, headers=h).status_code == 201
        invalid = {
            **second,
            "revisionId": "revision:1",
            "commandId": "save:3",
            "expectedVersion": 2,
            "predecessorRevisionId": "revision:2",
        }
        rejected = client.post(url, json=invalid, headers=h)
        assert rejected.status_code == 409, rejected.text
        with app.authority.connection_scope() as c:
            head = c.execute("SELECT * FROM fixed_work_authoring.heads").fetchone()
            assert head["head_revision_id"] == "revision:2"
            assert head["aggregate_version"] == 2
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_authoring.receipts"
                ).fetchone()["n"]
                == 2
            )
        # Another allowed URL must not expose this work under the wrong team binding.
        assert (
            client.get(
                url.replace("team:quality", "team:other")
                + "/work:1/revisions/revision:1"
            ).status_code
            == 404
        )


def test_directory_persists_pages_and_does_not_promote_read(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        url, h, policy = setup(app, client)
        assert client.post(url, json=body(), headers=h).status_code == 201
        other = {**body(), "workId": "work:2", "commandId": "second-work"}
        assert client.post(url, json=other, headers=h).status_code == 201
        first = client.get(url + "?pageSize=1")
        assert first.status_code == 200, first.text
        page = first.json()["result"]
        assert page["configurationCanSave"] is True
        assert [i["draft"]["workId"] for i in page["items"]] == ["work:1"]
        assert page["nextCursor"]
        second = client.get(url, params={"pageSize": 1, "cursor": page["nextCursor"]})
        assert second.status_code == 200, second.text
        assert [i["draft"]["workId"] for i in second.json()["result"]["items"]] == [
            "work:2"
        ]
        assert second.json()["result"]["nextCursor"] is None
        assert (
            client.get(
                url, params={"pageSize": 2, "cursor": page["nextCursor"]}
            ).status_code
            == 422
        )
        assert client.get(url + "?pageSize=51").status_code == 422
        with app.authority.connection_scope() as c:
            c.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='TEAM' AND action='REVISE'"
            )
        denied_save = client.get(url).json()["result"]
        assert denied_save["configurationCanSave"] is False
        assert len(denied_save["items"]) == 2
        policy["scopes"][0]["operations"] = ["READ"]
        app.policy_path.write_text(json.dumps(policy))
        assert (
            client.get(
                url, params={"pageSize": 1, "cursor": page["nextCursor"]}
            ).status_code
            == 422
        )
        refreshed = client.get(url).json()["result"]
        assert len(refreshed["items"]) == 2
        assert refreshed["configurationCanSave"] is False
        assert client.post(url, json=body(), headers=h).status_code == 404
        with app.authority.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_authoring.receipts"
                ).fetchone()["n"]
                == 2
            )
