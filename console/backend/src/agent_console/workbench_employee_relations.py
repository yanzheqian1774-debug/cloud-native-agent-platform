"""Current-readable Employee relations over original exact owner reads."""

from dataclasses import replace

from psycopg import Error as PostgresError

from .authority_contracts import AuthorityError
from .digital_employee_application import DigitalEmployeeError
from .digital_employee_definition import EmployeeDefinitionError
from .execution_domain import ScopeIdentity
from .execution_postgres import DigitalEmployeeInstanceId
from .resource_use_domain import canonical_digest
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import WorkbenchPageQuery
from .workbench_employee import (
    DigitalEmployeeOwnerAdapter,
    EmployeeDefinitionOwnerAdapter,
    _employee_revision_read,
    _instance_read,
    _OwnerPrincipal,
)
from .workbench_owner_authorization import WorkbenchOwnerError


class EmployeeRelations:
    def __init__(self, definitions, instances, cursors):
        self.definitions, self.instances, self.cursors = definitions, instances, cursors

    def __call__(self, call):
        try:
            return self.read(call)
        except (PostgresError, EmployeeDefinitionError, DigitalEmployeeError) as exc:
            raise WorkbenchOwnerError(
                "DIGITAL_EMPLOYEE_STORAGE_UNAVAILABLE", 503
            ) from exc

    def read(self, call):
        ctx, connection = call.context, call.connection
        scope = ScopeIdentity(ctx.scope.tenant_id, ctx.scope.security_domain)
        principal = _OwnerPrincipal(
            principal_id=ctx.principal_id,
            tenant_id=scope.namespace,
            security_domain=scope.security_domain,
        )
        operation = call.operation
        if operation not in {
            "READ_EMPLOYEE_HISTORY",
            "READ_EMPLOYEE_INSTANCES",
            "READ_INSTANCE_ASSIGNMENTS",
        }:
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        builder = (
            _instance_read
            if operation == "READ_INSTANCE_ASSIGNMENTS"
            else _employee_revision_read
        )
        for grant in builder(ctx, call.path, call.payload, call.query):
            call.authority.require(
                principal, grant.owner, grant.action, grant.exact_resource
            )
        if operation in {"READ_EMPLOYEE_HISTORY", "READ_EMPLOYEE_INSTANCES"}:
            parent = EmployeeDefinitionOwnerAdapter(self.definitions)(
                replace(call, operation="READ_EMPLOYEE_REVISION")
            )
            binding = {
                "employeeDefinitionId": parent["employeeDefinitionId"],
                "employeeDefinitionRevisionId": parent["employeeDefinitionRevisionId"],
                "employeeDefinitionDigest": parent["employeeDefinitionDigest"],
            }
        elif operation == "READ_INSTANCE_ASSIGNMENTS":
            parent = DigitalEmployeeOwnerAdapter(self.instances)(
                replace(call, operation="READ_EMPLOYEE_INSTANCE")
            )
            binding = {"instanceId": parent["instanceId"]}
        else:
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        # A cursor contains only the last disclosed authorized identity. Scope,
        # principal, relation and exact parent are bound without changing codec.
        route = "EMPLOYEE_RELATIONS:" + canonical_digest(
            [operation, ctx.principal_id, binding]
        )
        page_size, after = call.query["pageSize"], None
        if token := call.query.get("cursor"):
            after = self.cursors.resolve(
                token,
                route=route,
                context=ctx,
                page_size=page_size,
                key_size=1,
            )[0]
        kwargs = {"after": after, "limit": 201, "authorized": True}
        if operation == "READ_EMPLOYEE_HISTORY":
            ids = self.definitions.revision_ids_for_definition_for_workbench(
                connection, scope, binding["employeeDefinitionId"], **kwargs
            )
            owner = EmployeeDefinitionOwnerAdapter(self.definitions)
        elif operation == "READ_EMPLOYEE_INSTANCES":
            ids = self.instances.instance_ids_for_definition_for_workbench(
                connection,
                scope,
                binding["employeeDefinitionId"],
                binding["employeeDefinitionRevisionId"],
                binding["employeeDefinitionDigest"],
                **kwargs,
            )
            owner = DigitalEmployeeOwnerAdapter(self.instances)
        else:
            ids = self.instances.assignment_ids_for_instance_for_workbench(
                connection,
                scope,
                DigitalEmployeeInstanceId(binding["instanceId"]),
                **kwargs,
            )
            owner = DigitalEmployeeOwnerAdapter(self.instances)
        items, disclosed = [], []
        for identity in ids:
            if operation == "READ_EMPLOYEE_HISTORY":
                resource = f"employee:{binding['employeeDefinitionId']}:{identity}"
                grant_owner, child_operation = "EMPLOYEE", "READ_EMPLOYEE_REVISION"
                path = {**call.path, "revision_id": identity}
            elif operation == "READ_EMPLOYEE_INSTANCES":
                resource = "instance:" + identity
                grant_owner, child_operation = "INSTANCE", "READ_EMPLOYEE_INSTANCE"
                path = {"instance_id": identity}
            else:
                resource = "assignment:" + identity
                grant_owner, child_operation = "ASSIGNMENT", "READ_EMPLOYEE_ASSIGNMENT"
                path = {**call.path, "assignment_id": identity}
            try:
                call.authority.require(principal, grant_owner, "READ", resource)
            except AuthorityError:
                continue
            value = owner(replace(call, operation=child_operation, path=path))
            if operation == "READ_EMPLOYEE_HISTORY" and (
                value["employeeDefinitionId"] != binding["employeeDefinitionId"]
                or value["employeeDefinitionRevisionId"] != identity
            ):
                raise WorkbenchOwnerError("EMPLOYEE_HISTORY_PARENT_MISMATCH", 409)
            if operation == "READ_EMPLOYEE_INSTANCES":
                ref = value.get("employeeDefinition", {})
                if (
                    ref.get("employeeDefinitionId") != binding["employeeDefinitionId"]
                    or ref.get("employeeDefinitionRevisionId")
                    != binding["employeeDefinitionRevisionId"]
                    or ref.get("digest") != binding["employeeDefinitionDigest"]
                ):
                    raise WorkbenchOwnerError("EMPLOYEE_INSTANCE_PARENT_MISMATCH", 409)
            items.append(value)
            disclosed.append(identity)
            if len(items) > page_size:
                break
        more = len(items) > page_size
        next_cursor = (
            self.cursors.mint(
                route=route,
                context=ctx,
                page_size=page_size,
                last_key=(disclosed[page_size - 1],),
            )
            if more
            else None
        )
        return {
            "relation": operation,
            "parent": binding,
            "items": items[:page_size],
            "nextCursor": next_cursor,
            "visibility": "AUTHORIZED_ONLY",
            "scanLimited": len(ids) == 201 and not more,
            "executionStarted": False,
        }


def operations(definitions, instances, cursors):
    owner = EmployeeRelations(definitions, instances, cursors)
    path = f"{PREFIX}/employees/{{employee_definition_id}}/revisions/{{revision_id}}"
    return (
        WorkbenchOperation(
            "READ_EMPLOYEE_HISTORY",
            "GET",
            path + "/history",
            None,
            WorkbenchPageQuery,
            _employee_revision_read,
            owner,
        ),
        WorkbenchOperation(
            "READ_EMPLOYEE_INSTANCES",
            "GET",
            path + "/instances",
            None,
            WorkbenchPageQuery,
            _employee_revision_read,
            owner,
        ),
        WorkbenchOperation(
            "READ_INSTANCE_ASSIGNMENTS",
            "GET",
            f"{PREFIX}/instances/{{instance_id}}/assignments",
            None,
            WorkbenchPageQuery,
            _instance_read,
            owner,
        ),
    )
