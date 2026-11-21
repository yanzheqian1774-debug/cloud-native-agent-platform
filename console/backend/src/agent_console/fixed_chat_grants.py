"""Bind existing grant authority reads/writes to this owner's transaction."""

from .authority_contracts import AuthorityError
from .resource_automation import bound_grants


class SameConnectionAuthorization:
    def __init__(self, original, repository, connection):
        self.original, self.repository, self.connection = (
            original,
            repository,
            connection,
        )

    def __getattr__(self, name):
        return getattr(self.original, name)

    def has_current_grants(self, context, members, **kwargs):
        return self.original.has_current_grants(
            context,
            members,
            **{
                **kwargs,
                "connection": self.connection,
                "configure_transaction": False,
            },
        )

    def has_current_grant(self, context, member, **kwargs):
        return self.has_current_grants(context, (member,), **kwargs)[0]

    def has_dynamic_revocation(self, context, member, **kwargs):
        return self.repository.has_dynamic_revocation(context, member, **kwargs)


def grants_on_connection(service, connection):
    bound = bound_grants(service, connection)
    bound.authorization = SameConnectionAuthorization(
        service.authorization, bound.repository, connection
    )
    return bound


def static_read_revoked(generation, context, members):
    known, own = set(), set()
    for identity in (*generation.credentials, *generation.local_accounts):
        ids = {
            identity.credential_id,
            getattr(identity, "grant_source_id", identity.credential_id),
        }
        known.update(ids)
        if (
            identity.principal_id == context.principal_id
            and identity.scope == context.scope
        ):
            own.update(ids)
    relevant = {
        identity
        for identity, grant in generation.static_grant_revocation_tombstones
        if grant in members
    }
    if relevant - known:
        raise AuthorityError("FIXED_CHAT_READ_IDENTITY_UNVERIFIED")
    return bool(relevant & own)
