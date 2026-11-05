# ruff: noqa: F401,F811 -- Exact existing disposable-PG fixtures.
from dataclasses import replace

import pytest
from agent_console.resource_import import preview_manifests
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_resource_management import CONTENT, command, manager


def manifests():
    return [
        {
            "manifestVersion": "skill-mcp-workbench/v1",
            "kind": "skill",
            "name": name,
            "content": CONTENT,
        }
        for name in ["销售批量", "供应商批量"]
    ]


def test_batch_is_atomic_independent_drafts_replayed_once_and_payload_bound(manager):
    values = manifests()
    preview = preview_manifests(values, "skill")
    result = command(
        manager,
        "batch-import",
        key="batch-import-once",
        manifests=values,
        previewDigest=preview["previewDigest"],
    )
    assert result["importedRows"] == 2 and len(set(result["identities"])) == 2
    assert all(
        r["publishedRevisionId"] is None and r["lifecycleState"] == "DRAFT"
        for r in result["resources"]
    )
    assert (
        command(
            manager,
            "batch-import",
            key="batch-import-once",
            manifests=values,
            previewDigest=preview["previewDigest"],
        )
        == result
    )
    with pytest.raises(WorkbenchOwnerError, match="CONFLICT"):
        command(
            manager,
            "batch-import",
            key="batch-import-once",
            manifests=list(reversed(values)),
            previewDigest=preview["previewDigest"],
        )
    a, _ = manager
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_mcp_resource.resources "
                "WHERE record->>'name' IN ('销售批量','供应商批量')"
            ).fetchone()["n"]
            == 2
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )


def test_invalid_second_row_or_late_permission_failure_rolls_back_all_rows(manager):
    values = manifests()
    preview = preview_manifests(values, "skill")
    with pytest.raises(WorkbenchOwnerError, match="PREVIEW_INVALID"):
        command(
            manager,
            "batch-import",
            key="batch-invalid-preview",
            manifests=[values[0], {**values[1], "name": ""}],
            previewDigest=preview["previewDigest"],
        )
    a, m = manager
    original = m.authorize
    count = 0

    def fail_late(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 4:
            raise WorkbenchOwnerError("ISOLATED_LATE_DENIAL", 403)
        return original(*args, **kwargs)

    m.authorize = fail_late
    with pytest.raises(WorkbenchOwnerError, match="LATE_DENIAL"):
        command(
            manager,
            "batch-import",
            key="batch-late-denial",
            manifests=values,
            previewDigest=preview["previewDigest"],
        )
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_mcp_resource.resources "
                "WHERE record->>'name' IN ('销售批量','供应商批量')"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.prepared_resource_commands "
                "WHERE command_key LIKE 'resource-management:batch-%'"
            ).fetchone()["n"]
            == 0
        )


def test_authenticated_large_file_preflight_is_read_only_and_generic_limit_unchanged(
    manager,
):
    from agent_console.resource_management import install_management
    from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
    from fastapi.testclient import TestClient
    from test_workbench_bff import SessionStub

    a, m = manager
    session = SessionStub()
    session.context = a.subject
    path = "/api/workbench/v1/resource-management/skill/import-preview"
    app = create_workbench_bff(
        session,
        a.adapter,
        WorkbenchBffPolicy(
            "workbench.example",
            "https://workbench.example",
            route_body_limits=((path, 10 * 1024 * 1024),),
        ),
        route_installers=(install_management(m, a.adapter),),
    )
    data = "名称,业务用途,能力,说明\n批次测试,只读,READ_DATA,read only\n" + (
        "\n" * 140000
    )
    with TestClient(app, base_url="https://workbench.example") as client:
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Import-Filename": "resources.csv",
            "Origin": "https://workbench.example",
        }
        assert (
            client.post(path, content=data.encode(), headers=headers).status_code == 401
        )
        client.cookies.set("__Host-workbench_session", session.secret)
        assert (
            client.post(path, content=data.encode(), headers=headers).status_code == 403
        )
        headers["X-CSRF-Token"] = "csrf-token"
        response = client.post(path, content=data.encode(), headers=headers)
        assert response.status_code == 200, response.text
        assert (
            response.json()["result"]["ready"]
            and response.json()["result"]["validRows"] == 1
        )
        assert (
            client.post(
                "/api/workbench/v1/resource-management/skill/commands",
                content=data.encode(),
                headers=headers,
            ).status_code
            == 413
        )
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_mcp_resource.resources "
                "WHERE record->>'name'='批次测试'"
            ).fetchone()["n"]
            == 0
        )
