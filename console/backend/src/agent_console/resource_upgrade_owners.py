"""Same-connection owner operations for a reviewed selected-upgrade batch.

Internal only: the coordinator must lock and revalidate the complete preview,
heads, absence of conflicting drafts, exact successor contents and scope before
calling this runner inside UpgradeBatchRepository.apply. Existing private BFF
routes enable this module. It never creates substitute permissions or recomputes
a review.
"""

from dataclasses import dataclass, replace

from psycopg.pq import TransactionStatus

from .business_capability import BusinessCapabilityRevision, FixedReference
from .digital_employee_definition import EmployeeRevision, digest
from .resource_upgrade_batch_postgres import UpgradeBatchError
from .workbench_business_problem import OwnerPrincipal


@dataclass(frozen=True)
class EmployeePublication:
    revision: EmployeeRevision
    expected_version: int


@dataclass(frozen=True)
class CapabilityPublication:
    revision: BusinessCapabilityRevision
    expected_version: int
    reviewed_impact_digest: str


def _command(batch, stage, identity):
    return "selected-upgrade:" + digest([batch, stage, identity])


def _member(member):
    return {
        "kind": member.kind,
        "resourceId": member.resource_id,
        "revisionId": member.revision_id,
        "digest": member.digest,
    }


class SelectedUpgradeOwners:
    def __init__(self, resources, employees, capabilities, *, definitions=None):
        self.resources = resources
        self.definitions = definitions
        self.employees = employees
        self.capabilities = capabilities

    @staticmethod
    def _employee_call(call, operation, payload, path, action, resource):
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        decision = call.authority.require(principal, "EMPLOYEE", action, resource)
        return replace(
            call,
            operation=operation,
            payload=payload,
            path=path,
            query={},
            decisions=(decision,),
        )

    def publish_employee(self, call, batch, selected):
        revision = selected.revision
        path = {
            "employee_definition_id": revision.definition_id,
            "revision_id": revision.revision_id,
        }
        payload = {
            "employeeDefinitionId": revision.definition_id,
            "employeeDefinitionRevisionId": revision.revision_id,
            "role": revision.role,
            "responsibilities": list(revision.responsibilities),
            "members": [_member(m) for m in revision.members],
            "predecessorEmployeeRevisionId": revision.predecessor_revision_id,
            "responsibilityBindings": [
                {"responsibility": b.responsibility, "member": _member(b.member)}
                for b in revision.responsibility_bindings
            ],
            "expectedVersion": selected.expected_version,
            "commandId": _command(batch, "employee-create", revision.definition_id),
        }
        receipt = self.employees(
            self._employee_call(
                call,
                "CREATE_EMPLOYEE_REVISION",
                payload,
                path,
                "CREATE",
                "employee:collection",
            )
        )
        receipts = [receipt]
        for action in ("VALIDATE", "APPROVE", "PUBLISH"):
            receipt = self.employees(
                self._employee_call(
                    call,
                    f"{action}_EMPLOYEE_REVISION",
                    {
                        "employeeDefinitionDigest": revision.digest,
                        "expectedVersion": receipt["aggregateVersion"],
                        "commandId": _command(
                            batch, "employee-" + action, revision.definition_id
                        ),
                    },
                    path,
                    action,
                    f"employee:{revision.definition_id}:aggregate",
                )
            )
            receipts.append(receipt)
        if receipt["lifecycleState"] != "PUBLISHED":
            raise UpgradeBatchError("UPGRADE_EMPLOYEE_NOT_PUBLISHED")
        return receipts

    def publish_capability(self, call, batch, selected, reason):
        revision = selected.revision
        path = {
            "capability_id": revision.capability_id,
            "revision_id": revision.revision_id,
        }
        saved = self.capabilities(
            replace(
                call,
                operation="SAVE_CAPABILITY_DRAFT",
                path=path,
                query={},
                payload={
                    "revision": revision.canonical_record(),
                    "expectedVersion": selected.expected_version,
                    "commandId": _command(
                        batch, "capability-save", revision.capability_id
                    ),
                },
            )
        )
        # This digest is from the user-reviewed batch. Never substitute a new preview.
        published = self.capabilities(
            replace(
                call,
                operation="PUBLISH_CAPABILITY_REVISION",
                path=path,
                query={},
                payload={
                    "expectedVersion": saved["aggregateVersion"],
                    "digest": revision.content_digest,
                    "impactDigest": selected.reviewed_impact_digest,
                    "reason": reason,
                    "commandId": _command(
                        batch, "capability-publish", revision.capability_id
                    ),
                },
            )
        )
        return {"saved": saved, "published": published}

    def apply(self, call, **selection):
        if call.connection.info.transaction_status != TransactionStatus.INTRANS:
            raise UpgradeBatchError("UPGRADE_CALLER_TRANSACTION_REQUIRED")
        # Guard the whole chain even if a caller catches the owner exception.
        with call.connection.transaction():
            return self._apply(call, **selection)

    def _apply(
        self,
        call,
        *,
        batch,
        skill: FixedReference,
        skill_version,
        employees,
        capabilities,
        reason,
        resource_kind="skill",
    ):
        if resource_kind not in {"skill", "mcp", "knowledge"}:
            raise UpgradeBatchError("UPGRADE_RESOURCE_KIND_INVALID")
        scope = (call.context.scope.tenant_id, call.context.scope.security_domain)
        if not reason.strip():
            raise UpgradeBatchError("UPGRADE_REVIEW_REASON_REQUIRED")
        # Reject cross-scope or duplicate requests before any owner mutation.
        for values, identity in (
            (employees, "definition_id"),
            (capabilities, "capability_id"),
        ):
            seen = set()
            for selected in values:
                revision = selected.revision
                key = getattr(revision, identity)
                if (revision.scope.namespace, revision.scope.security_domain) != scope:
                    raise UpgradeBatchError("UPGRADE_SCOPE_MISMATCH")
                if (
                    key in seen
                    or selected.expected_version < 1
                    or revision.predecessor_revision_id is None
                ):
                    raise UpgradeBatchError("UPGRADE_SUCCESSOR_SELECTION_INVALID")
                seen.add(key)
        manager = self.definitions if resource_kind == "knowledge" else self.resources
        if manager is None:
            raise UpgradeBatchError("UPGRADE_KNOWLEDGE_OWNER_UNAVAILABLE")
        resource = manager.handle(
            replace(
                call,
                operation="DEFINITION_MANAGEMENT"
                if resource_kind == "knowledge"
                else "RESOURCE_MANAGEMENT",
                path={"kind": resource_kind},
                query={},
                payload={
                    "action": "publish-tested"
                    if resource_kind == "skill"
                    else "publish",
                    "identity": skill.resource_id,
                    "expectedVersion": skill_version,
                    "commandKey": _command(
                        batch, resource_kind + "-publish", skill.resource_id
                    ),
                },
            )
        )
        record = resource["resource"]
        exact = next(
            (r for r in record["revisions"] if r["revisionId"] == skill.revision_id),
            None,
        )
        if (
            record["publishedRevisionId"] != skill.revision_id
            or not exact
            or exact["digest"] != skill.digest
        ):
            raise UpgradeBatchError("UPGRADE_PUBLISHED_RESOURCE_MISMATCH")
        employee_receipts = [
            self.publish_employee(call, batch, item)
            for item in sorted(employees, key=lambda x: x.revision.definition_id)
        ]
        capability_receipts = [
            self.publish_capability(call, batch, item, reason)
            for item in sorted(capabilities, key=lambda x: x.revision.capability_id)
        ]
        return {
            "resource": {
                "identity": skill.resource_id,
                "revisionId": skill.revision_id,
                "digest": skill.digest,
                "aggregateVersion": resource["aggregateVersion"],
                "commandKey": resource["commandKey"],
                "policyDecisionId": resource["policyDecisionId"],
                "policyIssuer": resource["policyIssuer"],
                **(
                    {
                        "currentOperationTestsReady": resource[
                            "publicationVerification"
                        ]["ready"]
                    }
                    if resource_kind == "skill"
                    else {
                        "resourceKind": resource_kind,
                        "verificationLevel": "KNOWLEDGE_POLICY_PUBLICATION"
                        if resource_kind == "knowledge"
                        else "CONFIGURATION_POLICY_PUBLICATION",
                        **(
                            {
                                "indexingStarted": False,
                                "retrievalVerified": False,
                                "activeIndexSnapshotId": record.get(
                                    "activeIndexSnapshotId"
                                ),
                            }
                            if resource_kind == "knowledge"
                            else {}
                        ),
                        "invocationVerified": False,
                    }
                ),
            },
            "employees": employee_receipts,
            "capabilities": capability_receipts,
        }
