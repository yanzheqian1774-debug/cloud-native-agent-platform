# ruff: noqa: F401, F811 -- Exact isolated owner fixture dependencies.
"""Directory uses session scope and current per-version grants, never default tenant."""

import pytest
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from agent_console.workbench_pagination import WorkbenchCursorCodec
from agent_console.workbench_resource_directory import ResourceDirectory
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation


def act(a, handler, query, *, context=None):
    context = context or a.subject
    with a.repository.pool.connection() as c, c.transaction():
        return handler(
            AuthorizedOwnerCall(
                "READ_RESOURCE_DIRECTORY",
                context,
                c,
                {},
                {},
                query,
                (),
                AuthorizedOwnerAuthority(a.adapter, context, c, 1, ()),
                1,
                1,
            )
        )


def test_directory_filters_unreadable_inputs_and_paginates_only_readable_exact_versions(
    automation,
):
    a = automation
    handler = ResourceDirectory(
        {**a.services, "mcp": a.services["skill"]}, WorkbenchCursorCodec(b"x" * 32)
    )
    assert act(a, handler, {})["items"] == []
    assert a.run()["state"] == "READY"
    items, cursor = [], None
    for _ in range(4):
        page = act(
            a, handler, {"pageSize": 2, **({"cursor": cursor} if cursor else {})}
        )
        items += page["items"]
        cursor = page["nextCursor"]
        if not cursor:
            break
    assert len(items) == 4
    assert {v["kind"] for v in items} == {"skill", "agent", "knowledge", "runtime"}
    assert all(v["isCurrentPublished"] and not v["executionReady"] for v in items)
    assert {v["identity"] for v in items} == {r.resource_id for r in a.refs.values()}
    assert page["scope"] == {
        "tenantId": a.e.scope.namespace,
        "securityDomain": a.e.scope.security_domain,
    }
    assert act(a, handler, {"kind": "mcp"})["items"] == []
    assert act(a, handler, {"query": "unreadable-other-name"})["items"] == []


def test_exact_identity_drilldown_search_keeps_per_revision_read_authority(automation):
    a = automation
    handler = ResourceDirectory(a.services, WorkbenchCursorCodec(b"x" * 32))
    known = a.refs["skill"].resource_id
    assert act(a, handler, {"kind": "skill", "query": known})["items"] == []
    a.run()
    all_items = act(a, handler, {"kind": "skill"})["items"]
    assert len(all_items) == 1
    by_identity = act(a, handler, {"kind": "skill", "query": known})
    assert by_identity["items"] == all_items
    assert act(a, handler, {"query": "foreign-resource-identity"})["items"] == []


def test_directory_cursor_cannot_cross_filters_or_subject_and_get_has_no_new_work(
    automation,
):
    from dataclasses import replace

    a = automation
    a.run()
    handler = ResourceDirectory(a.services, WorkbenchCursorCodec(b"x" * 32))
    first = act(a, handler, {"pageSize": 1})
    assert first["nextCursor"]
    with pytest.raises(WorkbenchOwnerError):
        act(a, handler, {"pageSize": 1, "cursor": first["nextCursor"], "kind": "skill"})
    with pytest.raises(WorkbenchOwnerError):
        act(
            a,
            handler,
            {"pageSize": 1, "cursor": first["nextCursor"]},
            context=replace(a.subject, principal_id="different-user"),
        )
    for _ in range(3):
        act(a, handler, {})
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.resource_automation"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )


