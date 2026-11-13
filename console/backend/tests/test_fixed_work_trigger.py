"""One-use adapter gates. No timers, live identities, or model calls."""

from datetime import UTC, datetime, timedelta

import pytest
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    TrustedRequestContext,
)
from agent_console.fixed_work_trigger import TriggerPolicy
from agent_console.workbench_fixed_work_trigger import fixed_work_trigger_operations
from agent_console.workbench_owner_authorization import WorkbenchOwnerError


def policy(subject="human:alice", mode="EXPLICIT_ORIGINAL_SUBJECT"):
    return TriggerPolicy.model_validate(
        dict(
            schemaVersion="fixed-work-one-use-policy.v1",
            policyId="test-only",
            enabled=True,
            expiresAt=datetime.now(UTC) + timedelta(hours=1),
            bindings=[
                dict(
                    tenantId="test",
                    securityDomain="isolated",
                    subjectId=subject,
                    workId="work",
                    revisionId="rev",
                    workDigest="a" * 64,
                    preparationDigest="b" * 64,
                    mode=mode,
                )
            ],
        )
    )


def test_off_and_service_not_falsely_enabled():
    assert fixed_work_trigger_operations(None, None) == ()
    p = policy("service:fixed", "EXPLICIT_SERVICE")
    context = TrustedRequestContext(
        "service:fixed",
        AuthorityScope("test", "isolated"),
        "credential",
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy",
    )
    with pytest.raises(WorkbenchOwnerError, match="SERVICE_ADMISSION_UNAVAILABLE"):
        p.require(
            context,
            dict(work_id="work", revision_id="rev", digest="b" * 64),
            datetime.now(UTC),
        )


@pytest.mark.parametrize(
    "change",
    [dict(enabled=False), dict(expiresAt=datetime.now(UTC) - timedelta(seconds=1))],
)
def test_expired_and_disabled_refuse(change):
    p = policy().model_copy(update=change)
    with pytest.raises(WorkbenchOwnerError, match="UNAVAILABLE"):
        p.require(None, {}, datetime.now(UTC))
