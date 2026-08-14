import pytest
from agent_operator.workflow_graph import (
    WorkflowValidationError,
    build_workflow_graph,
)


def task(name: str, depends_on: list[str] | None = None) -> dict:
    value = {"name": name}

    if depends_on is not None:
        value["dependsOn"] = depends_on

    return value


def test_builds_serial_workflow() -> None:
    graph = build_workflow_graph(
        [
            task("research"),
            task("analyze", ["research"]),
            task("report", ["analyze"]),
        ]
    )

    assert graph.task_names == (
        "research",
        "analyze",
        "report",
    )

    assert graph.dependencies == {
        "research": (),
        "analyze": ("research",),
        "report": ("analyze",),
    }

    assert graph.topological_order() == [
        "research",
        "analyze",
        "report",
    ]


def test_builds_parallel_fan_out_workflow() -> None:
    graph = build_workflow_graph(
        [
            task("research"),
            task("market", ["research"]),
            task("technology", ["research"]),
        ]
    )

    order = graph.topological_order()

    assert order[0] == "research"
    assert set(order[1:]) == {
        "market",
        "technology",
    }


def test_builds_fan_in_workflow() -> None:
    graph = build_workflow_graph(
        [
            task("research"),
            task("market", ["research"]),
            task("technology", ["research"]),
            task("report", ["market", "technology"]),
        ]
    )

    order = graph.topological_order()

    assert order.index("research") < order.index("market")
    assert order.index("research") < order.index("technology")

    assert order.index("market") < order.index("report")
    assert order.index("technology") < order.index("report")


def test_rejects_empty_workflow() -> None:
    with pytest.raises(
        WorkflowValidationError,
        match="workflow must contain at least one task",
    ):
        build_workflow_graph([])


def test_rejects_duplicate_task_names() -> None:
    with pytest.raises(
        WorkflowValidationError,
        match="duplicate task name: research",
    ):
        build_workflow_graph(
            [
                task("research"),
                task("research"),
            ]
        )


def test_rejects_unknown_dependency() -> None:
    with pytest.raises(
        WorkflowValidationError,
        match="task 'report' depends on unknown task 'research'",
    ):
        build_workflow_graph(
            [
                task("report", ["research"]),
            ]
        )


def test_rejects_self_dependency() -> None:
    with pytest.raises(
        WorkflowValidationError,
        match="task 'research' cannot depend on itself",
    ):
        build_workflow_graph(
            [
                task("research", ["research"]),
            ]
        )


def test_rejects_dependency_cycle() -> None:
    with pytest.raises(
        WorkflowValidationError,
        match="workflow contains a dependency cycle",
    ):
        build_workflow_graph(
            [
                task("a", ["c"]),
                task("b", ["a"]),
                task("c", ["b"]),
            ]
        )


def test_accepts_multiple_root_tasks() -> None:
    graph = build_workflow_graph(
        [
            task("market"),
            task("technology"),
            task("report", ["market", "technology"]),
        ]
    )

    order = graph.topological_order()

    assert set(order[:2]) == {
        "market",
        "technology",
    }

    assert order[-1] == "report"


def test_rejects_duplicate_dependencies() -> None:
    with pytest.raises(
        WorkflowValidationError,
        match="task 'report' contains duplicate dependencies",
    ):
        build_workflow_graph(
            [
                task("research"),
                task("report", ["research", "research"]),
            ]
        )


def test_topological_order_is_stable_for_independent_tasks() -> None:
    graph = build_workflow_graph(
        [
            task("research"),
            task("market"),
            task("technology"),
            task("report", ["market", "technology"]),
        ]
    )

    assert graph.topological_order() == [
        "research",
        "market",
        "technology",
        "report",
    ]
