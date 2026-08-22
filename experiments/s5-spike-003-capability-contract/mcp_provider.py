"""MCP stdio translation behind the experimental provider boundary."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from capability_contract import (
    CapabilityRequest,
    CapabilityResult,
    InvocationHandle,
    ResultStatus,
)


class McpWorkItemProvider:
    provider_ref = "provider/mcp/local-work-item"

    def __init__(self, server: Path) -> None:
        self._server = server
        self._results: dict[str, CapabilityResult] = {}
        self.start_count = 0

    @staticmethod
    def _rpc(process: subprocess.Popen[str], request: dict[str, Any]) -> dict[str, Any]:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        return json.loads(process.stdout.readline())

    def start(self, request: CapabilityRequest) -> InvocationHandle:
        self.start_count += 1
        native_id = str(uuid4())
        with subprocess.Popen(
            [sys.executable, str(self._server)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as process:
            self._rpc(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18"},
                },
            )
            listed = self._rpc(
                process,
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            if not any(
                tool["name"] == "work_item_read" for tool in listed["result"]["tools"]
            ):
                raise RuntimeError("MCP work_item_read tool not discovered")
            called = self._rpc(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "work_item_read", "arguments": request.input},
                },
            )
        native = json.loads(called["result"]["content"][0]["text"])
        self._results[native_id] = CapabilityResult(
            status=ResultStatus.SUCCEEDED,
            correlation_id=request.correlation_id,
            output={
                "item_id": native["id"],
                "summary": native["title"],
                "completed": native["completed"],
            },
        )
        return InvocationHandle(self.provider_ref, native_id)

    def result(self, handle: InvocationHandle) -> CapabilityResult:
        return self._results.pop(handle.native_id)
