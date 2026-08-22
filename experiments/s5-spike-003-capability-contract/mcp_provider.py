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
    CapabilitySubmission,
    ErrorClass,
    InvocationHandle,
    ResultStatus,
)


class McpWorkItemProvider:
    provider_ref = "provider/mcp/local-work-item"

    def __init__(self, server: Path, native_mode: str = "success") -> None:
        self._server = server
        self._requests: dict[str, CapabilityRequest] = {}
        self._native_mode = native_mode
        self.native_evidence: dict[str, str] = {}
        self.start_count = 0

    @staticmethod
    def _rpc(process: subprocess.Popen[str], request: dict[str, Any]) -> dict[str, Any]:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        return json.loads(process.stdout.readline())

    def submit(self, request: CapabilityRequest) -> CapabilitySubmission:
        self.start_count += 1
        native_id = str(uuid4())
        self._requests[native_id] = request
        handle = InvocationHandle(self.provider_ref, native_id)
        return CapabilitySubmission(request.execution, handle)

    def _failure(
        self, request: CapabilityRequest, native_id: str, error: ErrorClass
    ) -> CapabilityResult:
        return CapabilityResult(
            status=ResultStatus.FAILED,
            invocation_id=request.execution.invocation_id,
            correlation_id=request.execution.correlation_id,
            error_class=error,
            message="capability provider failed",
            diagnostic_ref=f"native-evidence://{self.provider_ref}/{native_id}",
        )

    def observe(self, handle: InvocationHandle) -> CapabilityResult:
        native_id = handle.native_id
        request = self._requests.pop(native_id)
        with subprocess.Popen(
            [sys.executable, str(self._server), self._native_mode],
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
        if "error" in called:
            self.native_evidence[native_id] = "json-rpc-error"
            return self._failure(request, native_id, ErrorClass.PROVIDER_PROTOCOL_ERROR)
        if called.get("result", {}).get("isError"):
            self.native_evidence[native_id] = "mcp-tool-error"
            return self._failure(
                request, native_id, ErrorClass.REMOTE_EXECUTION_FAILURE
            )
        native = json.loads(called["result"]["content"][0]["text"])
        return CapabilityResult(
            status=ResultStatus.SUCCEEDED,
            invocation_id=request.execution.invocation_id,
            correlation_id=request.execution.correlation_id,
            output={
                "item_id": native["id"],
                "summary": native["title"],
                "completed": native["completed"],
            },
        )
