"""Real HTTP boundary: saved selection cannot follow a new endpoint."""

import copy
import json
import threading
from http.server import ThreadingHTTPServer

import pytest
from agent_console.definition_authority import canonical_digest
from agent_console.skill_mcp_repository import InMemorySkillMcpRepository, ResourceScope
from agent_console.skill_mcp_service import SkillMcpFailure, SkillMcpService
from test_skill_mcp_professional_experience import McpHandler


@pytest.fixture
def selected_source():
    class CountingHandler(McpHandler):
        requests = 0
        fail_at = 0
        tool_error = False

        def do_POST(self):
            type(self).requests += 1
            if self.requests == self.fail_at:
                self.send_error(503)
                return
            if self.tool_error and self.requests == 3:
                body = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "result": {
                            "isError": True,
                            "content": [{"type": "text", "text": "operation rejected"}],
                        },
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_POST()

    server = ThreadingHTTPServer(("127.0.0.1", 0), CountingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    repository = InMemorySkillMcpRepository()
    service = SkillMcpService(repository)
    scope = ResourceScope("tenant", "domain")
    try:
        record = service.create(
            scope,
            "mcp",
            "human",
            "Exact source",
            {
                "description": "Local test",
                "capabilities": ["quality.lookup"],
                "endpoint": f"http://127.0.0.1:{server.server_port}/mcp",
            },
        )
        rid = record["resourceId"]
        snapshot = service.discover(scope, rid, "human", 1, 2)["discoverySnapshot"]
        service.select_tools(
            scope,
            rid,
            "human",
            2,
            snapshot["snapshotId"],
            ["quality.lookup"],
            "bounded test",
        )
        CountingHandler.requests = 0
        yield service, repository, scope, rid, CountingHandler
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def invoke(service, scope, rid, record, *, cancel=False):
    return service.invoke_mcp(
        scope,
        rid,
        "human",
        record["aggregateVersion"],
        record["toolSelections"][0]["selectionId"],
        "quality.lookup",
        "ALLOW_BOUNDED_MCP_INVOCATION",
        {"supplier": "fixture"},
        2,
        cancel,
    )["invocation"]


def test_exact_runtime_provenance_and_cancel_without_dispatch(selected_source):
    service, repository, scope, rid, handler = selected_source
    record = repository.get(scope, "mcp", rid)
    result = invoke(service, scope, rid, record)
    assert result["status"] == "SUCCEEDED"
    assert result["dispatchState"] == "RESPONSE_RECEIVED"
    assert handler.requests == 3  # initialize, notification, one tools/call
    assert result["revisionId"] == record["revisions"][0]["revisionId"]
    assert result["revisionDigest"] == record["revisions"][0]["digest"]
    assert result["snapshotDigest"] == record["discoverySnapshots"][0]["digest"]
    assert result["snapshotId"] == record["discoverySnapshots"][0]["snapshotId"]
    assert repository.get(scope, "mcp", rid)["invocations"][0] == result
    handler.requests = 0
    cancelled = invoke(
        service, scope, rid, repository.get(scope, "mcp", rid), cancel=True
    )
    assert cancelled["dispatchState"] == "NOT_DISPATCHED"
    assert cancelled["status"] == "CANCELLED"
    assert handler.requests == 0


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("endpoint", "EXACT_MCP_SELECTION_SOURCE_REQUIRED"),
        ("content", "EXACT_MCP_RUNTIME_CONTENT_REQUIRED"),
        ("legacy", "EXACT_MCP_SELECTION_SOURCE_REQUIRED"),
        ("snapshot", "EXACT_MCP_SELECTION_SOURCE_REQUIRED"),
        ("catalog", "EXACT_MCP_DISCOVERY_CATALOG_REQUIRED"),
        ("duplicate", "EXACT_MCP_DISCOVERY_CATALOG_REQUIRED"),
        ("disabled", "MCP_SOURCE_UNAVAILABLE"),
        ("archived", "MCP_SOURCE_UNAVAILABLE"),
    ],
)
def test_invalid_selection_never_initializes_or_calls(
    selected_source, mutation, reason
):
    service, repository, scope, rid, handler = selected_source
    record = repository.get(scope, "mcp", rid)
    if mutation == "endpoint":
        revision = record["revisions"][0]
        revision["content"]["endpoint"] = "http://127.0.0.1:1/changed"
        revision["digest"] = service._digest(record, revision)
    elif mutation == "content":
        record["revisions"][0]["content"]["endpoint"] = "http://127.0.0.1:1/changed"
    elif mutation == "legacy":
        record["toolSelections"][0].pop("revisionId")
    elif mutation == "snapshot":
        record["discoverySnapshots"][0]["revisionDigest"] = "different"
    elif mutation == "catalog":
        record["discoverySnapshots"][0]["catalog"]["tools"][0]["name"] = "changed"
    elif mutation == "duplicate":
        snapshot = record["discoverySnapshots"][0]
        snapshot["catalog"]["tools"].append(
            copy.deepcopy(snapshot["catalog"]["tools"][0])
        )
        snapshot["digest"] = canonical_digest(
            snapshot["catalog"], domain="mcp-discovery-snapshot-v1"
        )
    elif mutation == "disabled":
        record["enabled"] = False
    else:
        record["archived"] = True
    repository.replace(
        record,
        expected_version=record["aggregateVersion"],
        fact={"type": "TEST_FIXTURE_PRECONDITION"},
    )
    before = repository.get(scope, "mcp", rid)
    with pytest.raises(SkillMcpFailure, match=reason):
        invoke(service, scope, rid, before)
    assert handler.requests == 0
    assert repository.get(scope, "mcp", rid) == before


@pytest.mark.parametrize(
    "fail_at,dispatch", [(1, "NOT_DISPATCHED"), (3, "CALL_ATTEMPTED")]
)
def test_transport_failure_keeps_dispatch_evidence_and_does_not_retry(
    selected_source, fail_at, dispatch
):
    service, repository, scope, rid, handler = selected_source
    handler.fail_at = fail_at
    record = repository.get(scope, "mcp", rid)
    result = invoke(service, scope, rid, record)
    assert result["status"] == "FAILED"
    assert result["dispatchState"] == dispatch
    assert handler.requests == fail_at
    assert result["evidence"]["retried"] is False
    assert result["revisionDigest"] == record["revisions"][0]["digest"]
    assert len(repository.get(scope, "mcp", rid)["invocations"]) == 1


def test_tool_error_response_is_not_success(selected_source):
    service, repository, scope, rid, handler = selected_source
    handler.tool_error = True
    result = invoke(service, scope, rid, repository.get(scope, "mcp", rid))
    assert result["status"] == "FAILED"
    assert result["reasonCode"] == "MCP_TOOL_REPORTED_ERROR"
    assert result["dispatchState"] == "RESPONSE_RECEIVED"
    assert result["result"]["isError"] is True
    assert handler.requests == 3
