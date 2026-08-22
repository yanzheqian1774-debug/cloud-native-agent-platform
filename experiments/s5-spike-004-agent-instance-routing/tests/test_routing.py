"""Falsification tests for S5-SPIKE-004 Checkpoint B routing."""

import sys
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT))

from generic_caller import GenericCaller, LogicalAgentRequest  # noqa: E402
from object_model import (  # noqa: E402
    AgentInstance,
    DesiredLifecycle,
    ExperimentalRuntimeProvider,
    RuntimeBinding,
)
from routing import ExperimentalPlatformRouter  # noqa: E402


def build_shared_gateway_route() -> tuple[
    GenericCaller, ExperimentalPlatformRouter, ExperimentalRuntimeProvider
]:
    instances = (
        AgentInstance(
            "researcher-a", "researcher", "v7", DesiredLifecycle.RUNNING, "binding-a"
        ),
        AgentInstance(
            "researcher-b", "researcher", "v7", DesiredLifecycle.RUNNING, "binding-b"
        ),
    )
    bindings = (
        RuntimeBinding("binding-a", "researcher-a", "shared-runtime"),
        RuntimeBinding("binding-b", "researcher-b", "shared-runtime"),
    )
    provider = ExperimentalRuntimeProvider("shared-runtime")
    provider.realize(
        bindings[0],
        realization_id="session-a-v1",
        native_kind="GatewaySession",
        native_id="shared-gateway/session-a-v1",
    )
    provider.realize(
        bindings[1],
        realization_id="session-b-v1",
        native_kind="GatewaySession",
        native_id="shared-gateway/session-b-v1",
    )
    router = ExperimentalPlatformRouter(
        instances=instances, bindings=bindings, providers=(provider,)
    )
    return GenericCaller(router), router, provider


def test_logical_definition_routes_deterministically_between_instances() -> None:
    caller, router, _ = build_shared_gateway_route()

    outcomes = [
        caller.invoke(LogicalAgentRequest(f"exec-{index}", "researcher", "inspect"))
        for index in range(1, 5)
    ]

    assert [item.instance_id for item in outcomes] == [
        "researcher-a",
        "researcher-b",
        "researcher-a",
        "researcher-b",
    ]
    assert [item.execution_id for item in outcomes] == [
        "exec-1",
        "exec-2",
        "exec-3",
        "exec-4",
    ]
    assert [item.execution_id for item in router.dispatch_evidence] == [
        item.execution_id for item in outcomes
    ]


def test_explicit_logical_instance_route_survives_realization_replacement() -> None:
    caller, router, provider = build_shared_gateway_route()
    request = LogicalAgentRequest(
        "exec-stable", "researcher", "inspect", "researcher-a"
    )

    before = caller.invoke(request)
    binding = RuntimeBinding("binding-a", "researcher-a", provider.provider_id)
    provider.replace(
        binding,
        realization_id="session-a-v2",
        native_kind="GatewaySession",
        native_id="shared-gateway/session-a-v2",
    )
    after = caller.invoke(request)

    assert before == after
    first_dispatch, second_dispatch = router.dispatch_evidence
    assert first_dispatch.execution_id == second_dispatch.execution_id == "exec-stable"
    assert first_dispatch.instance_id == second_dispatch.instance_id == "researcher-a"
    assert first_dispatch.native_id != second_dispatch.native_id


def test_shared_gateway_does_not_collapse_distinct_logical_instances() -> None:
    caller, router, _ = build_shared_gateway_route()

    caller.invoke(LogicalAgentRequest("exec-a", "researcher", "a", "researcher-a"))
    caller.invoke(LogicalAgentRequest("exec-b", "researcher", "b", "researcher-b"))

    first, second = router.dispatch_evidence
    assert first.instance_id != second.instance_id
    assert first.native_id.split("/")[0] == second.native_id.split("/")[0]
    assert first.native_id != second.native_id


def test_generic_caller_contains_only_logical_vocabulary() -> None:
    source = (EXPERIMENT / "generic_caller.py").read_text().lower()
    forbidden = (
        "pod",
        "container",
        "hermes",
        "openclaw",
        "gateway",
        "endpoint_url",
        "native_id",
        "realization",
        "provider",
    )

    assert all(word not in source for word in forbidden)
