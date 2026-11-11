"""Fixed business references reuse existing readers; no execution authority."""

from dataclasses import replace

from .authority_contracts import AuthorityError
from .digital_employee_definition import EmployeeDefinitionError
from .execution_domain import ScopeIdentity
from .knowledge_repository import KnowledgeRepositoryError
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_resources import PreparedResourceOwner
from .workbench_resource_directory import target


class BusinessProcessReferences:
    def __init__(self, employees=None, services=None):
        self.employees = employees
        self.services = services or {}
        self.resources = PreparedResourceOwner(self.services)

    def read(self, call, kind, reference, *, require_published=False):
        scope = ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        principal = OwnerPrincipal(
            call.context.principal_id, scope.namespace, scope.security_domain
        )
        try:
            if kind == "knowledge":
                if "knowledge" not in self.services:
                    self.unavailable()
                grant = target(kind, reference.resource_id, reference.revision_id)
                call.authority.require(
                    principal, grant.owner, grant.action, grant.exact_resource
                )
                if require_published:
                    row = call.connection.execute(
                        "SELECT record FROM knowledge_operation.knowledge "
                        "WHERE namespace=%s AND security_domain=%s "
                        "AND knowledge_id=%s FOR SHARE",
                        (scope.namespace, scope.security_domain, reference.resource_id),
                    ).fetchone()
                    if (
                        not row
                        or not row["record"].get("enabled", True)
                        or row["record"].get("archived", False)
                    ):
                        raise WorkbenchOwnerError(
                            "BUSINESS_PROCESS_REFERENCE_UNAVAILABLE", 409
                        )
                value = self.resources(
                    replace(
                        call,
                        operation="READ_PREPARED_RESOURCE",
                        path={
                            "kind": kind,
                            "identity": reference.resource_id,
                            "revision": reference.revision_id,
                        },
                        payload={},
                        query={},
                    )
                )
                self.check_digest(reference, value["revision"]["digest"])
                if require_published:
                    self.check_published(value["revision"]["state"])
                return value
            if self.employees is None:
                self.unavailable()
            call.authority.require(
                principal,
                "EMPLOYEE",
                "READ",
                f"employee:{reference.resource_id}:{reference.revision_id}",
            )
            value = self.employees.read_revision_for_workbench(
                call.connection,
                scope,
                reference.resource_id,
                reference.revision_id,
                authorized=True,
            )
            self.check_digest(reference, value["digest"])
            if require_published:
                self.check_published(value["publicationState"])
            return value
        except AuthorityError as error:
            raise WorkbenchOwnerError(
                "BUSINESS_PROCESS_REFERENCE_NOT_FOUND", 404
            ) from error
        except (EmployeeDefinitionError, KnowledgeRepositoryError) as error:
            raise WorkbenchOwnerError(
                "BUSINESS_PROCESS_REFERENCE_UNAVAILABLE", 409
            ) from error

    @staticmethod
    def references(content):
        return [("knowledge", reference) for reference in content.source_materials] + [
            ("employee", item.employee) for item in content.activities if item.employee
        ]

    def validate(self, call, content, *, require_published=False):
        for kind, reference in self.references(content):
            self.read(call, kind, reference, require_published=require_published)

    def describe(self, call, content):
        """Hide failed reference names without hiding the business definition."""
        items = {}
        for kind, reference in self.references(content):
            key = (kind, reference.resource_id, reference.revision_id, reference.digest)
            if key in items:
                continue
            result = {"kind": kind, "reference": reference.model_dump(mode="json")}
            try:
                value = self.read(call, kind, reference)
                name = (
                    value["name"] if kind == "knowledge" else value["revision"]["role"]
                )
                result.update(status="AVAILABLE", name=name)
            except WorkbenchOwnerError:
                result.update(status="UNAVAILABLE")
            items[key] = result
        return {"items": list(items.values()), "executionAuthorized": False}

    @staticmethod
    def check_published(state):
        if state != "PUBLISHED":
            raise WorkbenchOwnerError("BUSINESS_PROCESS_REFERENCE_NOT_PUBLISHED", 422)

    @staticmethod
    def check_digest(reference, actual):
        if actual != reference.digest:
            raise WorkbenchOwnerError(
                "BUSINESS_PROCESS_REFERENCE_VERSION_MISMATCH", 422
            )

    @staticmethod
    def unavailable():
        raise WorkbenchOwnerError("BUSINESS_PROCESS_REFERENCE_ADAPTER_UNAVAILABLE", 422)
