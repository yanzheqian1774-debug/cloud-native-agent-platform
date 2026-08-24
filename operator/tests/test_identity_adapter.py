import pytest
from agent_core.representation.v0_2 import DesiredRuntimeBinding, RuntimeBinding
from agent_operator.identity_adapter import adapt_task_target


def desired_binding() -> DesiredRuntimeBinding:
    return DesiredRuntimeBinding(
        RuntimeBinding(
            binding_id="desired",
            provider_ref="provider.example",
            mode="managed",
        )
    )


def test_adapter_preserves_current_definition_facing_task_target() -> None:
    spec = {"agentRef": {"name": "researcher"}, "input": {"prompt": "hello"}}
    original = {"agentRef": {"name": "researcher"}, "input": {"prompt": "hello"}}
    request = adapt_task_target(
        task_spec=spec,
        task_name="task-1",
        namespace="workloads",
        desired_runtime_binding=desired_binding(),
    )
    assert request.agent_name == "researcher"
    assert request.namespace == "workloads"
    assert request.source_task_name == "task-1"
    assert spec == original


@pytest.mark.parametrize("spec", [{}, {"agentRef": {}}, {"agentRef": {"name": ""}}])
def test_adapter_fails_safely_for_missing_task_target(spec: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        adapt_task_target(
            task_spec=spec,
            task_name="task-1",
            namespace="workloads",
            desired_runtime_binding=desired_binding(),
        )
