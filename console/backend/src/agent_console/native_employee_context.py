"""Immutable employee context for an explicitly selected Native successor.

The supplied authorization port must check the original invocation's exact
employee READ. This projection grants no tool, model or business authority.
"""

from .digital_employee_definition import EmployeeRevision
from .digital_employee_definition_postgres import PostgresEmployeeDefinitionRepository
from .execution_domain import ScopeIdentity
from .native_document_skill import NativeEmployeeDocumentSkillExecutor


def read_bound_employee_context(
    connection,
    preparation,
    task_id,
    *,
    authorize,
    executor_revision=NativeEmployeeDocumentSkillExecutor.revision,
):
    members = [p for p in preparation.participants if p.task_id == task_id]
    if len(members) != 1:
        raise ValueError("NATIVE_EMPLOYEE_TASK_BINDING_MISMATCH")
    member = members[0]
    executor = executor_revision
    if (member.executor_id, member.executor_revision, member.executor_digest) != (
        executor.executor_id,
        executor.executor_revision,
        executor.configuration_digest,
    ):
        raise ValueError("NATIVE_EMPLOYEE_EXECUTOR_MISMATCH")
    ref = member.definition
    authorize(ref)
    record = PostgresEmployeeDefinitionRepository._read(
        connection,
        ScopeIdentity(preparation.namespace, preparation.security_domain),
        ref.resource_id,
        ref.revision_id,
    )
    revision = EmployeeRevision.from_record(record["revision"])
    if (
        not record["published"]
        or record["digest"] != ref.digest
        or revision.digest != ref.digest
    ):
        raise ValueError("NATIVE_EMPLOYEE_REVISION_UNAVAILABLE")
    return {
        "schemaVersion": "native-employee-context.v1",
        "taskId": task_id,
        "reference": {
            "resource_id": ref.resource_id,
            "revision_id": ref.revision_id,
            "digest": ref.digest,
        },
        "role": revision.role,
        "responsibilities": list(revision.responsibilities),
        "authority": "TASK_CONTEXT_ONLY_NOT_PERMISSION",
    }
