"""Run deterministic Checkpoint B identity, failure, and lifecycle evidence."""

import json
from dataclasses import asdict
from pathlib import Path

import httpx
from capability_contract import CapabilityBinding, CapabilityIdentity
from generic_caller import BindingPolicy, execute
from mcp_provider import McpWorkItemProvider
from rest_provider import RestTodoProvider

ROOT = Path(__file__).parent
IDENTITY = CapabilityIdentity("work-item.read", "0.1")
POLICY = BindingPolicy({("agent/researcher", "work-item.read", "read")})


def native_response(status: int) -> httpx.Response:
    return httpx.Response(
        status,
        json={},
        request=httpx.Request("GET", "https://provider.invalid/native"),
    )


def invoke(provider: object, suffix: str):
    return execute(
        agent_id="agent/researcher",
        binding=CapabilityBinding(IDENTITY, provider.provider_ref, "read"),
        provider=provider,
        policy=POLICY,
        input_data={"todo_id": 1},
        correlation_id=f"s5-spike-003-b-{suffix}",
        invocation_id=f"platform-invocation-{suffix}",
    )


def run() -> dict[str, object]:
    rest_unavailable = RestTodoProvider(
        get=lambda *args, **kwargs: native_response(503)
    )
    mcp_protocol = McpWorkItemProvider(
        ROOT / "mcp_work_item_server.py", native_mode="protocol_error"
    )
    rest_remote = RestTodoProvider(get=lambda *args, **kwargs: native_response(422))
    mcp_remote = McpWorkItemProvider(
        ROOT / "mcp_work_item_server.py", native_mode="tool_error"
    )
    outcomes = {
        "rest_unavailable": invoke(rest_unavailable, "rest-unavailable"),
        "mcp_protocol": invoke(mcp_protocol, "mcp-protocol"),
        "rest_remote_failure": invoke(rest_remote, "rest-remote"),
        "mcp_remote_failure": invoke(mcp_remote, "mcp-remote"),
    }
    return {
        name: {
            key: value
            for key, value in asdict(outcome).items()
            if key != "diagnostic_ref"
        }
        for name, outcome in outcomes.items()
    }


if __name__ == "__main__":
    print(json.dumps(run(), default=str, indent=2))
