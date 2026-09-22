"""Check the delivery Skill's real dependency contract before owner writes."""

from .execution_preparation import ExecutionPreparationError
from .synthetic_delivery_skill import SyntheticDeliverySkillExecutor


def validate_delivery_mapping(semantics, operations):
    expected = SyntheticDeliverySkillExecutor.revision
    by_name = {operation["name"]: operation for operation in operations}
    tasks = semantics["tasks"]
    ids = {task["task_id"] for task in tasks}
    if len(ids) != len(tasks) or not ids:
        raise ExecutionPreparationError("DELIVERY_TASK_IDENTITIES_INVALID")
    graph = {}
    for task in tasks:
        operation = by_name.get(task["operation"])
        if operation is None:
            raise ExecutionPreparationError("DELIVERY_OPERATION_UNAVAILABLE")
        if (
            operation["executorId"],
            operation["executorRevision"],
            operation["executorConfigurationDigest"],
        ) != (
            expected.executor_id,
            expected.executor_revision,
            expected.configuration_digest,
        ):
            raise ExecutionPreparationError("DELIVERY_EXECUTOR_MISMATCH")
        dependencies = set(task["depends_on"])
        if not dependencies <= ids or task["task_id"] in dependencies:
            raise ExecutionPreparationError("DELIVERY_DEPENDENCY_INVALID")
        # READ_DATA consumes the fixed source; all other operations consume the
        # actual outputs of predecessors, never an invented empty dependency.
        if (task["operation"] == "READ_DATA") != (not dependencies):
            raise ExecutionPreparationError("DELIVERY_SOURCE_PATH_INVALID")
        graph[task["task_id"]] = dependencies
    reached = set()
    while len(reached) < len(graph):
        ready = {identity for identity, deps in graph.items() if deps <= reached}
        if ready <= reached:
            raise ExecutionPreparationError("DELIVERY_DEPENDENCY_CYCLE")
        reached |= ready
    if not any(task["operation"] == "RENDER_REPORT" for task in tasks):
        raise ExecutionPreparationError("DELIVERY_REPORT_REQUIRED")
