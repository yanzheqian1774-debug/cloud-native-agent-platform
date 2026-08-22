"""Run Checkpoint A real REST, real local MCP, and DENY evidence."""

import json
from pathlib import Path

from capability_contract import CapabilityBinding, CapabilityIdentity
from generic_caller import BindingPolicy, execute
from mcp_provider import McpWorkItemProvider
from rest_provider import RestTodoProvider

ROOT = Path(__file__).parent
IDENTITY = CapabilityIdentity("work-item.read", "0.1")


def run() -> dict[str, object]:
    allowed = {("agent/researcher", "work-item.read", "read")}
    policy = BindingPolicy(allowed)
    rest = RestTodoProvider()
    rest_result = execute(
        agent_id="agent/researcher",
        binding=CapabilityBinding(IDENTITY, rest.provider_ref, "read"),
        provider=rest,
        policy=policy,
        input_data={"todo_id": 1},
        correlation_id="s5-spike-003-rest",
    )
    mcp = McpWorkItemProvider(ROOT / "mcp_work_item_server.py")
    mcp_result = execute(
        agent_id="agent/researcher",
        binding=CapabilityBinding(IDENTITY, mcp.provider_ref, "read"),
        provider=mcp,
        policy=policy,
        input_data={"todo_id": 1},
        correlation_id="s5-spike-003-mcp",
    )
    deny = execute(
        agent_id="agent/untrusted",
        binding=CapabilityBinding(IDENTITY, rest.provider_ref, "read"),
        provider=rest,
        policy=policy,
        input_data={"todo_id": 1},
        correlation_id="s5-spike-003-deny",
    )
    return {
        "rest": rest_result,
        "mcp": mcp_result,
        "deny": deny,
        "deny_provider_start_count_unchanged": rest.start_count == 1,
    }


if __name__ == "__main__":
    print(json.dumps(run(), default=lambda value: value.__dict__, indent=2))
