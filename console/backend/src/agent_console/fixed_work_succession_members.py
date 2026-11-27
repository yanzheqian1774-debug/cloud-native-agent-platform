"""Exact Employee composition differences, never a resource-use authorization.

The public owner checks each changed Employee READ before calling this internal
projection. History validation may recompute immutable facts without displaying
these records; it does not confer current reader or execution permissions.
"""

from .digital_employee_definition import EmployeeRevision
from .digital_employee_definition_postgres import PostgresEmployeeDefinitionRepository
from .execution_domain import ScopeIdentity
from .fixed_work_succession import require


def changed_references(preview):
    return sorted(
        {
            (
                v["employee_definition_id"],
                v["employee_revision_id"],
                v["employee_digest"],
            )
            for item in preview["memberChanges"]
            for v in (item["before"], item["after"])
            if v is not None
        }
    )


def compositions(c, scope, preview):
    result = []
    for identity, revision_id, expected_digest in changed_references(preview):
        value = PostgresEmployeeDefinitionRepository.read_revision_for_workbench(
            c, ScopeIdentity(*scope), identity, revision_id, authorized=True
        )
        revision = EmployeeRevision.from_record(value["revision"])
        require(
            revision.scope == ScopeIdentity(*scope)
            and revision.definition_id == identity
            and revision.revision_id == revision_id
            and revision.digest == value["digest"] == expected_digest,
            "EMPLOYEE_CHANGED",
        )
        # Exact references already included in the authorized Employee record.
        # No Skill body, secret, capability grant or inferred publication state.
        result.append(
            {
                "employeeDefinitionId": identity,
                "employeeRevisionId": revision_id,
                "employeeDigest": expected_digest,
                "members": revision.record["members"],
            }
        )
    return result
