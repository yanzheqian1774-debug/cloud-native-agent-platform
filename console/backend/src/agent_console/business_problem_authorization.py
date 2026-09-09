"""Exact resource names for the Human-accepted 297 actions; no wildcards."""


def problem_resource(identity=None):
    return (
        "business-problem:collection"
        if identity is None
        else f"business-problem:{identity}"
    )


def criterion_resource(identity=None):
    return (
        "success-criterion:collection"
        if identity is None
        else f"success-criterion:{identity}"
    )


def criterion_revision_resource(identity):
    return f"success-criterion:revision:{identity}"


def criteria_resource(problem_id):
    return f"success-criteria-set:{problem_id}"


def plan_resource(plan_id, version):
    return f"plan:{plan_id}:{version}"


def reference_grants(command):
    return (
        (
            "WORKFLOW",
            "READ",
            f"workflow:{command.workflowDefinitionId}:{command.workflowDefinitionRevisionId}",
        ),
        (
            "EMPLOYEE",
            "READ",
            f"employee:{command.employeeDefinitionId}:{command.employeeDefinitionRevisionId}",
        ),
        ("INSTANCE", "READ", f"instance:{command.digitalEmployeeInstanceId}"),
        ("ASSIGNMENT", "READ", f"assignment:{command.assignmentId}"),
    )
