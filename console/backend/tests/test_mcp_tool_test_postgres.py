# ruff: noqa: F401,F811,E501 -- Shared disposable owner fixtures and exact SQL.
"""Real formal grants + committed claims + actual disposable localhost transport."""

import io
import json
import threading
from dataclasses import replace
from datetime import timedelta
from http.server import ThreadingHTTPServer

import pytest
from agent_console.authority_configuration import RequestabilityRule, StaticGrant
from agent_console.authority_contracts import ExactGrant, GrantSource
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.mcp_tool_test_api import install
from agent_console.mcp_tool_test_owner import ToolTestOwner, read_grant
from agent_console.mcp_tool_test_policy import ToolBinding, ToolTestPolicy
from agent_console.mcp_tool_test_postgres import ToolTestTargets, migrate
from agent_console.resource_use_domain import canonical_digest
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from agent_console.workbench_prepared_resources import reference
from fastapi.testclient import TestClient
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_resource_management import command, manager
from test_skill_mcp_professional_experience import McpHandler


@pytest.fixture
def live(manager, tmp_path):
    a, m = manager
    calls = []
    lost = [False]
    claimed = [False]

    class Handler(McpHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            data = json.loads(body)
            if data["method"] == "tools/call":
                with a.authority.connection_scope() as c:
                    claimed[0] = bool(
                        c.execute(
                            "SELECT 1 FROM authorization_admin.mcp_tool_test_facts WHERE kind='DISPATCH_CLAIM'"
                        ).fetchone()
                    )
                calls.append(data)
                if lost[0]:
                    self.close_connection = True
                    return
            self.rfile = io.BytesIO(body)
            super().do_POST()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        content = {
            "description": "Isolated read-only tool",
            "capabilities": ["quality.lookup"],
            "endpoint": f"http://127.0.0.1:{server.server_port}/mcp",
            "sideEffect": "READ",
        }
        r = command(manager, "create", kind="mcp", name="MCP test", content=content)[
            "resource"
        ]
        for act, extra in [("health", {}), ("discover", {})]:
            r = command(
                manager,
                act,
                kind="mcp",
                identity=r["resourceId"],
                expectedVersion=r["aggregateVersion"],
                **extra,
            )["resource"]
        snap = r["discoverySnapshots"][-1]
        r = command(
            manager,
            "select-tools",
            kind="mcp",
            identity=r["resourceId"],
            expectedVersion=r["aggregateVersion"],
            snapshotId=snap["snapshotId"],
            toolNames=["quality.lookup"],
        )["resource"]
        r = command(
            manager,
            "publish",
            kind="mcp",
            identity=r["resourceId"],
            expectedVersion=r["aggregateVersion"],
        )["resource"]
        rev = next(
            v for v in r["revisions"] if v["revisionId"] == r["publishedRevisionId"]
        )
        source = a.refs["knowledge"]
        svc = a.services["knowledge"]
        sr = svc.repository.get(
            svc.scope(a.subject.scope.tenant_id, a.subject.scope.security_domain),
            source.resource_id,
        )
        source_value = json.loads(
            sr["revisions"][-1]["content"]["documents"][0]["chunks"][0]["content"]
        )
        b = ToolBinding(
            namespace=a.subject.scope.tenant_id,
            securityDomain=a.subject.scope.security_domain,
            subject=a.subject.principal_id,
            mcp={
                "resource_id": r["resourceId"],
                "revision_id": rev["revisionId"],
                "digest": rev["digest"],
            },
            source=source,
            sourceContentDigest=canonical_digest(source_value),
            endpoint=content["endpoint"],
            selectionId=r["toolSelections"][-1]["selectionId"],
            snapshotId=snap["snapshotId"],
            snapshotDigest=snap["digest"],
            toolName="quality.lookup",
            inputSchema={"type": "object"},
            arguments={"sourceDigest": canonical_digest(source_value)},
            sideEffect="READ",
            expiresAt=m.grants.clock() + timedelta(minutes=30),
        )
        p = ToolTestPolicy(
            schemaVersion="mcp-published-tool-test.v1",
            enabled=True,
            policyId="isolated-mcp-test",
            policyVersion="1",
            issuer=m.policy.issuer,
            credentialPath=m.policy.credentialPath,
            bindings=(b,),
        )
        path = tmp_path / "mcp-policy.json"
        path.write_text(p.model_dump_json())
        path.chmod(0o600)
        migrate(a.authority)
        # Real browser credential and persisted session, not a stubbed context.
        old = m.grants.generation
        cred = replace(
            old.credentials[0],
            authentication_source=GrantSource.BROWSER_BOOTSTRAP,
            grants=tuple(
                StaticGrant(g.grant, GrantSource.BROWSER_BOOTSTRAP)
                for g in old.credentials[0].grants
            ),
        )
        gen = replace(
            old,
            credentials=(cred, *old.credentials[1:]),
            requestability=(
                *old.requestability,
                RequestabilityRule(
                    "SKILL",
                    "INVOKE_MCP_TOOL",
                    "skill-invocation:mcp-tool-test:",
                    "MCP_TOOL_TEST",
                ),
            ),
        )
        m.grants._generation_provider = lambda: gen
        m.grants.authorization._generation_provider = lambda: gen
        m.grants.target_validator.additional += (ToolTestTargets(),)
        sessions = BrowserSessionService(
            a.authority,
            StaticGenerationAuthenticator(
                lambda: gen, source=GrantSource.BROWSER_BOOTSTRAP
            ),
            BrowserSessionPolicy(
                timedelta(minutes=2),
                timedelta(minutes=30),
                timedelta(hours=1),
                timedelta(minutes=2),
            ),
            csrf_signing_key=b"x" * 32,
            recovery_epoch=1,
        )
        secret = sessions.create_session(
            sessions.issue_login_nonce(), "unit-subject-secret"
        )
        session, ctx = sessions.authenticate_session(secret.value)
        with a.authority.connection_scope() as c:
            call = AuthorizedOwnerCall(
                "FIXTURE_READ_GRANTS",
                ctx,
                c,
                {},
                {},
                {},
                (),
                AuthorizedOwnerAuthority(a.adapter, ctx, c, 1, ()),
                1,
                1,
            )
            a.automation.decide(
                call,
                (
                    read_grant(b),
                    ExactGrant(
                        "KNOWLEDGE",
                        "READ_RESOURCE",
                        reference("knowledge", source.resource_id, source.revision_id),
                    ),
                ),
                "test-source-read",
                a.policy.workScopes[0],
                a.policy.authenticate(m.grants, ctx),
            )
        owner = ToolTestOwner(path, m, a.adapter)
        app = create_workbench_bff(
            sessions,
            a.adapter,
            WorkbenchBffPolicy("workbench.example", "https://workbench.example"),
            route_installers=(install(owner),),
        )
        with TestClient(app, base_url="https://workbench.example") as client:
            client.cookies.set("__Host-workbench_session", secret.value)
            yield (
                client,
                owner,
                b,
                {
                    "Origin": "https://workbench.example",
                    "X-CSRF-Token": sessions.issue_csrf(session),
                },
                calls,
                lost,
                claimed,
                a,
                sessions,
                secret,
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_formal_browser_grant_durable_claim_real_transport_replay_and_loss(live):
    client, _owner, b, h, calls, lost, claimed, a, sessions, secret = live
    root = (
        "/api/workbench/v1/resource-management/mcp/" + b.mcp.resource_id + "/tool-tests"
    )
    body = {
        "commandKey": "ordinary-test-first",
        "bindingDigest": b.digest,
        "input": b.arguments,
    }
    assert client.post(root, json=body).status_code == 403
    prepared = client.post(root, json=body, headers=h)
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()["result"]["state"] == "PREPARED" and calls == []
    result = client.post(
        root + "/" + body["commandKey"] + "/dispatch", json={}, headers=h
    )
    assert result.status_code == 200, result.text
    assert (
        result.json()["result"]["state"] == "SUCCEEDED"
        and len(calls) == 1
        and claimed[0]
    )
    assert (
        result.json()["result"]["result"]["result"]["structuredContent"]["token"]
        == "[REDACTED]"
    )
    assert (
        client.post(
            root + "/" + body["commandKey"] + "/dispatch", json={}, headers=h
        ).json()
        == result.json()
    )
    assert len(calls) == 1
    lost[0] = True
    second = {**body, "commandKey": "ordinary-test-loss"}
    assert client.post(root, json=second, headers=h).status_code == 200
    response = client.post(
        root + "/" + second["commandKey"] + "/dispatch", json={}, headers=h
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"]["state"] == "UNKNOWN" and len(calls) == 2
    assert client.get(root + "/" + second["commandKey"]).json() == response.json()
    denied = client.post(
        root, json={**body, "commandKey": "different-key-same-tuple"}, headers=h
    )
    assert denied.status_code == 404, denied.text
    assert denied.json()["reasonCode"] == "MCP_TOOL_TEST_UNRESOLVED_TEST_EXISTS"
    assert len(calls) == 2
    with a.authority.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions WHERE basis_type='POLICY'"
            ).fetchone()["n"]
            > 0
        )
    sessions.logout(secret.value, actor_id=b.subject)
    assert client.get(root + "/" + body["commandKey"]).status_code == 401


def test_published_test_ignores_draft_but_rejects_new_published_head(live):
    client, owner, b, h, calls, _lost, _claimed, a, sessions, secret = live
    _, ctx = sessions.authenticate_session(secret.value)
    pair = (replace_namespace(a, subject=ctx), owner.manager)
    service = owner.manager.services["mcp"]
    scope = service.scope(b.namespace, b.securityDomain)
    record = service.repository.get(scope, "mcp", b.mcp.resource_id)
    draft = command(
        pair,
        "successor",
        kind="mcp",
        key="published-test-draft",
        identity=b.mcp.resource_id,
        expectedVersion=record["aggregateVersion"],
    )["resource"]
    root = (
        "/api/workbench/v1/resource-management/mcp/" + b.mcp.resource_id + "/tool-tests"
    )
    body = {
        "commandKey": "published-with-draft",
        "bindingDigest": b.digest,
        "input": b.arguments,
    }
    assert (
        client.post(
            root, json={**body, "input": {"sourceDigest": "0" * 64}}, headers=h
        ).status_code
        == 404
    )
    assert client.post(root, json=body, headers=h).status_code == 200
    result = client.post(
        root + "/" + body["commandKey"] + "/dispatch", json={}, headers=h
    )
    assert result.status_code == 200, result.text
    assert result.json()["result"]["state"] == "SUCCEEDED" and len(calls) == 1
    second = {**body, "commandKey": "head-race-test"}
    assert client.post(root, json=second, headers=h).status_code == 200
    command(
        pair,
        "publish",
        kind="mcp",
        key="published-head-race",
        identity=b.mcp.resource_id,
        expectedVersion=draft["aggregateVersion"],
    )
    rejected = client.post(
        root + "/" + second["commandKey"] + "/dispatch", json={}, headers=h
    )
    assert rejected.status_code == 404, rejected.text
    assert rejected.json()["reasonCode"] == "MCP_TOOL_TEST_PUBLISHED_HEAD_CHANGED"
    assert len(calls) == 1
    assert (
        client.get(root + "/" + body["commandKey"]).json()["result"]["state"]
        == "SUCCEEDED"
    )


def replace_namespace(value, **changes):
    from types import SimpleNamespace

    return SimpleNamespace(**{**vars(value), **changes})


def test_real_surrender_between_claim_and_send_fences_tool_and_read(live):
    from agent_console.authority_contracts import AuthorityError, GrantId
    from agent_console.grant_administration_application import GrantRevocationCommand

    client, owner, b, h, calls, _lost, _claimed, a, sessions, secret = live
    _, ctx = sessions.authenticate_session(secret.value)
    root = (
        "/api/workbench/v1/resource-management/mcp/" + b.mcp.resource_id + "/tool-tests"
    )
    key = "revoke-before-send"
    assert (
        client.post(
            root,
            json={"commandKey": key, "bindingDigest": b.digest, "input": b.arguments},
            headers=h,
        ).status_code
        == 200
    )

    def run(handler):
        return a.adapter.execute(
            ctx,
            (read_grant(b),),
            operation="MCP_TOOL_TEST",
            payload={"commandKey": key},
            path={"identity": b.mcp.resource_id, "key": key},
            query={},
            handler=handler,
        )

    claim = run(owner.claim)
    with a.authority.connection_scope() as c:
        gid = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE subject_principal_id=%s AND action='INVOKE_MCP_TOOL' AND exact_resource=%s",
            (b.subject, b.grant.exact_resource),
        ).fetchone()["grant_id"]
    owner.grants.revoke_grant(
        ctx,
        GrantRevocationCommand(
            GrantId(gid), "USER_REQUESTED", "mcp-surrender-once", True
        ),
    )
    with pytest.raises(AuthorityError):
        run(lambda call: owner.transport(call, claim["ticket"]))
    assert calls == []
    assert client.get(root + "/" + key).json()["result"]["state"] == "UNKNOWN"
    assert (
        client.post(root + "/" + key + "/dispatch", json={}, headers=h).json()[
            "result"
        ]["state"]
        == "UNKNOWN"
    )
    assert calls == []
    with a.authority.connection_scope() as c:
        gid = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE subject_principal_id=%s AND action='READ_RESOURCE' AND exact_resource=%s",
            (b.subject, read_grant(b).exact_resource),
        ).fetchone()["grant_id"]
    owner.grants.revoke_grant(
        ctx,
        GrantRevocationCommand(
            GrantId(gid), "USER_REQUESTED", "mcp-read-surrender-once", True
        ),
    )
    assert client.get(root + "/" + key).status_code in (403, 404)
    with a.authority.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.mcp_tool_test_facts WHERE command_key=%s",
                (key,),
            ).fetchone()["n"]
            == 1
        )


