import inspect
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from capability_contract import (  # noqa: E402
    Capability,
    CapabilityBinding,
    CapabilityIdentity,
    ResultStatus,
)
from generic_caller import BindingPolicy, execute  # noqa: E402
from mcp_provider import McpWorkItemProvider  # noqa: E402
from rest_provider import RestTodoProvider  # noqa: E402

IDENTITY = CapabilityIdentity("work-item.read", "0.1")
BINDING = CapabilityBinding(IDENTITY, "provider/rest/test", "read")
ALLOW = BindingPolicy({("agent/a", "work-item.read", "read")})


def test_identity_excludes_provider_risk_and_permission() -> None:
    assert set(CapabilityIdentity.__dataclass_fields__) == {"capability_id", "version"}
    capability = Capability(
        IDENTITY,
        "Read a work item",
        "schema://work-item-read-input/0.1",
        "schema://work-item-read-output/0.1",
        "risk://read-only",
    )
    assert capability.risk_classification_ref == "risk://read-only"


def test_rest_provider_normalizes_native_result() -> None:
    response = httpx.Response(
        200,
        json={"id": 1, "title": "a task", "completed": False},
        request=httpx.Request("GET", "https://example.test/todos/1"),
    )
    provider = RestTodoProvider(get=lambda *args, **kwargs: response)
    result = execute(
        agent_id="agent/a",
        binding=BINDING,
        provider=provider,
        policy=ALLOW,
        input_data={"todo_id": 1},
        correlation_id="rest-1",
    )
    assert result.status is ResultStatus.SUCCEEDED
    assert result.output == {"item_id": 1, "summary": "a task", "completed": False}


def test_mcp_provider_uses_same_agent_side_semantics() -> None:
    provider = McpWorkItemProvider(ROOT / "mcp_work_item_server.py")
    result = execute(
        agent_id="agent/a",
        binding=CapabilityBinding(IDENTITY, provider.provider_ref, "read"),
        provider=provider,
        policy=ALLOW,
        input_data={"todo_id": 1},
        correlation_id="mcp-1",
    )
    assert result.status is ResultStatus.SUCCEEDED
    assert result.output == {
        "item_id": 1,
        "summary": "delectus aut autem",
        "completed": False,
    }


def test_discoverable_binding_can_be_denied_without_provider_invocation() -> None:
    provider = RestTodoProvider(get=lambda *args, **kwargs: None)
    result = execute(
        agent_id="agent/denied",
        binding=BINDING,
        provider=provider,
        policy=ALLOW,
        input_data={"todo_id": 1},
        correlation_id="deny-1",
    )
    assert result.status is ResultStatus.DENIED
    assert result.error_code == "capability_not_authorized"
    assert provider.start_count == 0


def test_generic_caller_has_no_provider_kind_branch() -> None:
    source = inspect.getsource(execute).lower()
    assert 'provider == "rest"' not in source
    assert 'provider == "mcp"' not in source
    assert "provider_ref" not in source
