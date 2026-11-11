"""Real authorized publication with stale previews and immutable old definitions."""

import copy

import psycopg
import pytest
import test_workbench_business_capability_postgres as capability_fixture
import test_workbench_employee_commands_postgres as employee_fixture
from fastapi.testclient import TestClient
from test_workbench_business_capability_postgres import (
    PREFIX,
    member_grant,
    setup,
)
from test_workbench_team_postgres import allow

app = capability_fixture.app


def publish_employee(value, client, employee, headers):
    identity = employee["employeeDefinitionId"]
    revision = employee["employeeDefinitionRevisionId"]
    aggregate = f"employee:{identity}:aggregate"
    for action in ("VALIDATE", "PUBLISH"):
        allow(value, "EMPLOYEE", action, aggregate, "employee-" + action)
    allow(
        value,
        "EMPLOYEE",
        "APPROVE",
        aggregate,
        "employee-approve",
        principal="human:bob",
    )
    allow(
        value,
        "AGENT",
        "READ",
        f"agent:{value.agent_id}:{value.agent_revision_id}",
        "bob-agent",
        principal="human:bob",
    )
    path = f"/api/workbench/v1/employees/{identity}/revisions/{revision}"
    command = {
        "employeeDefinitionDigest": employee["employeeDefinitionDigest"],
        "expectedVersion": 1,
        "commandId": "emp-validate",
    }
    result = client.post(path + "/validation", json=command, headers=headers)
    assert result.status_code == 200, result.text
    with TestClient(value.application, base_url="https://console.example") as reviewer:
        csrf = employee_fixture.login(reviewer, "bob-secret")
        approved = reviewer.post(
            path + "/approvals",
            json={**command, "expectedVersion": 2, "commandId": "emp-approve"},
            headers=employee_fixture.unsafe_headers(csrf),
        )
        assert approved.status_code == 200, approved.text
    result = client.post(
        path + "/publication",
        json={**command, "expectedVersion": 3, "commandId": "emp-publish"},
        headers=headers,
    )
    assert result.status_code == 200, result.text


def access(value, body, action="READ", suffix="read"):
    revision = body["revision"]
    allow(
        value,
        "BUSINESS_CAPABILITY",
        action,
        f"business-capability:{revision['capability_id']}:{revision['revision_id']}",
        suffix,
    )


def path_for(body):
    revision = body["revision"]
    return PREFIX + f"/{revision['capability_id']}/revisions/{revision['revision_id']}"


def command(preview, key):
    return {
        "expectedVersion": preview["aggregateVersion"],
        "digest": preview["revisionDigest"],
        "impactDigest": preview["impactDigest"],
        "commandId": key,
        "reason": "核对本次定义和固定绑定;不代表业务执行通过",
    }


def test_publication_requires_published_member_and_exact_consolidated_review(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, employee, body = setup(client, app)
        member_grant(app, employee)
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "CREATE",
            "business-capability:collection",
            "cap-create",
        )
        result = client.post(PREFIX, json=body, headers=headers)
        assert result.status_code == 201, result.text
        access(app, body)
        path = path_for(body)
        unpublished = client.get(path + "/publication-preview")
        assert unpublished.status_code == 409, unpublished.text
        publish_employee(app, client, employee, headers)
        preview = client.get(path + "/publication-preview")
        assert preview.status_code == 200, preview.text
        data = preview.json()["result"]
        assert data["bindingChanges"] and data["fieldChanges"]
        assert data["automaticReferenceUpdates"] is False
        review = command(data, "pub:1")
        assert (
            client.post(path + "/publication", json=review, headers=headers).status_code
            == 404
        )
        access(app, body, "REVIEW_PUBLISH", "review-exact")
        assert (
            client.post(
                path + "/publication",
                json={**review, "impactDigest": "f" * 64},
                headers=headers,
            ).status_code
            == 409
        )
        published = client.post(path + "/publication", json=review, headers=headers)
        assert published.status_code == 201, published.text
        assert published.json()["result"]["aggregateVersion"] == 2
        assert published.json()["result"]["executionAuthorized"] is False
        replay = client.post(path + "/publication", json=review, headers=headers)
        assert replay.status_code == 201 and replay.json()["result"]["replayed"]
        read = client.get(path).json()["result"]
        assert read["currentDraftRevisionId"] is None
        assert read["publishedRevisionId"] == body["revision"]["revision_id"]
        with app.authority.connection_scope() as conn:
            rows = conn.execute(
                "SELECT * FROM business_capability.publications"
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["authority_basis"] == "HUMAN_EXACT_REVIEW"
            assert rows[0]["actor_id"] == "human:alice"
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='EMPLOYEE'"
            )
        assert (
            client.post(path + "/publication", json=review, headers=headers).status_code
            == 404
        )
        with app.authority.connection_scope() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_capability.publications"
                ).fetchone()["n"]
                == 1
            )


def test_published_and_one_draft_coexist_and_stale_preview_cannot_publish(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, employee, body = setup(client, app)
        member_grant(app, employee)
        publish_employee(app, client, employee, headers)
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "CREATE",
            "business-capability:collection",
            "cap-create",
        )
        assert client.post(PREFIX, json=body, headers=headers).status_code == 201
        access(app, body)
        access(app, body, "REVIEW_PUBLISH", "publish-old")
        path = path_for(body)
        preview = client.get(path + "/publication-preview").json()["result"]
        result = client.post(
            path + "/publication", json=command(preview, "pub:1"), headers=headers
        )
        assert result.status_code == 201, result.text
        original = client.get(path).json()["result"]["revision"]
        identity = body["revision"]["capability_id"]
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "REVISE",
            f"business-capability:{identity}:aggregate",
            "revise",
        )
        successor = copy.deepcopy(body)
        successor.update(expectedVersion=2, commandId="draft:2")
        successor["revision"].update(
            revision_id="capability-revision:2",
            predecessor_revision_id=body["revision"]["revision_id"],
            title="新的修改草稿",
        )
        assert client.post(PREFIX, json=successor, headers=headers).status_code == 201
        access(app, successor, suffix="read-draft")
        access(app, successor, "REVIEW_PUBLISH", "publish-draft")
        allow(
            app, "BUSINESS_CAPABILITY", "LIST", "business-capability:collection", "list"
        )
        listing = client.get(PREFIX).json()["result"]["items"]
        assert len(listing) == 1
        assert listing[0]["title"] == body["revision"]["title"]
        assert (
            listing[0]["currentPublished"]["revisionId"]
            == body["revision"]["revision_id"]
        )
        assert listing[0]["currentDraft"]["revisionId"] == "capability-revision:2"
        draft_path = path_for(successor)
        preview = client.get(draft_path + "/publication-preview").json()["result"]
        assert preview["previousPublishedRevisionId"] == body["revision"]["revision_id"]
        assert [x["field"] for x in preview["fieldChanges"]] == ["title"]
        newer = copy.deepcopy(successor)
        newer.update(expectedVersion=3, commandId="draft:3")
        newer["revision"].update(
            revision_id="capability-revision:3",
            predecessor_revision_id="capability-revision:2",
            title="再次修改",
        )
        assert client.post(PREFIX, json=newer, headers=headers).status_code == 201
        rejected = client.post(
            draft_path + "/publication",
            json=command(preview, "pub:stale"),
            headers=headers,
        )
        assert rejected.status_code == 409, rejected.text
        assert client.get(path).json()["result"]["revision"] == original
        with (
            pytest.raises(psycopg.Error, match="CAPABILITY_IMMUTABLE_RECORD"),
            app.authority.connection_scope() as conn,
        ):
            conn.execute("DELETE FROM business_capability.publications")