def test_concurrent_dispatch_and_response_finalize_rollback_never_resend(live):
    from concurrent.futures import ThreadPoolExecutor

    client, owner, b, h, calls, _lost, _claimed, a, sessions, secret = live
    root = (
        "/api/workbench/v1/resource-management/mcp/" + b.mcp.resource_id + "/tool-tests"
    )
    key = "concurrent-same-request"
    assert (
        client.post(
            root,
            json={"commandKey": key, "bindingDigest": b.digest, "input": b.arguments},
            headers=h,
        ).status_code
        == 200
    )
    barrier = threading.Barrier(2)

    def send():
        barrier.wait()
        return client.post(root + "/" + key + "/dispatch", json={}, headers=h)

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(lambda _: send(), range(2)))
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    assert len(calls) == 1
    assert client.get(root + "/" + key).json()["result"]["state"] == "SUCCEEDED"
    key = "finalization-lost"
    assert (
        client.post(
            root,
            json={"commandKey": key, "bindingDigest": b.digest, "input": b.arguments},
            headers=h,
        ).status_code
        == 200
    )
    _, ctx = sessions.authenticate_session(secret.value)

    def run(handler):
        return a.adapter.execute(
            ctx,
            (read_grant(b),),
            operation="MCP_TOOL_TEST",
            payload={"commandKey": key},
            path={"identity": b.mcp.resource_id, "key": key},
            query={},
            handler=handler,
        )

    claim = run(owner.claim)
    result = run(lambda call: owner.transport(call, claim["ticket"]))
    assert result["state"] == "SUCCEEDED" and len(calls) == 2
    # Simulate process loss before finalizer: no manufactured FAILED or new claim.
    assert client.get(root + "/" + key).json()["result"]["state"] == "UNKNOWN"
    assert (
        client.post(root + "/" + key + "/dispatch", json={}, headers=h).json()[
            "result"
        ]["state"]
        == "UNKNOWN"
    )
    assert len(calls) == 2
    owner.finalize(ctx, key, claim["ticket"], result)
    assert client.get(root + "/" + key).json()["result"]["state"] == "SUCCEEDED"
    assert len(calls) == 2


