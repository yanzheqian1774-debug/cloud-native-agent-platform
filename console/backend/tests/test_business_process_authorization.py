"""Scope grants cannot replace explicit denial or an unavailable authority."""

from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import (
    AuthorityError,
    DynamicAuthorizationState,
    ExactGrant,
)
from agent_console.business_process_authorization import require_process_grant


def make_call(
    grant,
    *,
    state=DynamicAuthorizationState.NONE,
    tombstone=None,
    credential_id="account:one",
    exact_error="AUTHORIZATION_NOT_FOUND",
):
    checks = []
    context = SimpleNamespace(
        principal_id="human:one",
        scope=SimpleNamespace(tenant_id="tenant:one", security_domain="domain:one"),
    )
    credential = SimpleNamespace(grant_source_id="source:one")
    generation = SimpleNamespace(
        credential_by_id=lambda key: None,
        account_by_id=lambda key: credential if key == "account:one" else None,
        static_grant_revocation_tombstones=frozenset(
            {(tombstone, grant)} if tombstone else ()
        ),
    )
    connection = object()

    def read(ctx, grants, **kwargs):
        assert ctx is context and grants == (grant,)
        assert kwargs["connection"] is connection
        assert kwargs["configure_transaction"] is False
        assert kwargs["generation"] == 7 and kwargs["recovery_epoch"] == 3
        return credential_id, (state,)

    def require(principal, owner, action, resource):
        assert principal.tenant_id == "tenant:one"
        assert principal.security_domain == "domain:one"
        checks.append((owner, action, resource))
        if len(checks) == 1 and exact_error:
            raise AuthorityError(exact_error)
        return "decision:current"

    adapter = SimpleNamespace(
        authorization=SimpleNamespace(
            generation=generation, read_linearized_authorization_states=read
        ),
        clock=lambda: 123,
        controller=SimpleNamespace(readiness=SimpleNamespace(recovery_epoch=3)),
    )
    return SimpleNamespace(
        context=context,
        connection=connection,
        policy_generation=7,
        authority=SimpleNamespace(require=require, adapter=adapter),
    ), checks


@pytest.mark.parametrize(
    "action,scope_action", [("READ", "READ_SCOPE"), ("REVISE", "MAINTAIN_SCOPE")]
)
def test_scope_decision_preserves_trusted_scope_and_transaction(action, scope_action):
    grant = ExactGrant(
        "BUSINESS_PROCESS", action, "business-process:PROCESS:one:revision"
    )
    call, checks = make_call(grant)
    assert require_process_grant(call, grant) == "decision:current"
    assert checks[-1] == (
        "BUSINESS_PROCESS",
        scope_action,
        "business-process:collection",
    )


@pytest.mark.parametrize(
    "options",
    [
        {"state": DynamicAuthorizationState.REVOKED},
        {"state": DynamicAuthorizationState.UNAVAILABLE},
        {"credential_id": None},
        {"credential_id": "unknown"},
        {"tombstone": "account:one"},
        {"tombstone": "source:one"},
        {"exact_error": "AUTHORIZATION_STATE_UNAVAILABLE"},
    ],
)
def test_denial_or_unknown_state_never_falls_through_to_scope(options):
    grant = ExactGrant(
        "BUSINESS_PROCESS", "READ", "business-process:PROCESS:one:revision"
    )
    call, checks = make_call(grant, **options)
    with pytest.raises(AuthorityError):
        require_process_grant(call, grant)
    assert len(checks) == 1


@pytest.mark.parametrize(
    "grant",
    [
        ExactGrant("BUSINESS_PROCESS", "REVISE", "business-process:architecture"),
        ExactGrant("BUSINESS_PROCESS", "CREATE", "business-process:collection"),
        ExactGrant("BUSINESS_PROCESS", "PUBLISH", "business-process:one"),
        ExactGrant("WORKFLOW", "READ", "workflow:one"),
    ],
)
def test_scope_does_not_expand_to_unrelated_powers(grant):
    call, checks = make_call(grant)
    with pytest.raises(AuthorityError):
        require_process_grant(call, grant)
    assert len(checks) == 1


def test_existing_exact_decision_needs_no_scope_grant():
    grant = ExactGrant(
        "BUSINESS_PROCESS", "READ", "business-process:PROCESS:one:revision"
    )
    call, checks = make_call(grant, exact_error=None)
    del call.authority.adapter
    assert require_process_grant(call, grant) == "decision:current"
    assert len(checks) == 1
