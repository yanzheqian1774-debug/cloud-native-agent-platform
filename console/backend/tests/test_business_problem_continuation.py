from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    ExactGrant,
    TrustedRequestContext,
)
from agent_console.business_problem_continuation import (
    BusinessProblemContinuationValidator,
    BusinessProblemCreateCoordinator,
)
from agent_console.business_problem_domain import (
    BusinessProblemCreatorReceipt,
    BusinessProblemRevision,
    committed_problem_owner_revision,
    problem_creator_mint_key,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.grant_administration_application import RecoveredOwnerContinuation
from agent_console.workbench_owner_authorization import WorkbenchOwnerError

NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)


def receipt(*, started_at: datetime = NOW) -> BusinessProblemCreatorReceipt:
    scope = ScopeIdentity("tenant-a", "quality")
    revision = BusinessProblemRevision(
        scope,
        "problem-1",
        "problem-1:1",
        1,
        None,
        "Supplier quality",
        "Reduce escaped defects",
        "business-owner",
        "human:alice",
        NOW - timedelta(minutes=1),
    )
    return BusinessProblemCreatorReceipt(
        scope=scope,
        creator_principal_id="human:alice",
        originating_command_type="CREATE_BUSINESS_PROBLEM",
        originating_command_idempotency_key="create-1",
        originating_command_payload_digest="a" * 64,
        business_problem_id=revision.business_problem_id,
        revision_id=revision.revision_id,
        revision=1,
        aggregate_version=1,
        revision_digest=revision.digest,
        canonical_resource_reference="business-problem:problem-1",
        committed_owner_revision=committed_problem_owner_revision(revision),
        policy_generation=7,
        recovery_epoch=11,
        receipt_started_at=started_at,
        expires_at=started_at + timedelta(minutes=10),
    )


def context() -> TrustedRequestContext:
    return TrustedRequestContext(
        "human:alice",
        AuthorityScope("tenant-a", "quality"),
        "session-1",
        AuthenticationSource.BROWSER_SESSION,
        "policy-1",
    )


class Grants:
    recovery_epoch = 11

    def __init__(self, recovered=None, *, failure: str | None = None):
        self.recovered = recovered
        self.failure = failure
        self.mints = []

    def recover_owner_continuation(self, trusted, claim, *, originating_command_key):
        assert trusted == context()
        assert originating_command_key == problem_creator_mint_key(receipt())
        return self.recovered

    def mint_owner_continuation(self, trusted, claim, *, originating_command_key):
        if self.failure:
            raise AuthorityError(self.failure)
        self.mints.append((trusted, claim, originating_command_key))
        self.recovered = RecoveredOwnerContinuation(
            "continuation-ref." + "b" * 64,
            claim.expires_at,
            None,
        )
        return "opaque"


def coordinate(grants: Grants, value: BusinessProblemCreatorReceipt, *, now=NOW):
    return BusinessProblemCreateCoordinator(
        grants,  # type: ignore[arg-type]
        clock=lambda: now,
        identity_factory=lambda prefix: f"{prefix}-one",
    )(
        context(),
        {"revision": {"business_problem_id": "problem-1"}, "_creatorReceipt": value},
    )


def test_post_commit_mints_once_and_returns_typed_available_reference() -> None:
    grants = Grants()
    result = coordinate(grants, receipt())
    assert result == {
        "revision": {"business_problem_id": "problem-1"},
        "creatorContinuation": {
            "schemaVersion": "problem-creator-continuation.v1",
            "relation": "PROBLEM_CREATOR",
            "purpose": "CONTINUE_PROBLEM_READ",
            "state": "AVAILABLE",
            "expiresAt": "2026-09-12T12:10:00Z",
            "continuationId": "continuation-ref." + "b" * 64,
        },
    }
    assert len(grants.mints) == 1
    claim = grants.mints[0][1]
    assert claim.members == (
        ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:problem-1"),
    )


def test_replay_recovers_consumed_request_without_minting_again() -> None:
    grants = Grants(
        RecoveredOwnerContinuation(
            "continuation-ref." + "c" * 64,
            NOW + timedelta(minutes=10),
            "grant-request-1",
        )
    )
    result = coordinate(grants, receipt())
    assert result["creatorContinuation"]["state"] == "CONSUMED"
    assert result["creatorContinuation"]["requestId"] == "grant-request-1"
    assert not grants.mints


@pytest.mark.parametrize("persisted", [False, True])
def test_expired_receipt_never_restarts_window(persisted: bool) -> None:
    value = receipt(started_at=NOW - timedelta(minutes=11))
    recovered = (
        RecoveredOwnerContinuation(
            "continuation-ref." + "d" * 64,
            value.expires_at,
            None,
        )
        if persisted
        else None
    )
    grants = Grants(recovered)
    result = coordinate(grants, value)
    assert result["creatorContinuation"]["state"] == "EXPIRED"
    assert ("continuationId" in result["creatorContinuation"]) is persisted
    assert not grants.mints


def test_mint_failure_preserves_owner_result_and_returns_typed_unavailable() -> None:
    grants = Grants(failure="AUTHORITY_STORAGE_UNAVAILABLE")
    with pytest.raises(WorkbenchOwnerError) as raised:
        coordinate(grants, receipt())
    assert raised.value.reason_code == "CONTINUATION_MINT_UNAVAILABLE"
    assert raised.value.status_code == 503


def test_recovery_epoch_change_invalidates_receipt() -> None:
    grants = Grants()
    grants.recovery_epoch = 12
    with pytest.raises(WorkbenchOwnerError) as raised:
        coordinate(grants, receipt())
    assert raised.value.reason_code == "CREATOR_CONTINUATION_INVALIDATED"


def test_validator_accepts_only_the_exact_creator_receipt_claim() -> None:
    value = receipt()
    repository = SimpleNamespace(
        get_creator_receipt_for_problem=lambda *args, **kwargs: value
    )
    validator = BusinessProblemContinuationValidator(repository)
    claim = BusinessProblemCreateCoordinator._claim(value, "offer-one")
    assert validator.validate_continuation(claim)
    assert not validator.validate_continuation(
        replace(claim, subject_principal_id="human:other")
    )
    assert not validator.is_known_exact_target(context(), claim.members[0])
    assert not validator.validate_offer(
        claim.scope,
        claim.members,
        claim.canonical_resource_reference,
        claim.owner_revision,
    )
