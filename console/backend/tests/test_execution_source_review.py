# ruff: noqa: F401,F811,E501 -- Existing disposable owner fixtures and SQL.
"""SQL owner checks and real loopback MCP; engineering fixtures are not live acceptance."""

import hashlib
import importlib.util
import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.execution_source_review import ExecutionSourceReview, ReviewPolicy
from agent_console.resource_use_domain import canonical_digest
from agent_console.skill_mcp_transport import (
    McpTransportFailure,
    StreamableHttpMcpClient,
)
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from agent_console.workbench_prepared_resources import PreparedResourceOwner
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_sales_supplement_owners import snapshot


@pytest.fixture
def review(automation, tmp_path):
    a = automation
    root = Path(__file__).parents[3]
    module_spec = importlib.util.spec_from_file_location(
        "source_mcp_fixture",
        root / "examples/sales-diagnostic/source_verification_mcp.py",
    )
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    source_ref = a.refs["knowledge"].model_dump(mode="json")
    source_file = tmp_path / "source.json"
    source_file.write_text(json.dumps(a.e.source))
    csv = root / "examples/sales-diagnostic/synthetic-sales.csv"
    csv_digest = hashlib.sha256(csv.read_bytes()).hexdigest()
    server = module.create_server(
        {
            "sourceJSON": str(source_file),
            "sourceCSV": str(csv),
            "sourceDigest": canonical_digest(a.e.source),
            "csvDigest": csv_digest,
            "sourceSnapshot": source_ref,
        },
        0,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    service = a.services["skill"]
    resource_services = {**a.services, "mcp": service}
    scope = service.scope(a.e.scope.namespace, a.e.scope.security_domain)
    actor = a.subject.principal_id
    record = service.create(
        scope,
        "mcp",
        actor,
        "isolated generated source verification",
        {
            "description": "Read the isolated generated source",
            "capabilities": [module.TOOL],
            "endpoint": f"http://127.0.0.1:{server.server_port}/mcp",
            "sideEffect": "READ",
        },
    )
    identity = record["resourceId"]
    try:
        for method in ["health", "discover"]:
            getattr(service, method)(
                scope, identity, actor, record["aggregateVersion"], 2
            )
            record = service.repository.get(scope, "mcp", identity)
        service.select_tools(
            scope,
            identity,
            actor,
            record["aggregateVersion"],
            record["discoverySnapshots"][-1]["snapshotId"],
            [module.TOOL],
            "isolated explicit read-only selection",
        )
        record = service.repository.get(scope, "mcp", identity)
        with a.repository.pool.connection() as c, c.transaction():
            setup = SimpleNamespace(
                context=a.subject,
                connection=c,
                operation="REVIEW_PREPARED_RESOURCE",
                authority=SimpleNamespace(require=lambda *args: None),
                path={
                    "kind": "mcp",
                    "identity": identity,
                    "revision": record["currentDraftRevisionId"],
                },
                payload={
                    "expectedVersion": record["aggregateVersion"],
                    "digest": record["revisions"][-1]["digest"],
                    "reason": "isolated explicit publication",
                    "idempotencyKey": "isolated-source-mcp-publication",
                },
                query={},
            )
            PreparedResourceOwner(resource_services)(setup)
        record = service.repository.get(scope, "mcp", identity)
        published = next(
            r
            for r in record["revisions"]
            if r["revisionId"] == record["publishedRevisionId"]
        )
        ref = {
            "resource_id": identity,
            "revision_id": published["revisionId"],
            "digest": published["digest"],
        }
        employee = next(
            r.selected for r in a.e.p.semantics.requirements if r.kind == "EMPLOYEE"
        ).model_dump(mode="json")
        view = {
            "digest": "a" * 64,
            "preparation": {
                "source_snapshot": source_ref,
                "semantics": {
                    "tasks": [{"task_id": "read", "title": "Read original source"}]
                },
                "participants": [
                    {
                        "task_id": "read",
                        "definition": employee,
                        "instance_id": "fixture-instance",
                        "assignment_id": "fixture-assignment",
                    }
                ],
            },
            "progress": {
                "state": "SUCCEEDED",
                "tasks": [
                    {"task_id": "read", "state": "SUCCEEDED", "attempt_id": None}
                ],
            },
        }
        policy = ReviewPolicy.model_validate(
            {
                "schemaVersion": "execution-source-review-policy.v1",
                "policyId": "isolated-source-check",
                "bindings": [
                    {
                        "subject": actor,
                        "tenantId": a.e.scope.namespace,
                        "securityDomain": a.e.scope.security_domain,
                        "executionDigest": view["digest"],
                        "source": source_ref,
                        "sourceDigest": canonical_digest(a.e.source),
                        "csvDigest": csv_digest,
                        "mcp": ref,
                        "selectionId": record["toolSelections"][-1]["selectionId"],
                        "toolName": module.TOOL,
                        "expiresAt": datetime.now(UTC) + timedelta(hours=1),
                    }
                ],
            }
        )
        denied = set()

        class ACL:
            def require(self, principal, owner, action, resource):
                if owner in denied or resource in denied:
                    raise AuthorityError("AUTHORIZATION_NOT_FOUND")
                return SimpleNamespace(decision_id="explicit-isolated-fixture-allow")

        acl = ACL()
        handler = ExecutionSourceReview(resource_services, policy=policy)
        # The saved-view read boundary is isolated here; actual original Run and
        # native outcomes are verified separately through the real installed app.
        handler.execution = lambda _: deepcopy(view)
        body = {
            "idempotencyKey": "isolated-original-check-key",
            "source": source_ref,
            "mcp": ref,
            "expectedVersion": record["aggregateVersion"],
        }
        with a.repository.pool.connection() as c, c.transaction():
            c.execute(
                "INSERT INTO execution_authority.prepared_resource_commands(namespace,security_domain,actor_id,command_key,digest,result) VALUES(%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    actor,
                    "resource-management:isolated-create",
                    "b" * 64,
                    json.dumps(
                        {
                            "schemaVersion": "resource-management-receipt.v1",
                            "kind": "mcp",
                            "action": "create",
                            "identity": identity,
                        }
                    ),
                ),
            )

        def call(operation, payload=None, query=None, context=None):
            with a.repository.pool.connection() as c, c.transaction():
                return handler(
                    AuthorizedOwnerCall(
                        decisions=(),
                        context=context or a.subject,
                        connection=c,
                        operation=operation,
                        authority=acl,
                        path={"digest": view["digest"], "key": body["idempotencyKey"]},
                        payload=payload or {},
                        query=query or {},
                    )
                )

        yield SimpleNamespace(
            a=a,
            view=view,
            handler=handler,
            record=record,
            body=body,
            call=call,
            denied=denied,
            service=service,
            scope=scope,
            identity=identity,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_pinned_original_text_and_employee_status_are_read_only(review):
    r = review
    before = snapshot(r.a)
    status = r.call("READ_EXECUTION_SOURCE_REVIEW")
    assert status["employees"][0]["tasks"][0]["state"] == "SUCCEEDED"
    assert status["runtimeHealth"] == "NOT_INFERRED_FROM_TASK_STATE"
    result = r.call("SEARCH_EXECUTION_ORIGINAL_TEXT", query={"query": "S01"})
    assert result["retrieval"]["classification"] == "LEXICAL"
    citation = result["retrieval"]["results"][0]["citation"]
    assert citation["revisionId"] == r.body["source"]["revision_id"]
    assert "S01" in citation["content"]
    assert (
        r.call(
            "SEARCH_EXECUTION_ORIGINAL_TEXT", query={"query": "never-existing-word-xyz"}
        )["retrieval"]["results"]
        == []
    )
    assert snapshot(r.a) == before


def test_real_source_mcp_check_original_key_and_no_run_write(review):
    r = review
    before = snapshot(r.a)
    receipt = r.call("VERIFY_EXECUTION_SOURCE", r.body)
    assert receipt["state"] == "MATCHED"
    assert receipt["actualSource"]["rows"] == r.a.e.source["snapshot"]["rows"]
    assert not receipt["executionStarted"] and not receipt["originalRunChanged"]
    assert r.call("VERIFY_EXECUTION_SOURCE", r.body) == receipt
    assert r.call("READ_EXECUTION_SOURCE_CHECK") == receipt
    record = r.service.repository.get(r.scope, "mcp", r.identity)
    assert len(record["invocations"]) == 1
    assert snapshot(r.a) == before
    r.denied.add("KNOWLEDGE")
    with pytest.raises(AuthorityError):
        r.call("READ_EXECUTION_SOURCE_CHECK")
    assert len(r.service.repository.get(r.scope, "mcp", r.identity)["invocations"]) == 1


@pytest.mark.parametrize(
    "bad", ["source", "mcp", "version", "foreign", "permission", "disabled", "expired"]
)
def test_source_check_rejects_before_external_operation(review, bad):
    r = review
    body = deepcopy(r.body)
    ctx = r.a.subject
    if bad in {"source", "mcp"}:
        body[bad]["digest"] = "0" * 64
    elif bad == "version":
        body["expectedVersion"] += 1
    elif bad == "foreign":
        ctx = replace(ctx, principal_id="human:other")
    elif bad == "permission":
        r.denied.add("SKILL")
    elif bad == "disabled":
        r.service.lifecycle(
            r.scope,
            "mcp",
            r.identity,
            ctx.principal_id,
            r.record["aggregateVersion"],
            "DISABLE",
            "isolated denial",
        )
    elif bad == "expired":
        p = r.handler.policy
        r.handler.policy = p.model_copy(
            update={
                "bindings": (
                    p.bindings[0].model_copy(
                        update={"expiresAt": datetime.now(UTC) - timedelta(seconds=1)}
                    ),
                )
            }
        )
    before = snapshot(r.a)
    with pytest.raises((WorkbenchOwnerError, AuthorityError)):
        r.call("VERIFY_EXECUTION_SOURCE", body, context=ctx)
    assert not r.service.repository.get(r.scope, "mcp", r.identity)["invocations"]
    assert snapshot(r.a) == before


def test_uncertain_tool_result_is_preserved_and_recovery_is_get_only(
    review, monkeypatch
):
    r = review
    original = StreamableHttpMcpClient.request
    calls = []

    def lost(self, method, *args, **kwargs):
        if method == "tools/call":
            calls.append(method)
            raise McpTransportFailure("MCP_TIMEOUT")
        return original(self, method, *args, **kwargs)

    monkeypatch.setattr(StreamableHttpMcpClient, "request", lost)
    result = r.call("VERIFY_EXECUTION_SOURCE", r.body)
    assert result["state"] == "UNDETERMINED"
    assert r.call("READ_EXECUTION_SOURCE_CHECK") == result
    assert r.call("VERIFY_EXECUTION_SOURCE", r.body) == result
    assert calls == ["tools/call"]
