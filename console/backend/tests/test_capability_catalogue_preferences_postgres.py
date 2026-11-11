"""Own preferences through real BFF identity, CSRF, exact grants and PostgreSQL."""

import pytest
import test_workbench_business_capability_postgres as fixture
from agent_console.capability_catalogue_preferences import latest
from fastapi.testclient import TestClient
from psycopg import errors
from test_workbench_team_postgres import allow

app = fixture.app
pytestmark = fixture.pytestmark
URL = fixture.PREFIX + "/preferences"


def test_own_preferences_cas_replay_csrf_and_immutable_audit(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        csrf = fixture.employee_fixture.login(client, "alice-secret")
        headers = fixture.employee_fixture.unsafe_headers(csrf)
        assert client.get(URL).status_code == 404
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "LIST",
            "business-capability:collection",
            "prefs-list",
        )
        assert client.get(URL).json()["result"]["version"] == 0
        body = {
            "expectedVersion": 0,
            "commandId": "prefs:1",
            "state": {"query": "交接", "layout": "list"},
        }
        assert client.post(URL, json=body).status_code == 403
        saved = client.post(URL, json=body, headers=headers)
        assert saved.status_code == 200, saved.text
        assert saved.json()["result"]["version"] == 1
        assert client.post(URL, json=body, headers=headers).json()["result"]["replayed"]
        changed = {**body, "state": {"query": "另一项"}}
        assert client.post(URL, json=changed, headers=headers).status_code == 409
        assert (
            client.post(
                URL, json={**body, "commandId": "prefs:2"}, headers=headers
            ).status_code
            == 409
        )
        assert (
            client.post(
                URL, json={**body, "principalId": "human:bob"}, headers=headers
            ).status_code
            == 422
        )
        with TestClient(app.application, base_url="https://console.example") as bob:
            fixture.employee_fixture.login(bob, "bob-secret")
            allow(
                app,
                "BUSINESS_CAPABILITY",
                "LIST",
                "business-capability:collection",
                "bob-prefs",
                "human:bob",
            )
            assert bob.get(URL).json()["result"]["version"] == 0
        with app.authority.connection_scope() as conn:
            rows = conn.execute(
                "SELECT * FROM business_capability.catalogue_preferences"
            ).fetchall()
            assert len(rows) == 1
            row = rows[0]
            assert row["principal_id"] == "human:alice" and row["decision_id"]
            assert (
                latest(conn, (row["namespace"], "other-workspace", row["principal_id"]))
                is None
            )
            assert (
                latest(
                    conn, ("other-tenant", row["security_domain"], row["principal_id"])
                )
                is None
            )
            with pytest.raises(errors.RaiseException), conn.transaction():
                conn.execute(
                    "UPDATE business_capability.catalogue_preferences SET state='{}'"
                )
        assert client.get(URL).json()["result"]["state"]["query"] == "交接"


def test_favorite_requires_real_read_rechecks_replay_and_can_remove_after_revocation(
    app,
):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, employee, definition = fixture.setup(client, app)
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "CREATE",
            "business-capability:collection",
            "prefs-create",
        )
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "LIST",
            "business-capability:collection",
            "prefs-list",
        )
        fixture.member_grant(app, employee)
        saved = client.post(fixture.PREFIX, json=definition, headers=headers)
        assert saved.status_code == 201, saved.text
        identity = definition["revision"]["capability_id"]
        revision = definition["revision"]["revision_id"]
        body = {
            "expectedVersion": 0,
            "commandId": "prefs:1",
            "state": {"favorites": [identity]},
        }
        assert client.post(URL, json=body, headers=headers).status_code == 404
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "READ",
            f"business-capability:{identity}:{revision}",
            "prefs-read",
        )
        assert client.post(URL, json=body, headers=headers).status_code == 200
        with app.authority.connection_scope() as conn:
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='BUSINESS_CAPABILITY' AND action='READ'"
            )
        assert client.post(URL, json=body, headers=headers).status_code == 404
        removed = client.post(
            URL,
            json={
                "expectedVersion": 1,
                "commandId": "prefs:2",
                "state": {"favorites": []},
            },
            headers=headers,
        )
        assert removed.status_code == 200, removed.text
        assert removed.json()["result"]["state"]["favorites"] == []
        missing = client.post(
            URL,
            json={
                "expectedVersion": 2,
                "commandId": "prefs:3",
                "state": {"favorites": ["missing"]},
            },
            headers=headers,
        )
        assert missing.status_code == 404
        assert client.get(URL).json()["result"]["version"] == 2


def test_preferences_typed_bounds_and_duplicate_favorites(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        csrf = fixture.employee_fixture.login(client, "alice-secret")
        headers = fixture.employee_fixture.unsafe_headers(csrf)
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "LIST",
            "business-capability:collection",
            "prefs-list",
        )
        for state in (
            {"layout": "other"},
            {"query": "q" * 501},
            {"scrollTop": -1},
            {"loadedCount": 0},
            {"loadedCount": 10_001},
            {"loadedCount": 1.5},
            {"favorites": ["a", "a"]},
            {"scope": "other"},
            {"favorites": ["x"] * 501},
        ):
            response = client.post(
                URL,
                json={"expectedVersion": 0, "commandId": "invalid", "state": state},
                headers=headers,
            )
            assert response.status_code == 422, response.text
        assert client.get(URL).json()["result"]["version"] == 0