def test_directory_real_bff_boundary_keeps_exact_reads_and_nonempty_command_contract(
    automation,
    monkeypatch,
):
    from contextlib import nullcontext
    from types import SimpleNamespace

    from agent_console.authority_contracts import AuthorityError
    from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
    from agent_console.workbench_resource_directory import install_directory, operations
    from fastapi.testclient import TestClient
    from test_workbench_bff import SessionStub

    a = automation
    a.adapter.controller.protected_request = lambda: nullcontext(
        SimpleNamespace(generation=1)
    )
    sessions = SessionStub()
    sessions.context = a.subject
    services = {**a.services, "mcp": a.services["skill"]}
    cursors = WorkbenchCursorCodec(b"x" * 32)
    app = create_workbench_bff(
        sessions,
        a.adapter,
        WorkbenchBffPolicy("workbench.example", "https://workbench.example"),
        operations=operations(services, cursors),
        route_installers=(install_directory(services, cursors, a.adapter),),
    )
    with TestClient(app, base_url="https://workbench.example") as client:
        assert client.get("/api/workbench/v1/resource-directory").status_code == 401
        client.cookies.set("__Host-workbench_session", sessions.secret)
        empty = client.get("/api/workbench/v1/resource-directory")
        assert empty.status_code == 200
        assert empty.json()["result"]["items"] == []
        from urllib.parse import quote

        ref = a.refs["knowledge"]
        path = (
            "/api/workbench/v1/resource-directory/knowledge/"
            + quote(ref.resource_id, safe="")
            + "/"
            + quote(ref.revision_id, safe="")
        )
        denied = client.get(path + "?projection=content")
        assert denied.status_code == 404
        assert "revision" not in denied.json()
        a.run()
        full = client.get(path)
        assert full.status_code == 200 and "usage" in full.json()["result"]

        def no_usage(*args):
            raise AssertionError("Content reads must not scan unrelated usages")

        monkeypatch.setattr(ResourceDirectory, "usage", no_usage)
        content = client.get(path + "?projection=content")
        assert content.status_code == 200
        assert content.json()["result"]["revision"] == full.json()["result"]["revision"]
        assert "usage" not in content.json()["result"]
        assert client.get(path + "?projection=all").status_code == 422
        response = client.get("/api/workbench/v1/resource-directory")
        assert response.status_code == 200
        assert len(response.json()["result"]["items"]) == 4
        assert (
            client.get("/api/workbench/v1/resource-directory?kind=mcp").json()[
                "result"
            ]["items"]
            == []
        )
        assert (
            client.get(
                "/api/workbench/v1/resource-directory?kind=skill&kind=mcp"
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/workbench/v1/resource-directory", headers={"X-Tenant-ID": "other"}
            ).status_code
            == 400
        )
        sessions.logged_out = True
        assert client.get("/api/workbench/v1/resource-directory").status_code == 401
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        a.adapter.execute(
            a.subject,
            (),
            operation="ANY_COMMAND",
            payload={},
            path={},
            query={},
            handler=lambda call: {},
        )


def test_directory_purpose_uses_only_authorized_exact_revision_content(automation):
    from agent_console.workbench_prepared_resources import TABLES

    a = automation
    handler = ResourceDirectory(a.services, WorkbenchCursorCodec(b"x" * 32))
    assert act(a, handler, {})["items"] == []
    a.run()
    items = act(a, handler, {})["items"]
    assert items
    purposes = []
    with a.repository.pool.connection() as connection:
        for item in items:
            table, column = TABLES[item["kind"]]
            row = connection.execute(
                f"SELECT r->'content' content FROM {table} t "
                "CROSS JOIN LATERAL jsonb_array_elements(t.record->'revisions') r "
                f"WHERE namespace=%s AND security_domain=%s AND {column}=%s "
                "AND r->>'revisionId'=%s",
                (
                    a.e.scope.namespace,
                    a.e.scope.security_domain,
                    item["identity"],
                    item["revisionId"],
                ),
            ).fetchone()
            content = row["content"] or {}
            expected = content.get("description") or content.get("businessPurpose")
            assert item["businessPurpose"] == expected
            purposes.append(item["businessPurpose"])
    assert any(purposes)


@pytest.mark.parametrize(
    "content",
    [
        None,
        [],
        {"description": {"secret": "not text"}},
        {"documents": [{"content": "not a purpose"}]},
    ],
)
def test_directory_does_not_invent_purpose_from_nontext_or_documents(content):
    from agent_console.workbench_resource_directory import revision_purpose

    assert revision_purpose({"content": content}) is None


def test_workflow_operation_projection_uses_exact_authorized_row_without_usage(
    automation, monkeypatch
):
    a = automation
    handler = ResourceDirectory(a.services, WorkbenchCursorCodec(b"x" * 32))
    query = {
        "kind": "skill",
        "status": "PUBLISHED",
        "projection": "workflow-skill-operations",
    }
    assert act(a, handler, query)["items"] == []
    a.run()

    def forbidden_usage(*args):
        raise AssertionError("Operation selector must not scan execution usage")

    monkeypatch.setattr(handler, "usage", forbidden_usage)
    summary = act(a, handler, {"kind": "skill", "status": "PUBLISHED"})["items"]
    assert all("workflowOperations" not in item for item in summary)
    items = act(a, handler, query)["items"]
    assert len(items) == 1
    item = items[0]
    source = item["workflowOperations"]
    assert source["identity"] == item["identity"]
    assert source["revisionId"] == item["revisionId"]
    assert source["digest"] == item["digest"]
    assert source["enabled"] is True and source["archived"] is False
    assert source["publishedRevisionId"] == item["revisionId"]
    service = a.services["skill"]
    record = service.repository.get(a.e.scope, "skill", item["identity"])
    exact = next(
        r for r in record["revisions"] if r["revisionId"] == item["revisionId"]
    )
    assert source["operations"] == exact["content"]["operations"]
    from dataclasses import replace

    assert (
        act(
            a, handler, query, context=replace(a.subject, principal_id="different-user")
        )["items"]
        == []
    )
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        act(
            a, handler, {"projection": "workflow-skill-operations", "kind": "knowledge"}
        )