def test_source_availability_digest_and_share_lock_fence_dispatch(live):
    import copy

    from psycopg.errors import LockNotAvailable
    from psycopg.types.json import Jsonb

    client, owner, b, h, calls, _, _, a, sessions, secret = live
    _, ctx = sessions.authenticate_session(secret.value)
    root = (
        "/api/workbench/v1/resource-management/mcp/" + b.mcp.resource_id + "/tool-tests"
    )
    params = (b.namespace, b.securityDomain, b.source.resource_id)
    with a.authority.connection_scope() as c:
        original = c.execute(
            "SELECT record FROM knowledge_operation.knowledge WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s",
            params,
        ).fetchone()["record"]

    def write(value):
        with a.authority.connection_scope() as c:
            c.execute(
                "UPDATE knowledge_operation.knowledge SET record=%s WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s",
                (Jsonb(value), *params),
            )

    for mode in ("disabled", "archived", "purged", "metadata"):
        key = "source-negative-original"
        assert (
            client.post(
                root,
                json={
                    "commandKey": key,
                    "bindingDigest": b.digest,
                    "input": b.arguments,
                },
                headers=h,
            ).status_code
            == 200
        )
        bad = copy.deepcopy(original)
        if mode == "disabled":
            bad["enabled"] = False
        elif mode == "archived":
            bad["archived"] = True
        elif mode == "purged":
            bad["purge"] = {"state": "PURGED"}
        else:
            bad["revisions"][-1]["content"]["name"] = (
                "corrupt name with unchanged revision digest"
            )
        write(bad)
        response = client.post(root + "/" + key + "/dispatch", json={}, headers=h)
        assert response.status_code in (403, 404), response.text
        assert calls == []
        write(original)

    def locked(call):
        owner.exact(call, b)
        # Original knowledge owner replacement is an UPDATE of this same row.
        # A distinct transaction cannot change availability while the send fence holds.
        with (
            pytest.raises(LockNotAvailable),
            a.authority.connection_scope() as other,
        ):
            other.execute("SET LOCAL lock_timeout='100ms'")
            other.execute(
                "UPDATE knowledge_operation.knowledge SET record=jsonb_set(record,'{archived}','true') WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s",
                params,
            )

    a.adapter.execute(
        ctx,
        (read_grant(b),),
        operation="MCP_TOOL_TEST",
        payload={},
        path={"identity": b.mcp.resource_id},
        query={},
        handler=locked,
    )
    assert calls == []
    # Formal source READ surrender is separate from MCP invocation authority.
    from agent_console.authority_contracts import GrantId
    from agent_console.grant_administration_application import GrantRevocationCommand

    source_ref = reference("knowledge", b.source.resource_id, b.source.revision_id)
    with a.authority.connection_scope() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE subject_principal_id=%s AND owner='KNOWLEDGE' AND action='READ_RESOURCE' AND exact_resource=%s",
            (b.subject, source_ref),
        ).fetchone()["grant_id"]
    owner.grants.revoke_grant(
        ctx,
        GrantRevocationCommand(
            GrantId(grant), "USER_REQUESTED", "mcp-source-read-surrender", True
        ),
    )
    denied = client.post(
        root + "/source-negative-original/dispatch", json={}, headers=h
    )
    assert denied.status_code in (403, 404)
    assert calls == []


