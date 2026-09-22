"""Delivery mapping fails before instances/Assignments or effects are created."""

import pytest
from agent_console.delivery_resource_bundle import resource_content
from agent_console.execution_preparation import ExecutionPreparationError
from agent_console.prepared_delivery_contract import validate_delivery_mapping


def tasks():
    return {
        "tasks": [
            {"task_id": "read", "operation": "READ_DATA", "depends_on": []},
            {
                "task_id": "report",
                "operation": "RENDER_REPORT",
                "depends_on": ["read"],
            },
        ]
    }


def test_delivery_minimal_graph_uses_real_executor_not_cost_substitute():
    operations = resource_content()["skill"]["operations"]
    validate_delivery_mapping(tasks(), operations)
    operations[0]["executorId"] = "cost-readonly"
    with pytest.raises(ExecutionPreparationError, match="EXECUTOR_MISMATCH"):
        validate_delivery_mapping(tasks(), operations)


@pytest.mark.parametrize(
    "change,reason",
    [
        (lambda t: t[1].update(depends_on=[]), "SOURCE_PATH_INVALID"),
        (lambda t: t[1].update(depends_on=["missing"]), "DEPENDENCY_INVALID"),
        (lambda t: t[1].update(operation="UNSUPPORTED"), "OPERATION_UNAVAILABLE"),
        (lambda t: t[1].update(operation="SUMMARIZE"), "REPORT_REQUIRED"),
    ],
)
def test_delivery_gap_is_visible_before_dispatch(change, reason):
    semantics = tasks()
    change(semantics["tasks"])
    with pytest.raises(ExecutionPreparationError, match=reason):
        validate_delivery_mapping(semantics, resource_content()["skill"]["operations"])
