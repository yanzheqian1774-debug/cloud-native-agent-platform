"""Real localhost read-only MCP adapter for explicitly generated project files."""

import argparse
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROTOCOL = "2025-06-18"
TOOL = "verify_project_sales_source"


def create_server(config, port):
    source_bytes = Path(config["sourceJSON"]).read_bytes()
    csv_bytes = Path(config["sourceCSV"]).read_bytes()
    source = json.loads(source_bytes)
    canonical = json.dumps(
        source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert source["synthetic"] is True
    assert hashlib.sha256(canonical).hexdigest() == config["sourceDigest"]
    assert hashlib.sha256(csv_bytes).hexdigest() == config["csvDigest"]
    output = {
        "schemaVersion": "project-sales-source-verification.v1",
        "synthetic": True,
        "sourceSnapshot": config["sourceSnapshot"],
        "sourceDigest": config["sourceDigest"],
        "csvDigest": config["csvDigest"],
        "rows": source["snapshot"]["rows"],
        "provenance": "USER_AUTHORIZED_GENERATED_PROJECT_SAMPLE",
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if (
                self.path != "/mcp"
                or int(self.headers.get("Content-Length", "0")) > 8192
            ):
                self.send_error(400)
                return
            try:
                request = json.loads(
                    self.rfile.read(int(self.headers.get("Content-Length", "0")))
                )
                method, args = request["method"], request.get("params", {})
                if method.startswith("notifications/"):
                    self.send_response(202)
                    self.end_headers()
                    return
                if method == "initialize":
                    result = {
                        "protocolVersion": PROTOCOL,
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "generated-project-sales-source",
                            "version": "1",
                        },
                    }
                elif method == "tools/list":
                    result = {
                        "tools": [
                            {
                                "name": TOOL,
                                "description": (
                                    "Read authorized generated sample rows "
                                    "and verify source digests without writes."
                                ),
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"sourceDigest": {"type": "string"}},
                                    "required": ["sourceDigest"],
                                    "additionalProperties": False,
                                },
                                "annotations": {
                                    "readOnlyHint": True,
                                    "destructiveHint": False,
                                    "idempotentHint": True,
                                },
                            }
                        ]
                    }
                elif method in {"resources/list", "prompts/list"}:
                    result = {method.split("/")[0]: []}
                elif (
                    method == "tools/call"
                    and args.get("name") == TOOL
                    and args.get("arguments")
                    == {"sourceDigest": config["sourceDigest"]}
                ):
                    result = {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    output, ensure_ascii=False, separators=(",", ":")
                                ),
                            }
                        ],
                        "isError": False,
                    }
                else:
                    raise ValueError("BOUND_SOURCE_OPERATION_REQUIRED")
                payload = {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
            except (ValueError, KeyError, TypeError):
                payload = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32602,
                        "message": "Bound generated-source operation required",
                    },
                }
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    create_server(json.loads(args.configuration.read_text()), args.port).serve_forever()