def test_receipt_seals_append_only_and_explicit_fault_injection(live):
    from agent_console.mcp_tool_test_postgres import read, seal
    from psycopg.errors import RaiseException
    from psycopg.types.json import Jsonb

    client, _owner, b, h, calls, _, _, a, sessions, secret = live
    _, ctx = sessions.authenticate_session(secret.value)
    root = (
        "/api/workbench/v1/resource-management/mcp/" + b.mcp.resource_id + "/tool-tests"
    )
    key = "integrity-original"
    assert (
        client.post(
            root,
            json={"commandKey": key, "bindingDigest": b.digest, "input": b.arguments},
            headers=h,
        ).status_code
        == 200
    )
    params = (b.namespace, b.securityDomain, b.subject, key)
    for action in (
        "UPDATE authorization_admin.mcp_tool_test_requests SET binding_digest=binding_digest",
        "DELETE FROM authorization_admin.mcp_tool_test_requests",
    ):
        with (
            pytest.raises(RaiseException, match="APPEND_ONLY"),
            a.authority.connection_scope() as c,
        ):
            c.execute(
                action
                + " WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND command_key=%s",
                params,
            )
    # Explicit superuser-only fault injection in disposable test DB, never an owner API.
    with a.authority.connection_scope() as c:
        c.execute(
            "ALTER TABLE authorization_admin.mcp_tool_test_requests DISABLE TRIGGER mcp_tool_test_requests_immutable"
        )
        c.execute(
            "UPDATE authorization_admin.mcp_tool_test_requests SET binding_digest=%s WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND command_key=%s",
            ("b" * 64, *params),
        )
        c.execute(
            "ALTER TABLE authorization_admin.mcp_tool_test_requests ENABLE TRIGGER mcp_tool_test_requests_immutable"
        )
    assert client.post(
        root + "/" + key + "/dispatch", json={}, headers=h
    ).status_code in (403, 404)
    assert client.get(root + "/" + key).status_code in (403, 404)
    assert calls == []
    with a.authority.connection_scope() as c:
        c.execute(
            "ALTER TABLE authorization_admin.mcp_tool_test_requests DISABLE TRIGGER mcp_tool_test_requests_immutable"
        )
        c.execute(
            "UPDATE authorization_admin.mcp_tool_test_requests SET binding_digest=%s WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND command_key=%s",
            (b.digest, *params),
        )
        c.execute(
            "ALTER TABLE authorization_admin.mcp_tool_test_requests ENABLE TRIGGER mcp_tool_test_requests_immutable"
        )
        row = read(c, ctx, key)
        orphan = {
            "state": "SUCCEEDED",
            "result": {"content": []},
            "_seal": {**seal(row, "RESULT"), "claimDigest": "a" * 64},
        }
        c.execute(
            "INSERT INTO authorization_admin.mcp_tool_test_facts(namespace,security_domain,subject_id,command_key,ordinal,kind,fact,fact_digest) VALUES(%s,%s,%s,%s,2,'RESULT',%s,%s)",
            (*params, Jsonb(orphan), canonical_digest(orphan)),
        )
    # Correct JSON hash and superficially valid result still cannot become success without claim.
    assert client.get(root + "/" + key).status_code in (403, 404)
    assert client.post(
        root + "/" + key + "/dispatch", json={}, headers=h
    ).status_code in (403, 404)
    for action in (
        "UPDATE authorization_admin.mcp_tool_test_facts SET fact=fact",
        "DELETE FROM authorization_admin.mcp_tool_test_facts",
    ):
        with (
            pytest.raises(RaiseException, match="APPEND_ONLY"),
            a.authority.connection_scope() as c,
        ):
            c.execute(
                action
                + " WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND command_key=%s",
                params,
            )
    assert calls == []
