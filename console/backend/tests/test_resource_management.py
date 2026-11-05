# ruff: noqa: F401,F811,E501 -- Existing disposable PostgreSQL fixtures.
from contextlib import nullcontext
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import AuthorityError
from agent_console.resource_management import (
    ManagementPolicy,
    ManagementScope,
    ManagementTargets,
    ResourceManagement,
    install_management,
)
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation

CONTENT = {
    "description": "隔离资源创建验证",
    "capabilities": ["READ_DATA"],
    "instructions": "只读取合成数据",
    "sideEffect": "READ",
}


@pytest.fixture
def manager(automation):
    a = automation
    g = a.automation.grants
    extra = tuple(
        RequestabilityRule("SKILL", act, "skill-invocation:", "RESOURCE_MANAGEMENT")
        for act in [
            "CREATE_RESOURCE",
            "MANAGE_RESOURCE",
            "CONNECT_MCP",
            "READ_RESOURCE",
            "REVIEW_PUBLISH_RESOURCE",
        ]
    )
    gen = replace(a.gen, requestability=a.gen.requestability + extra)
    g._generation_provider = lambda: gen
    g.authorization._generation_provider = lambda: gen
    g.target_validator.additional += (ManagementTargets(),)
    a.adapter.controller.protected_request = lambda: nullcontext(
        SimpleNamespace(generation=1)
    )
    policy = ManagementPolicy(
        enabled=True,
        policyId="isolated-authoring",
        policyVersion="1",
        issuer=a.policy.issuer,
        credentialPath=a.policy.credentialPath,
        workScopes=(
            ManagementScope(
                namespace=a.subject.scope.tenant_id,
                securityDomain=a.subject.scope.security_domain,
                subject=a.subject.principal_id,
                kinds=("skill", "mcp"),
                expiresAt=g.clock() + timedelta(hours=1),
            ),
        ),
    )
    return a, ResourceManagement({**a.services, "mcp": a.services["skill"]}, policy, g)


def command(pair, action, *, kind="skill", key=None, **payload):
    a, m = pair
    with a.authority.connection_scope() as c:
        call = AuthorizedOwnerCall(
            "RESOURCE_MANAGEMENT",
            a.subject,
            c,
            {
                "action": action,
                "commandKey": key or action + "-isolated-command",
                **payload,
            },
            {"kind": kind},
            {},
            (),
            AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ()),
            1,
            1,
        )
        return m.handle(call)


def test_authoring_create_import_edit_policy_publish_successor_preserves_history_and_no_run(
    manager,
):
    a, m = manager
    created = command(manager, "create", name="测试技能", content=CONTENT)
    assert command(manager, "create", name="测试技能", content=CONTENT) == created
    with pytest.raises(WorkbenchOwnerError, match="RESOURCE_COMMAND_CONFLICT"):
        command(manager, "create", name="不同参数", content=CONTENT)
    r = created["resource"]
    identity = r["resourceId"]
    old = r["revisions"][0].copy()
    edited = command(
        manager,
        "edit",
        identity=identity,
        expectedVersion=r["aggregateVersion"],
        content={**CONTENT, "description": "已更新描述"},
    )["resource"]
    assert edited["revisions"][0] == old
    with pytest.raises(WorkbenchOwnerError, match="STALE"):
        command(
            manager,
            "edit",
            key="stale-edit-key",
            identity=identity,
            expectedVersion=1,
            content=CONTENT,
        )
    published = command(
        manager,
        "publish",
        identity=identity,
        expectedVersion=edited["aggregateVersion"],
    )["resource"]
    assert (
        published["publishedRevisionId"]
        and published["revisions"][-1]["state"] == "PUBLISHED"
    )
    assert published["reviews"][-1]["actor"] == m.policy.issuer
    successor = command(
        manager,
        "successor",
        identity=identity,
        expectedVersion=published["aggregateVersion"],
    )["resource"]
    assert (
        successor["publishedRevisionId"] == published["publishedRevisionId"]
        and successor["currentDraftRevisionId"] != published["publishedRevisionId"]
    )
    manifest = {
        "manifestVersion": "skill-mcp-workbench/v1",
        "kind": "skill",
        "name": "导入副本",
        "content": CONTENT,
    }
    imported = command(manager, "import", manifest=manifest)["resource"]
    assert (
        imported["resourceId"] != identity and imported["publishedRevisionId"] is None
    )
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT to_regclass('workflow_planning.invocations') t"
            ).fetchone()["t"]
            is None
        )


def test_denied_foreign_resource_and_inline_secrets_rollback(manager):
    a, m = manager
    for payload in [
        {"content": {**CONTENT, "inputSchema": {"password": "not-a-real-secret"}}},
        {"content": CONTENT, "name": ""},
    ]:
        with pytest.raises((WorkbenchOwnerError, ValueError)):
            command(
                manager,
                "create",
                key="denied-create-" + str(len(payload)),
                name=payload.get("name", "拒绝"),
                content=payload["content"],
            )
    with pytest.raises(WorkbenchOwnerError, match="NOT_FOUND"):
        command(
            manager,
            "edit",
            identity=a.refs["skill"].resource_id,
            expectedVersion=1,
            content=CONTENT,
        )
    old = m.policy
    m.policy = old.model_copy(update={"enabled": False})
    with pytest.raises(AuthorityError):
        command(manager, "create", name="拒绝", content=CONTENT)
    m.policy = old
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.prepared_resource_commands WHERE result->>'schemaVersion'='resource-management-receipt.v1'"
            ).fetchone()["n"]
            == 0
        )


