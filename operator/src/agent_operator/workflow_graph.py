from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class WorkflowValidationError(ValueError):
    """Raised when a workflow DAG is invalid."""


@dataclass(frozen=True)
class WorkflowGraph:
    """Validated dependency graph for workflow tasks."""

    task_names: tuple[str, ...]
    dependencies: dict[str, tuple[str, ...]]

    def topological_order(self) -> list[str]:
        """Return task names in a valid dependency execution order."""

        indegree = {name: 0 for name in self.task_names}
        dependents: dict[str, list[str]] = {name: [] for name in self.task_names}

        for task_name, dependencies in self.dependencies.items():
            indegree[task_name] = len(dependencies)

            for dependency in dependencies:
                dependents[dependency].append(task_name)

        ready = deque(name for name in self.task_names if indegree[name] == 0)
        ordered: list[str] = []

        while ready:
            task_name = ready.popleft()
            ordered.append(task_name)

            for dependent in dependents[task_name]:
                indegree[dependent] -= 1

                if indegree[dependent] == 0:
                    ready.append(dependent)

        if len(ordered) != len(self.task_names):
            raise WorkflowValidationError("workflow contains a dependency cycle")

        return ordered


def build_workflow_graph(tasks: Sequence[Mapping[str, Any]]) -> WorkflowGraph:
    """Validate workflow tasks and build their dependency graph."""

    if not tasks:
        raise WorkflowValidationError("workflow must contain at least one task")

    task_names: list[str] = []
    dependencies: dict[str, tuple[str, ...]] = {}

    for task in tasks:
        name = task["name"]

        if name in dependencies:
            raise WorkflowValidationError(f"duplicate task name: {name}")

        task_dependencies = tuple(task.get("dependsOn", []))

        if len(task_dependencies) != len(set(task_dependencies)):
            raise WorkflowValidationError(
                f"task '{name}' contains duplicate dependencies"
            )

        task_names.append(name)
        dependencies[name] = task_dependencies

    known_tasks = set(task_names)

    for task_name, task_dependencies in dependencies.items():
        for dependency in task_dependencies:
            if dependency == task_name:
                raise WorkflowValidationError(
                    f"task '{task_name}' cannot depend on itself"
                )

            if dependency not in known_tasks:
                raise WorkflowValidationError(
                    f"task '{task_name}' depends on unknown task '{dependency}'"
                )

    graph = WorkflowGraph(
        task_names=tuple(task_names),
        dependencies=dependencies,
    )

    graph.topological_order()

    return graph


def find_ready_tasks(
    graph: WorkflowGraph,
    task_phases: Mapping[str, str],
) -> list[str]:
    """Return workflow tasks whose dependencies have all succeeded.

    Tasks already present in task_phases are considered already scheduled
    and are therefore not returned.
    """

    ready: list[str] = []

    for task_name in graph.task_names:
        if task_name in task_phases:
            continue

        dependencies = graph.dependencies[task_name]

        if all(
            task_phases.get(dependency) == "Succeeded" for dependency in dependencies
        ):
            ready.append(task_name)

    return ready
