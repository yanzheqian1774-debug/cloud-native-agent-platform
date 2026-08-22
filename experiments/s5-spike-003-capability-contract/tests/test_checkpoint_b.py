import inspect
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from capability_contract import (  # noqa: E402
    CapabilityBinding,
    CapabilityIdentity,
    CapabilityRequest,
    ErrorClass,
    ExecutionIdentity,
    ResultStatus,
)
from generic_caller import BindingPolicy, execute  # noqa: E402
from mcp_provider import McpWorkItemProvider  # noqa: E402
from rest_provider import RestTodoProvider  # noqa: E402

IDENTITY = CapabilityIdentity("work-item.read", "0.1")
ALLOW = BindingPolicy({("agent/a", "work-item.read", "read")})
SERVER = ROOT / "mcp_work_item_server.py"


def binding(provider: object) -> CapabilityBinding:
    return CapabilityBinding(IDENTITY, provider.provider_ref, "read")


def call(provider: object, input_data: dict[str, object] | None = None):
    return execute(
        agent_id="agent/a",
        binding=binding(provider),
        provider=provider,
        policy=ALLOW,
        input_data={"todo_id": 1} if input_data is None else input_data,
        correlation_id="business-correlation-7",
        invocation_id="platform-invocation-42",
    )


def response(status: int, payload: object) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload,
        request=httpx.Request("GET", "https://provider.invalid/native"),
    )


def test_platform_execution_identity_survives_rest_and_mcp_boundaries() -> None:
    rest = RestTodoProvider(
        get=lambda *args, **kwargs: response(
            200, {"id": 1, "title": "work", "completed": False}
        )
    )
    mcp = McpWorkItemProvider(SERVER)

    for outcome in (call(rest), call(mcp)):
        assert outcome.invocation_id == "platform-invocation-42"
        assert outcome.correlation_id == "business-correlation-7"
        assert "rest" not in outcome.invocation_id
        assert "mcp" not in outcome.invocation_id


def test_rest_unavailability_is_normalized_without_native_status_leakage() -> None:
    provider = RestTodoProvider(get=lambda *args, **kwargs: response(503, {}))
    outcome = call(provider)

    assert outcome.status is ResultStatus.FAILED
    assert outcome.error_class is ErrorClass.PROVIDER_UNAVAILABLE
    assert "503" not in (outcome.message or "")
    assert outcome.diagnostic_ref is not None
    assert "remote-status:503" in provider.native_evidence.values()


def test_mcp_protocol_error_is_normalized_without_json_rpc_leakage() -> None:
    provider = McpWorkItemProvider(SERVER, native_mode="protocol_error")
    outcome = call(provider)

    assert outcome.status is ResultStatus.FAILED
    assert outcome.error_class is ErrorClass.PROVIDER_PROTOCOL_ERROR
    assert "json" not in (outcome.message or "").lower()
    assert outcome.diagnostic_ref is not None
    assert "json-rpc-error" in provider.native_evidence.values()


def test_different_native_remote_failures_share_normalized_class() -> None:
    rest = RestTodoProvider(get=lambda *args, **kwargs: response(422, {}))
    mcp = McpWorkItemProvider(SERVER, native_mode="tool_error")

    assert call(rest).error_class is ErrorClass.REMOTE_EXECUTION_FAILURE
    assert call(mcp).error_class is ErrorClass.REMOTE_EXECUTION_FAILURE


def test_rest_timeout_input_and_unknown_are_distinct() -> None:
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("native timeout")

    timeout_result = call(RestTodoProvider(get=timeout))
    input_result = call(RestTodoProvider(), input_data={})
    malformed_result = call(
        RestTodoProvider(get=lambda *args, **kwargs: response(200, ["unexpected"]))
    )

    assert timeout_result.error_class is ErrorClass.TIMEOUT
    assert input_result.error_class is ErrorClass.INPUT_INVALID
    assert malformed_result.error_class is ErrorClass.UNKNOWN


def test_contract_supports_inline_and_deferred_outcome_without_caller_branch() -> None:
    execution = ExecutionIdentity("platform-invocation-42", "correlation-7")
    request = CapabilityRequest(IDENTITY, "read", {"todo_id": 1}, execution)
    rest = RestTodoProvider(
        get=lambda *args, **kwargs: response(
            200, {"id": 1, "title": "work", "completed": False}
        )
    )
    mcp = McpWorkItemProvider(SERVER)

    assert rest.submit(request).outcome is not None
    assert mcp.submit(request).outcome is None
    assert call(rest).status is ResultStatus.SUCCEEDED
    assert call(mcp).status is ResultStatus.SUCCEEDED


def test_generic_caller_does_not_classify_provider_native_failures() -> None:
    source = inspect.getsource(execute).lower()
    for native_term in ("http", "status_code", "jsonrpc", "mcp", "rest"):
        assert native_term not in source
