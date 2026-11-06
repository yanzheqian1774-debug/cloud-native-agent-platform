"""Check the delivery Skill's real dependency contract before owner writes."""

from .execution_preparation import ExecutionPreparationError
from .synthetic_delivery_skill import SyntheticDeliverySkillExecutor
from .synthetic_delivery_skill_v2 import SyntheticDeliverySkillExecutorV2


def delivery_revision(identity, revision, digest):
    return next(
        (
            item.revision
            for item in (
                SyntheticDeliverySkillExecutor,
                SyntheticDeliverySkillExecutorV2,
            )
            if (identity, revision, digest)
            == (
                item.revision.executor_id,
                item.revision.executor_revision,
                item.revision.configuration_digest,
            )
        ),
        None,
    )


def validate_delivery_mapping(semantics, operations):
    declared_revisions = {
        (op["executorId"], op["executorRevision"], op["executorConfigurationDigest"])
        for op in operations
    }
    if any(delivery_revision(*exact) is None for exact in declared_revisions):
        raise ExecutionPreparationError("DELIVERY_EXECUTOR_MISMATCH")
    if len(declared_revisions) > 1:
        raise ExecutionPreparationError("DELIVERY_EXECUTOR_REVISION_MIXED")
    by_name = {}
    for operation in operations:
        previous = by_name.get(operation["name"])
        if previous is not None and previous != operation:
            raise ExecutionPreparationError("DELIVERY_OPERATION_DECLARATION_CONFLICT")
        by_name[operation["name"]] = operation
    tasks = semantics["tasks"]
    ids = {task["task_id"] for task in tasks}
    if len(ids) != len(tasks) or not ids:
        raise ExecutionPreparationError("DELIVERY_TASK_IDENTITIES_INVALID")
    graph = {}
    revisions = set()
    for task in tasks:
        operation = by_name.get(task["operation"])
        if operation is None:
            raise ExecutionPreparationError("DELIVERY_OPERATION_UNAVAILABLE")
        exact = (
            operation["executorId"],
            operation["executorRevision"],
            operation["executorConfigurationDigest"],
        )
        expected = delivery_revision(*exact)
        if expected is None:
            raise ExecutionPreparationError("DELIVERY_EXECUTOR_MISMATCH")
        revisions.add(exact)
        if expected.executor_revision == "2":
            from .planning_contracts import INPUTS, OUTPUTS
            from .synthetic_delivery_skill_v2 import OPERATIONS

            if (
                task["operation"] not in OPERATIONS
                or task.get("output_kind") != OUTPUTS[task["operation"]]
                or not set(task.get("input_kinds", [])) <= INPUTS[task["operation"]]
            ):
                raise ExecutionPreparationError("DELIVERY_TYPED_MAPPING_MISMATCH")
        dependencies = set(task["depends_on"])
        if not dependencies <= ids or task["task_id"] in dependencies:
            raise ExecutionPreparationError("DELIVERY_DEPENDENCY_INVALID")
        # READ_DATA consumes the fixed source; all other operations consume the
        # actual outputs of predecessors, never an invented empty dependency.
        if (task["operation"] == "READ_DATA") != (not dependencies):
            raise ExecutionPreparationError("DELIVERY_SOURCE_PATH_INVALID")
        graph[task["task_id"]] = dependencies
    if len(revisions) != 1:
        raise ExecutionPreparationError("DELIVERY_EXECUTOR_REVISION_MIXED")
    reached = set()
    while len(reached) < len(graph):
        ready = {identity for identity, deps in graph.items() if deps <= reached}
        if ready <= reached:
            raise ExecutionPreparationError("DELIVERY_DEPENDENCY_CYCLE")
        reached |= ready
    if not any(task["operation"] == "RENDER_REPORT" for task in tasks):
        raise ExecutionPreparationError("DELIVERY_REPORT_REQUIRED")
