"""Reusable exact read-only Skill graph preflight before owner effects."""

from .execution_preparation import ExecutionPreparationError


def validate_mapping(semantics, operations, expected):
    by_name = {operation["name"]: operation for operation in operations}
    tasks = semantics["tasks"]
    ids = {task["task_id"] for task in tasks}
    if len(ids) != len(tasks) or not ids:
        raise ExecutionPreparationError("READONLY_TASK_IDENTITIES_INVALID")
    graph = {}
    for task in tasks:
        operation = by_name.get(task["operation"])
        if operation is None:
            raise ExecutionPreparationError("READONLY_OPERATION_UNAVAILABLE")
        if operation.get("sideEffectClass") != "READ_ONLY":
            raise ExecutionPreparationError("READONLY_SIDE_EFFECT_DENIED")
        if (
            operation["executorId"],
            operation["executorRevision"],
            operation["executorConfigurationDigest"],
        ) != (
            expected.executor_id,
            expected.executor_revision,
            expected.configuration_digest,
        ):
            raise ExecutionPreparationError("READONLY_EXECUTOR_MISMATCH")
        dependencies = set(task["depends_on"])
        if not dependencies <= ids or task["task_id"] in dependencies:
            raise ExecutionPreparationError("READONLY_DEPENDENCY_INVALID")
        # READ_DATA consumes the fixed source; all other operations consume the
        # actual outputs of predecessors, never an invented empty dependency.
        if (task["operation"] == "READ_DATA") != (not dependencies):
            raise ExecutionPreparationError("READONLY_SOURCE_PATH_INVALID")
        graph[task["task_id"]] = dependencies
    reached = set()
    while len(reached) < len(graph):
        ready = {identity for identity, deps in graph.items() if deps <= reached}
        if ready <= reached:
            raise ExecutionPreparationError("READONLY_DEPENDENCY_CYCLE")
        reached |= ready
    if not any(task["operation"] == "RENDER_REPORT" for task in tasks):
        raise ExecutionPreparationError("READONLY_REPORT_REQUIRED")
