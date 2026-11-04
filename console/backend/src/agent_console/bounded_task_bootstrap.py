"""Opt-in task authorization assembly; never selects or rolls back provider config."""

import json
from pathlib import Path

from .authority_contracts import AuthorityError
from .bounded_task_api import install_bounded_task_routes
from .bounded_task_authorization import BoundedTaskAuthorization
from .bounded_task_policy import require_scope
from .plan_suggestion_domain import ExactReference


def install_task_authorization(path, delegation, planning_admission, dependencies):
    source = Path(path)
    if not source.is_absolute():
        raise AuthorityError("TASK_AUTHORIZATION_ROOT_CONFIGURATION_INVALID")
    document = json.loads(source.read_text())
    if document.get("schemaVersion") not in {
        "bounded-task-roots.v1",
        "bounded-task-roots.v2",
    }:
        raise AuthorityError("TASK_AUTHORIZATION_ROOT_CONFIGURATION_INVALID")
    bindings = {}
    for item in document["roots"]:
        key = (item["purpose"], item["tenantId"], item["securityDomain"])
        require_scope(key[0], key[1:])
        if key[0] == "SALES_DIAGNOSTIC":
            if document["schemaVersion"] != "bounded-task-roots.v2":
                raise AuthorityError("TASK_AUTHORIZATION_ROOT_CONFIGURATION_INVALID")
            key = (*key, item["root"]["resource_id"])
        if key in bindings:
            raise AuthorityError("TASK_AUTHORIZATION_ROOT_CONFIGURATION_INVALID")
        bindings[key] = ExactReference.model_validate(item["root"]).model_dump(
            mode="json"
        )
    if not bindings:
        raise AuthorityError("TASK_AUTHORIZATION_ROOT_CONFIGURATION_INVALID")
    service = BoundedTaskAuthorization(delegation, root_bindings=bindings)
    service.migrate()
    if dependencies is not None and planning_admission is not None:
        config = dependencies.provider.configuration
        actual = {
            **planning_admission.configuration,
            "connect_seconds": config.connect_timeout_seconds,
            "read_seconds": config.read_timeout_seconds,
            "total_seconds": config.total_timeout_seconds,
        }
        planning_admission.actual_configuration = actual
        planning_admission.bounded_tasks_enabled = True
        dependencies.budget.owner.task_actual_configuration = actual
        service.actual_configuration = actual
    from .initial_case_creation import InitialCaseCreation

    creation = document.get("initialCases", [])
    if creation and document["schemaVersion"] != "bounded-task-roots.v2":
        raise AuthorityError("TASK_AUTHORIZATION_ROOT_CONFIGURATION_INVALID")
    creation = tuple(InitialCaseCreation.model_validate(item) for item in creation)
    keys = {(b.tenant_id, b.security_domain, b.subject_id, b.root_id) for b in creation}
    if len(keys) != len(creation):
        raise AuthorityError("TASK_AUTHORIZATION_ROOT_CONFIGURATION_INVALID")
    for binding in creation:
        require_scope("SALES_DIAGNOSTIC", (binding.tenant_id, binding.security_domain))
    delegation.repository.initial_case_creation_bindings = creation
    delegation.repository.bounded_task_authorization_enabled = True
    return install_bounded_task_routes(service)
