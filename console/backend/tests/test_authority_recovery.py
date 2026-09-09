from __future__ import annotations

import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agent_console.authority_configuration import StaticAuthorityGeneration
from agent_console.authority_contracts import (
    AuthorityError,
    AuthorityScope,
    ContinuationClaim,
    ControlState,
    ExactGrant,
)
from agent_console.authority_foundation import (
    ActivationBarrier,
    AuthorityGenerationController,
    AuthorityReadiness,
    SignedContinuationOwner,
)
from agent_console.authority_recovery import (
    HostControlRecord,
    HostRecoveryControl,
    RecoveryCoordinator,
)


def record(epoch: int, state: ControlState = ControlState.ACTIVE) -> HostControlRecord:
    return HostControlRecord(
        control_epoch=epoch,
        recovery_epoch=2,
        state=state,
        database_fingerprint="database-a",
        generation=4,
        generation_digest="d" * 64,
        operator_id="operator:test",
    )


def test_control_record_is_owner_only_atomic_and_monotonic(tmp_path: Path) -> None:
    path = tmp_path / "authority-control.json"
    control = HostRecoveryControl(path)
    control.replace(record(1))

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert control.read() == record(1)
    control.require_ready(
        database_fingerprint="database-a",
        generation=4,
        generation_digest="d" * 64,
        recovery_epoch=2,
    )
    with pytest.raises(AuthorityError, match="AUTHORITY_CONTROL_EPOCH_STALE"):
        control.replace(record(1))
    with pytest.raises(AuthorityError, match="AUTHORITY_RECOVERY_REQUIRED"):
        control.require_ready(
            database_fingerprint="database-b",
            generation=4,
            generation_digest="d" * 64,
            recovery_epoch=2,
        )


class FailingRecoveryRepository:
    def reconcile_recovery(self, **_: object) -> None:
        raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE")

    def complete_recovery(self, **_: object) -> None:
        raise AssertionError("must not complete")


def test_recovery_failure_leaves_serving_closed(tmp_path: Path) -> None:
    control = HostRecoveryControl(tmp_path / "authority-control.json")
    control.replace(record(1))
    coordinator = RecoveryCoordinator(control, FailingRecoveryRepository())

    with pytest.raises(AuthorityError, match="AUTHORITY_STORAGE_UNAVAILABLE"):
        coordinator.reconcile(
            control_epoch=2,
            recovery_epoch=3,
            database_fingerprint="database-a",
            generation=4,
            generation_digest="d" * 64,
            migration_version=18,
            operator_id="operator:test",
            audit_continuity_digest="e" * 64,
            now=datetime(2029, 1, 1, tzinfo=UTC),
        )
    assert control.read().state is ControlState.RECOVERY_CLOSED


def test_continuation_is_signed_bounded_and_expires() -> None:
    now = datetime(2029, 1, 1, tzinfo=UTC)
    owner = SignedContinuationOwner(b"k" * 32)
    claim = ContinuationClaim(
        nonce="offer-1",
        subject_principal_id="human:alice",
        scope=AuthorityScope("tenant-a", "quality"),
        purpose="CONTINUE_PROBLEM_PLAN",
        members=(ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:problem-1"),),
        canonical_resource_reference="problem-1:revision-1",
        owner_revision="revision-1",
        policy_generation=4,
        issued_at=now,
        expires_at=now.replace(minute=10),
    )
    opaque = owner.mint(claim)
    assert owner.resolve_continuation(opaque, now=now) == claim
    with pytest.raises(AuthorityError, match="CONTINUATION_INVALID"):
        owner.resolve_continuation(f"{opaque}x", now=now)
    with pytest.raises(AuthorityError, match="CONTINUATION_INVALID"):
        owner.resolve_continuation(opaque, now=claim.expires_at)


class MemoryGenerationRepository:
    def __init__(self, active: tuple[int, str, int]) -> None:
        self.active = active

    def active_generation(self) -> tuple[int, str, int]:
        return self.active

    def activate_generation(
        self, generation: int, digest: str, recovery_epoch: int, **_: object
    ) -> None:
        self.active = generation, digest, recovery_epoch


def test_generation_activation_uses_pending_gate_and_rejects_decrease(
    tmp_path: Path,
) -> None:
    first = StaticAuthorityGeneration(
        1, "a" * 64, "policy-1", "test", (), (), frozenset()
    )
    second = StaticAuthorityGeneration(
        2, "b" * 64, "policy-2", "test", (), (), frozenset()
    )
    control = HostRecoveryControl(tmp_path / "authority-control.json")
    control.replace(
        HostControlRecord(
            1,
            1,
            ControlState.ACTIVE,
            "database-a",
            1,
            "a" * 64,
            "operator:test",
        )
    )
    repository = MemoryGenerationRepository((1, "a" * 64, 1))
    barrier = ActivationBarrier(first)
    controller = AuthorityGenerationController(
        barrier,
        repository,
        control,
        AuthorityReadiness(1, "a" * 64, 1, "database-a"),
    )
    readiness = controller.activate(
        second,
        control_epoch=2,
        operator_id="operator:test",
        now=datetime(2029, 1, 1, tzinfo=UTC),
    )
    assert readiness.generation == 2
    assert control.read().state is ControlState.ACTIVE
    with controller.protected_request() as pinned:
        assert pinned is second
    with pytest.raises(AuthorityError, match="AUTHORITY_GENERATION_STALE"):
        controller.activate(
            first,
            control_epoch=4,
            operator_id="operator:test",
            now=datetime(2029, 1, 1, tzinfo=UTC),
        )
