"""Selected publication within the existing authorized request transaction.

The BFF must provide a generation-pinned AuthorizedOwnerCall; no endpoint or
implicit grant is introduced here. The caller commits the returned receipt.
"""

from .digital_employee_definition import digest
from .execution_domain import ScopeIdentity
from .resource_upgrade_batch_postgres import UpgradeBatchError, UpgradeBatchRepository


class SelectedUpgradeCoordinator:
    def __init__(self, previews, owners):
        self.previews, self.owners = previews, owners

    def preview(self, call, selected):
        value = self.previews.build(call, selected)
        return {"preview": value.preview, "reviewDigest": value.review_digest}

    def submit(self, call, selected, *, command, reviewed_digest, reason):
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise UpgradeBatchError("UPGRADE_REVIEW_REASON_REQUIRED")
        self.previews.authorize_sources(call, selected)
        prepared = []

        def revalidate():
            value = self.previews.build(call, selected, lock=True)
            prepared.append(value)
            return value.review_digest

        def apply():
            value = prepared[0]
            return self.owners.apply(
                call,
                batch=command,
                skill=selected.new_skill,
                skill_version=value.skill_version,
                resource_kind=selected.resource_kind,
                employees=value.employees,
                capabilities=value.capabilities,
                reason=reason,
            )

        return UpgradeBatchRepository.apply(
            call.connection,
            ScopeIdentity(
                call.context.scope.tenant_id, call.context.scope.security_domain
            ),
            call.context.principal_id,
            command,
            request={"selection": selected.record(), "reason": reason},
            reviewed_digest=reviewed_digest,
            authority_generation=call.policy_generation,
            recovery_epoch=call.recovery_epoch,
            decision_ids=tuple(
                d.decision_id for d in call.authority.decisions.values()
            ),
            completed_decision_ids=lambda: tuple(
                d.decision_id for d in call.authority.decisions.values()
            ),
            current_preview_digest=revalidate,
            apply_owners=apply,
        )

    def receipt(self, call, selected, *, command, reviewed_digest, reason):
        self.previews.authorize_sources(call, selected)
        result = UpgradeBatchRepository.read(
            call.connection,
            ScopeIdentity(
                call.context.scope.tenant_id, call.context.scope.security_domain
            ),
            call.context.principal_id,
            command,
        )
        if result["state"] == "COMMITTED":
            expected = digest(
                {
                    "request": {"selection": selected.record(), "reason": reason},
                    "previewDigest": reviewed_digest,
                }
            )
            if result["receipt"]["requestDigest"] != expected:
                raise UpgradeBatchError("UPGRADE_BATCH_COMMAND_CONFLICT")
        return result
