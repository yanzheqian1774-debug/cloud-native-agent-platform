import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agent_console.skill_mcp_repository import InMemorySkillMcpRepository, ResourceScope
from agent_console.skill_mcp_service import SkillMcpService
from agent_console.skill_mcp_transport import PROTOCOL_REVISION, StreamableHttpMcpClient


class McpHandler(BaseHTTPRequestHandler):
    drift = False

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        request = json.loads(self.rfile.read(length))
        assert self.headers["MCP-Protocol-Version"] == PROTOCOL_REVISION
        method = request["method"]
        if method == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_REVISION,
                "capabilities": {},
                "serverInfo": {"name": "acceptance-mcp", "version": "1"},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "quality.lookup",
                        "description": "Deterministic lookup",
                        "inputSchema": {"type": "object"},
                    }
                ]
                + (
                    [{"name": "quality.changed", "inputSchema": {"type": "object"}}]
                    if self.drift
                    else []
                )
            }
        elif method == "resources/list":
            result = {
                "resources": [{"uri": "quality://guide", "name": "Quality guide"}]
            }
        elif method == "prompts/list":
            result = {
                "prompts": [
                    {"name": "quality-summary", "description": "Summarize quality"}
                ]
            }
        elif method == "tools/call":
            result = {
                "content": [{"type": "text", "text": "supplier is healthy"}],
                "structuredContent": {
                    "supplier": request["params"]["arguments"].get("supplier"),
                    "token": "must-not-persist",
                },
            }
        else:
            self.send_error(404)
            return
        body = json.dumps(
            {"jsonrpc": "2.0", "id": request["id"], "result": result}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", "acceptance-session")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def test_real_streamable_http_discovery_selection_invocation_and_drift() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), McpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/mcp"
        assert (
            StreamableHttpMcpClient(endpoint).initialize().result["protocolVersion"]
            == PROTOCOL_REVISION
        )
        service = SkillMcpService(InMemorySkillMcpRepository())
        scope = ResourceScope("tenant", "domain")
        created = service.create(
            scope,
            "mcp",
            "human",
            "Acceptance MCP",
            {
                "description": "Local acceptance server",
                "capabilities": ["quality.lookup"],
                "endpoint": endpoint,
                "secretReference": "secret-ref:acceptance/mcp",
                "timeoutSeconds": 2,
            },
        )
        manifest = service.export_manifest(scope, "mcp", created["resourceId"])
        assert manifest["credentialMaterial"] == "NOT_INCLUDED"
        cloned = service.clone(
            scope,
            "mcp",
            created["resourceId"],
            "human",
            created["revisions"][0]["revisionId"],
            "Acceptance MCP Copy",
        )
        assert cloned["resource"]["relationships"][0]["type"] == "CLONED_FROM_TEMPLATE"
        health = service.health(scope, created["resourceId"], "human", 1, 2)
        assert health["healthObservation"]["status"] == "HEALTHY"
        discovered = service.discover(scope, created["resourceId"], "human", 2, 2)
        snapshot = discovered["discoverySnapshot"]
        assert snapshot["catalog"]["resources"][0]["uri"] == "quality://guide"
        selected = service.select_tools(
            scope,
            created["resourceId"],
            "human",
            3,
            snapshot["snapshotId"],
            ["quality.lookup"],
            "Human governed test selection",
        )
        selection = selected["resource"]["toolSelections"][0]
        invoked = service.invoke_mcp(
            scope,
            created["resourceId"],
            "human",
            4,
            selection["selectionId"],
            "quality.lookup",
            "ALLOW_BOUNDED_MCP_INVOCATION",
            {"supplier": "ACME", "password": "never-store"},
            2,
        )
        evidence = invoked["invocation"]
        assert evidence["status"] == "SUCCEEDED"
        assert evidence["input"]["password"] == "[REDACTED]"
        assert evidence["result"]["structuredContent"]["token"] == "[REDACTED]"
        cancelled = service.invoke_mcp(
            scope,
            created["resourceId"],
            "human",
            5,
            selection["selectionId"],
            "quality.lookup",
            "ALLOW_BOUNDED_MCP_INVOCATION",
            {},
            2,
            True,
        )
        assert cancelled["invocation"]["status"] == "CANCELLED"
        McpHandler.drift = True
        changed = service.discover(scope, created["resourceId"], "human", 6, 2)
        assert changed["resource"]["driftRecords"][0]["status"] == "DRIFT_DETECTED"
    finally:
        McpHandler.drift = False
        server.shutdown()
        server.server_close()
