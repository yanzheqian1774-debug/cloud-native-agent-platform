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
    if document.get("schemaVersion") != "bounded-task-roots.v1":
        raise AuthorityError("TASK_AUTHORIZATION_ROOT_CONFIGURATION_INVALID")
    bindings = {}
    for item in document["roots"]:
        key = (item["purpose"], item["tenantId"], item["securityDomain"])
        require_scope(key[0], key[1:])
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
    delegation.repository.bounded_task_authorization_enabled = True
    return install_bounded_task_routes(service)
