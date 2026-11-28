"""Explicit scope grants for tool drafts, preserving exact revocations."""

from .authority_contracts import AuthorityError, DynamicAuthorizationState
from .workbench_business_problem import OwnerPrincipal

OWNER = "TOOL"
COLLECTION = "tool:collection"


def require_tool_grant(call, grant):
    principal = OwnerPrincipal(
        call.context.principal_id,
        call.context.scope.tenant_id,
        call.context.scope.security_domain,
    )
    try:
        return call.authority.require(
            principal, grant.owner, grant.action, grant.exact_resource
        )
    except AuthorityError as error:
        if str(error) != "AUTHORIZATION_NOT_FOUND":
            raise
        if grant.owner != OWNER or grant.action not in {"READ", "REVISE", "VALIDATE"}:
            raise

    # Scope grants must never mask a revocation of the requested exact target.
    adapter = getattr(call.authority, "adapter", None)
    if adapter is None:
        raise AuthorityError("AUTHORIZATION_NOT_FOUND")
    reader = adapter.authorization
    credential_id, states = reader.read_linearized_authorization_states(
        call.context,
        (grant,),
        now=adapter.clock(),
        generation=call.policy_generation,
        recovery_epoch=adapter.controller.readiness.recovery_epoch,
        connection=call.connection,
        configure_transaction=False,
    )
    if credential_id is None or states != (DynamicAuthorizationState.NONE,):
        raise AuthorityError("AUTHORIZATION_NOT_FOUND")
    generation = reader.generation
    credential = generation.credential_by_id(credential_id) or generation.account_by_id(
        credential_id
    )
    if credential is None:
        raise AuthorityError("AUTHORIZATION_NOT_FOUND")
    sources = {credential_id, getattr(credential, "grant_source_id", credential_id)}
    if any(
        (source, grant) in generation.static_grant_revocation_tombstones
        for source in sources
    ):
        raise AuthorityError("AUTHORIZATION_NOT_FOUND")
    action = "READ_SCOPE" if grant.action == "READ" else "MAINTAIN_SCOPE"
    return call.authority.require(principal, OWNER, action, COLLECTION)
