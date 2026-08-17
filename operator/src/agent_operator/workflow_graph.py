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


def build_workflow_graph(
    tasks: Sequence[Mapping[str, Any]],
) -> WorkflowGraph:
    """Validate workflow tasks and build their dependency graph."""

    if not tasks:
        raise WorkflowValidationError("workflow must contain at least one task")

    task_names: list[str] = []
    dependencies: dict[str, tuple[str, ...]] = {}

    # Pass 1:
    # Collect all task names and validate duplicate task names.
    #
    # We must collect every task name before validating result sources,
    # because a task may reference another task declared later in the
    # Workflow specification.
    for task in tasks:
        name = task["name"]

        if name in task_names:
            raise WorkflowValidationError(f"duplicate task name: {name}")

        task_names.append(name)

    task_name_set = set(task_names)

    # Pass 2:
    # Build and validate control-flow dependencies.
    for task in tasks:
        name = task["name"]
        task_dependencies = tuple(task.get("dependsOn", []))

        if len(task_dependencies) != len(set(task_dependencies)):
            raise WorkflowValidationError(
                f"task '{name}' contains duplicate dependencies"
            )

        for dependency in task_dependencies:
            if dependency == name:
                raise WorkflowValidationError(f"task '{name}' cannot depend on itself")

            if dependency not in task_name_set:
                raise WorkflowValidationError(
                    f"task '{name}' depends on unknown task '{dependency}'"
                )

        dependencies[name] = task_dependencies

    # Pass 3:
    # Validate data-flow dependencies declared through input.from.
    #
    # A result source must:
    # - reference an existing task
    # - not reference the task itself
    # - not be duplicated
    # - also appear in dependsOn
    for task in tasks:
        task_name = task["name"]
        task_dependencies = set(dependencies[task_name])
        sources = task.get("input", {}).get("from", [])

        seen_sources: set[str] = set()

        for source in sources:
            source_task = source["task"]

            if source_task == task_name:
                raise WorkflowValidationError(
                    f"task {task_name!r} cannot consume its own result"
                )

            if source_task not in task_name_set:
                raise WorkflowValidationError(
                    f"task {task_name!r} references unknown result source "
                    f"{source_task!r}"
                )

            if source_task in seen_sources:
                raise WorkflowValidationError(
                    f"task {task_name!r} has duplicate result source {source_task!r}"
                )

            if source_task not in task_dependencies:
                raise WorkflowValidationError(
                    f"result source {source_task!r} for task "
                    f"{task_name!r} must also appear in dependsOn"
                )

            seen_sources.add(source_task)

    graph = WorkflowGraph(
        task_names=tuple(task_names),
        dependencies=dependencies,
    )

    # Force cycle validation while building the graph.
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


TERMINAL_UNSUCCESSFUL_PHASES = frozenset(
    {
        "Failed",
        "TimedOut",
        "Skipped",
    }
)


def find_skipped_tasks(
    graph: WorkflowGraph,
    task_phases: Mapping[str, str],
) -> list[str]:
    """Return unscheduled tasks blocked by unsuccessful dependencies.

    A task becomes Skipped as soon as any dependency reaches a terminal
    unsuccessful phase. Skips are propagated transitively in topological
    order so the full blocked subgraph converges in one reconciliation pass.

    Tasks already present in task_phases are treated as already scheduled or
    terminal and are never converted to Skipped by this function.
    """

    effective_phases = dict(task_phases)
    skipped: list[str] = []

    for task_name in graph.topological_order():
        if task_name in effective_phases:
            continue

        dependencies = graph.dependencies[task_name]

        if any(
            effective_phases.get(dependency) in TERMINAL_UNSUCCESSFUL_PHASES
            for dependency in dependencies
        ):
            skipped.append(task_name)
            effective_phases[task_name] = "Skipped"

    return skipped