def test_http_session_csrf_receipt_and_cross_scope(manager):
    from fastapi.testclient import TestClient
    from test_workbench_bff import SessionStub

    a, m = manager
    s = SessionStub()
    s.context = a.subject
    app = create_workbench_bff(
        s,
        a.adapter,
        WorkbenchBffPolicy("workbench.example", "https://workbench.example"),
        route_installers=(install_management(m, a.adapter),),
    )
    with TestClient(app, base_url="https://workbench.example") as c:
        root = "/api/workbench/v1/resource-management/skill"
        assert c.get(root).status_code == 401
        c.cookies.set("__Host-workbench_session", s.secret)
        assert c.get(root).json()["result"]["items"] == []
        body = {
            "action": "create",
            "commandKey": "http-create-once",
            "name": "HTTP测试",
            "content": CONTENT,
        }
        assert c.post(root + "/commands", json=body).status_code == 403
        headers = {"Origin": "https://workbench.example", "X-CSRF-Token": "csrf-token"}
        response = c.post(root + "/commands", json=body, headers=headers)
        assert response.status_code == 200, response.text
        assert c.get(root + "/commands/http-create-once").json() == response.json()
        assert len(c.get(root).json()["result"]["items"]) == 1
        assert c.get(root, headers={"X-Tenant-ID": "other"}).status_code == 400
        s.context = replace(a.subject, scope=type(a.subject.scope)("other", "other"))
        assert c.get(root).status_code in (403, 404)


def test_real_mcp_configuration_handshake_discovery_selection_never_calls_tools(
    manager,
):
    import threading
    from http.server import ThreadingHTTPServer

    from test_skill_mcp_professional_experience import McpHandler

    methods = []

    class Observed(McpHandler):
        def do_POST(self):
            import io
            import json

            body = self.rfile.read(int(self.headers["Content-Length"]))
            methods.append(json.loads(body)["method"])
            self.rfile = io.BytesIO(body)
            return super().do_POST()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Observed)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        content = {
            "description": "本机隔离MCP测试",
            "capabilities": ["quality.lookup"],
            "endpoint": f"http://127.0.0.1:{server.server_port}/mcp",
            "sideEffect": "READ",
        }
        r = command(manager, "create", kind="mcp", name="隔离连接", content=content)[
            "resource"
        ]
        r = command(
            manager,
            "health",
            kind="mcp",
            identity=r["resourceId"],
            expectedVersion=r["aggregateVersion"],
        )["resource"]
        assert r["healthObservations"][-1]["status"] == "HEALTHY"
        r = command(
            manager,
            "discover",
            kind="mcp",
            identity=r["resourceId"],
            expectedVersion=r["aggregateVersion"],
        )["resource"]
        snapshot = r["discoverySnapshots"][-1]
        r = command(
            manager,
            "select-tools",
            kind="mcp",
            identity=r["resourceId"],
            expectedVersion=r["aggregateVersion"],
            snapshotId=snapshot["snapshotId"],
            toolNames=["quality.lookup"],
        )["resource"]
        assert r["toolSelections"][-1]["toolNames"] == ["quality.lookup"]
        assert {"initialize", "tools/list", "resources/list", "prompts/list"} <= set(
            methods
        )
        assert "tools/call" not in methods
        before = list(methods)
        r = command(
            manager,
            "edit",
            kind="mcp",
            identity=r["resourceId"],
            expectedVersion=r["aggregateVersion"],
            content={**content, "secretReference": "secret-ref:isolated/reference"},
        )["resource"]
        with pytest.raises(WorkbenchOwnerError, match="CREDENTIAL_RESOLVER"):
            command(
                manager,
                "health",
                kind="mcp",
                key="credential-test-no-network",
                identity=r["resourceId"],
                expectedVersion=r["aggregateVersion"],
            )
        assert methods == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_concurrent_identical_create_has_one_resource_and_receipt(manager):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                command,
                manager,
                "create",
                name="并发验证",
                content=CONTENT,
                key="concurrent-create-once",
            )
            for _ in range(2)
        ]
        results = [f.result(timeout=15) for f in futures]
    assert results[0] == results[1]
    a, _ = manager
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_mcp_resource.resources WHERE record->>'name'='并发验证'"
            ).fetchone()["n"]
            == 1
        )


def test_revoked_management_cannot_replay_or_regrant_and_bad_import_is_bounded(manager):
    from agent_console.resource_management import target

    a, m = manager
    created = command(
        manager,
        "create",
        name="撤权验证",
        content=CONTENT,
        key="revocation-created-once",
    )
    identity = created["identity"]
    with a.authority.connection_scope() as c:
        rows = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE subject_principal_id=%s AND action='MANAGE_RESOURCE' AND exact_resource=%s",
            (a.subject.principal_id, target("skill", identity)),
        ).fetchall()
    assert rows
    for ordinal, row in enumerate(rows):
        a.authority.revoke_grant(
            row["grant_id"],
            actor_id=m.policy.issuer,
            reason="ISOLATED_REVOKE_TEST",
            idempotency_key="revoke-managed-" + str(ordinal),
            payload_digest="a" * 64,
            now=m.grants.clock(),
        )
    with pytest.raises(AuthorityError):
        command(
            manager,
            "create",
            name="撤权验证",
            content=CONTENT,
            key="revocation-created-once",
        )
    with pytest.raises(AuthorityError):
        command(
            manager,
            "edit",
            identity=identity,
            expectedVersion=1,
            content=CONTENT,
            key="revoked-edit-once",
        )
    with pytest.raises(WorkbenchOwnerError, match="MANIFEST_CONTENT_INVALID"):
        command(
            manager,
            "import",
            key="bad-manifest-once",
            manifest={
                "manifestVersion": "skill-mcp-workbench/v1",
                "kind": "skill",
                "name": "拒绝",
                "content": {"invalid": True},
            },
        )
