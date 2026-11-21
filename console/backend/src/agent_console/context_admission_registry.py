"""Dispatch the unchanged admission API to explicitly composed exact owners."""

from .authority_contracts import AuthenticationSource, AuthorityError
from .context_call_admission import request_row


class ContextAdmissionRegistry:
    def __init__(self, root, planning, services=(), *, readmission_plan=None):
        self.readmission_plan = readmission_plan
        self.repository = root.repository
        if planning.repository is not self.repository:
            raise AuthorityError("CONTEXT_ADMISSION_REGISTRY_REPOSITORY_MISMATCH")
        self.entries = [("understanding", root), ("planning", planning)]
        for service in services:
            if service is None:
                continue
            owner = service.authorization.context_admission
            if owner.repository is not self.repository:
                raise AuthorityError("CONTEXT_ADMISSION_REGISTRY_REPOSITORY_MISMATCH")
            if not any(owner is value for _, value in self.entries):
                self.entries.append(("understanding", owner))
        for index, (phase, owner) in enumerate(self.entries):
            if any(
                other_phase == phase and other.configuration == owner.configuration
                for other_phase, other in self.entries[:index]
            ):
                raise AuthorityError("CONTEXT_ADMISSION_REGISTRY_AMBIGUOUS")

    def owner(self, context, context_id):
        if context.authentication_source != AuthenticationSource.BROWSER_SESSION:
            raise AuthorityError("CONTEXT_ADMISSION_BROWSER_REQUIRED")
        with self.repository.connection_scope() as c:
            row = request_row(c, context_id)
            if not row or (row["tenant_id"], row["security_domain"]) != (
                context.scope.tenant_id,
                context.scope.security_domain,
            ):
                raise AuthorityError("CONTEXT_ADMISSION_NOT_FOUND")
            # Do not expose configuration registration to an unrelated reader.
            if context.principal_id != row["subject_id"]:
                self.entries[0][1].delegation._admin(context, c)
            phase = row["record"].get("phase", "understanding")
            matches = [
                owner
                for registered_phase, owner in self.entries
                if registered_phase == phase
                and owner.configuration == row["record"].get("configuration")
            ]
            if len(matches) != 1:
                raise AuthorityError("CONTEXT_ADMISSION_CONFIGURATION_MISMATCH")
            return matches[0]

    def read(self, context, context_id):
        return self.owner(context, context_id).read(context, context_id)

    def approve(self, context, context_id, spec):
        owner = self.owner(context, context_id)
        plan = self.readmission_plan
        if plan and any(e.context_id == context_id for e in plan.entries):
            return owner.approve(context, context_id, spec, readmission_plan=plan)
        return owner.approve(context, context_id, spec)

    def revoke(self, context, context_id, admission_id):
        return self.owner(context, context_id).revoke(context, context_id, admission_id)
