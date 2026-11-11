"""Filtered pages scan the authorized catalogue, not only the first raw page."""

import test_workbench_business_capability_postgres as fixture
from fastapi.testclient import TestClient
from test_workbench_team_postgres import allow

app = fixture.app
pytestmark = fixture.pytestmark
URL = fixture.PREFIX


def test_search_domain_favorites_and_cursor_are_authorized_and_bound(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, employee, body = fixture.setup(client, app)
        fixture.member_grant(app, employee)
        for action in ("CREATE", "LIST"):
            allow(
                app,
                "BUSINESS_CAPABILITY",
                action,
                "business-capability:collection",
                action,
            )
        for identity, title, domain in (
            ("a", "其他用途", None),
            ("b", "经营核对一", "运营管理"),
            ("c", "经营核对二", "运营管理"),
            ("private", "经营核对秘密", "保密领域"),
        ):
            revision = {
                **body["revision"],
                "capability_id": identity,
                "revision_id": identity + ":r1",
                "title": title,
            }
            if domain:
                revision["business_domain"] = domain
            saved = client.post(
                URL,
                json={
                    "revision": revision,
                    "expectedVersion": 0,
                    "commandId": "create:" + identity,
                },
                headers=headers,
            )
            assert saved.status_code == 201, saved.text
            if identity != "private":
                allow(
                    app,
                    "BUSINESS_CAPABILITY",
                    "READ",
                    f"business-capability:{identity}:{identity}:r1",
                    "read:" + identity,
                )
        domains = client.get(URL + "/domains").json()["result"]
        assert domains == {"domains": ["运营管理"], "hasUnassigned": True}
        query = {"pageSize": 1, "query": "经营核对", "domain": "运营管理"}
        first = client.get(URL, params=query).json()["result"]
        assert [v["capabilityId"] for v in first["items"]] == ["b"]
        assert first["nextCursor"]
        second = client.get(
            URL, params={**query, "cursor": first["nextCursor"]}
        ).json()["result"]
        assert [v["capabilityId"] for v in second["items"]] == ["c"]
        assert second["nextCursor"] is None
        changed = client.get(
            URL, params={**query, "query": "", "cursor": first["nextCursor"]}
        )
        assert changed.status_code == 422
        unassigned = client.get(URL, params={"domain": "__UNASSIGNED__"}).json()[
            "result"
        ]
        assert [v["capabilityId"] for v in unassigned["items"]] == ["a"]
        saved = client.post(
            URL + "/preferences",
            json={
                "expectedVersion": 0,
                "commandId": "favorite-c",
                "state": {"favorites": ["c"]},
            },
            headers=headers,
        )
        assert saved.status_code == 200, saved.text
        favorites = client.get(URL, params={**query, "favoritesOnly": True}).json()[
            "result"
        ]
        assert [v["capabilityId"] for v in favorites["items"]] == ["c"]
        assert favorites["nextCursor"] is None
        assert (
            client.get(URL, params={"domain": "保密领域"}).json()["result"]["items"]
            == []
        )
        with app.authority.connection_scope() as conn:
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='BUSINESS_CAPABILITY' AND action='READ'"
            )
        assert client.get(URL, params=query).json()["result"]["items"] == []
        assert client.get(URL + "/domains").json()["result"] == {
            "domains": [],
            "hasUnassigned": False,
        }
