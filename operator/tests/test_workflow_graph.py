import pytest
from agent_operator.workflow_graph import (
    WorkflowValidationError,
    build_workflow_graph,
    find_ready_tasks,
    find_skipped_tasks,
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


def test_find_ready_tasks_returns_root_tasks() -> None:
    graph = build_workflow_graph(
        [
            {"name": "research"},
            {"name": "market", "dependsOn": ["research"]},
            {"name": "technology", "dependsOn": ["research"]},
            {"name": "report", "dependsOn": ["market", "technology"]},
        ]
    )

    assert find_ready_tasks(graph, {}) == ["research"]


def test_find_ready_tasks_returns_tasks_with_succeeded_dependencies() -> None:
    graph = build_workflow_graph(
        [
            {"name": "research"},
            {"name": "market", "dependsOn": ["research"]},
            {"name": "technology", "dependsOn": ["research"]},
            {"name": "report", "dependsOn": ["market", "technology"]},
        ]
    )

    assert find_ready_tasks(
        graph,
        {
            "research": "Succeeded",
        },
    ) == ["market", "technology"]


def test_find_ready_tasks_waits_for_all_dependencies() -> None:
    graph = build_workflow_graph(
        [
            {"name": "research"},
            {"name": "market", "dependsOn": ["research"]},
            {"name": "technology", "dependsOn": ["research"]},
            {"name": "report", "dependsOn": ["market", "technology"]},
        ]
    )

    assert (
        find_ready_tasks(
            graph,
            {
                "research": "Succeeded",
                "market": "Succeeded",
                "technology": "Running",
            },
        )
        == []
    )


def test_find_ready_tasks_returns_fan_in_task_when_all_dependencies_succeed() -> None:
    graph = build_workflow_graph(
        [
            {"name": "research"},
            {"name": "market", "dependsOn": ["research"]},
            {"name": "technology", "dependsOn": ["research"]},
            {"name": "report", "dependsOn": ["market", "technology"]},
        ]
    )

    assert find_ready_tasks(
        graph,
        {
            "research": "Succeeded",
            "market": "Succeeded",
            "technology": "Succeeded",
        },
    ) == ["report"]


def test_build_workflow_graph_accepts_result_source_dependency() -> None:
    tasks = [
        {
            "name": "research",
            "dependsOn": [],
            "input": {
                "prompt": "research",
            },
        },
        {
            "name": "market",
            "dependsOn": ["research"],
            "input": {
                "prompt": "market",
                "from": [
                    {
                        "task": "research",
                    }
                ],
            },
        },
    ]

    graph = build_workflow_graph(tasks)

    assert graph.task_names == (
        "research",
        "market",
    )
    assert graph.dependencies == {
        "research": (),
        "market": ("research",),
    }
    assert graph.topological_order() == [
        "research",
        "market",
    ]


def test_build_workflow_graph_rejects_unknown_result_source() -> None:
    tasks = [
        {
            "name": "research",
            "dependsOn": [],
            "input": {
                "prompt": "research",
            },
        },
        {
            "name": "market",
            "dependsOn": [],
            "input": {
                "prompt": "market",
                "from": [
                    {
                        "task": "missing-task",
                    }
                ],
            },
        },
    ]

    with pytest.raises(
        WorkflowValidationError,
        match="references unknown result source",
    ):
        build_workflow_graph(tasks)


def test_build_workflow_graph_rejects_self_result_source() -> None:
    tasks = [
        {
            "name": "research",
            "dependsOn": [],
            "input": {
                "prompt": "research",
                "from": [
                    {
                        "task": "research",
                    }
                ],
            },
        },
    ]

    with pytest.raises(
        WorkflowValidationError,
        match="cannot consume its own result",
    ):
        build_workflow_graph(tasks)


def test_build_workflow_graph_rejects_duplicate_result_sources() -> None:
    tasks = [
        {
            "name": "research",
            "dependsOn": [],
            "input": {
                "prompt": "research",
            },
        },
        {
            "name": "market",
            "dependsOn": ["research"],
            "input": {
                "prompt": "market",
                "from": [
                    {
                        "task": "research",
                    },
                    {
                        "task": "research",
                    },
                ],
            },
        },
    ]

    with pytest.raises(
        WorkflowValidationError,
        match="has duplicate result source",
    ):
        build_workflow_graph(tasks)


def test_build_workflow_graph_rejects_result_source_not_in_dependencies() -> None:
    tasks = [
        {
            "name": "research",
            "dependsOn": [],
            "input": {
                "prompt": "research",
            },
        },
        {
            "name": "market",
            "dependsOn": [],
            "input": {
                "prompt": "market",
                "from": [
                    {
                        "task": "research",
                    }
                ],
            },
        },
    ]

    with pytest.raises(
        WorkflowValidationError,
        match="must also appear in dependsOn",
    ):
        build_workflow_graph(tasks)


def test_find_skipped_tasks_skips_failed_dependency() -> None:
    graph = build_workflow_graph(
        [
            {
                "name": "research",
                "dependsOn": [],
                "agentRef": {"name": "research-agent"},
                "input": {"prompt": "research"},
            },
            {
                "name": "report",
                "dependsOn": ["research"],
                "agentRef": {"name": "report-agent"},
                "input": {"prompt": "report"},
            },
        ]
    )

    skipped = find_skipped_tasks(
        graph,
        {
            "research": "Failed",
        },
    )

    assert skipped == ["report"]


def test_find_skipped_tasks_skips_timed_out_dependency() -> None:
    graph = build_workflow_graph(
        [
            {
                "name": "research",
                "dependsOn": [],
                "agentRef": {"name": "research-agent"},
                "input": {"prompt": "research"},
            },
            {
                "name": "report",
                "dependsOn": ["research"],
                "agentRef": {"name": "report-agent"},
                "input": {"prompt": "report"},
            },
        ]
    )

    skipped = find_skipped_tasks(
        graph,
        {
            "research": "TimedOut",
        },
    )

    assert skipped == ["report"]


def test_find_skipped_tasks_propagates_transitively() -> None:
    graph = build_workflow_graph(
        [
            {
                "name": "architect",
                "dependsOn": [],
                "agentRef": {"name": "architect-agent"},
                "input": {"prompt": "architect"},
            },
            {
                "name": "builder",
                "dependsOn": ["architect"],
                "agentRef": {"name": "builder-agent"},
                "input": {"prompt": "builder"},
            },
            {
                "name": "reviewer",
                "dependsOn": ["builder"],
                "agentRef": {"name": "reviewer-agent"},
                "input": {"prompt": "reviewer"},
            },
            {
                "name": "publish",
                "dependsOn": ["reviewer"],
                "agentRef": {"name": "publish-agent"},
                "input": {"prompt": "publish"},
            },
        ]
    )

    skipped = find_skipped_tasks(
        graph,
        {
            "architect": "Failed",
        },
    )

    assert skipped == [
        "builder",
        "reviewer",
        "publish",
    ]


def test_find_skipped_tasks_does_not_skip_independent_sibling() -> None:
    graph = build_workflow_graph(
        [
            {
                "name": "root",
                "dependsOn": [],
                "agentRef": {"name": "root-agent"},
                "input": {"prompt": "root"},
            },
            {
                "name": "failed-branch",
                "dependsOn": ["root"],
                "agentRef": {"name": "failed-agent"},
                "input": {"prompt": "failed"},
            },
            {
                "name": "independent-branch",
                "dependsOn": ["root"],
                "agentRef": {"name": "independent-agent"},
                "input": {"prompt": "independent"},
            },
            {
                "name": "failed-descendant",
                "dependsOn": ["failed-branch"],
                "agentRef": {"name": "descendant-agent"},
                "input": {"prompt": "descendant"},
            },
        ]
    )

    skipped = find_skipped_tasks(
        graph,
        {
            "root": "Succeeded",
            "failed-branch": "Failed",
            "independent-branch": "Running",
        },
    )

    assert skipped == ["failed-descendant"]


def test_find_skipped_tasks_skips_fan_in_immediately() -> None:
    graph = build_workflow_graph(
        [
            {
                "name": "root",
                "dependsOn": [],
                "agentRef": {"name": "root-agent"},
                "input": {"prompt": "root"},
            },
            {
                "name": "builder",
                "dependsOn": ["root"],
                "agentRef": {"name": "builder-agent"},
                "input": {"prompt": "builder"},
            },
            {
                "name": "tester",
                "dependsOn": ["root"],
                "agentRef": {"name": "tester-agent"},
                "input": {"prompt": "tester"},
            },
            {
                "name": "reviewer",
                "dependsOn": ["builder", "tester"],
                "agentRef": {"name": "reviewer-agent"},
                "input": {"prompt": "reviewer"},
            },
        ]
    )

    skipped = find_skipped_tasks(
        graph,
        {
            "root": "Succeeded",
            "builder": "Failed",
            "tester": "Running",
        },
    )

    assert skipped == ["reviewer"]


def test_find_skipped_tasks_never_skips_existing_task() -> None:
    graph = build_workflow_graph(
        [
            {
                "name": "root",
                "dependsOn": [],
                "agentRef": {"name": "root-agent"},
                "input": {"prompt": "root"},
            },
            {
                "name": "child",
                "dependsOn": ["root"],
                "agentRef": {"name": "child-agent"},
                "input": {"prompt": "child"},
            },
        ]
    )

    skipped = find_skipped_tasks(
        graph,
        {
            "root": "Failed",
            "child": "Running",
        },
    )

    assert skipped == []
