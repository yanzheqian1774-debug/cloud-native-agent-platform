"""Deterministic local MCP stdio server used only as protocol evidence."""

import json
import sys


def response(message: dict[str, object]) -> dict[str, object]:
    method = message["method"]
    if method == "initialize":
        result = {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "s5-spike-003-work-item", "version": "0.1"},
        }
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": "work_item_read",
                    "description": "Read a deterministic work item",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"todo_id": {"type": "integer"}},
                        "required": ["todo_id"],
                    },
                }
            ]
        }
    elif method == "tools/call":
        params = message["params"]
        assert isinstance(params, dict)
        arguments = params["arguments"]
        assert isinstance(arguments, dict)
        item = {
            "id": arguments["todo_id"],
            "title": "delectus aut autem",
            "completed": False,
        }
        result = {"content": [{"type": "text", "text": json.dumps(item)}]}
    else:
        raise ValueError(f"unsupported method: {method}")
    return {"jsonrpc": "2.0", "id": message["id"], "result": result}


for line in sys.stdin:
    print(json.dumps(response(json.loads(line))), flush=True)
