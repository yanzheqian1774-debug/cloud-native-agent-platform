"""Reuse current exact-grant authority for non-transactional model admission."""

from datetime import UTC, datetime

from .authority_contracts import AuthorityError, ExactGrant


class PlanningCurrentAuthority:
    def __init__(self, context, authorization, clock=lambda: datetime.now(UTC)):
        self.context = context
        self.authorization = authorization
        self.clock = clock

    def require(self, principal, owner, action, resource):
        if (
            principal.principal_id != self.context.principal_id
            or principal.tenant_id != self.context.scope.tenant_id
            or principal.security_domain != self.context.scope.security_domain
        ):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        decision = self.authorization.authorize_current(
            self.context, ExactGrant(owner, action, resource), now=self.clock()
        )
        if decision is None:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        return decision
