"""Selected publication routes under the existing BFF session/CSRF authority."""

from psycopg.errors import LockNotAvailable
from pydantic import Field

from .authority_contracts import ExactGrant
from .business_capability import BusinessCapabilityError, FixedReference
from .digital_employee_definition import EmployeeDefinitionError
from .resource_management import target
from .resource_upgrade_batch_postgres import UpgradeBatchError
from .resource_upgrade_preview import ConsumerSelection, UpgradeSelection
from .resource_upgrade_selection import UpgradeSelectionError
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_owner_authorization import WorkbenchOwnerError

_ID = r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$"


class UpgradeReference(StrictWorkbenchModel):
    resourceId: str = Field(pattern=_ID)
    revisionId: str = Field(pattern=_ID)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    def reference(self):
        return FixedReference(self.resourceId, self.revisionId, self.digest)


class UpgradeConsumer(StrictWorkbenchModel):
    original: UpgradeReference
    successorRevisionId: str = Field(pattern=_ID)

    def selection(self):
        return ConsumerSelection(self.original.reference(), self.successorRevisionId)


class UpgradePreviewInput(StrictWorkbenchModel):
    oldSkill: UpgradeReference
    newSkill: UpgradeReference
    employees: list[UpgradeConsumer] = Field(default_factory=list, max_length=64)
    capabilities: list[UpgradeConsumer] = Field(default_factory=list, max_length=64)

    def selection(self):
        return UpgradeSelection(
            self.oldSkill.reference(),
            self.newSkill.reference(),
            tuple(item.selection() for item in self.employees),
            tuple(item.selection() for item in self.capabilities),
        )


class UpgradeSubmitInput(UpgradePreviewInput):
    commandId: str = Field(pattern=_ID)
    reviewDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=1, max_length=1000)


def root_grant(context, path, payload, query):
    value = UpgradePreviewInput.model_validate(
        {
            k: payload[k]
            for k in ("oldSkill", "newSkill", "employees", "capabilities")
            if k in payload
        }
    )
    return (
        ExactGrant(
            "SKILL", "MANAGE_RESOURCE", target("skill", value.newSkill.resourceId)
        ),
    )


def operations(coordinator):
    def handle(call):
        try:
            if call.operation == "PREVIEW_SELECTED_RESOURCE_UPGRADE":
                value = UpgradePreviewInput.model_validate(call.payload)
                return coordinator.preview(call, value.selection())
            value = UpgradeSubmitInput.model_validate(call.payload)
            kwargs = dict(
                command=value.commandId,
                reviewed_digest=value.reviewDigest,
                reason=value.reason,
            )
            if call.operation == "READ_SELECTED_RESOURCE_UPGRADE_RECEIPT":
                return coordinator.receipt(call, value.selection(), **kwargs)
            return coordinator.submit(call, value.selection(), **kwargs)
        except LockNotAvailable as exc:
            raise WorkbenchOwnerError("UPGRADE_CONCURRENT_CHANGE", 409) from exc
        except (
            UpgradeBatchError,
            UpgradeSelectionError,
            BusinessCapabilityError,
            EmployeeDefinitionError,
        ) as exc:
            # AuthorizationError remains handled by the existing BFF envelope.
            raise WorkbenchOwnerError(str(exc), 409) from exc

    root = PREFIX + "/resource-upgrades"
    return tuple(
        WorkbenchOperation(
            name, "POST", root + suffix, schema, None, root_grant, handle
        )
        for name, suffix, schema in (
            ("PREVIEW_SELECTED_RESOURCE_UPGRADE", "/preview", UpgradePreviewInput),
            ("SUBMIT_SELECTED_RESOURCE_UPGRADE", "/submit", UpgradeSubmitInput),
            # POST carries the original selection to reauthorize every disclosed item.
            # This endpoint only reads the receipt; it never applies/retries owners.
            ("READ_SELECTED_RESOURCE_UPGRADE_RECEIPT", "/receipt", UpgradeSubmitInput),
        )
    )
