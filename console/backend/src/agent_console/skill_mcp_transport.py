"""Bounded backend-originated MCP Streamable HTTP transport."""

from __future__ import annotations

import ipaddress
import json
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

PROTOCOL_REVISION = "2025-06-18"
MAX_RESPONSE_BYTES = 512_000
REDACTED = "[REDACTED]"
SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
}


class McpTransportFailure(RuntimeError):
    pass


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (REDACTED if key.lower() in SENSITIVE_KEYS else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class McpResponse:
    result: dict[str, Any]
    session_id: str | None


class StreamableHttpMcpClient:
    """One-request JSON subset of Streamable HTTP with strict destination policy."""

    def __init__(self, endpoint: str, *, timeout: float = 5) -> None:
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise McpTransportFailure("MCP_DESTINATION_DENIED")
        try:
            literal = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            literal = None
        if parsed.hostname != "localhost" and (
            literal is None or not literal.is_loopback
        ):
            raise McpTransportFailure("MCP_DESTINATION_DENIED")
        try:
            addresses = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(
                    parsed.hostname,
                    parsed.port or (443 if parsed.scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            }
        except (OSError, ValueError) as exc:
            raise McpTransportFailure("MCP_DESTINATION_UNRESOLVED") from exc
        if not addresses or any(not address.is_loopback for address in addresses):
            raise McpTransportFailure("MCP_DESTINATION_DENIED")
        self.endpoint = endpoint
        self.timeout = min(max(timeout, 0.1), 30)

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        session_id: str | None = None,
    ) -> McpResponse:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": PROTOCOL_REVISION,
        }
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                response = client.post(self.endpoint, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise McpTransportFailure("MCP_TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise McpTransportFailure("MCP_CONNECTION_FAILED") from exc
        if response.is_redirect:
            raise McpTransportFailure("MCP_REDIRECT_DENIED")
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise McpTransportFailure("MCP_RESPONSE_TOO_LARGE")
        if (
            response.status_code != 200
            or "application/json" not in response.headers.get("content-type", "")
        ):
            raise McpTransportFailure("MCP_INVALID_RESPONSE")
        try:
            body = json.loads(response.content)
        except (ValueError, UnicodeDecodeError) as exc:
            raise McpTransportFailure("MCP_INVALID_RESPONSE") from exc
        if (
            not isinstance(body, dict)
            or body.get("jsonrpc") != "2.0"
            or body.get("id") != 1
        ):
            raise McpTransportFailure("MCP_INVALID_RESPONSE")
        if "error" in body:
            raise McpTransportFailure("MCP_PROTOCOL_ERROR")
        if not isinstance(body.get("result"), dict):
            raise McpTransportFailure("MCP_INVALID_RESPONSE")
        return McpResponse(
            redact(body["result"]), response.headers.get("Mcp-Session-Id")
        )

    def notify(self, method: str, *, session_id: str) -> None:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": PROTOCOL_REVISION,
            "Mcp-Session-Id": session_id,
        }
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                response = client.post(
                    self.endpoint,
                    headers=headers,
                    json={"jsonrpc": "2.0", "method": method},
                )
        except httpx.HTTPError as exc:
            raise McpTransportFailure("MCP_CONNECTION_FAILED") from exc
        if response.status_code not in {200, 202, 204}:
            raise McpTransportFailure("MCP_INVALID_RESPONSE")

    def initialize(self) -> McpResponse:
        response = self.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_REVISION,
                "capabilities": {},
                "clientInfo": {
                    "name": "enterprise-agent-platform-workbench",
                    "version": "0.2.2",
                },
            },
        )
        if response.result.get("protocolVersion") != PROTOCOL_REVISION:
            raise McpTransportFailure("MCP_PROTOCOL_REVISION_UNSUPPORTED")
        if response.session_id:
            self.notify("notifications/initialized", session_id=response.session_id)
        return response
