import hashlib

import pytest
from agent_console.governed_execution_authorization import (
    GovernedAuthorizationError,
    GovernedExecutionAuthority,
)


def configuration(*, expires_at="2100-01-01T00:00:00Z", credentials=None):
    credential = {
        "credentialId": "credential:operator",
        "principalId": "operator",
        "tenantId": "tenant-a",
        "securityDomain": "restricted",
        "credentialSha256": hashlib.sha256(b"secret-from-environment").hexdigest(),
        "expiresAt": expires_at,
        "grants": [
            {
                "owner": "EXECUTION",
                "action": "START",
                "resource": "execution:exact",
            }
        ],
    }
    return {
        "schemaVersion": "governed-execution-auth.v1",
        "policyVersion": "policy.v1",
        "auditSource": "unit-test",
        "credentials": credentials or [credential],
    }


def test_authentication_and_authorization_are_exact_and_owner_scoped():
    authority = GovernedExecutionAuthority(configuration())
    principal = authority.authenticate("Bearer secret-from-environment")
    decision = authority.require(principal, "EXECUTION", "START", "execution:exact")
    assert decision.owner == "EXECUTION"
    assert decision.action == "START"
    assert decision.resource == "execution:exact"
    assert not authority.allows(principal, "SKILL", "START", "execution:exact")
    assert not authority.allows(principal, "EXECUTION", "READ", "execution:exact")
    assert not authority.allows(principal, "EXECUTION", "START", "execution:other")


@pytest.mark.parametrize(
    "authorization",
    (None, "", "Basic secret-from-environment", "Bearer wrong"),
)
def test_missing_or_unmatched_credentials_fail_closed(authorization):
    authority = GovernedExecutionAuthority(configuration())
    with pytest.raises(GovernedAuthorizationError, match="AUTHENTICATION_REQUIRED"):
        authority.authenticate(authorization)


def test_expired_and_ambiguous_credentials_fail_closed():
    expired = GovernedExecutionAuthority(
        configuration(expires_at="2000-01-01T00:00:00Z")
    )
    with pytest.raises(GovernedAuthorizationError, match="AUTHENTICATION_REQUIRED"):
        expired.authenticate("Bearer secret-from-environment")

    duplicate = configuration()["credentials"][0]
    with pytest.raises(
        GovernedAuthorizationError, match="GOVERNED_AUTHORITY_UNAVAILABLE"
    ):
        GovernedExecutionAuthority(configuration(credentials=[duplicate, duplicate]))
